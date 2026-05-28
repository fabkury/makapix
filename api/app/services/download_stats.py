"""Vault access log → ``download_stats_daily`` rollup service.

Streams the Caddy JSON access log for the current environment's vault
subdomain, counts per-artwork downloads (split by bot vs human via
:mod:`app.utils.bot_detection`), and UPSERTs into ``download_stats_daily``.

Invoked daily by :func:`app.tasks.rollup_download_stats`. Idempotent — the
UPSERT overwrites the previous row's counts, so re-running for the same
date converges to the freshly-parsed total.
"""

from __future__ import annotations

import gzip
import io
import json
import logging
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .. import models
from ..db import SessionLocal
from ..utils.bot_detection import is_bot

logger = logging.getLogger(__name__)

# Vault artwork URI shape: /<h1>/<h2>/<h3>/<uuid>(<_upscaled>)?.<ext>
# Avatars (/avatar/...) and blog images (/blog_image/...) are intentionally
# not matched here — this rollup is artwork-only.
_ARTWORK_URI_RE = re.compile(
    r"^/([0-9a-f]{2})/([0-9a-f]{2})/([0-9a-f]{2})"
    r"/([0-9a-f-]{36})(?:_upscaled)?\.(?:png|gif|webp|bmp)$",
    re.IGNORECASE,
)

# Map ENVIRONMENT -> the vault access log this rollup should consume.
# The worker container in each environment talks only to its own DB; reading
# the wrong env's log would write stats for posts that don't exist locally.
_LOG_BY_ENV = {
    "production": "vault-access.log",
    "development": "vault-dev-access.log",
}

_LOG_DIR = Path("/var/log/caddy")


def _select_log_files() -> list[Path]:
    """Return the live log file plus any rotated peers from the last 48 h.

    Caddy's lumberjack rotation produces ``vault-access-YYYY-MM-DD...log.gz``
    siblings. We need to read both the live file and any rotated files that
    might still contain entries for `target_date` (the rotation can happen
    mid-day, splitting a day's events across multiple files).
    """
    env = os.environ.get("ENVIRONMENT", "development").lower()
    base = _LOG_BY_ENV.get(env, _LOG_BY_ENV["development"])
    if not _LOG_DIR.exists():
        logger.warning("Log directory %s does not exist; nothing to do", _LOG_DIR)
        return []

    cutoff = datetime.now(timezone.utc).timestamp() - 48 * 3600
    files: list[Path] = []
    # The live file is always called `<base>`. Caddy's rotated files have a
    # name like `<basename>-YYYY-MM-DDTHHMMSS.NNN.log` and `.log.gz`.
    base_stem = base.removesuffix(".log")
    for p in _LOG_DIR.iterdir():
        if not p.is_file():
            continue
        name = p.name
        if name == base or name.startswith(base_stem + "-"):
            try:
                if p.stat().st_mtime >= cutoff:
                    files.append(p)
            except OSError:
                continue
    files.sort()
    return files


def _open_log(path: Path) -> io.TextIOBase:
    """Open a log file transparently, including gzip-compressed rotations."""
    if path.suffix == ".gz":
        return gzip.open(path, mode="rt", encoding="utf-8", errors="replace")
    return open(path, mode="rt", encoding="utf-8", errors="replace")


def _iter_artwork_hits(
    files: Iterable[Path], target_date: date
) -> Iterable[tuple[UUID, bool]]:
    """Yield ``(storage_key, is_bot_flag)`` for each artwork download in target_date."""
    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc).timestamp()
    day_end = day_start + 86400.0

    for path in files:
        try:
            fh = _open_log(path)
        except OSError as e:
            logger.warning("Could not open %s: %s", path, e)
            continue
        with fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue

                # Caddy-level filtering: only count successful GETs.
                ts = entry.get("ts")
                if not isinstance(ts, (int, float)):
                    continue
                if ts < day_start or ts >= day_end:
                    continue
                if entry.get("status") != 200:
                    continue
                request = entry.get("request") or {}
                if request.get("method", "GET") != "GET":
                    continue

                uri = request.get("uri") or ""
                m = _ARTWORK_URI_RE.match(uri)
                if not m:
                    continue
                try:
                    storage_key = UUID(m.group(4))
                except ValueError:
                    continue

                # Caddy nests headers under request.headers, values are arrays.
                ua_list = (request.get("headers") or {}).get("User-Agent") or []
                ua = ua_list[0] if ua_list else None
                yield storage_key, is_bot(ua)


def rollup_download_stats(target_date: date) -> dict[str, object]:
    """Aggregate one calendar day's artwork downloads from the vault log.

    Returns a small telemetry dict suitable for Celery task logs.
    """
    files = _select_log_files()
    logger.info(
        "rollup_download_stats(date=%s): scanning %d log file(s)",
        target_date, len(files),
    )

    # Aggregate in memory: {storage_key: [human_count, bot_count]}
    counts: dict[UUID, list[int]] = defaultdict(lambda: [0, 0])
    for storage_key, bot in _iter_artwork_hits(files, target_date):
        counts[storage_key][1 if bot else 0] += 1

    if not counts:
        return {
            "date": target_date.isoformat(),
            "artworks_seen": 0,
            "downloads_human": 0,
            "downloads_bot": 0,
            "orphan_downloads": 0,
        }

    db = SessionLocal()
    try:
        # Resolve storage_key -> post_id in a single round-trip.
        storage_keys = list(counts.keys())
        rows = db.execute(
            select(models.Post.id, models.Post.storage_key).where(
                models.Post.storage_key.in_(storage_keys)
            )
        ).all()
        key_to_id: dict[UUID, int] = {sk: pid for pid, sk in rows}

        upsert_payload = []
        orphan_h = 0
        orphan_b = 0
        for sk, (h, b) in counts.items():
            post_id = key_to_id.get(sk)
            if post_id is None:
                orphan_h += h
                orphan_b += b
                continue
            upsert_payload.append(
                {
                    "post_id": post_id,
                    "date": target_date,
                    "downloads_human": h,
                    "downloads_bot": b,
                }
            )

        if upsert_payload:
            stmt = pg_insert(models.DownloadStatsDaily).values(upsert_payload)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_download_stats_daily_post_date",
                set_={
                    "downloads_human": stmt.excluded.downloads_human,
                    "downloads_bot": stmt.excluded.downloads_bot,
                },
            )
            db.execute(stmt)
            db.commit()

        total_h = sum(h for h, _ in counts.values())
        total_b = sum(b for _, b in counts.values())
        logger.info(
            "rollup_download_stats(%s): wrote %d artwork rows; "
            "human=%d bot=%d orphans=%d/%d",
            target_date, len(upsert_payload), total_h, total_b, orphan_h, orphan_b,
        )
        return {
            "date": target_date.isoformat(),
            "artworks_seen": len(upsert_payload),
            "downloads_human": total_h,
            "downloads_bot": total_b,
            "orphan_downloads": orphan_h + orphan_b,
        }
    finally:
        db.close()

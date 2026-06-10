"""Vault access log → download statistics rollup service.

One nightly pass (invoked by :func:`app.tasks.rollup_download_stats`)
produces two outputs:

1. ``download_stats_daily`` — the pre-existing per-artwork download counts.
   Semantics unchanged for historical comparability: GET + status 200 only,
   artwork class only, vault-subdomain log only.

2. ``vault_sharding_stats_daily`` — instrumentation for the vault resharding
   migration (docs/vault-resharding/). Downloads split by sharding level
   (2 = new, 3 = legacy) and asset class (artwork/avatar/blog_image), with
   deliberately wider semantics: GET/HEAD with status 200/206/304 all count
   (a 304 revalidation is a live reference to the URL), and 404s are counted
   separately as ``misses``. Reads BOTH log feeds:

   - the vault-subdomain log (``vault-access.log`` / ``vault-dev-access.log``)
   - the shared default log (``access.log``), which captures main-domain
     ``/api/vault/...`` requests served by FastAPI StaticFiles — these never
     appear in the vault-subdomain log, and the legacy URL form demonstrably
     exists in stored data. Entries are filtered by ``request.host`` so each
     environment only counts its own traffic.

   Aggregate rows (post_id NULL) are upserted for every (class, level)
   combination INCLUDING all-zero days — a missing day means "rollup did not
   run", never "quiet day". The retirement streak logic depends on that
   distinction.

Both UPSERTs are idempotent — re-running for the same date converges to the
freshly-parsed totals.
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
from typing import Iterable, NamedTuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .. import models
from ..db import SessionLocal
from ..utils.bot_detection import is_bot

logger = logging.getLogger(__name__)

# Vault asset URI shape, both sharding depths and all asset classes:
#   /<s1>/<s2>/<uuid>(<_upscaled>)?.<ext>                  (v2, artwork)
#   /<s1>/<s2>/<s3>/<uuid>(<_upscaled>)?.<ext>             (v1, artwork)
#   /avatar/<...>/<uuid>.<ext>, /blog_image/<...>/<uuid>.<ext>
# plus an optional /api/vault prefix for main-domain requests served by
# FastAPI StaticFiles. Query strings must be stripped before matching.
_VAULT_URI_RE = re.compile(
    r"^/(?:api/vault/)?"
    r"(?:(?P<cls>avatar|blog_image)/)?"
    r"(?P<s1>[0-9a-f]{2})/(?P<s2>[0-9a-f]{2})(?:/(?P<s3>[0-9a-f]{2}))?"
    r"/(?P<uuid>[0-9a-f-]{36})(?P<upscaled>_upscaled)?\.(?P<ext>png|gif|webp|bmp|jpg)$",
    re.IGNORECASE,
)

ASSET_CLASSES = ("artwork", "avatar", "blog_image")
SHARD_LEVELS = (2, 3)

# Statuses that count as a download under the resharding instrumentation's
# semantics: 200 full body, 206 partial, 304 revalidation (still a live
# reference to the URL — see docs/vault-resharding/DECISIONS.md D8).
_DOWNLOAD_STATUSES = {200, 206, 304}
_MISS_STATUS = 404

# Map ENVIRONMENT -> the vault-subdomain access log for this environment.
# The worker container in each environment talks only to its own DB; reading
# the wrong env's log would write stats for posts that don't exist locally.
_LOG_BY_ENV = {
    "production": "vault-access.log",
    "development": "vault-dev-access.log",
}

# Map ENVIRONMENT -> main-domain host whose /api/vault/... requests belong to
# this environment. These land in the shared default log (access.log).
_MAIN_HOST_BY_ENV = {
    "production": "makapix.club",
    "development": "development.makapix.club",
}

_MAIN_LOG_BASE = "access.log"

_LOG_DIR = Path("/var/log/caddy")


def _environment() -> str:
    return os.environ.get("ENVIRONMENT", "development").lower()


class VaultHit(NamedTuple):
    asset_class: str  # artwork | avatar | blog_image
    shard_level: int  # 2 | 3
    storage_key: UUID
    status: int
    method: str
    bot: bool


def _select_log_files(base: str, target_date: date) -> list[Path]:
    """Return log files that may contain entries for ``target_date``.

    The live file is always called ``<base>``. Caddy's lumberjack rotation
    produces siblings named ``<stem>-YYYY-MM-DDTHH-MM-SS.mmm.log[.gz]``; the
    timestamp is the rotation moment, and a rotated file only contains
    entries from BEFORE it. So a rotated file is relevant iff its rotation
    timestamp falls on or after the start of the target day (with 12 h of
    slack because the stamp's timezone is not guaranteed). Files with
    unparseable names fall back to an mtime check.
    """
    day_start = datetime.combine(
        target_date, datetime.min.time(), tzinfo=timezone.utc
    ).timestamp()
    cutoff = day_start - 12 * 3600

    if not _LOG_DIR.exists():
        logger.warning("Log directory %s does not exist; nothing to do", _LOG_DIR)
        return []

    base_stem = base.removesuffix(".log")
    files: list[Path] = []
    for p in _LOG_DIR.iterdir():
        if not p.is_file():
            continue
        name = p.name
        if name == base:
            files.append(p)
            continue
        if not name.startswith(base_stem + "-"):
            continue
        # "<stem>-2026-06-10T01-23-45.123.log[.gz]" -> "2026-06-10T01-23-45"
        stamp = name[len(base_stem) + 1 :].split(".")[0]
        rotated_at: datetime | None = None
        try:
            rotated_at = datetime.strptime(stamp, "%Y-%m-%dT%H-%M-%S").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            pass
        try:
            if rotated_at is not None:
                if rotated_at.timestamp() >= cutoff:
                    files.append(p)
            elif p.stat().st_mtime >= cutoff:
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


def _iter_vault_hits(
    files: Iterable[Path],
    target_date: date,
    *,
    hosts: set[str] | None = None,
    require_api_prefix: bool = False,
) -> Iterable[VaultHit]:
    """Yield a :class:`VaultHit` for each vault asset request in target_date.

    Args:
        hosts: if given, only count entries whose request.host (port
            stripped) is in this set — used for the shared default log,
            which mixes every site that lacks its own log file.
        require_api_prefix: only count URIs starting with /api/vault/ —
            on the main domain a bare /<aa>/<bb>/... path is not vault
            traffic.
    """
    day_start = datetime.combine(
        target_date, datetime.min.time(), tzinfo=timezone.utc
    ).timestamp()
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

                # Caddy names access loggers per configured output:
                # plain "http.log.access" in the shared default log, but
                # "http.log.access.log0"/".log1"/... for sites with their
                # own log directive (the vault subdomains). Prefix-match.
                if not str(entry.get("logger") or "").startswith(
                    "http.log.access"
                ):
                    continue
                ts = entry.get("ts")
                if not isinstance(ts, (int, float)):
                    continue
                if ts < day_start or ts >= day_end:
                    continue

                request = entry.get("request") or {}
                method = request.get("method", "GET")
                if method not in ("GET", "HEAD"):
                    continue

                if hosts is not None:
                    host = (request.get("host") or "").split(":")[0].lower()
                    if host not in hosts:
                        continue

                uri = (request.get("uri") or "").split("?", 1)[0]
                if require_api_prefix and not uri.startswith("/api/vault/"):
                    continue
                m = _VAULT_URI_RE.match(uri)
                if not m:
                    continue

                status = entry.get("status")
                if status not in _DOWNLOAD_STATUSES and status != _MISS_STATUS:
                    continue

                try:
                    storage_key = UUID(m.group("uuid"))
                except ValueError:
                    continue

                # Caddy nests headers under request.headers, values are arrays.
                ua_list = (request.get("headers") or {}).get("User-Agent") or []
                ua = ua_list[0] if ua_list else None

                yield VaultHit(
                    asset_class=m.group("cls") or "artwork",
                    shard_level=3 if m.group("s3") else 2,
                    storage_key=storage_key,
                    status=status,
                    method=method,
                    bot=is_bot(ua),
                )


def compute_legacy_streak(db: Session, as_of: date) -> int:
    """Consecutive liveness-valid days ending at ``as_of`` with zero non-bot
    legacy (level-3) downloads.

    A day counts toward the streak only if it is *liveness-valid*:
    aggregate rows exist for it (the rollup ran) AND level-2 traffic was
    nonzero (an all-quiet day means the pipeline is broken, not that the
    internet went silent). Any non-bot level-3 download, data gap, or dead
    day breaks the streak. See docs/vault-resharding/PLAN.md §8.
    """
    stats = models.VaultShardingStatsDaily
    rows = db.execute(
        select(
            stats.date,
            stats.shard_level,
            func.sum(stats.downloads_human),
            func.sum(stats.downloads_bot),
        )
        .where(stats.post_id.is_(None))
        .group_by(stats.date, stats.shard_level)
    ).all()

    by_day: dict[date, dict[int, tuple[int, int]]] = defaultdict(dict)
    for day, level, human, bot in rows:
        by_day[day][level] = (int(human or 0), int(bot or 0))

    streak = 0
    day = as_of
    while True:
        levels = by_day.get(day)
        if not levels or 2 not in levels or 3 not in levels:
            break  # data gap: rollup didn't run for this day
        l2_human, l2_bot = levels[2]
        l3_human, _l3_bot = levels[3]
        if (l2_human + l2_bot) <= 0:
            break  # liveness failure: no level-2 traffic at all
        if l3_human > 0:
            break  # non-bot legacy downloads occurred
        streak += 1
        day = day - timedelta(days=1)
    return streak


def rollup_download_stats(target_date: date) -> dict[str, object]:
    """Aggregate one calendar day's vault traffic from the access logs.

    Returns a small telemetry dict suitable for Celery task logs.
    """
    env = _environment()
    vault_base = _LOG_BY_ENV.get(env, _LOG_BY_ENV["development"])
    main_host = _MAIN_HOST_BY_ENV.get(env, _MAIN_HOST_BY_ENV["development"])

    vault_files = _select_log_files(vault_base, target_date)
    main_files = _select_log_files(_MAIN_LOG_BASE, target_date)
    logger.info(
        "rollup_download_stats(date=%s): scanning %d vault + %d main log file(s)",
        target_date,
        len(vault_files),
        len(main_files),
    )

    # --- Pass 1: vault-subdomain feed -------------------------------------
    # legacy_counts keeps the pre-existing download_stats_daily semantics:
    # artwork only, GET + 200 only. sharded_* uses the wider D8 semantics.
    legacy_counts: dict[UUID, list[int]] = defaultdict(lambda: [0, 0])
    # (asset_class, shard_level) -> [human, bot, misses]
    sharded_agg: dict[tuple[str, int], list[int]] = {
        (cls, lvl): [0, 0, 0] for cls in ASSET_CLASSES for lvl in SHARD_LEVELS
    }
    # storage_key -> [human, bot] for level-3 artwork downloads (stragglers)
    straggler_counts: dict[UUID, list[int]] = defaultdict(lambda: [0, 0])

    def _tally(hit: VaultHit) -> None:
        bucket = sharded_agg[(hit.asset_class, hit.shard_level)]
        if hit.status == _MISS_STATUS:
            bucket[2] += 1
            return
        bucket[1 if hit.bot else 0] += 1
        if hit.asset_class == "artwork" and hit.shard_level == 3:
            straggler_counts[hit.storage_key][1 if hit.bot else 0] += 1

    for hit in _iter_vault_hits(vault_files, target_date):
        _tally(hit)
        if hit.asset_class == "artwork" and hit.method == "GET" and hit.status == 200:
            legacy_counts[hit.storage_key][1 if hit.bot else 0] += 1

    # --- Pass 2: main-domain /api/vault feed (sharding stats only) --------
    for hit in _iter_vault_hits(
        main_files, target_date, hosts={main_host}, require_api_prefix=True
    ):
        _tally(hit)

    db = SessionLocal()
    try:
        # Resolve storage_key -> post_id in a single round-trip.
        all_keys = set(legacy_counts) | set(straggler_counts)
        key_to_id: dict[UUID, int] = {}
        if all_keys:
            rows = db.execute(
                select(models.Post.id, models.Post.storage_key).where(
                    models.Post.storage_key.in_(list(all_keys))
                )
            ).all()
            key_to_id = {sk: pid for pid, sk in rows}

        # --- download_stats_daily (unchanged semantics) --------------------
        legacy_payload = []
        orphan_h = 0
        orphan_b = 0
        for sk, (h, b) in legacy_counts.items():
            post_id = key_to_id.get(sk)
            if post_id is None:
                orphan_h += h
                orphan_b += b
                continue
            legacy_payload.append(
                {
                    "post_id": post_id,
                    "date": target_date,
                    "downloads_human": h,
                    "downloads_bot": b,
                }
            )
        if legacy_payload:
            stmt = pg_insert(models.DownloadStatsDaily).values(legacy_payload)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_download_stats_daily_post_date",
                set_={
                    "downloads_human": stmt.excluded.downloads_human,
                    "downloads_bot": stmt.excluded.downloads_bot,
                },
            )
            db.execute(stmt)

        # --- vault_sharding_stats_daily: aggregate rows ---------------------
        # Always written, including all-zero days (data-gap detection).
        agg_payload = [
            {
                "date": target_date,
                "asset_class": cls,
                "shard_level": lvl,
                "post_id": None,
                "downloads_human": counts[0],
                "downloads_bot": counts[1],
                "misses": counts[2],
            }
            for (cls, lvl), counts in sharded_agg.items()
        ]
        # --- vault_sharding_stats_daily: per-post straggler rows ------------
        straggler_orphans = 0
        for sk, (h, b) in straggler_counts.items():
            post_id = key_to_id.get(sk)
            if post_id is None:
                straggler_orphans += h + b
                continue
            agg_payload.append(
                {
                    "date": target_date,
                    "asset_class": "artwork",
                    "shard_level": 3,
                    "post_id": post_id,
                    "downloads_human": h,
                    "downloads_bot": b,
                    "misses": 0,
                }
            )

        stmt = pg_insert(models.VaultShardingStatsDaily).values(agg_payload)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_vault_sharding_stats_daily",
            set_={
                "downloads_human": stmt.excluded.downloads_human,
                "downloads_bot": stmt.excluded.downloads_bot,
                "misses": stmt.excluded.misses,
            },
        )
        db.execute(stmt)
        db.commit()

        streak = compute_legacy_streak(db, as_of=target_date)

        legacy_h = sum(
            counts[0] for (cls, lvl), counts in sharded_agg.items() if lvl == 3
        )
        total_h = sum(h for h, _ in legacy_counts.values())
        total_b = sum(b for _, b in legacy_counts.values())
        total_misses = sum(counts[2] for counts in sharded_agg.values())
        logger.info(
            "rollup_download_stats(%s): %d artwork rows, %d straggler rows; "
            "human=%d bot=%d orphans=%d/%d legacy_non_bot=%d misses=%d streak=%d",
            target_date,
            len(legacy_payload),
            len(straggler_counts),
            total_h,
            total_b,
            orphan_h,
            orphan_b,
            legacy_h,
            total_misses,
            streak,
        )
        return {
            "date": target_date.isoformat(),
            "artworks_seen": len(legacy_payload),
            "downloads_human": total_h,
            "downloads_bot": total_b,
            "orphan_downloads": orphan_h + orphan_b,
            "legacy_hits_non_bot": legacy_h,
            "misses": total_misses,
            "straggler_orphans": straggler_orphans,
            "streak_days": streak,
        }
    finally:
        db.close()

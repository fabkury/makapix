#!/usr/bin/env python3
"""Vault resharding migration tool — see docs/vault-resharding/PLAN.md §6.

Subcommands (delete-legacy/prune-empty-dirs land in a later PR, gated on
the plan's phase progression):

    status      Reconciliation report with gate-mapped fields (DB vs disk,
                both sharding schemes, orphans, out-of-scope paths).
    copy        Phase 1: ensure every DB-referenced v1 (3-level) file has an
                identical v2 (2-level) twin. Never touches v1 files.
    verify      Phase 2: full sha256 pass over every referenced file pair;
                writes a JSON manifest; exits nonzero on any failure.
    flip        Phase 3: point the DB at the v2 locations. Per post:
                re-verify/repair the v2 sibling set (D9), then rewrite
                storage_shard + art_url. Rewrites the other D11 URL columns
                (users.avatar_url, social_notifications.*, blog_posts
                image_urls[] and body) pattern-scoped, and only when the v2
                target file exists. Every change is appended to a JSONL
                manifest BEFORE the DB write. Idempotent — re-run until the
                summary reports no work.
    unflip      Phase 3 rollback: consumes a flip manifest (never a blind
                pattern rewrite — that would corrupt v2-born assets), in
                reverse order. Restores a row only if its current value
                still matches what flip wrote AND the v1 file still exists.
    clean-tmp   Remove stray atomic-write temp files (*.reshard-tmp).

Common flags: --class artwork|avatar|blog_image (default: all), --dry-run,
--limit N, --key UUID, --json. Flip extras: --manifest PATH (output;
required input for unflip), --batch N (commit interval, default 500),
--null-dangling (NULL nullable scalar URL columns whose target file exists
at NEITHER location — pre-existing broken thumbnails; recorded in the
manifest).

Usage (inside the api container):

    cd deploy/stack
    docker compose exec api python scripts/reshard_vault.py status --json
    docker compose exec api python scripts/reshard_vault.py copy --dry-run
    docker compose exec api python scripts/reshard_vault.py copy --limit 10
    docker compose exec api python scripts/reshard_vault.py verify
    # Phase 3 (after pg_dump; see PLAN.md §9):
    docker compose exec api python scripts/reshard_vault.py flip --dry-run
    docker compose exec api python scripts/reshard_vault.py flip --limit 10
    docker compose exec api python scripts/reshard_vault.py flip
    docker compose exec api python scripts/reshard_vault.py unflip \
        --manifest /workspace/api/reshard-reports/flip-manifest-<ts>.jsonl

Safety invariants (PLAN.md §5):
- I2: stored values are the source of truth; this tool flags (never "fixes")
  rows whose stored shard disagrees with the sha256 derivation.
- I3: every mode is idempotent and re-runnable; copy/verify converge.
- I6: only the allowlisted subtrees are touched — 2-hex-char shard dirs,
  avatar/, blog_image/. Everything else at the vault root (bdr/, lost+found,
  ...) is reported as out-of-scope and never read, copied, or deleted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

sys.path.insert(0, "/workspace/api")

from sqlalchemy import text  # noqa: E402

from app import models  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.vault import (  # noqa: E402
    TMP_SUFFIX,
    compute_storage_shard_v1,
    compute_storage_shard_v2,
    get_vault_location,
    write_file_atomic,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("reshard_vault")

ASSET_CLASSES = ("artwork", "avatar", "blog_image")

# Sub-vault directory prefix per asset class ("" = the vault root itself).
CLASS_PREFIX = {"artwork": "", "avatar": "avatar", "blog_image": "blog_image"}

# Vault-root entries that are expected but not artwork shard dirs.
KNOWN_NON_SHARD_DIRS = {"avatar", "blog_image"}

_HEX2 = re.compile(r"^[0-9a-f]{2}$")
_FILE_NAME_RE = re.compile(
    r"^(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    r"(?P<up>_upscaled)?\.(?P<ext>png|gif|webp|bmp|jpg)$"
)

# Path part of a stored vault URL (after stripping scheme://host), both
# depths, all classes, optional /api/vault prefix.
_VAULT_PATH_RE = re.compile(
    r"^/(?:api/vault/)?"
    r"(?:(?P<cls>avatar|blog_image)/)?"
    r"(?P<s1>[0-9a-f]{2})/(?P<s2>[0-9a-f]{2})(?:/(?P<s3>[0-9a-f]{2}))?"
    r"/(?P<uuid>[0-9a-f-]{36})(?P<up>_upscaled)?\.(?P<ext>png|gif|webp|bmp|jpg)$"
)

# Vault URLs embedded in free text (blog_posts.body markdown).
_URL_IN_TEXT_RE = re.compile(
    r"(?:https?://[A-Za-z0-9.-]+|/api/vault)"
    r"(/(?:avatar/|blog_image/)?[0-9a-f]{2}/[0-9a-f]{2}(?:/[0-9a-f]{2})?"
    r"/[0-9a-f-]{36}(?:_upscaled)?\.(?:png|gif|webp|bmp|jpg))"
)

# D11 URL-bearing columns: (table, column, kind). `kind` is how values are
# extracted: scalar string, text[] array, or free text to regex-scan.
URL_COLUMNS = [
    ("posts", "art_url", "scalar"),
    ("users", "avatar_url", "scalar"),
    ("social_notifications", "actor_avatar_url", "scalar"),
    ("social_notifications", "content_art_url", "scalar"),
    ("blog_posts", "image_urls", "array"),
    ("blog_posts", "body", "text"),
]


@dataclass(frozen=True)
class Ref:
    """A DB-referenced vault file (one physical file per scheme)."""

    asset_class: str
    uuid: str  # canonical lowercase string form
    ext: str  # ".png"
    upscaled: bool = False
    optional: bool = False  # upscaled variants may legitimately not exist


def class_base(asset_class: str) -> Path:
    prefix = CLASS_PREFIX[asset_class]
    base = get_vault_location()
    return base / prefix if prefix else base


def ref_file_name(ref: Ref) -> str:
    return f"{ref.uuid}{'_upscaled' if ref.upscaled else ''}{ref.ext}"


def ref_paths(ref: Ref) -> tuple[Path, Path]:
    """(v1_path, v2_path) for a referenced file."""
    key = UUID(ref.uuid)
    base = class_base(ref.asset_class)
    name = ref_file_name(ref)
    return (
        base / compute_storage_shard_v1(key) / name,
        base / compute_storage_shard_v2(key) / name,
    )


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_vault_url(value: str) -> dict | None:
    """Parse a stored vault URL into its components, or None if not one."""
    if not value:
        return None
    path = value
    if "://" in value:
        try:
            from urllib.parse import urlparse

            path = urlparse(value).path
        except ValueError:
            return None
    m = _VAULT_PATH_RE.match(path)
    if not m:
        return None
    return {
        "cls": m.group("cls") or "artwork",
        "components": tuple(
            c for c in (m.group("s1"), m.group("s2"), m.group("s3")) if c
        ),
        "uuid": m.group("uuid").lower(),
        "upscaled": bool(m.group("up")),
        "ext": "." + m.group("ext").lower(),
        "level": 3 if m.group("s3") else 2,
    }


# ---------------------------------------------------------------------------
# Reference collection (always FROM the DB; disk walks only detect orphans)
# ---------------------------------------------------------------------------


def collect_refs(db, classes: list[str]) -> tuple[set[Ref], dict]:
    """Build the set of DB-referenced vault files plus a DB-side report."""
    report: dict = {
        "posts_artwork": 0,
        "null_shard_rows": 0,
        "shard_derivation_mismatches": [],
        "v1_url_refs": {},
        "anomalous_url_refs": [],
    }
    refs: set[Ref] = set()

    # --- artwork via posts/post_files (canonical references) --------------
    if "artwork" in classes:
        rows = db.execute(text("""
                SELECT p.id, p.storage_key::text AS storage_key, p.storage_shard,
                       COALESCE(array_agg(pf.format)
                                FILTER (WHERE pf.format IS NOT NULL),
                                '{}') AS formats
                FROM posts p
                LEFT JOIN post_files pf ON pf.post_id = p.id
                WHERE p.kind = 'artwork' AND p.storage_key IS NOT NULL
                GROUP BY p.id
                """)).all()
        ext_by_format = {"png": ".png", "gif": ".gif", "webp": ".webp", "bmp": ".bmp"}
        for row in rows:
            report["posts_artwork"] += 1
            key = UUID(row.storage_key)
            shard = row.storage_shard
            if not shard:
                report["null_shard_rows"] += 1
                continue
            expected = (
                compute_storage_shard_v1(key)
                if len(shard) == 8
                else compute_storage_shard_v2(key)
            )
            if shard != expected:
                report["shard_derivation_mismatches"].append(
                    {"post_id": row.id, "stored": shard, "derived": expected}
                )
                continue
            for fmt in row.formats:
                ext = ext_by_format.get(fmt)
                if ext:
                    refs.add(Ref("artwork", row.storage_key.lower(), ext))
            # The upscaled variant may or may not have been generated.
            refs.add(
                Ref(
                    "artwork",
                    row.storage_key.lower(),
                    ".webp",
                    upscaled=True,
                    optional=True,
                )
            )

    # --- URL-bearing columns (D11) -----------------------------------------
    # These catch files whose only live reference is a stored URL (e.g. an
    # old avatar still shown by a notification snapshot).
    for table, column, kind in URL_COLUMNS:
        if kind == "scalar":
            values = [
                v
                for (v,) in db.execute(
                    text(
                        f"SELECT {column} FROM {table} "
                        f"WHERE {column} IS NOT NULL AND {column} != ''"
                    )
                )
            ]
        elif kind == "array":
            values = [
                v for (v,) in db.execute(text(f"SELECT unnest({column}) FROM {table}"))
            ]
        else:  # text: scan for embedded vault URLs
            values = []
            for (body,) in db.execute(
                text(f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL")
            ):
                values.extend(m.group(1) for m in _URL_IN_TEXT_RE.finditer(body))

        col_key = f"{table}.{column}"
        v1_count = 0
        for value in values:
            parsed = parse_vault_url(value)
            if not parsed:
                continue
            if parsed["cls"] not in classes:
                continue
            key = UUID(parsed["uuid"])
            derived = (
                compute_storage_shard_v1(key)
                if parsed["level"] == 3
                else compute_storage_shard_v2(key)
            )
            if "/".join(parsed["components"]) != derived:
                report["anomalous_url_refs"].append(
                    {"column": col_key, "url": value, "derived": derived}
                )
                continue
            if parsed["level"] == 3:
                v1_count += 1
            refs.add(
                Ref(parsed["cls"], parsed["uuid"], parsed["ext"], parsed["upscaled"])
            )
        report["v1_url_refs"][col_key] = v1_count

    return refs, report


# ---------------------------------------------------------------------------
# Disk walk (allowlist-scoped; never leaves the recognized subtrees)
# ---------------------------------------------------------------------------


@dataclass
class DiskFile:
    asset_class: str
    level: int  # 2 | 3
    path: Path
    uuid: str
    ext: str
    upscaled: bool


def walk_disk(classes: list[str]) -> dict:
    """Walk the allowlisted subtrees; classify every entry found."""
    result = {
        "files": [],  # list[DiskFile]
        "tmp_files": [],
        "unknown_files": [],
        "out_of_scope_paths": [],
    }

    root = get_vault_location()
    if not root.exists():
        raise SystemExit(f"VAULT_LOCATION {root} does not exist")

    # Out-of-scope detection at the vault root (artwork tree shares the root).
    for entry in sorted(root.iterdir()):
        if entry.name in KNOWN_NON_SHARD_DIRS:
            continue
        if entry.is_dir() and _HEX2.match(entry.name):
            continue
        if entry.name.endswith(TMP_SUFFIX):
            result["tmp_files"].append(str(entry))
            continue
        result["out_of_scope_paths"].append(str(entry))

    def classify_file(asset_class: str, level: int, f: Path) -> None:
        if f.name.endswith(TMP_SUFFIX):
            result["tmp_files"].append(str(f))
            return
        m = _FILE_NAME_RE.match(f.name)
        if not m:
            result["unknown_files"].append(str(f))
            return
        result["files"].append(
            DiskFile(
                asset_class=asset_class,
                level=level,
                path=f,
                uuid=m.group("uuid").lower(),
                ext="." + m.group("ext").lower(),
                upscaled=bool(m.group("up")),
            )
        )

    for asset_class in classes:
        base = class_base(asset_class)
        if not base.exists():
            continue
        for d1 in sorted(base.iterdir()):
            if not (d1.is_dir() and _HEX2.match(d1.name)):
                if asset_class != "artwork" and d1.name not in KNOWN_NON_SHARD_DIRS:
                    if d1.name.endswith(TMP_SUFFIX):
                        result["tmp_files"].append(str(d1))
                    else:
                        result["out_of_scope_paths"].append(str(d1))
                continue
            for d2 in sorted(d1.iterdir()):
                if d2.is_file():
                    # Files directly under <a>/ are not part of either scheme.
                    classify = (
                        result["tmp_files"]
                        if d2.name.endswith(TMP_SUFFIX)
                        else result["unknown_files"]
                    )
                    classify.append(str(d2))
                    continue
                if not _HEX2.match(d2.name):
                    result["out_of_scope_paths"].append(str(d2))
                    continue
                for entry in sorted(d2.iterdir()):
                    if entry.is_file():
                        # <a>/<b>/<file> = the 2-level scheme.
                        classify_file(asset_class, 2, entry)
                    elif entry.is_dir() and _HEX2.match(entry.name):
                        # <a>/<b>/<c>/ = a 3-level shard dir.
                        for f in sorted(entry.iterdir()):
                            if f.is_file():
                                classify_file(asset_class, 3, f)
                            else:
                                result["out_of_scope_paths"].append(str(f))
                    else:
                        result["out_of_scope_paths"].append(str(entry))

    return result


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


def filter_refs(refs: set[Ref], args) -> list[Ref]:
    out = [r for r in refs if r.asset_class in args.classes]
    if args.key:
        out = [r for r in out if r.uuid == args.key.lower()]
    return sorted(out, key=lambda r: (r.asset_class, r.uuid, r.ext, r.upscaled))


def mode_status(db, args) -> int:
    refs, db_report = collect_refs(db, args.classes)
    disk = walk_disk(args.classes)

    ref_index = {(r.asset_class, r.uuid, r.ext, r.upscaled) for r in refs}
    by_loc: dict[tuple, dict[int, DiskFile]] = defaultdict(dict)
    for f in disk["files"]:
        by_loc[(f.asset_class, f.uuid, f.ext, f.upscaled)][f.level] = f

    v1_only = twinned = stale = v2_only = orphans = 0
    orphan_examples = []
    for key, levels in by_loc.items():
        if key not in ref_index:
            orphans += len(levels)
            if len(orphan_examples) < 20:
                orphan_examples.append(str(next(iter(levels.values())).path))
        if 3 in levels and 2 in levels:
            if levels[3].path.stat().st_size == levels[2].path.stat().st_size:
                twinned += 1
            else:
                stale += 1
        elif 3 in levels:
            v1_only += 1
        else:
            v2_only += 1

    report = {
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "vault_location": str(get_vault_location()),
        "classes": args.classes,
        "db": {
            **db_report,
            "shard_derivation_mismatches": len(
                db_report["shard_derivation_mismatches"]
            ),
            "anomalous_url_refs": len(db_report["anomalous_url_refs"]),
            "referenced_files": len(refs),
        },
        "disk": {
            "v1_only_files": v1_only,
            "twinned": twinned,
            "stale_twins": stale,
            "v2_only": v2_only,
            "orphans": orphans,
            "orphan_examples": orphan_examples,
            "unknown_files": disk["unknown_files"],
            "out_of_scope_paths": disk["out_of_scope_paths"],
            "tmp_files": disk["tmp_files"],
        },
        "details": {
            "shard_derivation_mismatches": db_report["shard_derivation_mismatches"][
                :50
            ],
            "anomalous_url_refs": db_report["anomalous_url_refs"][:50],
        },
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        d = report["db"]
        k = report["disk"]
        print(f"Environment:        {report['environment']}")
        print(f"Vault:              {report['vault_location']}")
        print(f"Artwork posts:      {d['posts_artwork']}")
        print(f"Referenced files:   {d['referenced_files']}")
        print(f"NULL-shard rows:    {d['null_shard_rows']}")
        print(f"Shard mismatches:   {d['shard_derivation_mismatches']}")
        print(f"Anomalous URL refs: {d['anomalous_url_refs']}")
        print("v1 URL refs by column:")
        for col, n in d["v1_url_refs"].items():
            print(f"  {col}: {n}")
        print(
            f"Disk: v1-only={k['v1_only_files']} twinned={k['twinned']} "
            f"stale={k['stale_twins']} v2-only={k['v2_only']} orphans={k['orphans']}"
        )
        print(f"Tmp files:          {len(k['tmp_files'])}")
        print(f"Unknown files:      {len(k['unknown_files'])}")
        print(f"Out-of-scope paths: {len(k['out_of_scope_paths'])}")
        for p in k["out_of_scope_paths"][:10]:
            print(f"  (out of scope) {p}")
    return 0


def copy_refs(refs: list[Ref], *, dry_run: bool = False, limit: int = 0) -> dict:
    """Phase 1 work loop: ensure every v1 source has an identical v2 twin."""
    counts: dict = defaultdict(int)
    missing_sources: list[str] = []
    done = 0
    for ref in refs:
        if limit and done >= limit:
            counts["limit_reached"] = 1
            break
        v1, v2 = ref_paths(ref)
        if not v1.exists():
            if v2.exists():
                counts["v2_only"] += 1
            elif ref.optional:
                counts["optional_absent"] += 1
            else:
                counts["missing_source"] += 1
                missing_sources.append(str(v1))
            continue
        if v2.exists() and sha256_file(v1) == sha256_file(v2):
            counts["already_twinned"] += 1
            continue
        action = "re-copied (stale twin)" if v2.exists() else "copied"
        if dry_run:
            counts["would_copy"] += 1
        else:
            write_file_atomic(v2, v1.read_bytes())
            counts["copied"] += 1
            done += 1
            logger.info("%s %s -> %s", action, v1, v2)
    summary = dict(counts)
    summary["missing_source_examples"] = missing_sources[:20]
    summary["missing_source_total"] = len(missing_sources)
    return summary


def verify_refs(refs: list[Ref]) -> dict:
    """Phase 2 work loop: sha256-compare every referenced v1/v2 pair."""
    results: dict = {
        "verified": 0,
        "v2_only": 0,
        "optional_absent": 0,
        "failures": [],
    }
    for ref in refs:
        v1, v2 = ref_paths(ref)
        v1_exists, v2_exists = v1.exists(), v2.exists()
        if not v1_exists and not v2_exists:
            if ref.optional:
                results["optional_absent"] += 1
            else:
                results["failures"].append(
                    {
                        "file": ref_file_name(ref),
                        "class": ref.asset_class,
                        "reason": "missing at both locations",
                    }
                )
            continue
        if not v1_exists:
            # v2-born asset (created after the cutover) — nothing to compare.
            results["v2_only"] += 1
            continue
        if not v2_exists:
            results["failures"].append(
                {"file": str(v1), "class": ref.asset_class, "reason": "v2 twin missing"}
            )
            continue
        if v1.stat().st_size != v2.stat().st_size:
            results["failures"].append(
                {"file": str(v1), "class": ref.asset_class, "reason": "size mismatch"}
            )
            continue
        if sha256_file(v1) != sha256_file(v2):
            results["failures"].append(
                {"file": str(v1), "class": ref.asset_class, "reason": "sha256 mismatch"}
            )
            continue
        results["verified"] += 1
    return results


def mode_copy(db, args) -> int:
    refs, db_report = collect_refs(db, args.classes)
    if db_report["shard_derivation_mismatches"]:
        logger.error(
            "Refusing to copy: %d post(s) whose stored shard disagrees with "
            "the sha256 derivation. Resolve these first (see `status`).",
            len(db_report["shard_derivation_mismatches"]),
        )
        return 1

    summary = copy_refs(filter_refs(refs, args), dry_run=args.dry_run, limit=args.limit)
    print(json.dumps(summary, indent=2) if args.json else summary)
    if summary["missing_source_total"]:
        logger.warning(
            "%d referenced file(s) missing at BOTH locations — investigate "
            "before relying on gate G1.",
            summary["missing_source_total"],
        )
    return 0


def mode_verify(db, args) -> int:
    refs, db_report = collect_refs(db, args.classes)
    results = verify_refs(filter_refs(refs, args))

    manifest = {
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "classes": args.classes,
        "db_report": {
            **db_report,
            "shard_derivation_mismatches": len(
                db_report["shard_derivation_mismatches"]
            ),
            "anomalous_url_refs": len(db_report["anomalous_url_refs"]),
        },
        "results": {
            "verified": results["verified"],
            "v2_only": results["v2_only"],
            "optional_absent": results["optional_absent"],
            "failure_count": len(results["failures"]),
        },
        "failures": results["failures"],
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(manifest, indent=2))
    logger.info("Verification manifest written to %s", report_path)

    print(json.dumps(manifest["results"], indent=2))
    if results["failures"]:
        logger.error("%d verification failure(s)", len(results["failures"]))
        return 1
    return 0


# ---------------------------------------------------------------------------
# Phase 3: flip / unflip
# ---------------------------------------------------------------------------


class FlipManifest:
    """Append-only JSONL record of every DB value the flip changes.

    Each line: {"table", "pk", "column", "old", "new"}. Written and flushed
    BEFORE the corresponding DB write, so the manifest is always a superset
    of applied changes — `unflip` skips entries whose current value doesn't
    match, so replaying a too-long manifest is safe.
    """

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(path, "a", encoding="utf-8")

    def record(self, table: str, pk, column: str, old, new) -> None:
        self._fh.write(
            json.dumps(
                {
                    "table": table,
                    "pk": str(pk),
                    "column": column,
                    "old": old,
                    "new": new,
                }
            )
            + "\n"
        )
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def close(self) -> None:
        self._fh.close()


def _parsed_paths(parsed: dict) -> tuple[Path, Path]:
    """(v1_path, v2_path) for a parsed vault URL."""
    key = UUID(parsed["uuid"])
    base = class_base(parsed["cls"])
    name = f"{parsed['uuid']}{'_upscaled' if parsed['upscaled'] else ''}{parsed['ext']}"
    return (
        base / compute_storage_shard_v1(key) / name,
        base / compute_storage_shard_v2(key) / name,
    )


def _rewrite_v1_url(value: str, parsed: dict) -> str | None:
    """Rewrite the parsed v1 vault URL inside ``value`` to its v2 form,
    preserving the prefix style (absolute vault base or /api/vault).
    Returns None if the expected fragment is not present verbatim."""
    key = UUID(parsed["uuid"])
    old_frag = "/".join(parsed["components"]) + "/" + parsed["uuid"]
    new_frag = compute_storage_shard_v2(key) + "/" + parsed["uuid"]
    if old_frag not in value:
        return None
    return value.replace(old_frag, new_frag)


def _check_v1_url_target(parsed: dict, args, counters) -> str | None:
    """Shared D11 gate for URL rewrites. Returns:
    "rewrite" | "null" (dangling, --null-dangling active) | None (skip)."""
    key = UUID(parsed["uuid"])
    if "/".join(parsed["components"]) != compute_storage_shard_v1(key):
        counters["skipped_anomalous_url"] += 1
        return None
    v1_path, v2_path = _parsed_paths(parsed)
    if v2_path.exists():
        return "rewrite"
    if args.null_dangling and not v1_path.exists():
        return "null"
    counters["skipped_missing_v2_target"] += 1
    logger.warning(
        "flip: v2 target missing for %s (v1 exists: %s) — skipped",
        v2_path,
        v1_path.exists(),
    )
    return None


def _reverify_post_siblings(post, v2_shard: str, dry_run: bool, counters) -> None:
    """D9: immediately before flipping a post, ensure every file of its v1
    sibling set has an identical v2 twin; copy missing twins, repair stale
    ones. Globs the v1 folder (not post_files) so late-created variants and
    the upscaled file are covered."""
    v1_folder = get_vault_location() / post.storage_shard
    v2_folder = get_vault_location() / v2_shard
    if not v1_folder.is_dir():
        counters["posts_no_v1_files"] += 1
        return
    for v1_file in sorted(v1_folder.glob(f"{post.storage_key}*")):
        if v1_file.name.endswith(TMP_SUFFIX):
            continue
        v2_file = v2_folder / v1_file.name
        if v2_file.exists() and sha256_file(v1_file) == sha256_file(v2_file):
            continue
        if dry_run:
            counters["would_repair_twins"] += 1
        else:
            write_file_atomic(v2_file, v1_file.read_bytes())
            counters["repaired_twins"] += 1
            logger.info("flip: repaired twin %s", v2_file)


def mode_flip(db, args) -> int:
    _, db_report = collect_refs(db, args.classes)
    if db_report["shard_derivation_mismatches"]:
        logger.error(
            "Refusing to flip: %d post(s) whose stored shard disagrees with "
            "the sha256 derivation. Resolve these first (see `status`).",
            len(db_report["shard_derivation_mismatches"]),
        )
        return 1

    counters: dict = defaultdict(int)
    manifest: FlipManifest | None = None
    if not args.dry_run:
        manifest = FlipManifest(Path(args.manifest))
        logger.info("Flip manifest: %s", manifest.path)

    def commit_batch() -> None:
        counters["_pending"] += 1
        if counters["_pending"] >= args.batch:
            db.commit()
            counters["_pending"] = 0

    # --- 1. posts: storage_shard + art_url ---------------------------------
    if "artwork" in args.classes:
        posts = (
            db.query(models.Post)
            .filter(
                models.Post.kind == "artwork",
                models.Post.storage_key.isnot(None),
                models.Post.storage_shard.isnot(None),
            )
            .order_by(models.Post.id)
            .all()
        )
        for post in posts:
            if len(post.storage_shard) != 8:
                continue  # already flipped or v2-born
            if args.key and str(post.storage_key).lower() != args.key:
                continue
            if args.limit and counters["posts_flipped"] >= args.limit:
                counters["limit_reached"] = 1
                break

            v1_shard = post.storage_shard
            v2_shard = compute_storage_shard_v2(post.storage_key)

            # art_url decision first — a post whose art_url can't be safely
            # rewritten is skipped whole, never half-flipped.
            new_art_url = None
            if post.art_url:
                parsed = parse_vault_url(post.art_url)
                if parsed and parsed["level"] == 3:
                    if parsed["uuid"] != str(post.storage_key).lower():
                        counters["skipped_art_url_uuid_mismatch"] += 1
                        logger.warning(
                            "flip: post %d art_url uuid != storage_key — skipped",
                            post.id,
                        )
                        continue
                    new_art_url = _rewrite_v1_url(post.art_url, parsed)
                    if new_art_url is None:
                        counters["skipped_art_url_rewrite_failed"] += 1
                        continue
                # level-2 or non-vault URL: leave art_url untouched

            _reverify_post_siblings(post, v2_shard, args.dry_run, counters)

            if args.dry_run:
                counters["posts_would_flip"] += 1
                continue

            manifest.record("posts", post.id, "storage_shard", v1_shard, v2_shard)
            post.storage_shard = v2_shard
            if new_art_url:
                manifest.record("posts", post.id, "art_url", post.art_url, new_art_url)
                post.art_url = new_art_url
            counters["posts_flipped"] += 1
            commit_batch()
        db.commit()

    # --- 2. scalar URL columns ---------------------------------------------
    scalar_targets = [
        (models.User, "users", "avatar_url", True),
        (models.SocialNotification, "social_notifications", "actor_avatar_url", True),
        (models.SocialNotification, "social_notifications", "content_art_url", True),
    ]
    for model, table, attr, nullable in scalar_targets:
        col = getattr(model, attr)
        rows = db.query(model).filter(col.isnot(None), col != "").all()
        for row in rows:
            value = getattr(row, attr)
            parsed = parse_vault_url(value)
            if not parsed or parsed["level"] != 3:
                continue
            if parsed["cls"] not in args.classes:
                continue
            action = _check_v1_url_target(parsed, args, counters)
            if action is None:
                continue
            if action == "null" and not nullable:
                counters["skipped_missing_v2_target"] += 1
                continue
            new_value = None if action == "null" else _rewrite_v1_url(value, parsed)
            if action == "rewrite" and new_value is None:
                counters["skipped_url_rewrite_failed"] += 1
                continue
            if args.dry_run:
                counters[f"would_rewrite:{table}.{attr}"] += 1
                continue
            manifest.record(table, row.id, attr, value, new_value)
            setattr(row, attr, new_value)
            counters[
                f"{'nulled' if action == 'null' else 'rewritten'}:{table}.{attr}"
            ] += 1
            commit_batch()
        db.commit()

    # --- 3. blog_posts: image_urls[] and body markdown ----------------------
    if "blog_image" in args.classes:
        for row in db.query(models.BlogPost).order_by(models.BlogPost.id).all():
            # image_urls[]
            old_list = list(row.image_urls or [])
            new_list = []
            changed = False
            for element in old_list:
                parsed = parse_vault_url(element)
                if parsed and parsed["level"] == 3 and parsed["cls"] in args.classes:
                    action = _check_v1_url_target(parsed, args, counters)
                    if action == "rewrite":
                        rewritten = _rewrite_v1_url(element, parsed)
                        if rewritten:
                            new_list.append(rewritten)
                            changed = True
                            continue
                    # dangling array elements are left in place (arrays
                    # can't hold NULL meaningfully) and counted above
                new_list.append(element)
            if changed:
                if args.dry_run:
                    counters["would_rewrite:blog_posts.image_urls"] += 1
                else:
                    manifest.record(
                        "blog_posts", row.id, "image_urls", old_list, new_list
                    )
                    row.image_urls = new_list
                    counters["rewritten:blog_posts.image_urls"] += 1
                    commit_batch()

            # body markdown
            body = row.body or ""
            new_body = body
            for m in _URL_IN_TEXT_RE.finditer(body):
                parsed = parse_vault_url(m.group(1))
                if not parsed or parsed["level"] != 3:
                    continue
                if parsed["cls"] not in args.classes:
                    continue
                if _check_v1_url_target(parsed, args, counters) != "rewrite":
                    continue
                rewritten = _rewrite_v1_url(m.group(1), parsed)
                if rewritten:
                    new_body = new_body.replace(m.group(1), rewritten)
            if new_body != body:
                if args.dry_run:
                    counters["would_rewrite:blog_posts.body"] += 1
                else:
                    manifest.record("blog_posts", row.id, "body", body, new_body)
                    row.body = new_body
                    counters["rewritten:blog_posts.body"] += 1
                    commit_batch()
        db.commit()

    if manifest:
        manifest.close()
    counters.pop("_pending", None)
    summary = dict(counters)
    if manifest:
        summary["manifest"] = str(manifest.path)
    print(json.dumps(summary, indent=2) if args.json else summary)
    return 0


_UNFLIP_MODELS = {
    "posts": models.Post,
    "users": models.User,
    "social_notifications": models.SocialNotification,
    "blog_posts": models.BlogPost,
}


def _unflip_pk(table: str, pk: str):
    return UUID(pk) if table == "social_notifications" else int(pk)


def mode_unflip(db, args) -> int:
    if not args.manifest or not Path(args.manifest).is_file():
        logger.error("unflip requires --manifest pointing at a flip manifest")
        return 1

    entries = []
    with open(args.manifest, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    counters: dict = defaultdict(int)
    pending = 0
    # Reverse order: later changes unwind first.
    for entry in reversed(entries):
        model = _UNFLIP_MODELS.get(entry["table"])
        if model is None:
            counters["skipped_unknown_table"] += 1
            continue
        row = db.get(model, _unflip_pk(entry["table"], entry["pk"]))
        if row is None:
            counters["skipped_missing_row"] += 1
            continue
        current = getattr(row, entry["column"])
        if isinstance(current, list):
            current = list(current)
        if current != entry["new"]:
            counters["skipped_changed_since_flip"] += 1
            logger.warning(
                "unflip: %s %s.%s changed since flip — skipped",
                entry["table"],
                entry["pk"],
                entry["column"],
            )
            continue

        # Safety: never point the DB at a v1 location whose file is gone.
        old = entry["old"]
        if entry["column"] == "storage_shard":
            v1_folder = get_vault_location() / old
            if not (v1_folder.is_dir() and any(v1_folder.glob(f"{row.storage_key}*"))):
                counters["skipped_no_v1_file"] += 1
                logger.warning(
                    "unflip: post %s has no files at v1 shard %s — skipped",
                    entry["pk"],
                    old,
                )
                continue
        elif isinstance(old, str):
            parsed = parse_vault_url(old)
            if (
                parsed
                and parsed["level"] == 3
                and not _parsed_paths(parsed)[0].exists()
            ):
                counters["skipped_no_v1_file"] += 1
                logger.warning(
                    "unflip: v1 file gone for %s.%s (%s) — skipped",
                    entry["table"],
                    entry["column"],
                    entry["pk"],
                )
                continue
        elif isinstance(old, list):
            missing = False
            for element in old:
                parsed = parse_vault_url(element)
                if (
                    parsed
                    and parsed["level"] == 3
                    and not _parsed_paths(parsed)[0].exists()
                ):
                    missing = True
                    break
            if missing:
                counters["skipped_no_v1_file"] += 1
                continue

        if args.dry_run:
            counters["would_restore"] += 1
            continue
        setattr(row, entry["column"], old)
        counters["restored"] += 1
        pending += 1
        if pending >= args.batch:
            db.commit()
            pending = 0
    db.commit()

    summary = dict(counters)
    print(json.dumps(summary, indent=2) if args.json else summary)
    return 0


def mode_clean_tmp(db, args) -> int:
    disk = walk_disk(args.classes)
    removed = 0
    for tmp in disk["tmp_files"]:
        p = Path(tmp)
        try:
            # Safety margin: an in-flight atomic write could still own a
            # fresh temp file.
            if time.time() - p.stat().st_mtime < 3600:
                logger.info("Skipping fresh tmp file %s", p)
                continue
            if args.dry_run:
                logger.info("Would remove %s", p)
            else:
                p.unlink()
                logger.info("Removed %s", p)
                removed += 1
        except OSError as e:
            logger.warning("Could not remove %s: %s", p, e)
    print({"removed": removed, "found": len(disk["tmp_files"])})
    return 0


# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "mode",
        choices=["status", "copy", "verify", "flip", "unflip", "clean-tmp"],
    )
    parser.add_argument(
        "--class",
        dest="classes",
        action="append",
        choices=list(ASSET_CLASSES),
        help="Restrict to an asset class (repeatable; default: all)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Cap copy operations")
    parser.add_argument("--key", help="Restrict to one storage key (UUID)")
    parser.add_argument(
        "--report",
        default=f"/workspace/api/reshard-reports/verify-{time.strftime('%Y%m%d-%H%M%S')}.json",
        help="Verification manifest path (verify mode)",
    )
    parser.add_argument(
        "--manifest",
        default=f"/workspace/api/reshard-reports/flip-manifest-{time.strftime('%Y%m%d-%H%M%S')}.jsonl",
        help="Flip manifest path (output for flip; required input for unflip)",
    )
    parser.add_argument(
        "--batch", type=int, default=500, help="DB commit interval (flip/unflip)"
    )
    parser.add_argument(
        "--null-dangling",
        action="store_true",
        help="flip: NULL nullable scalar URL columns whose target file exists "
        "at NEITHER location (pre-existing broken references)",
    )
    args = parser.parse_args()
    if not args.classes:
        args.classes = list(ASSET_CLASSES)
    if args.key:
        args.key = str(UUID(args.key))  # normalize / validate

    db = SessionLocal()
    try:
        return {
            "status": mode_status,
            "copy": mode_copy,
            "verify": mode_verify,
            "flip": mode_flip,
            "unflip": mode_unflip,
            "clean-tmp": mode_clean_tmp,
        }[args.mode](db, args)
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

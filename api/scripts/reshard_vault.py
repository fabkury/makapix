#!/usr/bin/env python3
"""Vault resharding migration tool — see docs/vault-resharding/PLAN.md §6.

Subcommands (this PR ships the non-destructive modes; flip/unflip/
delete-legacy land in a later PR, gated on the plan's phase progression):

    status      Reconciliation report with gate-mapped fields (DB vs disk,
                both sharding schemes, orphans, out-of-scope paths).
    copy        Phase 1: ensure every DB-referenced v1 (3-level) file has an
                identical v2 (2-level) twin. Never touches v1 files.
    verify      Phase 2: full sha256 pass over every referenced file pair;
                writes a JSON manifest; exits nonzero on any failure.
    clean-tmp   Remove stray atomic-write temp files (*.reshard-tmp).

Common flags: --class artwork|avatar|blog_image (default: all), --dry-run,
--limit N, --key UUID, --json.

Usage (inside the api container):

    cd deploy/stack
    docker compose exec api python scripts/reshard_vault.py status --json
    docker compose exec api python scripts/reshard_vault.py copy --dry-run
    docker compose exec api python scripts/reshard_vault.py copy --limit 10
    docker compose exec api python scripts/reshard_vault.py verify

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
    parser.add_argument("mode", choices=["status", "copy", "verify", "clean-tmp"])
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
            "clean-tmp": mode_clean_tmp,
        }[args.mode](db, args)
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

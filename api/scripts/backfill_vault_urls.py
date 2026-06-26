#!/usr/bin/env python3
"""Backfill vault URLs from /api/vault/... to https://vault.makapix.club/...

Rewrites posts.art_url, users.avatar_url, and blog_posts.image_urls[] rows whose
stored URL starts with `/api/vault/` to an absolute URL on the public vault
subdomain. Rows that don't match (e.g. external GitHub Pages imports) are left
alone.

Idempotent: rerunning is safe because the LIKE filter only matches unrewritten
rows. Reversible with `--reverse` (rewrites absolute vault URLs back to
`/api/vault/`).

Usage (inside the api container):

    # Dry-run first
    python /workspace/api/scripts/backfill_vault_urls.py \
        --base-url https://vault.makapix.club --dry-run

    # For real
    python /workspace/api/scripts/backfill_vault_urls.py \
        --base-url https://vault.makapix.club

    # Reverse (rollback)
    python /workspace/api/scripts/backfill_vault_urls.py \
        --base-url https://vault.makapix.club --reverse

Run separately per environment (dev base URL = https://vault-dev.makapix.club).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time

sys.path.insert(0, "/workspace/api")

from sqlalchemy import text

from app.db import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("backfill_vault_urls")

OLD_PREFIX = "/api/vault/"

SCALAR_UPDATE_SQL = text("""
    UPDATE {table} SET {col} = :new_prefix || substring({col}, char_length(:old_prefix) + 1)
    WHERE id BETWEEN :lo AND :hi AND {col} LIKE :old_prefix || '%'
    """)

# Array column (blog_posts.image_urls is text[])
ARRAY_UPDATE_SQL = text("""
    UPDATE blog_posts
    SET image_urls = (
        SELECT array_agg(
            CASE WHEN x LIKE :old_prefix || '%'
                 THEN :new_prefix || substring(x, char_length(:old_prefix) + 1)
                 ELSE x
            END
        )
        FROM unnest(image_urls) x
    )
    WHERE id BETWEEN :lo AND :hi
      AND EXISTS (SELECT 1 FROM unnest(image_urls) x WHERE x LIKE :old_prefix || '%')
    """)

MAX_ID_SQL = text("SELECT COALESCE(MAX(id), 0) FROM {table}")
COUNT_MATCHING_SCALAR_SQL = text(
    "SELECT COUNT(*) FROM {table} WHERE {col} LIKE :old_prefix || '%'"
)
COUNT_MATCHING_ARRAY_SQL = text("""
    SELECT COUNT(*) FROM blog_posts
    WHERE EXISTS (SELECT 1 FROM unnest(image_urls) x WHERE x LIKE :old_prefix || '%')
    """)


def backfill_scalar(
    engine,
    table: str,
    col: str,
    old_prefix: str,
    new_prefix: str,
    batch_size: int,
    dry_run: bool,
) -> int:
    with engine.connect() as conn:
        max_id = (
            conn.execute(text(f"SELECT COALESCE(MAX(id), 0) FROM {table}")).scalar()
            or 0
        )
        to_rewrite = (
            conn.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE {col} LIKE :p || '%'"),
                {"p": old_prefix},
            ).scalar()
            or 0
        )
    logger.info(
        "%s.%s: %s rows match prefix %r (max id %s)",
        table,
        col,
        to_rewrite,
        old_prefix,
        max_id,
    )
    if to_rewrite == 0 or dry_run:
        return to_rewrite

    sql = text(
        f"UPDATE {table} SET {col} = :new_prefix || substring({col}, "
        f"char_length(:old_prefix) + 1) "
        f"WHERE id BETWEEN :lo AND :hi AND {col} LIKE :old_prefix || '%'"
    )

    total_updated = 0
    lo = 0
    while lo <= max_id:
        hi = lo + batch_size - 1
        with engine.begin() as conn:
            result = conn.execute(
                sql,
                {
                    "old_prefix": old_prefix,
                    "new_prefix": new_prefix,
                    "lo": lo,
                    "hi": hi,
                },
            )
            updated = result.rowcount or 0
        if updated:
            total_updated += updated
            logger.info(
                "  %s.%s: rewrote %s rows in id range [%s, %s] (total %s/%s)",
                table,
                col,
                updated,
                lo,
                hi,
                total_updated,
                to_rewrite,
            )
        lo = hi + 1
        time.sleep(0.05)  # gentle on the DB
    return total_updated


def backfill_blog_image_urls(
    engine,
    old_prefix: str,
    new_prefix: str,
    batch_size: int,
    dry_run: bool,
) -> int:
    with engine.connect() as conn:
        max_id = (
            conn.execute(text("SELECT COALESCE(MAX(id), 0) FROM blog_posts")).scalar()
            or 0
        )
        to_rewrite = (
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM blog_posts "
                    "WHERE EXISTS (SELECT 1 FROM unnest(image_urls) x WHERE x LIKE :p || '%')"
                ),
                {"p": old_prefix},
            ).scalar()
            or 0
        )
    logger.info(
        "blog_posts.image_urls: %s rows have at least one element matching prefix %r (max id %s)",
        to_rewrite,
        old_prefix,
        max_id,
    )
    if to_rewrite == 0 or dry_run:
        return to_rewrite

    total_updated = 0
    lo = 0
    while lo <= max_id:
        hi = lo + batch_size - 1
        with engine.begin() as conn:
            result = conn.execute(
                ARRAY_UPDATE_SQL,
                {
                    "old_prefix": old_prefix,
                    "new_prefix": new_prefix,
                    "lo": lo,
                    "hi": hi,
                },
            )
            updated = result.rowcount or 0
        if updated:
            total_updated += updated
            logger.info(
                "  blog_posts.image_urls: rewrote %s rows in id range [%s, %s] (total %s/%s)",
                updated,
                lo,
                hi,
                total_updated,
                to_rewrite,
            )
        lo = hi + 1
        time.sleep(0.05)
    return total_updated


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Absolute base URL of the public vault, e.g. https://vault.makapix.club",
    )
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without modifying any rows",
    )
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="Rewrite absolute base-url URLs back to /api/vault/ (rollback)",
    )
    parser.add_argument(
        "--table",
        choices=["posts", "users", "blog_posts", "all"],
        default="all",
    )
    args = parser.parse_args()

    base = args.base_url.rstrip("/") + "/"

    if args.reverse:
        old_prefix = base
        new_prefix = OLD_PREFIX
        logger.info("REVERSE mode: rewriting %r -> %r", old_prefix, new_prefix)
    else:
        old_prefix = OLD_PREFIX
        new_prefix = base
        logger.info("FORWARD mode: rewriting %r -> %r", old_prefix, new_prefix)

    if args.dry_run:
        logger.info("DRY-RUN: no rows will be modified")

    tables = ["posts", "users", "blog_posts"] if args.table == "all" else [args.table]
    grand_total = 0
    for t in tables:
        if t == "posts":
            n = backfill_scalar(
                engine,
                "posts",
                "art_url",
                old_prefix,
                new_prefix,
                args.batch_size,
                args.dry_run,
            )
        elif t == "users":
            n = backfill_scalar(
                engine,
                "users",
                "avatar_url",
                old_prefix,
                new_prefix,
                args.batch_size,
                args.dry_run,
            )
        elif t == "blog_posts":
            n = backfill_blog_image_urls(
                engine, old_prefix, new_prefix, args.batch_size, args.dry_run
            )
        grand_total += n

    if args.dry_run:
        logger.info(
            "DRY-RUN complete: %s rows would be rewritten across selected tables",
            grand_total,
        )
    else:
        logger.info("Done: %s rows rewritten across selected tables", grand_total)
    return 0


if __name__ == "__main__":
    sys.exit(main())

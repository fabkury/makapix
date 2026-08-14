#!/usr/bin/env python3
"""
Bulk-import relicense: unlock the founding catalog for remixing.

Owner decision 2026-08-14 (docs/artwork-provenance/PLAN.md §2.2 L15): the
Dec-2025/Jan-2026 founding bulk import was blanket-stamped CC-BY-ND-4.0, which
under the ND ⇒ not-Remixable rule (ADR 0003) would launch the back-catalog
~91% locked. The owner holds the rights to those works and chose to drop them
to "no license / All rights reserved" — in-Club remixing is enabled by the
Remixable flag + the ToS grant clause instead, and off-Club rights go DOWN,
not up.

Scope: posts with license CC-BY-ND-4.0 created before 2026-02-01 UTC, so any
LATER deliberate ND choice by an artist is preserved. Sets license_id = NULL
and remixable = true. Idempotent: relicensed rows no longer match the filter.

Usage (from within the API container):
    python /workspace/api/scripts/relicense_bulk_import.py [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Add the app to the path
sys.path.insert(0, "/workspace/api")

from app.db import SessionLocal
from app.models import License, Post

ND_IDENTIFIER = "CC-BY-ND-4.0"
BULK_WINDOW_END = datetime(2026, 2, 1, tzinfo=timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        nd = db.query(License).filter(License.identifier == ND_IDENTIFIER).first()
        if nd is None:
            logger.error("License %s not found — nothing to do", ND_IDENTIFIER)
            return 1

        query = db.query(Post).filter(
            Post.license_id == nd.id, Post.created_at < BULK_WINDOW_END
        )
        posts = query.all()
        preserved = (
            db.query(Post)
            .filter(Post.license_id == nd.id, Post.created_at >= BULK_WINDOW_END)
            .count()
        )
        logger.info(
            "Matched %d bulk-window ND posts (preserving %d later ND posts)",
            len(posts),
            preserved,
        )

        if args.dry_run:
            for p in posts[:10]:
                logger.info("  would relicense post %d (%s)", p.id, p.public_sqid)
            if len(posts) > 10:
                logger.info("  ... and %d more", len(posts) - 10)
            logger.info("Dry run — no changes made")
            return 0

        for p in posts:
            p.license_id = None
            p.remixable = True
        db.commit()
        logger.info(
            "Relicensed %d posts (license → none, remixable → true)", len(posts)
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

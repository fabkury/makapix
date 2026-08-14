#!/usr/bin/env python3
"""
Provenance backfill (one-off, idempotent) — docs/artwork-provenance/PLAN.md D4.

Posts that carried an .mkpx layers file at upload came from the app's editor
pipeline; that is the only provenance legacy rows can honestly support. Sets,
for posts where `mkpx_attached_at IS NOT NULL` and both provenance columns are
NULL (the idempotence guard):

- upload_channel = 'app'
- creation_method = 'editor'   (hand-drawn vs import is unknowable)
- source_details._server = {inferred marker, backfilled_at, mkpx_at_upload}

All other rows stay NULL — unknown by design, never coerced.

Usage (from within the API container):
    python /workspace/api/scripts/backfill_provenance.py [--dry-run]
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
from app.models import Post
from app.utils.provenance import (
    CREATION_METHOD_EDITOR,
    SERVER_ZONE_KEY,
    UPLOAD_CHANNEL_APP,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        posts = (
            db.query(Post)
            .filter(
                Post.mkpx_attached_at.isnot(None),
                Post.upload_channel.is_(None),
                Post.creation_method.is_(None),
            )
            .all()
        )
        logger.info("Matched %d mkpx-bearing posts with NULL provenance", len(posts))

        if args.dry_run:
            for p in posts[:10]:
                logger.info("  would backfill post %d (%s)", p.id, p.public_sqid)
            if len(posts) > 10:
                logger.info("  ... and %d more", len(posts) - 10)
            logger.info("Dry run — no changes made")
            return 0

        now = datetime.now(timezone.utc).isoformat()
        for p in posts:
            p.upload_channel = UPLOAD_CHANNEL_APP
            p.creation_method = CREATION_METHOD_EDITOR
            details = dict(p.source_details or {})
            zone = dict(details.get(SERVER_ZONE_KEY) or {})
            zone.update(
                {
                    "inferred": {
                        "upload_channel": UPLOAD_CHANNEL_APP,
                        "creation_method": CREATION_METHOD_EDITOR,
                    },
                    "backfilled_at": now,
                    "mkpx_at_upload": True,
                }
            )
            details[SERVER_ZONE_KEY] = zone
            p.source_details = details
        db.commit()
        logger.info("Backfilled %d posts", len(posts))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""One-time backfill: mirror external GitHub avatars into the avatar vault.

Part of the closed self-hosted model (docs/remove-external-hosting/): GitHub
OAuth historically stored avatars.githubusercontent.com URLs in
users.avatar_url. New logins are mirrored automatically by the
mirror_github_avatar task; this script converges the existing rows.

Fail-open per user: a fetch/store failure leaves the external URL in place
(it keeps rendering from GitHub's CDN) and is reported in the summary.
Idempotent: rerunning only touches rows whose avatar_url still matches.

Usage (inside the api container):

    # Dry-run first
    python /workspace/api/scripts/backfill_github_avatars.py --dry-run

    # For real
    python /workspace/api/scripts/backfill_github_avatars.py

Run separately per environment (dev and prod have separate databases).
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

sys.path.insert(0, "/workspace/api")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("backfill_github_avatars")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List affected users without fetching or writing anything",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Seconds to sleep between users (be gentle to the CDN and vault)",
    )
    args = parser.parse_args()

    from app import models
    from app.db import SessionLocal
    from app.tasks import GITHUB_AVATAR_HOST_MARKER, mirror_github_avatar_sync

    db = SessionLocal()
    try:
        users = (
            db.query(models.User)
            .filter(models.User.avatar_url.like(f"%{GITHUB_AVATAR_HOST_MARKER}%"))
            .order_by(models.User.id)
            .all()
        )
        logger.info("Found %d user(s) with external GitHub avatars", len(users))
        if args.dry_run:
            for u in users:
                logger.info(
                    "would mirror: user %s (%s) %s", u.id, u.handle, u.avatar_url
                )
            return 0

        outcomes: dict[str, int] = {}
        failures: list[tuple[int, str]] = []
        for u in users:
            try:
                result = mirror_github_avatar_sync(db, u.id)
                status = result.get("status", "unknown")
            except Exception as e:  # fail-open: keep the external URL
                db.rollback()
                status = "error"
                failures.append((u.id, str(e)))
                logger.warning("user %s failed: %s", u.id, e)
            outcomes[status] = outcomes.get(status, 0) + 1
            time.sleep(args.sleep)

        logger.info("Done: %s", outcomes)
        for uid, err in failures:
            logger.warning("FAILED user %s: %s", uid, err)
        return 1 if failures else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())

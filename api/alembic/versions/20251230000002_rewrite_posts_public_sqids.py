"""rewrite_posts_public_sqids

Revision ID: 20251230000002
Revises: 20251230000001
Create Date: 2025-12-30 00:00:02.000000

One-time migration:
- Rewrite ALL posts.public_sqid values using the current Sqids configuration
  (SQIDS_ALPHABET from environment, matching api/app/sqids_config.py).

Rationale:
- Ensure canonical URLs (/p/{public_sqid}) are always decodable with the single,
  current SQIDS_ALPHABET.
- Remove any legacy/public_sqid values that were generated with a different
  alphabet/config.

Notes:
- public_sqid is nullable; we intentionally NULL it out first to avoid transient
  UNIQUE constraint collisions during the rewrite.
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "20251230000002"
down_revision = "20251230000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    import os
    from sqids import Sqids

    # Must match api/app/sqids_config.py behavior
    sqids_alphabet = os.getenv(
        "SQIDS_ALPHABET",
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    )
    sqids = Sqids(alphabet=sqids_alphabet, min_length=0)

    connection = op.get_bind()

    # Phase 1: clear values to avoid UNIQUE collisions during rewrite
    connection.execute(text("UPDATE posts SET public_sqid = NULL"))

    # Phase 2: rewrite deterministically from integer id
    result = connection.execute(text("SELECT id FROM posts ORDER BY id ASC"))
    for (post_id,) in result.fetchall():
        new_sqid = sqids.encode([int(post_id)])
        connection.execute(
            text("UPDATE posts SET public_sqid = :sqid WHERE id = :id"),
            {"sqid": new_sqid, "id": int(post_id)},
        )


def downgrade() -> None:
    # Downgrade is intentionally a no-op:
    # rewriting back would require knowing the prior alphabet/config.
    pass

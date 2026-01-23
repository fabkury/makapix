"""replace has_transparency with transparency-metadata fields

Revision ID: 20251214000000
Revises: 20251212000001
Create Date: 2025-12-14 00:00:00.000000

Makapix Club transparency-metadata:
- uses_transparency: any pixel anywhere has alpha != 255
- uses_alpha: any pixel anywhere has alpha not in {0, 255}

Per product decision:
- Existing rows are known to have no transparency/alpha -> backfill False.
- Breaking change: drop posts.has_transparency.
"""

from __future__ import annotations

from alembic import op

revision = "20251214000000"
down_revision = "20251212000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns with safe defaults.
    op.execute(
        "ALTER TABLE posts ADD COLUMN IF NOT EXISTS uses_transparency BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE posts ADD COLUMN IF NOT EXISTS uses_alpha BOOLEAN NOT NULL DEFAULT FALSE"
    )

    # Existing images are known to not use transparency or alpha.
    op.execute("UPDATE posts SET uses_transparency = FALSE, uses_alpha = FALSE")

    # Drop legacy field.
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS has_transparency")


def downgrade() -> None:
    # Restore legacy field (best-effort mapping from uses_transparency).
    op.execute(
        "ALTER TABLE posts ADD COLUMN IF NOT EXISTS has_transparency BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute("UPDATE posts SET has_transparency = COALESCE(uses_transparency, FALSE)")

    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS uses_alpha")
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS uses_transparency")

"""drop file_kb and use file_bytes only

Revision ID: 20251212000001
Revises: 20251212000000
Create Date: 2025-12-12 00:00:01.000000

Makapix server now treats artwork file sizes as raw bytes only.
This migration removes posts.file_kb and updates the artwork-required CHECK
constraint accordingly.
"""

from __future__ import annotations

from alembic import op

revision = "20251212000001"
down_revision = "20251212000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old constraint if present (it referenced file_kb).
    op.execute(
        "ALTER TABLE posts DROP CONSTRAINT IF EXISTS ck_posts_artwork_fields_required"
    )

    # Drop the column (Postgres supports IF EXISTS).
    op.execute("ALTER TABLE posts DROP COLUMN IF EXISTS file_kb")

    # Recreate constraint ensuring artwork posts have required fields.
    op.create_check_constraint(
        "ck_posts_artwork_fields_required",
        "posts",
        """
        kind != 'artwork'
        OR (
          art_url IS NOT NULL
          AND canvas IS NOT NULL
          AND width IS NOT NULL
          AND height IS NOT NULL
          AND file_bytes IS NOT NULL
        )
        """,
    )


def downgrade() -> None:
    # Best-effort: restore column without reintroducing KiB conversions.
    op.execute("ALTER TABLE posts ADD COLUMN IF NOT EXISTS file_kb INTEGER")

    op.execute(
        "ALTER TABLE posts DROP CONSTRAINT IF EXISTS ck_posts_artwork_fields_required"
    )
    op.create_check_constraint(
        "ck_posts_artwork_fields_required",
        "posts",
        """
        kind != 'artwork'
        OR (
          art_url IS NOT NULL
          AND canvas IS NOT NULL
          AND width IS NOT NULL
          AND height IS NOT NULL
          AND file_bytes IS NOT NULL
        )
        """,
    )

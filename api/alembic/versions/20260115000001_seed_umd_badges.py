"""Seed UMD badges (roots, master).

Revision ID: 20260115000001
Revises: 20260115000000
Create Date: 2026-01-15

This migration adds the 'roots' and 'master' badges for the User Management Dashboard.
"""

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260115000001"
down_revision: str | None = "20260115000000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Seed roots and master badges."""
    op.execute("""
        INSERT INTO badge_definitions (badge, label, description, icon_url_64, icon_url_16, is_tag_badge)
        VALUES
            ('roots', 'Roots', 'Original community member', '/badges/roots_64.png', '/badges/roots_16.png', true),
            ('master', 'Master', 'Recognized master artist', '/badges/master_64.png', '/badges/master_16.png', true)
        ON CONFLICT (badge) DO NOTHING
    """)


def downgrade() -> None:
    """Remove roots and master badges."""
    op.execute("""
        DELETE FROM badge_definitions WHERE badge IN ('roots', 'master')
    """)

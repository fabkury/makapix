"""clear view tracking data

Revision ID: 20251125181822
Revises: 20251126000000
Create Date: 2025-11-25 18:18:22.000000

This migration clears all existing view tracking data to ensure clean state
before implementing author view exclusion and authenticated/unauthenticated filtering.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20251125181822"
down_revision = "20251126000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clear all view tracking data
    # This is a one-time cleanup before implementing author exclusion
    op.execute("TRUNCATE TABLE view_events CASCADE")
    op.execute("TRUNCATE TABLE post_stats_daily CASCADE")
    op.execute("TRUNCATE TABLE post_stats_cache CASCADE")


def downgrade() -> None:
    # Cannot restore deleted data, so downgrade is a no-op
    pass


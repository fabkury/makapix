"""Remove canvas column from posts table

Revision ID: 20260130000000
Revises: 20260128000000
Create Date: 2026-01-30 00:00:00.000000

The canvas column is deprecated. The width and height integer columns
are the source of truth and are always populated.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260130000000"
down_revision = "20260128000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("posts", "canvas")


def downgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("canvas", sa.String(50), nullable=True),
    )

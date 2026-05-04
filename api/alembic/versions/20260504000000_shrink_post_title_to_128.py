"""Shrink posts.title from VARCHAR(200) to VARCHAR(128)

Revision ID: 20260504000000
Revises: 20260429000000
Create Date: 2026-05-04 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260504000000"
down_revision = "20260429000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE posts SET title = LEFT(title, 128) WHERE LENGTH(title) > 128")
    op.alter_column(
        "posts",
        "title",
        existing_type=sa.String(length=200),
        type_=sa.String(length=128),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "posts",
        "title",
        existing_type=sa.String(length=128),
        type_=sa.String(length=200),
        existing_nullable=False,
    )

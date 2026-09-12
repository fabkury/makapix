"""posts.promoted_at — when a moderator promoted the post

Revision ID: e5f6a7b8c9d0
Revises: c3d4e5f6a7b8
Create Date: 2026-09-12

Adds posts.promoted_at (timestamptz, nullable) so promoted surfaces can sort by
promotion time instead of creation time (docs/promoted-feed-order/). Existing
promoted rows are grandfathered: promoted_at := created_at, so the feed order is
unchanged at deploy and only diverges as new promotions happen.

Hand-written (not autogenerate) to avoid dragging along unrelated, pre-existing
model/DB drift — same precedent as revision b3d9a1c40f21.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Grandfather: the current (created_at) order becomes the promoted-time order.
    op.execute(
        sa.text(
            "UPDATE posts SET promoted_at = created_at "
            "WHERE promoted = TRUE AND promoted_at IS NULL"
        )
    )
    op.create_index(
        "ix_posts_promoted_promoted_at",
        "posts",
        ["promoted", sa.text("promoted_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_posts_promoted_promoted_at", table_name="posts")
    op.drop_column("posts", "promoted_at")

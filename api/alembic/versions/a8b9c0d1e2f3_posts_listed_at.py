"""posts.listed_at + posts.pending_listing — feed position for bumps

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-10-02

Adds posts.listed_at (timestamptz, NOT NULL, default now()): the time a post
was last placed at the top of the date-sorted feeds (docs/feed-bump/ D1).
Backfilled to created_at, so every feed is byte-identical at deploy and only
diverges as bumps happen.

Adds posts.pending_listing (varchar, nullable): 'first' | 'replace', the
bump owed when a moderator approves the post (D11/D12). Posts pending at
deploy that were never approved get 'first' (D13); a revoked post (has an
approve_public_visibility audit entry) gets nothing.

Hand-written (not autogenerate) to avoid dragging along unrelated, pre-existing
model/DB drift — same precedent as revision b3d9a1c40f21.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "posts",
        sa.Column("listed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(sa.text("UPDATE posts SET listed_at = created_at"))
    op.alter_column(
        "posts",
        "listed_at",
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.create_index(
        "ix_posts_listed_at",
        "posts",
        [sa.text("listed_at DESC"), sa.text("id DESC")],
    )

    op.add_column(
        "posts",
        sa.Column("pending_listing", sa.String(8), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE posts SET pending_listing = 'first' "
            "WHERE public_visibility = FALSE AND deleted_by_user = FALSE "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM audit_logs a"
            "  WHERE a.action = 'approve_public_visibility'"
            "  AND a.target_type = 'post'"
            "  AND a.target_id = posts.id::text"
            ")"
        )
    )


def downgrade() -> None:
    op.drop_column("posts", "pending_listing")
    op.drop_index("ix_posts_listed_at", table_name="posts")
    op.drop_column("posts", "listed_at")

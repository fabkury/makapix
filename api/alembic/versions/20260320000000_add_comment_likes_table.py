"""Add comment_likes table

Revision ID: 20260320000000
Revises: 20260206000000
Create Date: 2026-03-20 00:00:00.000000

"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260320000000"
down_revision = "20260206000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "comment_likes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("comment_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["comment_id"], ["comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "comment_id", "user_id", name="uq_comment_likes_comment_user"
        ),
    )
    op.create_index("ix_comment_likes_comment_id", "comment_likes", ["comment_id"])
    op.create_index("ix_comment_likes_user_id", "comment_likes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_comment_likes_user_id", table_name="comment_likes")
    op.drop_index("ix_comment_likes_comment_id", table_name="comment_likes")
    op.drop_table("comment_likes")

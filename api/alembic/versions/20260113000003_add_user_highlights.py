"""Add user_highlights table

Revision ID: 20260113000003
Revises: 20260113000002
Create Date: 2026-01-13

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260113000003"
down_revision: str | None = "20260113000002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create user_highlights table for storing user's featured posts."""
    op.create_table(
        "user_highlights",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_highlights_user_id"
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["posts.id"],
            name="fk_user_highlights_post_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("user_id", "post_id", name="uq_user_highlights_user_post"),
        sa.UniqueConstraint(
            "user_id", "position", name="uq_user_highlights_user_position"
        ),
    )
    op.create_index("ix_user_highlights_user_id", "user_highlights", ["user_id"])
    op.create_index("ix_user_highlights_post_id", "user_highlights", ["post_id"])
    op.create_index(
        "ix_user_highlights_user_position",
        "user_highlights",
        ["user_id", "position"],
    )


def downgrade() -> None:
    """Drop user_highlights table."""
    op.drop_index("ix_user_highlights_user_position", "user_highlights")
    op.drop_index("ix_user_highlights_post_id", "user_highlights")
    op.drop_index("ix_user_highlights_user_id", "user_highlights")
    op.drop_table("user_highlights")

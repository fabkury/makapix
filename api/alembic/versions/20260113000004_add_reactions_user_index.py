"""Add reactions user index for reacted posts query

Revision ID: 20260113000004
Revises: 20260113000003
Create Date: 2026-01-13

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260113000004"
down_revision: str | None = "20260113000003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add index for efficient 'posts user reacted to' queries."""
    op.create_index(
        "ix_reactions_user_created",
        "reactions",
        ["user_id", "created_at"],
        postgresql_ops={"created_at": "DESC"},
    )


def downgrade() -> None:
    """Remove reactions user index."""
    op.drop_index("ix_reactions_user_created", "reactions")

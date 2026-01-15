"""Add violations table for UMD.

Revision ID: 20260115000000
Revises: f5003d17e4bb
Create Date: 2026-01-15

This migration creates the violations table for tracking user violations
in the User Management Dashboard (UMD).
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260115000000"
down_revision: str | None = "f5003d17e4bb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "violations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("moderator_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["moderator_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_violations_id", "violations", ["id"])
    op.create_index("ix_violations_user_id", "violations", ["user_id"])
    op.create_index("ix_violations_moderator_id", "violations", ["moderator_id"])
    op.create_index("ix_violations_created_at", "violations", ["created_at"])
    op.create_index(
        "ix_violations_user_created",
        "violations",
        ["user_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_violations_user_created", table_name="violations")
    op.drop_index("ix_violations_created_at", table_name="violations")
    op.drop_index("ix_violations_moderator_id", table_name="violations")
    op.drop_index("ix_violations_user_id", table_name="violations")
    op.drop_index("ix_violations_id", table_name="violations")
    op.drop_table("violations")

"""Add welcome_completed field to users table.

Revision ID: 20251217000000
Revises: 20251214000000_replace_has_transparency_with_transparency_metadata
Create Date: 2024-12-17
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251217000000"
down_revision = "20251214000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add welcome_completed column with default False
    op.add_column(
        "users",
        sa.Column(
            "welcome_completed", sa.Boolean(), nullable=False, server_default="false"
        ),
    )

    # Add index for filtering by welcome_completed
    op.create_index(
        "ix_users_welcome_completed",
        "users",
        ["welcome_completed"],
        unique=False,
    )

    # Mark all existing users as having completed welcome (since they existed before this feature)
    op.execute("UPDATE users SET welcome_completed = true")


def downgrade() -> None:
    op.drop_index("ix_users_welcome_completed", table_name="users")
    op.drop_column("users", "welcome_completed")

"""Add system notification support to social_notifications.

Make post_id nullable and add actor_avatar_url for system notifications.

Revision ID: 20260115000002
Revises: 20260115000001
Create Date: 2026-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260115000002"
down_revision = "20260115000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make post_id nullable to support system notifications without artwork
    op.alter_column(
        "social_notifications",
        "post_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # Add actor_avatar_url for displaying actor's profile photo in system notifications
    op.add_column(
        "social_notifications",
        sa.Column("actor_avatar_url", sa.String(1000), nullable=True),
    )


def downgrade() -> None:
    # Remove actor_avatar_url column
    op.drop_column("social_notifications", "actor_avatar_url")

    # Make post_id NOT NULL again (will fail if there are NULL values)
    op.alter_column(
        "social_notifications",
        "post_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

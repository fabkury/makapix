"""add_social_notifications

Revision ID: 20251231000000
Revises: 20251230000002
Create Date: 2025-12-31 00:00:00.000000

Adds the social_notifications table for tracking user notifications
when their artwork receives reactions or comments.

Note: Blog post notifications are intentionally excluded (feature postponed).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "20251231000000"
down_revision = "20251230000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create social_notifications table
    op.create_table(
        "social_notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),

        # Type: 'reaction' or 'comment'
        sa.Column("notification_type", sa.String(50), nullable=False),

        # Target content (artwork only)
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),

        # Actor (who triggered the notification)
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_handle", sa.String(50), nullable=True),  # Denormalized for display

        # Notification details
        sa.Column("emoji", sa.String(20), nullable=True),  # For reaction notifications
        sa.Column("comment_id", UUID(as_uuid=True), nullable=True),  # For comment notifications
        sa.Column("comment_preview", sa.Text(), nullable=True),  # First 100 chars of comment

        # Content metadata (denormalized for display)
        sa.Column("content_title", sa.String(200), nullable=True),
        sa.Column("content_sqid", sa.String(50), nullable=True),  # For URL generation

        # Status
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),

        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # Create indexes for efficient querying

    # Primary access pattern: list notifications for a user, newest first
    op.create_index(
        "ix_social_notifications_user_created",
        "social_notifications",
        ["user_id", sa.text("created_at DESC")]
    )

    # Unread count query optimization (partial index)
    op.create_index(
        "ix_social_notifications_user_unread",
        "social_notifications",
        ["user_id", "created_at"],
        postgresql_where=sa.text("is_read = false")
    )

    # Lookup notifications for a specific post (for cascade delete efficiency)
    op.create_index(
        "ix_social_notifications_post",
        "social_notifications",
        ["post_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_social_notifications_post", table_name="social_notifications")
    op.drop_index("ix_social_notifications_user_unread", table_name="social_notifications")
    op.drop_index("ix_social_notifications_user_created", table_name="social_notifications")
    op.drop_table("social_notifications")

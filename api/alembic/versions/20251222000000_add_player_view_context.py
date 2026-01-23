"""Add player view context fields to view_events

Revision ID: 20251222000000
Revises: 20251217000000
Create Date: 2025-12-22 00:00:00.000000

This migration adds player-specific context fields to view_events table:
- player_id: Reference to the player that submitted the view
- local_datetime: Player's local datetime as ISO string
- local_timezone: Player's IANA timezone identifier
- play_order: Play order mode (0=server, 1=created_at, 2=random)
- channel: Channel being played (all, promoted, user, by_user, artwork, hashtag)
- channel_context: Context for channel (user_sqid or hashtag)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20251222000000"
down_revision = "20251217000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add player_id column with foreign key to players table
    op.add_column(
        "view_events",
        sa.Column(
            "player_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("players.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # Add player context columns
    op.add_column(
        "view_events",
        sa.Column("local_datetime", sa.String(50), nullable=True),
    )

    op.add_column(
        "view_events",
        sa.Column("local_timezone", sa.String(50), nullable=True),
    )

    op.add_column(
        "view_events",
        sa.Column("play_order", sa.Integer(), nullable=True),
    )

    op.add_column(
        "view_events",
        sa.Column("channel", sa.String(20), nullable=True),
    )

    op.add_column(
        "view_events",
        sa.Column("channel_context", sa.String(100), nullable=True),
    )

    # Create indexes for new columns
    op.create_index("ix_view_events_player_id", "view_events", ["player_id"])
    op.create_index("ix_view_events_channel", "view_events", ["channel"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_view_events_channel", table_name="view_events")
    op.drop_index("ix_view_events_player_id", table_name="view_events")

    # Drop columns
    op.drop_column("view_events", "channel_context")
    op.drop_column("view_events", "channel")
    op.drop_column("view_events", "play_order")
    op.drop_column("view_events", "local_timezone")
    op.drop_column("view_events", "local_datetime")
    op.drop_column("view_events", "player_id")

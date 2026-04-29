"""Add player capabilities, reported state, and command ack columns

Revision ID: 20260429000000
Revises: 20260320000000
Create Date: 2026-04-29 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260429000000"
down_revision = "20260320000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column("capabilities", JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "players",
        sa.Column(
            "capabilities_updated_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column("players", sa.Column("is_paused", sa.Boolean(), nullable=True))
    op.add_column("players", sa.Column("brightness", sa.SmallInteger(), nullable=True))
    op.add_column("players", sa.Column("rotation", sa.SmallInteger(), nullable=True))
    op.add_column("players", sa.Column("mirror", sa.String(length=16), nullable=True))
    op.add_column(
        "players",
        sa.Column("state_updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "player_command_logs",
        sa.Column("ack_status", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "player_command_logs",
        sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("player_command_logs", "acked_at")
    op.drop_column("player_command_logs", "ack_status")
    op.drop_column("players", "state_updated_at")
    op.drop_column("players", "mirror")
    op.drop_column("players", "rotation")
    op.drop_column("players", "brightness")
    op.drop_column("players", "is_paused")
    op.drop_column("players", "capabilities_updated_at")
    op.drop_column("players", "capabilities")

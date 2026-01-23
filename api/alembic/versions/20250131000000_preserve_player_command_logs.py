"""preserve player command logs

Revision ID: 20250131000000
Revises: 20250130000000
Create Date: 2025-01-31 00:00:00.000000

This migration changes player_command_logs.player_id to:
- Be nullable (allows preserving logs when player is deleted)
- Use SET NULL on delete instead of CASCADE
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20250131000000"
down_revision = "20250130000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop existing foreign key constraint
    op.drop_constraint(
        "player_command_logs_player_id_fkey", "player_command_logs", type_="foreignkey"
    )

    # Make player_id nullable
    op.alter_column(
        "player_command_logs",
        "player_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )

    # Re-create foreign key with SET NULL on delete
    op.create_foreign_key(
        "player_command_logs_player_id_fkey",
        "player_command_logs",
        "players",
        ["player_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop the SET NULL foreign key
    op.drop_constraint(
        "player_command_logs_player_id_fkey", "player_command_logs", type_="foreignkey"
    )

    # Delete orphaned logs (where player_id is null)
    op.execute("DELETE FROM player_command_logs WHERE player_id IS NULL")

    # Make player_id non-nullable again
    op.alter_column(
        "player_command_logs",
        "player_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )

    # Re-create foreign key with CASCADE on delete
    op.create_foreign_key(
        "player_command_logs_player_id_fkey",
        "player_command_logs",
        "players",
        ["player_id"],
        ["id"],
        ondelete="CASCADE",
    )

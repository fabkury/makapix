"""add players migration

Revision ID: 20250129000000
Revises: 20251128000000
Create Date: 2025-01-29 00:00:00.000000

This migration:
- Drops the unused devices table
- Creates players table for player registration and control
- Creates player_command_logs table for command auditing
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20250129000000"
down_revision = "20251128000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop devices table (unused/empty)
    op.drop_table("devices")
    
    # Create players table
    op.create_table(
        "players",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("player_key", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("device_model", sa.String(100), nullable=True),
        sa.Column("firmware_version", sa.String(50), nullable=True),
        sa.Column("registration_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("registration_code", sa.String(6), nullable=True, unique=True),
        sa.Column("registration_code_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connection_status", sa.String(20), nullable=False, server_default="offline"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_post_id", sa.Integer(), nullable=True),
        sa.Column("cert_serial_number", sa.String(100), nullable=True, unique=True),
        sa.Column("cert_issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cert_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="players_owner_id_fkey"),
        sa.ForeignKeyConstraint(["current_post_id"], ["posts.id"], name="players_current_post_id_fkey"),
    )
    
    # Create indexes
    op.create_index("ix_players_player_key", "players", ["player_key"])
    op.create_index("ix_players_owner_id", "players", ["owner_id"])
    op.create_index("ix_players_registration_code", "players", ["registration_code"])
    op.create_index("ix_players_cert_serial_number", "players", ["cert_serial_number"])
    
    # Create player_command_logs table
    op.create_table(
        "player_command_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("command_type", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], name="player_command_logs_player_id_fkey", ondelete="CASCADE"),
    )
    
    # Create indexes for command logs
    op.create_index("ix_player_command_logs_player_id", "player_command_logs", ["player_id"])
    op.create_index("ix_player_command_logs_created_at", "player_command_logs", ["created_at"])


def downgrade() -> None:
    # Drop player_command_logs table
    op.drop_table("player_command_logs")
    
    # Drop players table
    op.drop_table("players")
    
    # Recreate devices table (basic structure)
    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("cert_serial_number", sa.String(100), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="devices_user_id_fkey"),
    )
    op.create_index("ix_devices_user_id", "devices", ["user_id"])
    op.create_index("ix_devices_cert_serial_number", "devices", ["cert_serial_number"])


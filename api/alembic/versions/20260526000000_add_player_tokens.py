"""Add player_tokens for HTTPS player authentication

Revision ID: 20260526000000
Revises: 20260504000000
Create Date: 2026-05-26 00:00:00.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260526000000"
down_revision = "20260504000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_player_tokens_id"), "player_tokens", ["id"], unique=False)
    op.create_index(
        op.f("ix_player_tokens_player_id"),
        "player_tokens",
        ["player_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_player_tokens_token_hash"),
        "player_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_player_tokens_revoked"),
        "player_tokens",
        ["revoked"],
        unique=False,
    )
    op.create_index(
        op.f("ix_player_tokens_created_at"),
        "player_tokens",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_player_tokens_created_at"), table_name="player_tokens")
    op.drop_index(op.f("ix_player_tokens_revoked"), table_name="player_tokens")
    op.drop_index(op.f("ix_player_tokens_token_hash"), table_name="player_tokens")
    op.drop_index(op.f("ix_player_tokens_player_id"), table_name="player_tokens")
    op.drop_index(op.f("ix_player_tokens_id"), table_name="player_tokens")
    op.drop_table("player_tokens")

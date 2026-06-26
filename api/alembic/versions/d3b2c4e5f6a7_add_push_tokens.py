"""add push_tokens table + users.notification_prefs

Revision ID: d3b2c4e5f6a7
Revises: c2a1b3d4e5f6
Create Date: 2026-06-26

Mobile push targets for native app clients (change-request §4). Distinct from
the physical-player `devices`/`players` tables.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d3b2c4e5f6a7"
down_revision = "c2a1b3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "notification_prefs",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.create_table(
        "push_tokens",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(length=8), nullable=False),
        sa.Column("token", sa.String(length=512), nullable=False),
        sa.Column("device_label", sa.String(length=120), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_push_tokens_id", "push_tokens", ["id"])
    op.create_index("ix_push_tokens_user_id", "push_tokens", ["user_id"])
    op.create_index("ix_push_tokens_token", "push_tokens", ["token"], unique=True)
    op.create_index("ix_push_tokens_revoked", "push_tokens", ["revoked"])


def downgrade() -> None:
    op.drop_table("push_tokens")
    op.drop_column("users", "notification_prefs")

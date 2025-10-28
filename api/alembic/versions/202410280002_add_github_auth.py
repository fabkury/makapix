"""add github auth fields and refresh tokens

Revision ID: 202410280002
Revises: 202410280001
Create Date: 2025-10-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202410280002"
down_revision = "202410280001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add GitHub auth fields to users table
    op.add_column("users", sa.Column("github_user_id", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("github_username", sa.String(100), nullable=True))
    
    # Create indexes for GitHub fields
    op.create_index("ix_users_github_user_id", "users", ["github_user_id"], unique=True)
    op.create_index("ix_users_github_username", "users", ["github_username"])
    
    # Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"])
    op.create_index("ix_refresh_tokens_revoked", "refresh_tokens", ["revoked"])


def downgrade() -> None:
    # Drop refresh_tokens table
    op.drop_table("refresh_tokens")
    
    # Remove GitHub fields from users table
    op.drop_index("ix_users_github_username", table_name="users")
    op.drop_index("ix_users_github_user_id", table_name="users")
    op.drop_column("users", "github_username")
    op.drop_column("users", "github_user_id")

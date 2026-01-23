"""add public visibility and auto approval fields

Revision ID: 20251125000000
Revises: 20251124000000
Create Date: 2025-11-25 00:00:00.000000

This migration adds:
- public_visibility field to posts table (controls visibility in Recent Artworks, search, etc.)
- auto_public_approval field to users table (privilege for auto-approving public visibility)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20251125000000"
down_revision = "20251124000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add public_visibility to posts table
    # Default is false - new posts require moderator approval for public visibility
    op.add_column(
        "posts",
        sa.Column(
            "public_visibility", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.create_index("ix_posts_public_visibility", "posts", ["public_visibility"])

    # Add composite index for efficient Recent Artworks queries
    op.create_index(
        "ix_posts_public_visibility_created",
        "posts",
        ["public_visibility", sa.text("created_at DESC")],
    )

    # Add auto_public_approval to users table
    # Default is false - users need moderator to grant this privilege
    op.add_column(
        "users",
        sa.Column(
            "auto_public_approval", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.create_index("ix_users_auto_public_approval", "users", ["auto_public_approval"])


def downgrade() -> None:
    # Remove indexes first
    op.drop_index("ix_users_auto_public_approval", table_name="users")
    op.drop_index("ix_posts_public_visibility_created", table_name="posts")
    op.drop_index("ix_posts_public_visibility", table_name="posts")

    # Remove columns
    op.drop_column("users", "auto_public_approval")
    op.drop_column("posts", "public_visibility")

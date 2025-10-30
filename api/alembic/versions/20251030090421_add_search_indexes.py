"""add search indexes (trigram/GIN)

Revision ID: 20251030090421
Revises: 20251030050624
Create Date: 2025-10-30 09:04:21.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20251030090421"
down_revision = "20251030050624"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pg_trgm extension for trigram similarity search
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    
    # Create trigram indexes on users table for handle and display_name
    op.create_index(
        "ix_users_handle_trgm",
        "users",
        ["handle"],
        postgresql_using="gin",
        postgresql_ops={"handle": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_users_display_name_trgm",
        "users",
        ["display_name"],
        postgresql_using="gin",
        postgresql_ops={"display_name": "gin_trgm_ops"},
    )
    
    # Create GIN trigram indexes on posts table for title and description
    op.create_index(
        "ix_posts_title_trgm",
        "posts",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_posts_description_trgm",
        "posts",
        ["description"],
        postgresql_using="gin",
        postgresql_ops={"description": "gin_trgm_ops"},
    )


def downgrade() -> None:
    # Drop trigram indexes
    op.drop_index("ix_posts_description_trgm", table_name="posts")
    op.drop_index("ix_posts_title_trgm", table_name="posts")
    op.drop_index("ix_users_display_name_trgm", table_name="users")
    op.drop_index("ix_users_handle_trgm", table_name="users")
    
    # Note: We don't drop the pg_trgm extension as it might be used elsewhere


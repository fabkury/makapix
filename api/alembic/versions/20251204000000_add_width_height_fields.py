"""add width and height fields to posts

Revision ID: 20251204000000
Revises: 20251202000000
Create Date: 2025-12-04 00:00:00.000000

This migration adds width and height integer fields to the posts table and migrates
existing canvas string data (e.g., "64x64") into these new fields.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251204000000"
down_revision = "20251202000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add width and height columns (nullable initially)
    op.add_column("posts", sa.Column("width", sa.Integer(), nullable=True))
    op.add_column("posts", sa.Column("height", sa.Integer(), nullable=True))
    
    # Migrate existing canvas data to width and height
    # Parse canvas strings like "64x64" into width and height integers
    op.execute("""
        UPDATE posts
        SET 
            width = CAST(SPLIT_PART(canvas, 'x', 1) AS INTEGER),
            height = CAST(SPLIT_PART(canvas, 'x', 2) AS INTEGER)
        WHERE canvas IS NOT NULL AND canvas ~ '^[0-9]+x[0-9]+$'
    """)
    
    # Make width and height NOT NULL after data migration
    op.alter_column("posts", "width", nullable=False)
    op.alter_column("posts", "height", nullable=False)
    
    # Add indexes for potential filtering by dimensions
    op.create_index("ix_posts_width", "posts", ["width"])
    op.create_index("ix_posts_height", "posts", ["height"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_posts_height", table_name="posts")
    op.drop_index("ix_posts_width", table_name="posts")
    
    # Drop columns
    op.drop_column("posts", "height")
    op.drop_column("posts", "width")

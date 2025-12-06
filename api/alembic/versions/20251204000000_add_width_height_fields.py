"""add width, height, and related fields to posts

Revision ID: 20251204000000
Revises: 20251202000000
Create Date: 2025-12-04 00:00:00.000000

This migration adds width, height, file_bytes, frame_count, min_frame_duration_ms,
and has_transparency fields to the posts table and migrates existing data.
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
    
    # Add file_bytes column (nullable initially)
    op.add_column("posts", sa.Column("file_bytes", sa.Integer(), nullable=True))
    
    # Add frame_count column with default value
    op.add_column("posts", sa.Column("frame_count", sa.Integer(), nullable=False, server_default="1"))
    
    # Add min_frame_duration_ms column (nullable, for animated images)
    op.add_column("posts", sa.Column("min_frame_duration_ms", sa.Integer(), nullable=True))
    
    # Add has_transparency column with default value
    op.add_column("posts", sa.Column("has_transparency", sa.Boolean(), nullable=False, server_default="false"))
    
    # Migrate existing canvas data to width and height
    # Parse canvas strings like "64x64" into width and height integers
    op.execute("""
        UPDATE posts
        SET 
            width = CAST(SPLIT_PART(canvas, 'x', 1) AS INTEGER),
            height = CAST(SPLIT_PART(canvas, 'x', 2) AS INTEGER)
        WHERE canvas IS NOT NULL AND canvas ~ '^[0-9]+x[0-9]+$'
    """)
    
    # Migrate file_bytes from file_kb (approximate, since we only have KB)
    op.execute("""
        UPDATE posts
        SET file_bytes = file_kb * 1024
        WHERE file_bytes IS NULL
    """)
    
    # Make width and height NOT NULL after data migration
    op.alter_column("posts", "width", nullable=False)
    op.alter_column("posts", "height", nullable=False)
    op.alter_column("posts", "file_bytes", nullable=False)
    
    # Add indexes for potential filtering by dimensions
    op.create_index("ix_posts_width", "posts", ["width"])
    op.create_index("ix_posts_height", "posts", ["height"])


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_posts_height", table_name="posts")
    op.drop_index("ix_posts_width", table_name="posts")
    
    # Drop columns
    op.drop_column("posts", "has_transparency")
    op.drop_column("posts", "min_frame_duration_ms")
    op.drop_column("posts", "frame_count")
    op.drop_column("posts", "file_bytes")
    op.drop_column("posts", "height")
    op.drop_column("posts", "width")

"""add artwork metadata fields

Revision ID: 20251204000000
Revises: 20251202000000
Create Date: 2025-12-04 00:00:00.000000

This migration adds new metadata fields to the posts table:
- file_bytes: Exact file size in bytes
- frame_count: Number of animation frames (default 1 for static images)
- min_frame_duration_ms: Minimum non-zero frame duration in milliseconds (NULL for static)
- has_transparency: Whether image has alpha channel or transparent pixels
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20251204000000"
down_revision = "20251202000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add file_bytes column - compute from existing file_kb * 1024 as approximation
    op.add_column(
        "posts",
        sa.Column("file_bytes", sa.Integer(), nullable=True),
    )
    
    # Backfill file_bytes from existing file_kb (approximate)
    op.execute("UPDATE posts SET file_bytes = file_kb * 1024")
    
    # Make file_bytes NOT NULL after backfill
    op.alter_column("posts", "file_bytes", nullable=False)
    
    # Add frame_count column with default value of 1 (static images)
    op.add_column(
        "posts",
        sa.Column("frame_count", sa.Integer(), nullable=False, server_default="1"),
    )
    
    # Add min_frame_duration_ms column (nullable for static images)
    op.add_column(
        "posts",
        sa.Column("min_frame_duration_ms", sa.Integer(), nullable=True),
    )
    
    # Add has_transparency column with default value of False
    op.add_column(
        "posts",
        sa.Column("has_transparency", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    # Drop the new columns in reverse order
    op.drop_column("posts", "has_transparency")
    op.drop_column("posts", "min_frame_duration_ms")
    op.drop_column("posts", "frame_count")
    op.drop_column("posts", "file_bytes")

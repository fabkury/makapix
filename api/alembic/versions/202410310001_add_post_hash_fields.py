"""add expected_hash and mime_type to posts for hash mismatch detection

Revision ID: 202410310001
Revises: 202410300001
Create Date: 2025-10-31 00:00:01.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "202410310001"
down_revision = "202410300001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add expected_hash and mime_type to posts table for hash mismatch detection
    op.add_column("posts", sa.Column("expected_hash", sa.String(64), nullable=True))
    op.add_column("posts", sa.Column("mime_type", sa.String(50), nullable=True))
    
    # Add index for hash lookups
    op.create_index("ix_posts_expected_hash", "posts", ["expected_hash"])
    
    # Add composite index for non-conformant posts by creation date
    op.create_index("ix_posts_non_conformant_created", "posts", ["non_conformant", sa.text("created_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_posts_non_conformant_created", table_name="posts")
    op.drop_index("ix_posts_expected_hash", table_name="posts")
    op.drop_column("posts", "mime_type")
    op.drop_column("posts", "expected_hash")


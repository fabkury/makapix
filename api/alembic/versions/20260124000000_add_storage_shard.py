"""Add storage_shard column to posts table.

This column stores the pre-computed folder path (e.g., "8c/4f/2a") derived
from SHA-256(storage_key). This eliminates redundant hash computations on
every file access.

Revision ID: 20260124000000
Revises: 20260119000001
Create Date: 2026-01-24

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260124000000"
down_revision = "20260119000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add storage_shard column and backfill existing artwork posts."""
    # Add nullable column
    op.add_column("posts", sa.Column("storage_shard", sa.String(8), nullable=True))

    # Backfill existing artwork posts using PostgreSQL SHA-256
    # The pgcrypto extension provides digest() for SHA-256 hashing
    op.execute("""
        UPDATE posts
        SET storage_shard =
            SUBSTR(encode(digest(storage_key::text, 'sha256'), 'hex'), 1, 2) || '/' ||
            SUBSTR(encode(digest(storage_key::text, 'sha256'), 'hex'), 3, 2) || '/' ||
            SUBSTR(encode(digest(storage_key::text, 'sha256'), 'hex'), 5, 2)
        WHERE kind = 'artwork' AND storage_key IS NOT NULL
    """)


def downgrade() -> None:
    """Remove storage_shard column from posts table."""
    op.drop_column("posts", "storage_shard")

"""Add base and size fields to posts.

These computed fields store:
- base: min(width, height) - the shorter dimension
- size: max(width, height) - the longer dimension

Both fields are indexed for fast queries.

Revision ID: 20260118000000
Revises: 20260115000002
Create Date: 2026-01-18

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260118000000"
down_revision = "20260115000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add base column (nullable, indexed)
    op.add_column("posts", sa.Column("base", sa.Integer(), nullable=True))
    op.create_index("ix_posts_base", "posts", ["base"])

    # Add size column (nullable, indexed)
    op.add_column("posts", sa.Column("size", sa.Integer(), nullable=True))
    op.create_index("ix_posts_size", "posts", ["size"])

    # Populate base and size from existing width/height where available
    op.execute("""
        UPDATE posts
        SET
            base = LEAST(width, height),
            size = GREATEST(width, height)
        WHERE width IS NOT NULL AND height IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_index("ix_posts_size", table_name="posts")
    op.drop_column("posts", "size")
    op.drop_index("ix_posts_base", table_name="posts")
    op.drop_column("posts", "base")

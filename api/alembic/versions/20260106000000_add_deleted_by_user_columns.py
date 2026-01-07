"""Add deleted_by_user columns for soft delete with cleanup.

Revision ID: 20260106000000
Revises: 20260103000000
Create Date: 2026-01-06

This migration:
1. Adds deleted_by_user (boolean) and deleted_by_user_date (datetime) columns
2. Drops the existing uq_posts_hash unique constraint
3. Creates a partial unique index on hash for non-deleted posts only
4. Adds indexes for efficient cleanup queries
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260106000000"
down_revision: str | None = "20260103000000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add new columns
    op.add_column(
        "posts",
        sa.Column("deleted_by_user", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "posts",
        sa.Column("deleted_by_user_date", sa.DateTime(timezone=True), nullable=True),
    )

    # 2. Drop old unique constraint on hash
    # The constraint may exist as either a constraint or an index
    op.execute("ALTER TABLE posts DROP CONSTRAINT IF EXISTS uq_posts_hash")
    op.execute("DROP INDEX IF EXISTS uq_posts_hash")

    # 3. Create partial unique index (hash unique only for non-deleted posts)
    # This allows deleted posts to have duplicate hashes
    op.execute("""
        CREATE UNIQUE INDEX uq_posts_hash_active
        ON posts (hash)
        WHERE deleted_by_user = FALSE
    """)

    # 4. Add indexes for cleanup queries
    op.create_index("ix_posts_deleted_by_user", "posts", ["deleted_by_user"])
    op.create_index("ix_posts_deleted_by_user_date", "posts", ["deleted_by_user_date"])


def downgrade() -> None:
    # Remove new indexes
    op.drop_index("ix_posts_deleted_by_user_date", table_name="posts")
    op.drop_index("ix_posts_deleted_by_user", table_name="posts")

    # Drop partial unique index
    op.execute("DROP INDEX IF EXISTS uq_posts_hash_active")

    # Restore original unique constraint
    op.create_unique_constraint("uq_posts_hash", "posts", ["hash"])

    # Remove columns
    op.drop_column("posts", "deleted_by_user_date")
    op.drop_column("posts", "deleted_by_user")

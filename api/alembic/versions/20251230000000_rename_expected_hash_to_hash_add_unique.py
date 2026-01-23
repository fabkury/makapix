"""rename_expected_hash_to_hash_add_unique

Revision ID: 20251230000000
Revises: 20251229000000
Create Date: 2025-12-30 00:00:00.000000

- Rename posts.expected_hash -> posts.hash
- Add UNIQUE constraint/index on posts.hash to prevent duplicate artworks
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251230000000"
down_revision = "20251229000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename column
    op.alter_column("posts", "expected_hash", new_column_name="hash")

    # Rename/drop old index (best-effort, depends on DB state)
    op.execute("DROP INDEX IF EXISTS ix_posts_expected_hash")

    # Enforce uniqueness (allows multiple NULLs)
    op.execute("ALTER TABLE posts DROP CONSTRAINT IF EXISTS uq_posts_hash")
    op.execute("DROP INDEX IF EXISTS uq_posts_hash")
    op.create_unique_constraint("uq_posts_hash", "posts", ["hash"])


def downgrade() -> None:
    op.execute("ALTER TABLE posts DROP CONSTRAINT IF EXISTS uq_posts_hash")
    op.execute("DROP INDEX IF EXISTS uq_posts_hash")
    op.execute("DROP INDEX IF EXISTS ix_posts_hash")

    # Restore old name
    op.alter_column("posts", "hash", new_column_name="expected_hash")

    # Restore old non-unique index for compatibility
    op.create_index("ix_posts_expected_hash", "posts", ["expected_hash"])

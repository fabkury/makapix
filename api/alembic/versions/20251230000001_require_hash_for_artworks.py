"""require_hash_for_artworks

Revision ID: 20251230000001
Revises: 20251230000000
Create Date: 2025-12-30 00:00:01.000000

Enforce that artwork posts always have a SHA256 hash:
- For kind='artwork': posts.hash must be NOT NULL
- For other kinds (e.g. 'playlist'): hash may be NULL
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "20251230000001"
down_revision = "20251230000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE posts
        ADD CONSTRAINT ck_posts_artwork_hash_required
        CHECK (kind <> 'artwork' OR hash IS NOT NULL)
        """)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE posts DROP CONSTRAINT IF EXISTS ck_posts_artwork_hash_required"
    )

"""Add formats_available column to posts table.

This column stores the list of available file formats after SSAFPP
(Server-Side Artwork File Post-Processing) has completed for an artwork.

Available formats may include: png, gif, webp, bmp
Animated artworks will only have: gif, webp

Revision ID: 20260119000001
Revises: 20260119000000
Create Date: 2026-01-19

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260119000001"
down_revision = "20260119000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add formats_available ARRAY column to posts table."""
    op.add_column(
        "posts",
        sa.Column(
            "formats_available",
            postgresql.ARRAY(sa.String(10)),
            nullable=False,
            server_default="{}",
        ),
    )

    # Backfill existing artwork posts: set formats_available = [file_format]
    op.execute("""
        UPDATE posts
        SET formats_available = ARRAY[file_format]
        WHERE kind = 'artwork'
          AND file_format IS NOT NULL
          AND file_format != ''
    """)


def downgrade() -> None:
    """Remove formats_available column from posts table."""
    op.drop_column("posts", "formats_available")

"""Add licenses table and license_id to posts.

Creative Commons license support for artwork posts. Artists can select a
license when uploading, and the badge is displayed on post pages.

Revision ID: 20260126000000
Revises: 20260124000000
Create Date: 2026-01-26

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260126000000"
down_revision: str | None = "20260124000000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create licenses table, seed data, add license_id to posts, and backfill."""
    # Create licenses table
    op.create_table(
        "licenses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("identifier", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("canonical_url", sa.String(500), nullable=False),
        sa.Column("badge_path", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("identifier", name="uq_licenses_identifier"),
    )
    op.create_index("ix_licenses_id", "licenses", ["id"])
    op.create_index("ix_licenses_identifier", "licenses", ["identifier"])

    # Seed 8 Creative Commons licenses
    op.execute("""
        INSERT INTO licenses (identifier, title, canonical_url, badge_path)
        VALUES
            ('CC-BY-4.0', 'Creative Commons Attribution 4.0 International', 'https://creativecommons.org/licenses/by/4.0/', '/licenses/by.svg'),
            ('CC-BY-NC-4.0', 'Creative Commons Attribution-NonCommercial 4.0 International', 'https://creativecommons.org/licenses/by-nc/4.0/', '/licenses/by-nc.svg'),
            ('CC-BY-ND-4.0', 'Creative Commons Attribution-NoDerivatives 4.0 International', 'https://creativecommons.org/licenses/by-nd/4.0/', '/licenses/by-nd.svg'),
            ('CC-BY-NC-ND-4.0', 'Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International', 'https://creativecommons.org/licenses/by-nc-nd/4.0/', '/licenses/by-nc-nd.svg'),
            ('CC-BY-SA-4.0', 'Creative Commons Attribution-ShareAlike 4.0 International', 'https://creativecommons.org/licenses/by-sa/4.0/', '/licenses/by-sa.svg'),
            ('CC-BY-NC-SA-4.0', 'Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International', 'https://creativecommons.org/licenses/by-nc-sa/4.0/', '/licenses/by-nc-sa.svg'),
            ('CC0-1.0', 'CC0 1.0 Universal Public Domain Dedication', 'https://creativecommons.org/publicdomain/zero/1.0/', '/licenses/cc-zero.svg'),
            ('PDM-1.0', 'Public Domain Mark 1.0', 'https://creativecommons.org/publicdomain/mark/1.0/', '/licenses/publicdomain.svg')
    """)

    # Add license_id column to posts (nullable)
    op.add_column(
        "posts",
        sa.Column(
            "license_id",
            sa.Integer(),
            sa.ForeignKey("licenses.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_posts_license_id", "posts", ["license_id"])

    # Backfill existing artwork posts with CC BY-ND 4.0 (id=3)
    op.execute("""
        UPDATE posts
        SET license_id = (SELECT id FROM licenses WHERE identifier = 'CC-BY-ND-4.0')
        WHERE kind = 'artwork'
    """)


def downgrade() -> None:
    """Remove license_id from posts and drop licenses table."""
    op.drop_index("ix_posts_license_id", "posts")
    op.drop_column("posts", "license_id")
    op.drop_index("ix_licenses_identifier", "licenses")
    op.drop_index("ix_licenses_id", "licenses")
    op.drop_table("licenses")

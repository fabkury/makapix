"""Add badge_definitions table

Revision ID: 20260113000002
Revises: 20260113000001
Create Date: 2026-01-13

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260113000002"
down_revision: str | None = "20260113000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create badge_definitions table and seed with initial data."""
    # Create badge_definitions table
    op.create_table(
        "badge_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("badge", sa.String(50), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon_url_64", sa.String(500), nullable=False),
        sa.Column("icon_url_16", sa.String(500), nullable=True),
        sa.Column("is_tag_badge", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("badge", name="uq_badge_definitions_badge"),
    )
    op.create_index("ix_badge_definitions_badge", "badge_definitions", ["badge"])

    # Seed initial badge definitions
    op.execute("""
        INSERT INTO badge_definitions (badge, label, description, icon_url_64, icon_url_16, is_tag_badge)
        VALUES
            ('early-adopter', 'Early Adopter', 'Joined during beta', '/badges/early-adopter_64.png', '/badges/early-adopter_16.png', true),
            ('top-contributor', 'Top Contributor', 'Posted 100+ artworks', '/badges/top-contributor_64.png', NULL, false),
            ('moderator', 'Moderator', 'Community moderator', '/badges/moderator_64.png', '/badges/moderator_16.png', true)
    """)


def downgrade() -> None:
    """Drop badge_definitions table."""
    op.drop_index("ix_badge_definitions_badge", "badge_definitions")
    op.drop_table("badge_definitions")

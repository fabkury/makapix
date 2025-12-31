"""add_content_art_url_to_social_notifications

Revision ID: 20251231000001
Revises: 20251231000000
Create Date: 2025-12-31 15:30:00.000000

Adds content_art_url column to social_notifications table
for displaying artwork thumbnails in the notifications list.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20251231000001"
down_revision = "20251231000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "social_notifications",
        sa.Column("content_art_url", sa.String(1000), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("social_notifications", "content_art_url")

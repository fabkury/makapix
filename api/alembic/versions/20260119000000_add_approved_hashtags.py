"""Add approved_hashtags column to users table.

This column stores the list of monitored hashtags that a user has explicitly
opted into viewing. Posts containing monitored hashtags will be filtered out
unless the user has approved those specific hashtags.

Monitored hashtags: politics, nsfw, explicit, 13plus, violence

Revision ID: 20260119000000
Revises: 20260118000000
Create Date: 2026-01-19

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260119000000"
down_revision = "20260118000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add approved_hashtags ARRAY column to users table."""
    op.add_column(
        "users",
        sa.Column(
            "approved_hashtags",
            postgresql.ARRAY(sa.String(50)),
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    """Remove approved_hashtags column from users table."""
    op.drop_column("users", "approved_hashtags")

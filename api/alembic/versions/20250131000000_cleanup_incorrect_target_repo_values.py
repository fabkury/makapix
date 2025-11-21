"""Cleanup incorrect target_repo values

Revision ID: 20250131000000
Revises: 20251030090421
Create Date: 2025-01-31 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250131000000'
down_revision = '20251030090421'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clean up incorrect target_repo values that are GitHub Pages URLs
    # Values ending with .github.io are GitHub Pages URLs, not repository names
    op.execute("""
        UPDATE github_installations
        SET target_repo = NULL
        WHERE target_repo LIKE '%.github.io'
    """)


def downgrade() -> None:
    # No way to restore the incorrect values, so this is a no-op
    pass







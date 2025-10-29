"""set fabkury as site owner

Revision ID: 202410310002
Revises: 202410300001
Create Date: 2025-10-31 00:00:02.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "202410310002"
down_revision = "202410300001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Set fabkury user as site owner with both owner and moderator roles
    # This uses raw SQL to ensure the update happens regardless of application-level checks
    op.execute("""
        UPDATE users 
        SET roles = '["owner", "moderator"]'::json
        WHERE handle = 'fabkury'
    """)


def downgrade() -> None:
    # Remove owner role from fabkury (keep only moderator if they had it)
    op.execute("""
        UPDATE users 
        SET roles = (
            SELECT jsonb_agg(elem)
            FROM jsonb_array_elements_text(roles::jsonb) AS elem
            WHERE elem != 'owner'
        )::json
        WHERE handle = 'fabkury' AND roles::jsonb ? 'owner'
    """)

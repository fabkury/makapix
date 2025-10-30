"""cleanup incorrect target_repo values

Revision ID: 20251030153059
Revises: 20251030090421
Create Date: 2025-10-30 15:30:59.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20251030153059"
down_revision = "20251030090421"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clean up incorrect target_repo values that are GitHub Pages URLs (ending with .github.io)
    # These should be NULL or actual repository names, not GitHub Pages URLs
    connection = op.get_bind()
    
    # Update all target_repo values that end with .github.io to NULL
    result = connection.execute(
        sa.text("""
            UPDATE github_installations 
            SET target_repo = NULL 
            WHERE target_repo LIKE '%.github.io'
        """)
    )
    
    # Log how many records were updated
    print(f"Cleaned up {result.rowcount} incorrect target_repo values")


def downgrade() -> None:
    # Cannot restore the original incorrect values
    pass


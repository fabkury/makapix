"""cleanup deep comments

Revision ID: 202410290003
Revises: 202410290002
Create Date: 2025-10-29 00:00:03.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "202410290003"
down_revision = "202410290002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Delete comments with depth > 2 (invalid according to new policy)
    # Also delete any child comments that reference deleted parents
    connection = op.get_bind()
    
    # First, delete all comments with depth > 2
    connection.execute(
        sa.text("DELETE FROM comments WHERE depth > 2")
    )
    
    # Then, recursively delete orphaned comments (comments whose parent was deleted)
    # This handles comments that might have had valid depth but their parent was deleted
    max_iterations = 10  # Safety limit
    for _ in range(max_iterations):
        result = connection.execute(
            sa.text("""
                DELETE FROM comments 
                WHERE parent_id IS NOT NULL 
                AND parent_id NOT IN (SELECT id FROM comments)
            """)
        )
        if result.rowcount == 0:
            break  # No more orphaned comments


def downgrade() -> None:
    # Cannot restore deleted comments
    pass


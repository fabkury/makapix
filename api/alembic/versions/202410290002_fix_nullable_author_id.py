"""fix nullable author_id and user_id

Revision ID: 202410290002
Revises: 202410290001
Create Date: 2025-10-29 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "202410290002"
down_revision = "202410290001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make author_id and user_id nullable
    op.alter_column('comments', 'author_id',
                    existing_type=sa.dialects.postgresql.UUID(),
                    nullable=True)
    
    op.alter_column('reactions', 'user_id',
                    existing_type=sa.dialects.postgresql.UUID(),
                    nullable=True)


def downgrade() -> None:
    # Revert to not null (but this may fail if there are null values)
    op.alter_column('reactions', 'user_id',
                    existing_type=sa.dialects.postgresql.UUID(),
                    nullable=False)
    
    op.alter_column('comments', 'author_id',
                    existing_type=sa.dialects.postgresql.UUID(),
                    nullable=False)


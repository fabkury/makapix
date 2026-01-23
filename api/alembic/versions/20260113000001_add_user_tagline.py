"""Add user tagline field

Revision ID: 20260113000001
Revises: 20260109000000_add_batch_download_requests_table
Create Date: 2026-01-13

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260113000001"
down_revision: str | None = "20260109000000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add tagline column to users table."""
    op.add_column(
        "users",
        sa.Column("tagline", sa.String(48), nullable=True),
    )


def downgrade() -> None:
    """Remove tagline column from users table."""
    op.drop_column("users", "tagline")

"""users.terms_version_accepted (docs/ugc-safety/ D26)

ToS version (effective-date string) accepted at self-signup. NULL = pre-ToS
account or an account not created through self-signup (continued use =
acceptance per the Terms).

Revision ID: b7f2c9d4e1a8
Revises: a6045606b0a3
Create Date: 2026-07-06

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b7f2c9d4e1a8"
down_revision = "a6045606b0a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("terms_version_accepted", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "terms_version_accepted")

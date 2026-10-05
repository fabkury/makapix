"""users.locale — language for transactional emails

Revision ID: d3e4f5a6b7c8
Revises: a8b9c0d1e2f3
Create Date: 2026-10-05

Adds users.locale (varchar(35), nullable): the BCP 47 tag of the language the
app shows the user; NULL = English (docs/localized-text/ D6).

Hand-written (not autogenerate) to avoid dragging along unrelated, pre-existing
model/DB drift — same precedent as revision b3d9a1c40f21.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d3e4f5a6b7c8"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("locale", sa.String(35), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "locale")

"""users.mention_policy — who may @mention a user

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-09-22

Adds users.mention_policy (varchar, NOT NULL, default 'everyone') for the
mentions feature (docs/mentions/, app decision D11): 'everyone' | 'following'
(only members the user follows may mention them) | 'nobody'. Existing rows get
the default via the server default.

Hand-written (not autogenerate) to avoid dragging along unrelated, pre-existing
model/DB drift — same precedent as revision b3d9a1c40f21.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "mention_policy",
            sa.String(16),
            nullable=False,
            server_default="everyone",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "mention_policy")

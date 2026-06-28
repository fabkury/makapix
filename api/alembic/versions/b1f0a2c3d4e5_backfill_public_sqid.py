"""backfill public_sqid for users missing it

Revision ID: b1f0a2c3d4e5
Revises: a71f178d6e9b
Create Date: 2026-06-26

The JWT `sub` claim now carries `public_sqid` (change-request §3.2). public_sqid
is assigned just after insert at signup; this backfills any legacy rows where it
is NULL/empty so every user has a stable public id.

No schema change: the column stays nullable here. The access-token resolver
(`get_current_user`) still falls back to the legacy `user_id` claim, so this
backfill is not load-bearing for auth — it just guarantees `sub` is populated.
Enforcing NOT NULL is a deliberate follow-up (it requires updating the many test
fixtures that create users without a public_sqid).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b1f0a2c3d4e5"
down_revision = "a71f178d6e9b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Deterministic, collision-free per user id, so it cannot violate the UNIQUE
    # constraint on public_sqid.
    from app.sqids_config import encode_user_id

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id FROM users WHERE public_sqid IS NULL OR public_sqid = ''")
    ).fetchall()
    for (user_id,) in rows:
        bind.execute(
            sa.text("UPDATE users SET public_sqid = :sqid WHERE id = :id"),
            {"sqid": encode_user_id(user_id), "id": user_id},
        )


def downgrade() -> None:
    # Data backfill; not meaningfully reversible.
    pass

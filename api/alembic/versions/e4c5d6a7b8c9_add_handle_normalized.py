"""add handle_normalized (confusable skeleton) for handle uniqueness

Revision ID: e4c5d6a7b8c9
Revises: d3b2c4e5f6a7
Create Date: 2026-06-30

Adds users.handle_normalized — the confusable skeleton of the handle — backfills
it for existing rows, and enforces a unique index. Existing handles are NOT
re-validated against the new character policy (they're grandfathered); only the
uniqueness key is computed for them.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Pure helper, no model import — safe to use inside a migration.
from app.utils.handle_normalize import compute_handle_skeleton

revision = "e4c5d6a7b8c9"
down_revision = "d3b2c4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("handle_normalized", sa.String(length=128), nullable=True)
    )

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, handle FROM users")).fetchall()
    skeletons: dict[str, int] = {}
    for row in rows:
        skeleton = compute_handle_skeleton(row.handle)
        if skeleton in skeletons:
            raise RuntimeError(
                "Cannot add unique handle_normalized index: existing handles "
                f"collide on skeleton {skeleton!r} "
                f"(user ids {skeletons[skeleton]} and {row.id}). "
                "Resolve the duplicate handle before migrating."
            )
        skeletons[skeleton] = row.id
        conn.execute(
            sa.text("UPDATE users SET handle_normalized = :s WHERE id = :i"),
            {"s": skeleton, "i": row.id},
        )

    op.alter_column("users", "handle_normalized", nullable=False)
    op.create_index(
        "ix_users_handle_normalized", "users", ["handle_normalized"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_users_handle_normalized", table_name="users")
    op.drop_column("users", "handle_normalized")

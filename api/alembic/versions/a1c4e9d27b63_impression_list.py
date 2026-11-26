"""impression list — post_impression_users + users.show_in_impression_lists

Revision ID: a1c4e9d27b63
Revises: ff72e75e41df
Create Date: 2026-11-26

The "Displayed on" list (docs/impression-list/): one row per (artwork,
member) whose screens showed it, and the per-account switch that hides a
member from every such list. The table starts empty by decision (L10): no
seeding from view_events.

Hand-written (not autogenerate) to avoid dragging along unrelated,
pre-existing model/DB drift — same precedent as revision b3d9a1c40f21.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a1c4e9d27b63"
down_revision = "ff72e75e41df"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "show_in_impression_lists",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_table(
        "post_impression_users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "post_id",
            sa.Integer(),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "shown_count", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("first_shown_on", sa.Date(), nullable=False),
        sa.Column("last_shown_on", sa.Date(), nullable=False),
        sa.Column(
            "device_models",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "web_player", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("app", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("post_id", "user_id", name="uq_post_impression_users"),
    )
    op.create_index(
        "ix_post_impression_users_user_id", "post_impression_users", ["user_id"]
    )
    op.create_index(
        "ix_post_impression_users_last_shown_on",
        "post_impression_users",
        ["last_shown_on"],
    )
    op.create_index(
        "ix_post_impression_users_post_last",
        "post_impression_users",
        ["post_id", sa.text("last_shown_on DESC"), sa.text("id DESC")],
    )


def downgrade() -> None:
    op.drop_table("post_impression_users")
    op.drop_column("users", "show_in_impression_lists")

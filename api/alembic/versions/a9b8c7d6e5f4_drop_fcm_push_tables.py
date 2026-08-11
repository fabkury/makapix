"""drop push_tokens + users.notification_prefs (FCM server half deleted)

The FCM/mobile-push server half is removed at the app team's request
(docs/notification-architecture/messages/0002 — they chose "drop"; the app
never built the client half, so no token was ever registered). Verified
before this migration: push_tokens had 0 rows and no user carried
non-default notification_prefs on either dev or prod — the drop is
lossless. downgrade() recreates both exactly as revision d3b2c4e5f6a7
defined them.

Hand-written (not autogenerate output) to avoid dragging along unrelated,
pre-existing model/DB drift — same precedent as revision e7a1c9d0b2f4.

Revision ID: a9b8c7d6e5f4
Revises: e7a1c9d0b2f4
Create Date: 2026-08-11

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a9b8c7d6e5f4"
down_revision = "e7a1c9d0b2f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_push_tokens_revoked", table_name="push_tokens")
    op.drop_index("ix_push_tokens_token", table_name="push_tokens")
    op.drop_index("ix_push_tokens_user_id", table_name="push_tokens")
    op.drop_index("ix_push_tokens_id", table_name="push_tokens")
    op.drop_table("push_tokens")
    op.drop_column("users", "notification_prefs")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "notification_prefs",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.create_table(
        "push_tokens",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("platform", sa.String(length=8), nullable=False),
        sa.Column("token", sa.String(length=512), nullable=False),
        sa.Column("device_label", sa.String(length=120), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_push_tokens_id", "push_tokens", ["id"])
    op.create_index("ix_push_tokens_user_id", "push_tokens", ["user_id"])
    op.create_index("ix_push_tokens_token", "push_tokens", ["token"], unique=True)
    op.create_index("ix_push_tokens_revoked", "push_tokens", ["revoked"])

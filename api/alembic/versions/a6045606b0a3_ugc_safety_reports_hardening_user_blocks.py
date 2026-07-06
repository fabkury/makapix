"""ugc-safety: reports hardening + user_blocks

Adds the user_blocks table (docs/ugc-safety/ D1) and hardens reports for
anonymous reporting: reporter_id nullable (D2), reporter_ip for anon abuse
correlation (D24, swept after 30 days), mod_notes so moderator notes never
overwrite the reporter's text (D25).

NOTE: hand-trimmed — autogenerate emitted large amounts of pre-existing
schema drift (JSON/JSONB, FK ondelete, index variants) that this migration
intentionally does not touch.

Revision ID: a6045606b0a3
Revises: b3d9a1c40f21
Create Date: 2026-07-06 18:04:24.258648

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a6045606b0a3"
down_revision = "b3d9a1c40f21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_blocks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("blocker_id", sa.Integer(), nullable=False),
        sa.Column("blocked_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["blocked_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["blocker_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_pair"),
    )
    op.create_index(
        op.f("ix_user_blocks_blocked_id"), "user_blocks", ["blocked_id"], unique=False
    )
    op.create_index(
        op.f("ix_user_blocks_blocker_id"), "user_blocks", ["blocker_id"], unique=False
    )

    op.add_column(
        "reports", sa.Column("reporter_ip", sa.String(length=45), nullable=True)
    )
    op.add_column("reports", sa.Column("mod_notes", sa.Text(), nullable=True))
    op.alter_column("reports", "reporter_id", existing_type=sa.INTEGER(), nullable=True)


def downgrade() -> None:
    op.alter_column(
        "reports", "reporter_id", existing_type=sa.INTEGER(), nullable=False
    )
    op.drop_column("reports", "mod_notes")
    op.drop_column("reports", "reporter_ip")

    op.drop_index(op.f("ix_user_blocks_blocker_id"), table_name="user_blocks")
    op.drop_index(op.f("ix_user_blocks_blocked_id"), table_name="user_blocks")
    op.drop_table("user_blocks")

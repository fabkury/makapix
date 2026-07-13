"""comment mod-deletion attribution and original_body

Adds deleted_by_mod + original_body to comments and blog_post_comments so
moderator deletions are no longer misattributed to the comment author, and
the pre-deletion body survives for moderator review / undelete.

Backfills attribution for rows tombstoned by the report take-down path (and
the 2026-07-07 manual PII cleanup that mimicked it), which stamped the body
'[deleted by moderator]' while setting deleted_by_owner.

Revision ID: aa19177d8af1
Revises: f5d6e7a8b9c0
Create Date: 2026-07-13 21:20:00.682346

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "aa19177d8af1"
down_revision = "f5d6e7a8b9c0"
branch_labels = None
depends_on = None

MOD_TOMBSTONE = "[deleted by moderator]"


def upgrade() -> None:
    for table in ("comments", "blog_post_comments"):
        op.add_column(
            table,
            sa.Column(
                "deleted_by_mod",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.add_column(table, sa.Column("original_body", sa.Text(), nullable=True))
        op.execute(
            f"UPDATE {table} SET deleted_by_mod = TRUE, deleted_by_owner = FALSE "
            f"WHERE body = '{MOD_TOMBSTONE}'"
        )


def downgrade() -> None:
    for table in ("comments", "blog_post_comments"):
        # Restore the pre-migration encoding of moderator take-downs
        op.execute(
            f"UPDATE {table} SET deleted_by_owner = TRUE "
            f"WHERE deleted_by_mod = TRUE"
        )
        op.drop_column(table, "original_body")
        op.drop_column(table, "deleted_by_mod")

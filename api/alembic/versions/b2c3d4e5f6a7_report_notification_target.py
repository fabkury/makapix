"""Report notifications carry their target (docs/report-artwork/).

social_notifications.target_user_id: the reported user on user-target
new_report / report_resolved rows (post/comment targets reuse post_id and
the content_* columns). social_notifications.reason_code: the report's
reason code so clients can compose the copy.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "social_notifications",
        sa.Column("target_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "social_notifications",
        sa.Column("reason_code", sa.String(length=50), nullable=True),
    )
    op.create_foreign_key(
        "fk_social_notifications_target_user_id_users",
        "social_notifications",
        "users",
        ["target_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_social_notifications_target_user_id",
        "social_notifications",
        ["target_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_social_notifications_target_user_id", table_name="social_notifications"
    )
    op.drop_constraint(
        "fk_social_notifications_target_user_id_users",
        "social_notifications",
        type_="foreignkey",
    )
    op.drop_column("social_notifications", "reason_code")
    op.drop_column("social_notifications", "target_user_id")

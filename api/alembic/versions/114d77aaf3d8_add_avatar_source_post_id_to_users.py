"""add avatar_source_post_id to users

Revision ID: 114d77aaf3d8
Revises: aa19177d8af1
Create Date: 2026-07-19 16:21:19.914809

Attribution for "use as profile photo": the post the user's current avatar was
copied from. Internal-only; SET NULL on post hard-deletion (avatar bytes are a
snapshot in the avatar vault, so only attribution is lost).
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "114d77aaf3d8"
down_revision = "aa19177d8af1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("avatar_source_post_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_users_avatar_source_post_id"),
        "users",
        ["avatar_source_post_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_users_avatar_source_post_id_posts",
        "users",
        "posts",
        ["avatar_source_post_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_users_avatar_source_post_id_posts", "users", type_="foreignkey"
    )
    op.drop_index(op.f("ix_users_avatar_source_post_id"), table_name="users")
    op.drop_column("users", "avatar_source_post_id")

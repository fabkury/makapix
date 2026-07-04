"""add retired_artworks table

Tracks old vault files retired by replace-artwork, which now rotates the
post's storage_key so vault URLs stay immutable. The old key's files keep
serving for a 7-day grace period (laggard players / cached URLs), then the
cleanup_retired_artwork beat task sweeps them using the fields stored here.

Hand-written (not autogenerate output) to avoid dragging along unrelated,
pre-existing model/DB drift — same precedent as revision 2ca55835e75a.

Revision ID: 17f06c5f7cc3
Revises: 2ca55835e75a
Create Date: 2026-07-04

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "17f06c5f7cc3"
down_revision = "2ca55835e75a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "retired_artworks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=True),
        sa.Column("storage_key", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_shard", sa.String(length=8), nullable=False),
        sa.Column("formats", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("had_mkpx", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("delete_after", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_retired_artworks_post_id", "retired_artworks", ["post_id"])
    op.create_index(
        "ix_retired_artworks_storage_key", "retired_artworks", ["storage_key"]
    )
    op.create_index(
        "ix_retired_artworks_delete_after", "retired_artworks", ["delete_after"]
    )


def downgrade() -> None:
    op.drop_index("ix_retired_artworks_delete_after", table_name="retired_artworks")
    op.drop_index("ix_retired_artworks_storage_key", table_name="retired_artworks")
    op.drop_index("ix_retired_artworks_post_id", table_name="retired_artworks")
    op.drop_table("retired_artworks")

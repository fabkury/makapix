"""add mkpx layers-file columns to posts

Two nullable columns tracking the optional attached .mkpx layers file
(docs/mkpx-upload/): mkpx_file_bytes (also feeds the storage-quota sum)
and mkpx_attached_at (doubles as the client cache-invalidation stamp).

Hand-trimmed from autogenerate output: only the mkpx columns belong to
this revision (autogenerate also surfaced unrelated, pre-existing
model/DB drift, which must not ride along).

Revision ID: 2ca55835e75a
Revises: e4c5d6a7b8c9
Create Date: 2026-07-02 22:39:53.399401

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "2ca55835e75a"
down_revision = "e4c5d6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("posts", sa.Column("mkpx_file_bytes", sa.Integer(), nullable=True))
    op.add_column(
        "posts",
        sa.Column("mkpx_attached_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("posts", "mkpx_attached_at")
    op.drop_column("posts", "mkpx_file_bytes")

"""Artwork provenance & lineage: posts provenance columns, remixable, post_lineage.

Hand-written (docs/artwork-provenance/PLAN.md v2):

1. posts.upload_channel / creation_method / source_details — client-declared
   provenance, NULL = unknown (D1/D2).
2. posts.remixable — default true for new and legacy rows (ADR 0003), except
   NoDerivatives-licensed posts which are backfilled false (L5).
3. post_lineage — multi-parent Lineage Links (L2, ADR 0002). parent_sqid is a
   snapshot so links survive parent hard-delete as tombstones (L10); child
   hard-delete cascades its links away.

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-08-14
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None

ND_LICENSE_IDENTIFIERS = ("CC-BY-ND-4.0", "CC-BY-NC-ND-4.0")


def upgrade() -> None:
    op.add_column("posts", sa.Column("upload_channel", sa.String(16), nullable=True))
    op.add_column("posts", sa.Column("creation_method", sa.String(32), nullable=True))
    op.add_column(
        "posts", sa.Column("source_details", postgresql.JSONB(), nullable=True)
    )
    op.add_column(
        "posts",
        sa.Column(
            "remixable", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )

    # ND licenses forbid derivatives — force those posts non-Remixable (L5).
    op.execute(
        sa.text(
            "UPDATE posts SET remixable = false WHERE license_id IN "
            "(SELECT id FROM licenses WHERE identifier IN :nd)"
        ).bindparams(sa.bindparam("nd", value=ND_LICENSE_IDENTIFIERS, expanding=True))
    )

    op.create_table(
        "post_lineage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "child_post_id",
            sa.Integer(),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_post_id",
            sa.Integer(),
            sa.ForeignKey("posts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("parent_sqid", sa.String(16), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "child_post_id", "parent_sqid", name="uq_post_lineage_child_parent_sqid"
        ),
    )
    op.create_index("ix_post_lineage_child_post_id", "post_lineage", ["child_post_id"])
    op.create_index(
        "ix_post_lineage_parent_post_id", "post_lineage", ["parent_post_id"]
    )


def downgrade() -> None:
    op.drop_table("post_lineage")
    op.drop_column("posts", "remixable")
    op.drop_column("posts", "source_details")
    op.drop_column("posts", "creation_method")
    op.drop_column("posts", "upload_channel")

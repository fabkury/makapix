"""Add batch_download_requests table for PMD.

Revision ID: 20260109000000
Revises: 20260106000000
Create Date: 2026-01-09

This migration creates the batch_download_requests table for tracking
user batch download requests in the Post Management Dashboard (PMD).
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260109000000"
down_revision: str | None = "20260106000000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "batch_download_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("post_ids", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column(
            "include_comments", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "include_reactions", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("send_email", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "status", sa.String(length=20), nullable=False, server_default="pending"
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("artwork_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_batch_download_requests_id", "batch_download_requests", ["id"]
    )
    op.create_index(
        "ix_batch_download_requests_user_id", "batch_download_requests", ["user_id"]
    )
    op.create_index(
        "ix_batch_download_requests_status", "batch_download_requests", ["status"]
    )
    op.create_index(
        "ix_batch_download_requests_created_at",
        "batch_download_requests",
        ["created_at"],
    )
    op.create_index(
        "ix_batch_download_requests_expires_at",
        "batch_download_requests",
        ["expires_at"],
    )
    op.create_index(
        "ix_bdr_user_created",
        "batch_download_requests",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_bdr_status_expires",
        "batch_download_requests",
        ["status", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_bdr_status_expires", table_name="batch_download_requests")
    op.drop_index("ix_bdr_user_created", table_name="batch_download_requests")
    op.drop_index(
        "ix_batch_download_requests_expires_at", table_name="batch_download_requests"
    )
    op.drop_index(
        "ix_batch_download_requests_created_at", table_name="batch_download_requests"
    )
    op.drop_index(
        "ix_batch_download_requests_status", table_name="batch_download_requests"
    )
    op.drop_index(
        "ix_batch_download_requests_user_id", table_name="batch_download_requests"
    )
    op.drop_index("ix_batch_download_requests_id", table_name="batch_download_requests")
    op.drop_table("batch_download_requests")

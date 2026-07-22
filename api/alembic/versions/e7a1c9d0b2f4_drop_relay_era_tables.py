"""drop relay-era tables (external-hosting legacy)

Removes the three tables left over from the open-architecture era in which
users could publish artwork to their own GitHub Pages and register it at
Makapix (docs/remove-external-hosting/). All artwork is now exclusively
self-hosted in the vault. The tables were verified empty on both dev and
prod before this migration; the drop is lossless and downgrade() recreates
them exactly as the squashed baseline defined them.

Hand-written (not autogenerate output) to avoid dragging along unrelated,
pre-existing model/DB drift — same precedent as revision 17f06c5f7cc3.

Revision ID: e7a1c9d0b2f4
Revises: 114d77aaf3d8
Create Date: 2026-07-22

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "e7a1c9d0b2f4"
down_revision = "114d77aaf3d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_relay_jobs_created_at", table_name="relay_jobs")
    op.drop_index("ix_relay_jobs_status", table_name="relay_jobs")
    op.drop_index("ix_relay_jobs_user_id", table_name="relay_jobs")
    op.drop_index("ix_relay_jobs_id", table_name="relay_jobs")
    op.drop_table("relay_jobs")

    op.drop_index(
        "ix_github_installations_installation_id", table_name="github_installations"
    )
    op.drop_index("ix_github_installations_user_id", table_name="github_installations")
    op.drop_table("github_installations")

    op.drop_index(
        "ix_conformance_checks_next_check_at", table_name="conformance_checks"
    )
    op.drop_index("ix_conformance_checks_user_id", table_name="conformance_checks")
    op.drop_table("conformance_checks")


def downgrade() -> None:
    # Recreated exactly as in the squashed baseline (20260128000000).
    op.create_table(
        "conformance_checks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(50), nullable=False, server_default="ok"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_conformance_checks_user_id", "conformance_checks", ["user_id"], unique=True
    )
    op.create_index(
        "ix_conformance_checks_next_check_at", "conformance_checks", ["next_check_at"]
    )

    op.create_table(
        "relay_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("repo", sa.String(200), nullable=True),
        sa.Column("commit", sa.String(100), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("bundle_path", sa.String(500), nullable=True),
        sa.Column("manifest_data", postgresql.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_relay_jobs_id", "relay_jobs", ["id"])
    op.create_index("ix_relay_jobs_user_id", "relay_jobs", ["user_id"])
    op.create_index("ix_relay_jobs_status", "relay_jobs", ["status"])
    op.create_index("ix_relay_jobs_created_at", "relay_jobs", ["created_at"])

    op.create_table(
        "github_installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("installation_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("account_login", sa.String(100), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("target_repo", sa.String(200), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_github_installations_user_id", "github_installations", ["user_id"]
    )
    op.create_index(
        "ix_github_installations_installation_id",
        "github_installations",
        ["installation_id"],
        unique=True,
    )

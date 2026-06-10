"""add vault_sharding_stats_daily for resharding migration

Daily vault downloads split by sharding scheme (2-level vs legacy 3-level),
instrumentation for the vault resharding migration (docs/vault-resharding/).
Aggregate rows have post_id IS NULL; the unique constraint uses NULLS NOT
DISTINCT (PostgreSQL 15+) so those rows are upsertable.

Revision ID: a71f178d6e9b
Revises: 565dd083aee9
Create Date: 2026-06-10 15:40:19.816317

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a71f178d6e9b"
down_revision = "565dd083aee9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vault_sharding_stats_daily",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("asset_class", sa.String(length=16), nullable=False),
        sa.Column("shard_level", sa.SmallInteger(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=True),
        sa.Column("downloads_human", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("downloads_bot", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("misses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "date",
            "asset_class",
            "shard_level",
            "post_id",
            name="uq_vault_sharding_stats_daily",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        "ix_vault_sharding_stats_daily_date",
        "vault_sharding_stats_daily",
        ["date"],
        unique=False,
    )
    op.create_index(
        "ix_vault_sharding_stats_daily_post_id",
        "vault_sharding_stats_daily",
        ["post_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_vault_sharding_stats_daily_post_id",
        table_name="vault_sharding_stats_daily",
    )
    op.drop_index(
        "ix_vault_sharding_stats_daily_date",
        table_name="vault_sharding_stats_daily",
    )
    op.drop_table("vault_sharding_stats_daily")

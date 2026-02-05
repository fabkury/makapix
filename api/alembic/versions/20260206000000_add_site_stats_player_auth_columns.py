"""Add player and authenticated columns to site_stats_daily

Revision ID: 20260206000000
Revises: 20260204000000
Create Date: 2026-02-06 00:00:00.000000

Adds columns for:
- Player view aggregates (from ViewEvent table)
- Authenticated user breakdown (from SiteEvent where user_id is not null)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260206000000"
down_revision = "20260204000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Player view aggregates (from ViewEvent table)
    op.add_column(
        "site_stats_daily",
        sa.Column(
            "total_player_views", sa.Integer, nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "site_stats_daily",
        sa.Column("active_players", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "site_stats_daily",
        sa.Column(
            "views_by_player", sa.JSON, nullable=False, server_default=sa.text("'{}'")
        ),
    )

    # Authenticated user breakdown
    op.add_column(
        "site_stats_daily",
        sa.Column(
            "authenticated_page_views",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "site_stats_daily",
        sa.Column(
            "authenticated_unique_visitors",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "site_stats_daily",
        sa.Column(
            "authenticated_views_by_page",
            sa.JSON,
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "site_stats_daily",
        sa.Column(
            "authenticated_views_by_country",
            sa.JSON,
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "site_stats_daily",
        sa.Column(
            "authenticated_views_by_device",
            sa.JSON,
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "site_stats_daily",
        sa.Column(
            "authenticated_top_referrers",
            sa.JSON,
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("site_stats_daily", "authenticated_top_referrers")
    op.drop_column("site_stats_daily", "authenticated_views_by_device")
    op.drop_column("site_stats_daily", "authenticated_views_by_country")
    op.drop_column("site_stats_daily", "authenticated_views_by_page")
    op.drop_column("site_stats_daily", "authenticated_unique_visitors")
    op.drop_column("site_stats_daily", "authenticated_page_views")
    op.drop_column("site_stats_daily", "views_by_player")
    op.drop_column("site_stats_daily", "active_players")
    op.drop_column("site_stats_daily", "total_player_views")

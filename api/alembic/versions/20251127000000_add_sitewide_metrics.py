"""add sitewide metrics tables

Revision ID: 20251127000000
Revises: 20251126000000_add_view_tracking
Create Date: 2025-11-27 00:00:00.000000

This migration adds tables for sitewide metrics and statistics:
- site_events: Raw sitewide event storage (7-day retention)
- site_stats_daily: Daily aggregated sitewide statistics (permanent)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20251127000000"
down_revision = "20250127000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================================================
    # SITE EVENTS TABLE - Raw sitewide event storage (7-day retention)
    # ========================================================================
    
    op.create_table(
        "site_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(50), nullable=False),  # page_view, signup, upload, api_call, error
        sa.Column("page_path", sa.String(500), nullable=True),  # /recent, /posts/[id], etc.
        sa.Column("visitor_ip_hash", sa.String(64), nullable=False),  # SHA256 hash of IP
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("device_type", sa.String(20), nullable=False),  # desktop, mobile, tablet
        sa.Column("country_code", sa.String(2), nullable=True),  # ISO 3166-1 alpha-2
        sa.Column("referrer_domain", sa.String(255), nullable=True),  # Extracted referrer domain
        sa.Column("event_data", postgresql.JSONB(), nullable=True),  # Event-specific data
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    
    # Indexes for site_events
    op.create_index("ix_site_events_id", "site_events", ["id"])
    op.create_index("ix_site_events_event_type", "site_events", ["event_type"])
    op.create_index("ix_site_events_user_id", "site_events", ["user_id"])
    op.create_index("ix_site_events_created_at", "site_events", ["created_at"])
    op.create_index("ix_site_events_type_created", "site_events", ["event_type", "created_at"])
    op.create_index("ix_site_events_country_code", "site_events", ["country_code"])
    op.create_index("ix_site_events_device_type", "site_events", ["device_type"])
    
    # ========================================================================
    # SITE STATS DAILY TABLE - Daily aggregated sitewide statistics (permanent)
    # ========================================================================
    
    op.create_table(
        "site_stats_daily",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), nullable=False, unique=True),
        sa.Column("total_page_views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_visitors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_signups", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_posts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_api_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_errors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("views_by_page", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("views_by_country", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("views_by_device", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("errors_by_type", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("top_referrers", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    
    # Indexes for site_stats_daily
    op.create_index("ix_site_stats_daily_date", "site_stats_daily", ["date"])
    
    # Unique constraint: one row per date
    op.create_unique_constraint(
        "uq_site_stats_daily_date",
        "site_stats_daily",
        ["date"]
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("site_stats_daily")
    op.drop_table("site_events")


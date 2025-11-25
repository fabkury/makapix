"""add view tracking tables

Revision ID: 20251126000000
Revises: 20251125000000_add_public_visibility
Create Date: 2025-11-26 00:00:00.000000

This migration adds tables for view tracking and statistics:
- view_events: Raw view event storage (7-day retention)
- post_stats_daily: Daily aggregated statistics (permanent)
- post_stats_cache: Cached computed statistics
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20251126000000"
down_revision = "20251125000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================================================
    # VIEW EVENTS TABLE - Raw view event storage (7-day retention)
    # ========================================================================
    
    op.create_table(
        "view_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("viewer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("viewer_ip_hash", sa.String(64), nullable=False),  # SHA256 hash of IP
        sa.Column("country_code", sa.String(2), nullable=True),  # ISO 3166-1 alpha-2
        sa.Column("device_type", sa.String(20), nullable=False),  # desktop, mobile, tablet, player
        sa.Column("view_source", sa.String(20), nullable=False),  # web, api, widget, player
        sa.Column("view_type", sa.String(20), nullable=False),  # intentional, listing, search, widget
        sa.Column("user_agent_hash", sa.String(64), nullable=True),  # For device fingerprinting
        sa.Column("referrer_domain", sa.String(255), nullable=True),  # Extracted referrer domain
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    
    # Indexes for view_events
    op.create_index("ix_view_events_id", "view_events", ["id"])
    op.create_index("ix_view_events_post_id", "view_events", ["post_id"])
    op.create_index("ix_view_events_viewer_user_id", "view_events", ["viewer_user_id"])
    op.create_index("ix_view_events_created_at", "view_events", ["created_at"])
    op.create_index("ix_view_events_post_created", "view_events", ["post_id", "created_at"])
    op.create_index("ix_view_events_country_code", "view_events", ["country_code"])
    op.create_index("ix_view_events_device_type", "view_events", ["device_type"])
    op.create_index("ix_view_events_view_type", "view_events", ["view_type"])
    
    # ========================================================================
    # POST STATS DAILY TABLE - Daily aggregated statistics (permanent)
    # ========================================================================
    
    op.create_table(
        "post_stats_daily",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("total_views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unique_viewers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("views_by_country", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("views_by_device", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("views_by_type", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    
    # Indexes for post_stats_daily
    op.create_index("ix_post_stats_daily_post_id", "post_stats_daily", ["post_id"])
    op.create_index("ix_post_stats_daily_date", "post_stats_daily", ["date"])
    op.create_index("ix_post_stats_daily_post_date", "post_stats_daily", ["post_id", "date"])
    
    # Unique constraint: one row per post per date
    op.create_unique_constraint(
        "uq_post_stats_daily_post_date",
        "post_stats_daily",
        ["post_id", "date"]
    )
    
    # ========================================================================
    # POST STATS CACHE TABLE - Cached computed statistics
    # ========================================================================
    
    op.create_table(
        "post_stats_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("stats_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    
    # Indexes for post_stats_cache
    op.create_index("ix_post_stats_cache_post_id", "post_stats_cache", ["post_id"], unique=True)
    op.create_index("ix_post_stats_cache_expires_at", "post_stats_cache", ["expires_at"])
    
    # Grant permissions to API worker user
    # Note: The API worker user is typically named "api_worker" or from DB_API_WORKER_USER env var
    import os
    api_worker_user = os.getenv("DB_API_WORKER_USER", "api_worker")
    op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE view_events TO "{api_worker_user}"')
    op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE post_stats_daily TO "{api_worker_user}"')
    op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE post_stats_cache TO "{api_worker_user}"')
    op.execute(f'GRANT USAGE, SELECT ON SEQUENCE post_stats_daily_id_seq TO "{api_worker_user}"')
    op.execute(f'GRANT USAGE, SELECT ON SEQUENCE post_stats_cache_id_seq TO "{api_worker_user}"')


def downgrade() -> None:
    # Drop post_stats_cache
    op.drop_index("ix_post_stats_cache_expires_at", table_name="post_stats_cache")
    op.drop_index("ix_post_stats_cache_post_id", table_name="post_stats_cache")
    op.drop_table("post_stats_cache")
    
    # Drop post_stats_daily
    op.drop_constraint("uq_post_stats_daily_post_date", "post_stats_daily", type_="unique")
    op.drop_index("ix_post_stats_daily_post_date", table_name="post_stats_daily")
    op.drop_index("ix_post_stats_daily_date", table_name="post_stats_daily")
    op.drop_index("ix_post_stats_daily_post_id", table_name="post_stats_daily")
    op.drop_table("post_stats_daily")
    
    # Drop view_events
    op.drop_index("ix_view_events_view_type", table_name="view_events")
    op.drop_index("ix_view_events_device_type", table_name="view_events")
    op.drop_index("ix_view_events_country_code", table_name="view_events")
    op.drop_index("ix_view_events_post_created", table_name="view_events")
    op.drop_index("ix_view_events_created_at", table_name="view_events")
    op.drop_index("ix_view_events_viewer_user_id", table_name="view_events")
    op.drop_index("ix_view_events_post_id", table_name="view_events")
    op.drop_index("ix_view_events_id", table_name="view_events")
    op.drop_table("view_events")


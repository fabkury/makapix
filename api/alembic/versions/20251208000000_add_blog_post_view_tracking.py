"""add blog post view tracking tables

Revision ID: 20251208000000
Revises: 20251204000000
Create Date: 2025-12-08 00:00:00.000000

This migration adds tables for blog post view tracking and statistics:
- blog_post_view_events: Raw view event storage (7-day retention)
- blog_post_stats_daily: Daily aggregated statistics (permanent)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20251208000000"
down_revision = "20251204000000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ========================================================================
    # BLOG POST VIEW EVENTS TABLE - Raw view event storage (7-day retention)
    # ========================================================================
    
    op.create_table(
        "blog_post_view_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("blog_post_id", sa.Integer(), sa.ForeignKey("blog_posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("viewer_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
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
    
    # Indexes for blog_post_view_events
    op.create_index("ix_blog_post_view_events_id", "blog_post_view_events", ["id"])
    op.create_index("ix_blog_post_view_events_blog_post_id", "blog_post_view_events", ["blog_post_id"])
    op.create_index("ix_blog_post_view_events_viewer_user_id", "blog_post_view_events", ["viewer_user_id"])
    op.create_index("ix_blog_post_view_events_created_at", "blog_post_view_events", ["created_at"])
    op.create_index("ix_blog_post_view_events_post_created", "blog_post_view_events", ["blog_post_id", "created_at"])
    op.create_index("ix_blog_post_view_events_country_code", "blog_post_view_events", ["country_code"])
    op.create_index("ix_blog_post_view_events_device_type", "blog_post_view_events", ["device_type"])
    op.create_index("ix_blog_post_view_events_view_type", "blog_post_view_events", ["view_type"])
    
    # ========================================================================
    # BLOG POST STATS DAILY TABLE - Daily aggregated statistics (permanent)
    # ========================================================================
    
    op.create_table(
        "blog_post_stats_daily",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("blog_post_id", sa.Integer(), sa.ForeignKey("blog_posts.id", ondelete="CASCADE"), nullable=False),
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
    
    # Indexes and constraints for blog_post_stats_daily
    op.create_index("ix_blog_post_stats_daily_blog_post_id", "blog_post_stats_daily", ["blog_post_id"])
    op.create_index("ix_blog_post_stats_daily_date", "blog_post_stats_daily", ["date"])
    op.create_index("ix_blog_post_stats_daily_post_date", "blog_post_stats_daily", ["blog_post_id", "date"])
    
    # Unique constraint to ensure one record per (blog_post_id, date)
    op.create_unique_constraint(
        "uq_blog_post_stats_daily_post_date",
        "blog_post_stats_daily",
        ["blog_post_id", "date"]
    )


def downgrade() -> None:
    # Drop blog_post_stats_daily table
    op.drop_table("blog_post_stats_daily")
    
    # Drop blog_post_view_events table
    op.drop_table("blog_post_view_events")

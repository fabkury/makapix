"""
Statistics aggregation service for blog post analytics.

Provides on-demand computation of blog post statistics with Redis caching.
Aggregates data from raw view events and daily rollups.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Cache TTL in seconds (5 minutes)
STATS_CACHE_TTL = 300


@dataclass
class DailyViewCount:
    """Daily view count data."""

    date: str  # ISO format date string
    views: int
    unique_viewers: int


@dataclass
class BlogPostStats:
    """Complete statistics for a blog post.

    Includes both "all" (including unauthenticated) and "authenticated-only" statistics.
    This allows the frontend to toggle between the two without additional API calls.
    """

    blog_post_id: str
    # "All" statistics (including unauthenticated)
    total_views: int
    unique_viewers: int
    views_by_country: dict[str, int]  # Top 10 countries
    views_by_device: dict[str, int]  # desktop, mobile, tablet, player
    views_by_type: dict[str, int]  # intentional, listing, search, widget
    daily_views: list[DailyViewCount]  # Last 30 days
    total_reactions: int
    reactions_by_emoji: dict[str, int]
    total_comments: int
    # Authenticated-only statistics
    total_views_authenticated: int
    unique_viewers_authenticated: int
    views_by_country_authenticated: dict[str, int]  # Top 10 countries
    views_by_device_authenticated: dict[str, int]  # desktop, mobile, tablet, player
    views_by_type_authenticated: dict[str, int]  # intentional, listing, search, widget
    daily_views_authenticated: list[DailyViewCount]  # Last 30 days
    total_reactions_authenticated: int
    reactions_by_emoji_authenticated: dict[str, int]
    total_comments_authenticated: int
    # Timestamps
    first_view_at: str | None  # ISO format datetime
    last_view_at: str | None  # ISO format datetime
    computed_at: str  # ISO format datetime

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["daily_views"] = [
            asdict(d) if isinstance(d, DailyViewCount) else d for d in self.daily_views
        ]
        result["daily_views_authenticated"] = [
            asdict(d) if isinstance(d, DailyViewCount) else d
            for d in self.daily_views_authenticated
        ]
        return result


class BlogPostStatsService:
    """
    Service for computing and caching blog post statistics.

    Statistics are computed on-demand and cached in Redis for 5 minutes.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_blog_post_stats(self, blog_post_id: int) -> BlogPostStats | None:
        """
        Get statistics for a blog post.

        Checks Redis cache first, then computes if cache miss.

        Args:
            blog_post_id: Integer ID of the blog post

        Returns:
            BlogPostStats object or None if blog post doesn't exist
        """
        from ..cache import cache_get, cache_set
        from .. import models

        # Verify blog post exists
        blog_post = (
            self.db.query(models.BlogPost)
            .filter(models.BlogPost.id == blog_post_id)
            .first()
        )
        if not blog_post:
            return None

        # Check Redis cache
        cache_key = f"blog_post_stats:{blog_post_id}"
        cached_data = cache_get(cache_key)
        if cached_data:
            logger.debug(f"Stats cache hit for blog post {blog_post_id}")
            return self._dict_to_stats(cached_data)

        # Compute fresh stats
        logger.debug(f"Stats cache miss for blog post {blog_post_id}, computing...")
        stats = self._compute_stats(blog_post_id)

        # Cache the result
        cache_set(cache_key, stats.to_dict(), ttl=STATS_CACHE_TTL)

        return stats

    def invalidate_cache(self, blog_post_id: int) -> None:
        """
        Invalidate the stats cache for a blog post.

        Should be called when a blog post receives new views, reactions, or comments.
        """
        from ..cache import cache_delete

        cache_key = f"blog_post_stats:{blog_post_id}"
        cache_delete(cache_key)

    def _compute_stats(self, blog_post_id: int) -> BlogPostStats:
        """
        Compute statistics for a blog post from the database.

        Aggregates data from:
        - blog_post_view_events table (last 7 days of raw events)
        - blog_post_stats_daily table (older aggregated data)
        - blog_post_reactions table
        - blog_post_comments table
        """
        from .. import models

        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        # ===== VIEW STATISTICS =====

        # Get raw view events from the last 7 days
        recent_views = (
            self.db.query(models.BlogPostViewEvent)
            .filter(
                models.BlogPostViewEvent.blog_post_id == blog_post_id,
                models.BlogPostViewEvent.created_at >= seven_days_ago,
            )
            .all()
        )

        # Get daily aggregates for older data (8-30 days ago)
        daily_stats = (
            self.db.query(models.BlogPostStatsDaily)
            .filter(
                models.BlogPostStatsDaily.blog_post_id == blog_post_id,
                models.BlogPostStatsDaily.date >= thirty_days_ago.date(),
                models.BlogPostStatsDaily.date < seven_days_ago.date(),
            )
            .all()
        )

        # Separate authenticated and unauthenticated views
        authenticated_views = [v for v in recent_views if v.viewer_user_id is not None]

        # Aggregate total views and unique viewers (all)
        total_views = len(recent_views)
        unique_ip_hashes = set(v.viewer_ip_hash for v in recent_views)
        unique_viewers = len(unique_ip_hashes)

        # Aggregate authenticated-only views and unique viewers
        total_views_authenticated = len(authenticated_views)
        unique_ip_hashes_authenticated = set(
            v.viewer_ip_hash for v in authenticated_views
        )
        unique_viewers_authenticated = len(unique_ip_hashes_authenticated)

        # Add older aggregated data (all)
        for ds in daily_stats:
            total_views += ds.total_views
            unique_viewers += (
                ds.unique_viewers
            )  # Note: may slightly overcount across boundaries

        # Aggregate views by country (all)
        views_by_country: dict[str, int] = {}
        for v in recent_views:
            if v.country_code:
                views_by_country[v.country_code] = (
                    views_by_country.get(v.country_code, 0) + 1
                )
        for ds in daily_stats:
            for country, count in (ds.views_by_country or {}).items():
                views_by_country[country] = views_by_country.get(country, 0) + count

        # Sort by count and keep top 10
        views_by_country = dict(
            sorted(views_by_country.items(), key=lambda x: -x[1])[:10]
        )

        # Aggregate views by country (authenticated only)
        views_by_country_authenticated: dict[str, int] = {}
        for v in authenticated_views:
            if v.country_code:
                views_by_country_authenticated[v.country_code] = (
                    views_by_country_authenticated.get(v.country_code, 0) + 1
                )

        # Sort by count and keep top 10
        views_by_country_authenticated = dict(
            sorted(views_by_country_authenticated.items(), key=lambda x: -x[1])[:10]
        )

        # Aggregate views by device (all)
        views_by_device: dict[str, int] = {}
        for v in recent_views:
            views_by_device[v.device_type] = views_by_device.get(v.device_type, 0) + 1
        for ds in daily_stats:
            for device, count in (ds.views_by_device or {}).items():
                views_by_device[device] = views_by_device.get(device, 0) + count

        # Aggregate views by device (authenticated only)
        views_by_device_authenticated: dict[str, int] = {}
        for v in authenticated_views:
            views_by_device_authenticated[v.device_type] = (
                views_by_device_authenticated.get(v.device_type, 0) + 1
            )

        # Aggregate views by type (all)
        views_by_type: dict[str, int] = {}
        for v in recent_views:
            views_by_type[v.view_type] = views_by_type.get(v.view_type, 0) + 1
        for ds in daily_stats:
            for vtype, count in (ds.views_by_type or {}).items():
                views_by_type[vtype] = views_by_type.get(vtype, 0) + count

        # Aggregate views by type (authenticated only)
        views_by_type_authenticated: dict[str, int] = {}
        for v in authenticated_views:
            views_by_type_authenticated[v.view_type] = (
                views_by_type_authenticated.get(v.view_type, 0) + 1
            )

        # ===== DAILY VIEW TRENDS (last 30 days) =====

        daily_views: list[DailyViewCount] = []

        # Initialize all 30 days with zeros
        for i in range(30):
            day = (now - timedelta(days=i)).date()
            daily_views.append(
                DailyViewCount(date=day.isoformat(), views=0, unique_viewers=0)
            )

        # Create lookup dict for daily views
        daily_lookup = {d.date: d for d in daily_views}

        # Fill in data from recent views (last 7 days) - all
        views_by_day: dict[str, list] = {}
        for v in recent_views:
            day_str = v.created_at.date().isoformat()
            if day_str not in views_by_day:
                views_by_day[day_str] = []
            views_by_day[day_str].append(v)

        for day_str, views in views_by_day.items():
            if day_str in daily_lookup:
                daily_lookup[day_str].views = len(views)
                daily_lookup[day_str].unique_viewers = len(
                    set(v.viewer_ip_hash for v in views)
                )

        # Fill in data from daily aggregates (older than 7 days)
        for ds in daily_stats:
            day_str = ds.date.isoformat()
            if day_str in daily_lookup:
                daily_lookup[day_str].views = ds.total_views
                daily_lookup[day_str].unique_viewers = ds.unique_viewers

        # Sort by date ascending (oldest first)
        daily_views.sort(key=lambda x: x.date)

        # ===== DAILY VIEW TRENDS AUTHENTICATED (last 30 days) =====

        daily_views_authenticated: list[DailyViewCount] = []

        # Initialize all 30 days with zeros
        for i in range(30):
            day = (now - timedelta(days=i)).date()
            daily_views_authenticated.append(
                DailyViewCount(date=day.isoformat(), views=0, unique_viewers=0)
            )

        # Create lookup dict for daily authenticated views
        daily_lookup_authenticated = {d.date: d for d in daily_views_authenticated}

        # Fill in data from authenticated views (last 7 days)
        views_by_day_authenticated: dict[str, list] = {}
        for v in authenticated_views:
            day_str = v.created_at.date().isoformat()
            if day_str not in views_by_day_authenticated:
                views_by_day_authenticated[day_str] = []
            views_by_day_authenticated[day_str].append(v)

        for day_str, views in views_by_day_authenticated.items():
            if day_str in daily_lookup_authenticated:
                daily_lookup_authenticated[day_str].views = len(views)
                daily_lookup_authenticated[day_str].unique_viewers = len(
                    set(v.viewer_ip_hash for v in views)
                )

        # Sort by date ascending (oldest first)
        daily_views_authenticated.sort(key=lambda x: x.date)

        # ===== FIRST AND LAST VIEW TIMESTAMPS =====

        first_view_at = None
        last_view_at = None

        if recent_views:
            sorted_views = sorted(recent_views, key=lambda v: v.created_at)
            last_view_at = sorted_views[-1].created_at.isoformat()

            # Check if we have older data
            oldest_daily = (
                self.db.query(models.BlogPostStatsDaily)
                .filter(
                    models.BlogPostStatsDaily.blog_post_id == blog_post_id,
                    models.BlogPostStatsDaily.total_views > 0,
                )
                .order_by(models.BlogPostStatsDaily.date.asc())
                .first()
            )

            if oldest_daily:
                first_view_at = datetime.combine(
                    oldest_daily.date, datetime.min.time(), tzinfo=timezone.utc
                ).isoformat()
            else:
                first_view_at = sorted_views[0].created_at.isoformat()
        elif daily_stats:
            sorted_daily = sorted(daily_stats, key=lambda d: d.date)
            if sorted_daily:
                first_view_at = datetime.combine(
                    sorted_daily[0].date, datetime.min.time(), tzinfo=timezone.utc
                ).isoformat()
                last_view_at = datetime.combine(
                    sorted_daily[-1].date,
                    datetime.max.time().replace(microsecond=0),
                    tzinfo=timezone.utc,
                ).isoformat()

        # ===== REACTION STATISTICS =====

        reactions = (
            self.db.query(models.BlogPostReaction)
            .filter(models.BlogPostReaction.blog_post_id == blog_post_id)
            .all()
        )

        # Separate authenticated and unauthenticated reactions
        authenticated_reactions = [r for r in reactions if r.user_id is not None]

        total_reactions = len(reactions)
        reactions_by_emoji: dict[str, int] = {}
        for r in reactions:
            reactions_by_emoji[r.emoji] = reactions_by_emoji.get(r.emoji, 0) + 1

        # Sort by count descending
        reactions_by_emoji = dict(
            sorted(reactions_by_emoji.items(), key=lambda x: -x[1])
        )

        # Authenticated-only reactions
        total_reactions_authenticated = len(authenticated_reactions)
        reactions_by_emoji_authenticated: dict[str, int] = {}
        for r in authenticated_reactions:
            reactions_by_emoji_authenticated[r.emoji] = (
                reactions_by_emoji_authenticated.get(r.emoji, 0) + 1
            )

        # Sort by count descending
        reactions_by_emoji_authenticated = dict(
            sorted(reactions_by_emoji_authenticated.items(), key=lambda x: -x[1])
        )

        # ===== COMMENT STATISTICS =====

        comments = (
            self.db.query(models.BlogPostComment)
            .filter(
                models.BlogPostComment.blog_post_id == blog_post_id,
                models.BlogPostComment.hidden_by_mod == False,
                models.BlogPostComment.deleted_by_owner == False,
            )
            .all()
        )

        total_comments = len(comments)

        # Authenticated-only comments
        authenticated_comments = [c for c in comments if c.author_id is not None]
        total_comments_authenticated = len(authenticated_comments)

        # ===== BUILD RESULT =====

        return BlogPostStats(
            blog_post_id=str(blog_post_id),
            # All statistics
            total_views=total_views,
            unique_viewers=unique_viewers,
            views_by_country=views_by_country,
            views_by_device=views_by_device,
            views_by_type=views_by_type,
            daily_views=daily_views,
            total_reactions=total_reactions,
            reactions_by_emoji=reactions_by_emoji,
            total_comments=total_comments,
            # Authenticated-only statistics
            total_views_authenticated=total_views_authenticated,
            unique_viewers_authenticated=unique_viewers_authenticated,
            views_by_country_authenticated=views_by_country_authenticated,
            views_by_device_authenticated=views_by_device_authenticated,
            views_by_type_authenticated=views_by_type_authenticated,
            daily_views_authenticated=daily_views_authenticated,
            total_reactions_authenticated=total_reactions_authenticated,
            reactions_by_emoji_authenticated=reactions_by_emoji_authenticated,
            total_comments_authenticated=total_comments_authenticated,
            # Timestamps
            first_view_at=first_view_at,
            last_view_at=last_view_at,
            computed_at=now.isoformat(),
        )

    def _dict_to_stats(self, data: dict) -> BlogPostStats:
        """Convert dictionary back to BlogPostStats object."""
        daily_views = [
            DailyViewCount(**d) if isinstance(d, dict) else d
            for d in data.get("daily_views", [])
        ]
        daily_views_authenticated = [
            DailyViewCount(**d) if isinstance(d, dict) else d
            for d in data.get("daily_views_authenticated", [])
        ]

        return BlogPostStats(
            blog_post_id=data["blog_post_id"],
            # All statistics
            total_views=data["total_views"],
            unique_viewers=data["unique_viewers"],
            views_by_country=data["views_by_country"],
            views_by_device=data["views_by_device"],
            views_by_type=data["views_by_type"],
            daily_views=daily_views,
            total_reactions=data["total_reactions"],
            reactions_by_emoji=data["reactions_by_emoji"],
            total_comments=data["total_comments"],
            # Authenticated-only statistics
            total_views_authenticated=data.get("total_views_authenticated", 0),
            unique_viewers_authenticated=data.get("unique_viewers_authenticated", 0),
            views_by_country_authenticated=data.get(
                "views_by_country_authenticated", {}
            ),
            views_by_device_authenticated=data.get("views_by_device_authenticated", {}),
            views_by_type_authenticated=data.get("views_by_type_authenticated", {}),
            daily_views_authenticated=daily_views_authenticated,
            total_reactions_authenticated=data.get("total_reactions_authenticated", 0),
            reactions_by_emoji_authenticated=data.get(
                "reactions_by_emoji_authenticated", {}
            ),
            total_comments_authenticated=data.get("total_comments_authenticated", 0),
            # Timestamps
            first_view_at=data.get("first_view_at"),
            last_view_at=data.get("last_view_at"),
            computed_at=data["computed_at"],
        )


def get_blog_post_stats(db: Session, blog_post_id: int) -> BlogPostStats | None:
    """
    Convenience function to get blog post statistics.

    Args:
        db: Database session
        blog_post_id: Integer ID of the blog post

    Returns:
        BlogPostStats object or None if blog post doesn't exist
    """
    service = BlogPostStatsService(db)
    return service.get_blog_post_stats(blog_post_id)


def invalidate_blog_post_stats_cache(db: Session, blog_post_id: int) -> None:
    """
    Convenience function to invalidate blog post stats cache.

    Should be called when new views, reactions, or comments are added.
    """
    service = BlogPostStatsService(db)
    service.invalidate_cache(blog_post_id)

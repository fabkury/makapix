"""
Statistics aggregation service for artwork analytics.

Provides on-demand computation of post statistics with Redis caching.
Aggregates data from raw view events and daily rollups.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func, distinct, cast, Date
from sqlalchemy.orm import Session

from ..utils.view_tracking import visitor_key

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Cache TTL in seconds (5 minutes)
STATS_CACHE_TTL = 300


@dataclass
class DailyViewCount:
    """Daily view/impression count data (docs/artwork-views/ D2)."""

    date: str  # ISO format date string
    views: int  # deduped Artwork Views
    unique_viewers: int  # == views for post-redesign days; legacy for older
    impressions: int = 0  # playback exposure (never summed with views)


@dataclass
class PostStats:
    """Complete statistics for a post.

    Includes both "all" (including unauthenticated) and "authenticated-only" statistics.
    This allows the frontend to toggle between the two without additional API calls.
    """

    post_id: str
    # "All" statistics (including unauthenticated)
    total_views: int
    unique_viewers: int
    total_impressions: int
    views_by_country: dict[str, int]  # Top 10 countries
    views_by_device: dict[str, int]  # desktop, mobile, tablet, player
    views_by_type: dict[str, int]  # canonical: {"view": n, "impression": m}
    daily_views: list[DailyViewCount]  # Last 30 days
    total_reactions: int
    reactions_by_emoji: dict[str, int]
    total_comments: int
    # Authenticated-only statistics
    total_views_authenticated: int
    unique_viewers_authenticated: int
    total_impressions_authenticated: int
    views_by_country_authenticated: dict[str, int]  # Top 10 countries
    views_by_device_authenticated: dict[str, int]  # desktop, mobile, tablet, player
    views_by_type_authenticated: dict[str, int]  # canonical keys
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


class PostStatsService:
    """
    Service for computing and caching post statistics.

    Statistics are computed on-demand and cached in Redis for 5 minutes.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_post_stats(self, post_id: int) -> PostStats | None:
        """
        Get statistics for a post.

        Checks Redis cache first, then computes if cache miss.

        Args:
            post_id: Integer ID of the post

        Returns:
            PostStats object or None if post doesn't exist
        """
        from ..cache import cache_get, cache_set
        from .. import models

        # Verify post exists
        post = self.db.query(models.Post).filter(models.Post.id == post_id).first()
        if not post:
            return None

        # Check Redis cache
        cache_key = f"post_stats:{post_id}"
        cached_data = cache_get(cache_key)
        if cached_data:
            logger.debug(f"Stats cache hit for post {post_id}")
            return self._dict_to_stats(cached_data)

        # Compute fresh stats
        logger.debug(f"Stats cache miss for post {post_id}, computing...")
        stats = self._compute_stats(post_id)

        # Cache the result
        cache_set(cache_key, stats.to_dict(), ttl=STATS_CACHE_TTL)

        return stats

    def invalidate_cache(self, post_id: int) -> None:
        """
        Invalidate the stats cache for a post.

        Should be called when a post receives new views, reactions, or comments.
        """
        from ..cache import cache_delete

        cache_key = f"post_stats:{post_id}"
        cache_delete(cache_key)

    def _compute_stats(self, post_id: int) -> PostStats:
        """
        Compute statistics for a post from the database.

        Aggregates data from:
        - view_events table (last 7 days of raw events)
        - post_stats_daily table (older aggregated data)
        - reactions table
        - comments table
        """
        from .. import models

        # ===== VIEW STATISTICS (30-day window) =====
        # One stitching rule (docs/artwork-views/ D10): daily aggregate rows
        # for days <= the rollup watermark, raw events for days after it.
        # Rolled-but-retained raw rows are therefore never double-counted,
        # and there is no crack at the old "7 days" boundary.
        from .view_metrics import (
            VIEW,
            canonical_view_type,
            get_view_watermark,
            impressions_from_breakdown,
            views_from_breakdown,
        )

        now = datetime.now(timezone.utc)
        today = now.date()
        window_start = today - timedelta(days=29)  # 30 calendar days incl. today

        watermark = get_view_watermark(self.db)

        daily_stats: list = []
        if watermark is not None:
            daily_stats = (
                self.db.query(models.PostStatsDaily)
                .filter(
                    models.PostStatsDaily.post_id == post_id,
                    models.PostStatsDaily.date >= window_start,
                    models.PostStatsDaily.date <= watermark,
                )
                .all()
            )

        raw_start = window_start
        if watermark is not None and watermark + timedelta(days=1) > raw_start:
            raw_start = watermark + timedelta(days=1)
        recent_views = (
            self.db.query(models.ViewEvent)
            .filter(
                models.ViewEvent.post_id == post_id,
                models.ViewEvent.created_at
                >= datetime(
                    raw_start.year, raw_start.month, raw_start.day, tzinfo=timezone.utc
                ),
            )
            .all()
        )

        # ----- Aggregate raw (post-watermark) days with the same rules as the
        # rollup: Views deduped per Visitor per UTC day; country/device
        # breakdowns are Views-only, first event wins; Impressions counted.
        raw_days: dict[str, dict] = {}
        views_by_country: dict[str, int] = {}
        views_by_device: dict[str, int] = {}
        views_by_country_authenticated: dict[str, int] = {}
        views_by_device_authenticated: dict[str, int] = {}
        views_by_type: dict[str, int] = {"view": 0, "impression": 0}
        views_by_type_authenticated: dict[str, int] = {"view": 0, "impression": 0}
        first_raw_view = None
        last_raw_view = None

        for v in recent_views:
            event_utc = v.created_at.astimezone(timezone.utc)
            day_str = event_utc.date().isoformat()
            slot = raw_days.setdefault(
                day_str,
                {
                    "visitors": set(),
                    "auth_visitors": set(),
                    "impressions": 0,
                    "impressions_auth": 0,
                },
            )
            if canonical_view_type(v.view_type) == VIEW:
                visitor = visitor_key(v.viewer_user_id, v.viewer_ip_hash)
                if visitor not in slot["visitors"]:
                    slot["visitors"].add(visitor)
                    if v.country_code:
                        views_by_country[v.country_code] = (
                            views_by_country.get(v.country_code, 0) + 1
                        )
                    views_by_device[v.device_type] = (
                        views_by_device.get(v.device_type, 0) + 1
                    )
                    views_by_type["view"] += 1
                if (
                    v.viewer_user_id is not None
                    and visitor not in slot["auth_visitors"]
                ):
                    slot["auth_visitors"].add(visitor)
                    if v.country_code:
                        views_by_country_authenticated[v.country_code] = (
                            views_by_country_authenticated.get(v.country_code, 0) + 1
                        )
                    views_by_device_authenticated[v.device_type] = (
                        views_by_device_authenticated.get(v.device_type, 0) + 1
                    )
                    views_by_type_authenticated["view"] += 1
            else:
                slot["impressions"] += 1
                views_by_type["impression"] += 1
                if v.viewer_user_id is not None:
                    slot["impressions_auth"] += 1
                    views_by_type_authenticated["impression"] += 1
            if last_raw_view is None or event_utc > last_raw_view:
                last_raw_view = event_utc
            if first_raw_view is None or event_utc < first_raw_view:
                first_raw_view = event_utc

        # ----- Build the 30-day daily series (all + authenticated) -----
        daily_map: dict[str, DailyViewCount] = {}
        daily_map_auth: dict[str, DailyViewCount] = {}
        for i in range(30):
            day_str = (window_start + timedelta(days=i)).isoformat()
            daily_map[day_str] = DailyViewCount(
                date=day_str, views=0, unique_viewers=0, impressions=0
            )
            daily_map_auth[day_str] = DailyViewCount(
                date=day_str, views=0, unique_viewers=0, impressions=0
            )

        # Daily rows (legacy rows are read through the breakdown helpers;
        # their country/device breakdowns include impressions — an accepted
        # approximation that ages out of the window).
        for ds in daily_stats:
            day_str = ds.date.isoformat()
            row_views = views_from_breakdown(ds.views_by_type)
            row_impressions = impressions_from_breakdown(ds.views_by_type)
            row_views_auth = views_from_breakdown(ds.views_by_type_authenticated)
            row_impressions_auth = impressions_from_breakdown(
                ds.views_by_type_authenticated
            )
            if day_str in daily_map:
                daily_map[day_str].views = row_views
                daily_map[day_str].unique_viewers = ds.unique_viewers
                daily_map[day_str].impressions = row_impressions
                daily_map_auth[day_str].views = row_views_auth
                daily_map_auth[day_str].unique_viewers = ds.unique_viewers_authenticated
                daily_map_auth[day_str].impressions = row_impressions_auth

            views_by_type["view"] += row_views
            views_by_type["impression"] += row_impressions
            views_by_type_authenticated["view"] += row_views_auth
            views_by_type_authenticated["impression"] += row_impressions_auth
            for country, count in (ds.views_by_country or {}).items():
                views_by_country[country] = views_by_country.get(country, 0) + count
            for device, count in (ds.views_by_device or {}).items():
                views_by_device[device] = views_by_device.get(device, 0) + count
            for country, count in (ds.views_by_country_authenticated or {}).items():
                views_by_country_authenticated[country] = (
                    views_by_country_authenticated.get(country, 0) + count
                )
            for device, count in (ds.views_by_device_authenticated or {}).items():
                views_by_device_authenticated[device] = (
                    views_by_device_authenticated.get(device, 0) + count
                )

        # Raw days overlay
        for day_str, slot in raw_days.items():
            if day_str in daily_map:
                daily_map[day_str].views = len(slot["visitors"])
                daily_map[day_str].unique_viewers = len(slot["visitors"])
                daily_map[day_str].impressions = slot["impressions"]
                daily_map_auth[day_str].views = len(slot["auth_visitors"])
                daily_map_auth[day_str].unique_viewers = len(slot["auth_visitors"])
                daily_map_auth[day_str].impressions = slot["impressions_auth"]

        daily_views = sorted(daily_map.values(), key=lambda x: x.date)
        daily_views_authenticated = sorted(
            daily_map_auth.values(), key=lambda x: x.date
        )

        # ----- Window totals (cross-day uniques are a sum of daily uniques —
        # approximate by design, labeled as such in the UI per D13) -----
        total_views = sum(d.views for d in daily_views)
        unique_viewers = sum(d.unique_viewers for d in daily_views)
        total_impressions = sum(d.impressions for d in daily_views)
        total_views_authenticated = sum(d.views for d in daily_views_authenticated)
        unique_viewers_authenticated = sum(
            d.unique_viewers for d in daily_views_authenticated
        )
        total_impressions_authenticated = sum(
            d.impressions for d in daily_views_authenticated
        )

        # Sort country breakdowns by count and keep top 10
        views_by_country = dict(
            sorted(views_by_country.items(), key=lambda x: -x[1])[:10]
        )
        views_by_country_authenticated = dict(
            sorted(views_by_country_authenticated.items(), key=lambda x: -x[1])[:10]
        )

        # ===== FIRST AND LAST VIEW TIMESTAMPS =====

        first_view_at = None
        last_view_at = None

        # Oldest daily row with any activity (all-time, not window-bounded)
        oldest_daily = (
            self.db.query(models.PostStatsDaily)
            .filter(
                models.PostStatsDaily.post_id == post_id,
                models.PostStatsDaily.total_views > 0,
            )
            .order_by(models.PostStatsDaily.date.asc())
            .first()
        )

        if oldest_daily:
            first_view_at = datetime.combine(
                oldest_daily.date, datetime.min.time(), tzinfo=timezone.utc
            ).isoformat()
        elif first_raw_view is not None:
            first_view_at = first_raw_view.isoformat()

        if last_raw_view is not None:
            last_view_at = last_raw_view.isoformat()
        elif daily_stats:
            latest_daily = max(daily_stats, key=lambda d: d.date)
            last_view_at = datetime.combine(
                latest_daily.date,
                datetime.max.time().replace(microsecond=0),
                tzinfo=timezone.utc,
            ).isoformat()

        # ===== REACTION STATISTICS =====

        reactions = (
            self.db.query(models.Reaction)
            .filter(models.Reaction.post_id == post_id)
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
            self.db.query(models.Comment)
            .filter(
                models.Comment.post_id == post_id,
                models.Comment.hidden_by_mod == False,
                models.Comment.deleted_by_owner == False,
                models.Comment.deleted_by_mod == False,
            )
            .all()
        )

        total_comments = len(comments)

        # Authenticated-only comments
        authenticated_comments = [c for c in comments if c.author_id is not None]
        total_comments_authenticated = len(authenticated_comments)

        # ===== BUILD RESULT =====

        return PostStats(
            post_id=str(post_id),
            # All statistics
            total_views=total_views,
            unique_viewers=unique_viewers,
            total_impressions=total_impressions,
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
            total_impressions_authenticated=total_impressions_authenticated,
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

    def _dict_to_stats(self, data: dict) -> PostStats:
        """Convert dictionary back to PostStats object."""
        daily_views = [
            DailyViewCount(**d) if isinstance(d, dict) else d
            for d in data.get("daily_views", [])
        ]
        daily_views_authenticated = [
            DailyViewCount(**d) if isinstance(d, dict) else d
            for d in data.get("daily_views_authenticated", [])
        ]

        return PostStats(
            post_id=data["post_id"],
            # All statistics
            total_views=data["total_views"],
            unique_viewers=data["unique_viewers"],
            total_impressions=data.get("total_impressions", 0),
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
            total_impressions_authenticated=data.get(
                "total_impressions_authenticated", 0
            ),
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


def get_post_stats(db: Session, post_id: int) -> PostStats | None:
    """
    Convenience function to get post statistics.

    Args:
        db: Database session
        post_id: Integer ID of the post

    Returns:
        PostStats object or None if post doesn't exist
    """
    service = PostStatsService(db)
    return service.get_post_stats(post_id)


def invalidate_post_stats_cache(db: Session, post_id: int) -> None:
    """
    Convenience function to invalidate post stats cache.

    Should be called when new views, reactions, or comments are added.
    """
    service = PostStatsService(db)
    service.invalidate_cache(post_id)

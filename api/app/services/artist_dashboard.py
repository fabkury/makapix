"""
Artist Dashboard statistics service.

Provides aggregated statistics across all posts for an artist,
as well as paginated post-level statistics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.orm import Session

from ..utils.view_tracking import visitor_key

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class ArtistStats:
    """Aggregated statistics for an artist across all their posts."""

    user_id: int
    user_key: str
    total_posts: int
    # Aggregated view statistics (all), 30-day window
    total_views: int
    unique_viewers: int
    total_impressions: int
    views_by_country: dict[str, int]  # Top 10 countries
    views_by_device: dict[str, int]  # desktop, mobile, tablet, player
    daily_views: list[dict]  # 30 days of {date, views, unique_viewers, impressions}
    # Aggregated reactions and comments
    total_reactions: int
    reactions_by_emoji: dict[str, int]
    total_comments: int
    # Authenticated-only statistics
    total_views_authenticated: int
    unique_viewers_authenticated: int
    total_impressions_authenticated: int
    views_by_country_authenticated: dict[str, int]
    views_by_device_authenticated: dict[str, int]
    daily_views_authenticated: list[dict]
    total_reactions_authenticated: int
    reactions_by_emoji_authenticated: dict[str, int]
    total_comments_authenticated: int
    # Timestamps
    first_post_at: str | None
    latest_post_at: str | None
    computed_at: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "user_id": self.user_id,
            "user_key": str(self.user_key),
            "total_posts": self.total_posts,
            "total_views": self.total_views,
            "unique_viewers": self.unique_viewers,
            "total_impressions": self.total_impressions,
            "views_by_country": self.views_by_country,
            "views_by_device": self.views_by_device,
            "daily_views": self.daily_views,
            "total_reactions": self.total_reactions,
            "reactions_by_emoji": self.reactions_by_emoji,
            "total_comments": self.total_comments,
            "total_views_authenticated": self.total_views_authenticated,
            "unique_viewers_authenticated": self.unique_viewers_authenticated,
            "total_impressions_authenticated": self.total_impressions_authenticated,
            "views_by_country_authenticated": self.views_by_country_authenticated,
            "views_by_device_authenticated": self.views_by_device_authenticated,
            "daily_views_authenticated": self.daily_views_authenticated,
            "total_reactions_authenticated": self.total_reactions_authenticated,
            "reactions_by_emoji_authenticated": self.reactions_by_emoji_authenticated,
            "total_comments_authenticated": self.total_comments_authenticated,
            "first_post_at": self.first_post_at,
            "latest_post_at": self.latest_post_at,
            "computed_at": self.computed_at,
        }


@dataclass
class PostStatsListItem:
    """Simplified post statistics for list view in dashboard."""

    post_id: int
    public_sqid: str
    title: str
    created_at: str
    # View statistics (all), 30-day window
    total_views: int
    unique_viewers: int
    total_impressions: int
    # Reactions and comments
    total_reactions: int
    total_comments: int
    # Authenticated-only statistics
    total_views_authenticated: int
    unique_viewers_authenticated: int
    total_impressions_authenticated: int
    total_reactions_authenticated: int
    total_comments_authenticated: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "post_id": self.post_id,
            "public_sqid": self.public_sqid,
            "title": self.title,
            "created_at": self.created_at,
            "total_views": self.total_views,
            "unique_viewers": self.unique_viewers,
            "total_impressions": self.total_impressions,
            "total_reactions": self.total_reactions,
            "total_comments": self.total_comments,
            "total_views_authenticated": self.total_views_authenticated,
            "unique_viewers_authenticated": self.unique_viewers_authenticated,
            "total_impressions_authenticated": self.total_impressions_authenticated,
            "total_reactions_authenticated": self.total_reactions_authenticated,
            "total_comments_authenticated": self.total_comments_authenticated,
        }


class ArtistDashboardService:
    """
    Service for computing artist dashboard statistics.

    Aggregates statistics across all posts by an artist.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_artist_stats(self, user_key: UUID) -> ArtistStats | None:
        """
        Get aggregated statistics for an artist across all their posts.

        Args:
            user_key: UUID of the user

        Returns:
            ArtistStats object or None if user doesn't exist
        """
        from .. import models

        # Verify user exists
        user = (
            self.db.query(models.User).filter(models.User.user_key == user_key).first()
        )
        if not user:
            return None

        # Get all posts by this user
        posts = self.db.query(models.Post).filter(models.Post.owner_id == user.id).all()

        if not posts:
            # Return empty stats if user has no posts
            return ArtistStats(
                user_id=user.id,
                user_key=str(user.user_key),
                total_posts=0,
                total_views=0,
                unique_viewers=0,
                total_impressions=0,
                views_by_country={},
                views_by_device={},
                daily_views=[],
                total_reactions=0,
                reactions_by_emoji={},
                total_comments=0,
                total_views_authenticated=0,
                unique_viewers_authenticated=0,
                total_impressions_authenticated=0,
                views_by_country_authenticated={},
                views_by_device_authenticated={},
                daily_views_authenticated=[],
                total_reactions_authenticated=0,
                reactions_by_emoji_authenticated={},
                total_comments_authenticated=0,
                first_post_at=None,
                latest_post_at=None,
                computed_at=datetime.now(timezone.utc).isoformat(),
            )

        post_ids = [post.id for post in posts]

        # Get timestamps
        first_post = min(posts, key=lambda p: p.created_at)
        latest_post = max(posts, key=lambda p: p.created_at)

        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)

        # ===== VIEW STATISTICS (30-day window) =====
        # One stitching rule (docs/artwork-views/ D10): daily aggregate rows
        # for days <= the rollup watermark, raw events for days after it.
        # Artist-level numbers are sums of per-(post, day) figures, so
        # unique-viewer sums are approximate across days AND posts (labeled
        # as such in the UI per D13).
        from .view_metrics import (
            VIEW,
            canonical_view_type,
            get_view_watermark,
            impressions_from_breakdown,
            views_from_breakdown,
        )

        today = now.date()
        window_start = today - timedelta(days=29)  # 30 calendar days incl. today

        watermark = get_view_watermark(self.db)

        daily_stats: list = []
        if watermark is not None:
            daily_stats = (
                self.db.query(models.PostStatsDaily)
                .filter(
                    models.PostStatsDaily.post_id.in_(post_ids),
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
                models.ViewEvent.post_id.in_(post_ids),
                models.ViewEvent.created_at
                >= datetime(
                    raw_start.year, raw_start.month, raw_start.day, tzinfo=timezone.utc
                ),
            )
            .all()
        )

        # Daily series slots (all + authenticated): [views, uniques, impressions]
        day_slots: dict[str, list[int]] = {}
        day_slots_auth: dict[str, list[int]] = {}
        for i in range(30):
            day_str = (window_start + timedelta(days=i)).isoformat()
            day_slots[day_str] = [0, 0, 0]
            day_slots_auth[day_str] = [0, 0, 0]

        views_by_country: dict[str, int] = {}
        views_by_device: dict[str, int] = {}
        views_by_country_authenticated: dict[str, int] = {}
        views_by_device_authenticated: dict[str, int] = {}

        # ----- Rolled days: merge daily rows (legacy rows read through the
        # breakdown helpers; the authenticated columns are used too — the old
        # code skipped days 8-30 for authenticated stats based on a stale
        # assumption that the columns didn't exist).
        for ds in daily_stats:
            day_str = ds.date.isoformat()
            row_views = views_from_breakdown(ds.views_by_type)
            row_impressions = impressions_from_breakdown(ds.views_by_type)
            row_views_auth = views_from_breakdown(ds.views_by_type_authenticated)
            row_impressions_auth = impressions_from_breakdown(
                ds.views_by_type_authenticated
            )
            if day_str in day_slots:
                day_slots[day_str][0] += row_views
                day_slots[day_str][1] += ds.unique_viewers
                day_slots[day_str][2] += row_impressions
                day_slots_auth[day_str][0] += row_views_auth
                day_slots_auth[day_str][1] += ds.unique_viewers_authenticated
                day_slots_auth[day_str][2] += row_impressions_auth
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

        # ----- Raw (post-watermark) days: same rules as the rollup — Views
        # deduped per Visitor per (post, UTC day); breakdowns Views-only.
        raw_seen: set[tuple] = set()
        raw_seen_auth: set[tuple] = set()
        for v in recent_views:
            event_utc = v.created_at.astimezone(timezone.utc)
            day_str = event_utc.date().isoformat()
            if day_str not in day_slots:
                continue
            if canonical_view_type(v.view_type) == VIEW:
                visitor = visitor_key(v.viewer_user_id, v.viewer_ip_hash)
                slot_key = (v.post_id, day_str, visitor)
                if slot_key not in raw_seen:
                    raw_seen.add(slot_key)
                    day_slots[day_str][0] += 1
                    day_slots[day_str][1] += 1
                    if v.country_code:
                        views_by_country[v.country_code] = (
                            views_by_country.get(v.country_code, 0) + 1
                        )
                    views_by_device[v.device_type] = (
                        views_by_device.get(v.device_type, 0) + 1
                    )
                if v.viewer_user_id is not None and slot_key not in raw_seen_auth:
                    raw_seen_auth.add(slot_key)
                    day_slots_auth[day_str][0] += 1
                    day_slots_auth[day_str][1] += 1
                    if v.country_code:
                        views_by_country_authenticated[v.country_code] = (
                            views_by_country_authenticated.get(v.country_code, 0) + 1
                        )
                    views_by_device_authenticated[v.device_type] = (
                        views_by_device_authenticated.get(v.device_type, 0) + 1
                    )
            else:
                day_slots[day_str][2] += 1
                if v.viewer_user_id is not None:
                    day_slots_auth[day_str][2] += 1

        # ----- Series + window totals -----
        daily_views = [
            {
                "date": day_str,
                "views": slot[0],
                "unique_viewers": slot[1],
                "impressions": slot[2],
            }
            for day_str, slot in sorted(day_slots.items())
        ]
        daily_views_authenticated = [
            {
                "date": day_str,
                "views": slot[0],
                "unique_viewers": slot[1],
                "impressions": slot[2],
            }
            for day_str, slot in sorted(day_slots_auth.items())
        ]

        total_views = sum(d["views"] for d in daily_views)
        unique_viewers = sum(d["unique_viewers"] for d in daily_views)
        total_impressions = sum(d["impressions"] for d in daily_views)
        total_views_authenticated = sum(d["views"] for d in daily_views_authenticated)
        unique_viewers_authenticated = sum(
            d["unique_viewers"] for d in daily_views_authenticated
        )
        total_impressions_authenticated = sum(
            d["impressions"] for d in daily_views_authenticated
        )

        # Sort country breakdowns by count and keep top 10
        views_by_country = dict(
            sorted(views_by_country.items(), key=lambda x: -x[1])[:10]
        )
        views_by_country_authenticated = dict(
            sorted(views_by_country_authenticated.items(), key=lambda x: -x[1])[:10]
        )

        # ===== REACTION STATISTICS =====

        reactions = (
            self.db.query(models.Reaction)
            .filter(models.Reaction.post_id.in_(post_ids))
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
                models.Comment.post_id.in_(post_ids),
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

        return ArtistStats(
            user_id=user.id,
            user_key=str(user.user_key),
            total_posts=len(posts),
            # All statistics
            total_views=total_views,
            unique_viewers=unique_viewers,
            total_impressions=total_impressions,
            views_by_country=views_by_country,
            views_by_device=views_by_device,
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
            daily_views_authenticated=daily_views_authenticated,
            total_reactions_authenticated=total_reactions_authenticated,
            reactions_by_emoji_authenticated=reactions_by_emoji_authenticated,
            total_comments_authenticated=total_comments_authenticated,
            # Timestamps
            first_post_at=first_post.created_at.isoformat(),
            latest_post_at=latest_post.created_at.isoformat(),
            computed_at=now.isoformat(),
        )

    def get_posts_stats_list(
        self, user_key: UUID, limit: int = 20, offset: int = 0
    ) -> list[PostStatsListItem]:
        """
        Get paginated list of posts with simplified statistics for an artist.

        Args:
            user_key: UUID of the user
            limit: Maximum number of posts to return
            offset: Number of posts to skip

        Returns:
            List of PostStatsListItem objects
        """
        from .. import models
        from ..services.stats import PostStatsService

        # Get user
        user = (
            self.db.query(models.User).filter(models.User.user_key == user_key).first()
        )
        if not user:
            return []

        # Get paginated posts
        posts = (
            self.db.query(models.Post)
            .filter(models.Post.owner_id == user.id)
            .order_by(models.Post.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        if not posts:
            return []

        # Get stats for each post
        stats_service = PostStatsService(self.db)
        result = []

        for post in posts:
            # Get full stats for post
            stats = stats_service.get_post_stats(post.id)

            if stats:
                result.append(
                    PostStatsListItem(
                        post_id=post.id,
                        public_sqid=post.public_sqid or "",
                        title=post.title,
                        created_at=post.created_at.isoformat(),
                        total_views=stats.total_views,
                        unique_viewers=stats.unique_viewers,
                        total_impressions=stats.total_impressions,
                        total_reactions=stats.total_reactions,
                        total_comments=stats.total_comments,
                        total_views_authenticated=stats.total_views_authenticated,
                        unique_viewers_authenticated=stats.unique_viewers_authenticated,
                        total_impressions_authenticated=stats.total_impressions_authenticated,
                        total_reactions_authenticated=stats.total_reactions_authenticated,
                        total_comments_authenticated=stats.total_comments_authenticated,
                    )
                )
            else:
                # If stats computation failed, return zeros
                result.append(
                    PostStatsListItem(
                        post_id=post.id,
                        public_sqid=post.public_sqid or "",
                        title=post.title,
                        created_at=post.created_at.isoformat(),
                        total_views=0,
                        unique_viewers=0,
                        total_impressions=0,
                        total_reactions=0,
                        total_comments=0,
                        total_views_authenticated=0,
                        unique_viewers_authenticated=0,
                        total_impressions_authenticated=0,
                        total_reactions_authenticated=0,
                        total_comments_authenticated=0,
                    )
                )

        return result


def get_artist_stats(db: Session, user_key: UUID) -> ArtistStats | None:
    """
    Convenience function to get artist statistics.

    Args:
        db: Database session
        user_key: UUID of the user

    Returns:
        ArtistStats object or None if user doesn't exist
    """
    service = ArtistDashboardService(db)
    return service.get_artist_stats(user_key)


def get_posts_stats_list(
    db: Session, user_key: UUID, limit: int = 20, offset: int = 0
) -> list[PostStatsListItem]:
    """
    Convenience function to get paginated list of post statistics.

    Args:
        db: Database session
        user_key: UUID of the user
        limit: Maximum number of posts to return
        offset: Number of posts to skip

    Returns:
        List of PostStatsListItem objects
    """
    service = ArtistDashboardService(db)
    return service.get_posts_stats_list(user_key, limit, offset)

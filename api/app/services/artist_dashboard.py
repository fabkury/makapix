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

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class ArtistStats:
    """Aggregated statistics for an artist across all their posts."""

    user_id: int
    user_key: str
    total_posts: int
    # Aggregated view statistics (all)
    total_views: int
    unique_viewers: int
    views_by_country: dict[str, int]  # Top 10 countries
    views_by_device: dict[str, int]  # desktop, mobile, tablet, player
    # Aggregated reactions and comments
    total_reactions: int
    reactions_by_emoji: dict[str, int]
    total_comments: int
    # Authenticated-only statistics
    total_views_authenticated: int
    unique_viewers_authenticated: int
    views_by_country_authenticated: dict[str, int]
    views_by_device_authenticated: dict[str, int]
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
            "views_by_country": self.views_by_country,
            "views_by_device": self.views_by_device,
            "total_reactions": self.total_reactions,
            "reactions_by_emoji": self.reactions_by_emoji,
            "total_comments": self.total_comments,
            "total_views_authenticated": self.total_views_authenticated,
            "unique_viewers_authenticated": self.unique_viewers_authenticated,
            "views_by_country_authenticated": self.views_by_country_authenticated,
            "views_by_device_authenticated": self.views_by_device_authenticated,
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
    # View statistics (all)
    total_views: int
    unique_viewers: int
    # Reactions and comments
    total_reactions: int
    total_comments: int
    # Authenticated-only statistics
    total_views_authenticated: int
    unique_viewers_authenticated: int
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
            "total_reactions": self.total_reactions,
            "total_comments": self.total_comments,
            "total_views_authenticated": self.total_views_authenticated,
            "unique_viewers_authenticated": self.unique_viewers_authenticated,
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
                views_by_country={},
                views_by_device={},
                total_reactions=0,
                reactions_by_emoji={},
                total_comments=0,
                total_views_authenticated=0,
                unique_viewers_authenticated=0,
                views_by_country_authenticated={},
                views_by_device_authenticated={},
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

        # ===== VIEW STATISTICS =====

        # Get recent view events (last 7 days) for all posts
        recent_views = (
            self.db.query(models.ViewEvent)
            .filter(
                models.ViewEvent.post_id.in_(post_ids),
                models.ViewEvent.created_at >= seven_days_ago,
            )
            .all()
        )

        # Get daily aggregates for older data (8-30 days ago)
        daily_stats = (
            self.db.query(models.PostStatsDaily)
            .filter(
                models.PostStatsDaily.post_id.in_(post_ids),
                models.PostStatsDaily.date >= thirty_days_ago.date(),
                models.PostStatsDaily.date < seven_days_ago.date(),
            )
            .all()
        )

        # Separate authenticated and unauthenticated views
        authenticated_views = [v for v in recent_views if v.viewer_user_id is not None]

        # Aggregate total views and unique viewers (all)
        # Note: For unique viewers across days, we collect all unique IP hashes
        # from recent views. For daily_stats, we sum the views but note that
        # unique_viewers is an approximation as we can't deduplicate across days
        # from aggregated data.
        total_views = len(recent_views)
        unique_ip_hashes = set(v.viewer_ip_hash for v in recent_views)
        unique_viewers = len(unique_ip_hashes)

        # Aggregate authenticated-only views and unique viewers from recent views
        total_views_authenticated = len(authenticated_views)
        unique_ip_hashes_authenticated = set(
            v.viewer_ip_hash for v in authenticated_views
        )
        unique_viewers_authenticated = len(unique_ip_hashes_authenticated)

        # Add older aggregated data (all)
        # Note: unique_viewers from daily_stats is summed as an approximation
        # since we can't deduplicate IP hashes across aggregated days
        for ds in daily_stats:
            total_views += ds.total_views
            unique_viewers += ds.unique_viewers  # This is an approximation

        # For authenticated stats from daily_stats, we note that PostStatsDaily
        # doesn't currently separate authenticated/unauthenticated data.
        # Therefore, authenticated stats are based only on recent_views.
        # This is acceptable for a 30-day window as we keep 7 days of raw events.

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
            views_by_country=views_by_country,
            views_by_device=views_by_device,
            total_reactions=total_reactions,
            reactions_by_emoji=reactions_by_emoji,
            total_comments=total_comments,
            # Authenticated-only statistics
            total_views_authenticated=total_views_authenticated,
            unique_viewers_authenticated=unique_viewers_authenticated,
            views_by_country_authenticated=views_by_country_authenticated,
            views_by_device_authenticated=views_by_device_authenticated,
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
                        total_reactions=stats.total_reactions,
                        total_comments=stats.total_comments,
                        total_views_authenticated=stats.total_views_authenticated,
                        unique_viewers_authenticated=stats.unique_viewers_authenticated,
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
                        total_reactions=0,
                        total_comments=0,
                        total_views_authenticated=0,
                        unique_viewers_authenticated=0,
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

"""
User profile statistics service.

Provides on-demand computation of user profile statistics with Redis caching.
Aggregates data from posts, reactions, views, and follows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Cache TTL in seconds (5 minutes)
USER_PROFILE_STATS_CACHE_TTL = 300


@dataclass
class UserProfileStats:
    """Statistics for a user profile."""

    total_posts: int
    total_reactions_received: int
    total_views: int
    follower_count: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class UserProfileStatsService:
    """
    Service for computing and caching user profile statistics.

    Statistics are computed on-demand and cached in Redis for 5 minutes.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_user_stats(self, user_id: int) -> UserProfileStats | None:
        """
        Get statistics for a user profile.

        Checks Redis cache first, then computes if cache miss.

        Args:
            user_id: Integer ID of the user

        Returns:
            UserProfileStats object or None if user doesn't exist
        """
        from ..cache import cache_get, cache_set
        from .. import models

        # Verify user exists
        user = self.db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return None

        # Check Redis cache
        cache_key = f"user_profile_stats:{user_id}"
        cached_data = cache_get(cache_key)
        if cached_data:
            logger.debug(f"User stats cache hit for user {user_id}")
            return self._dict_to_stats(cached_data)

        # Compute fresh stats
        logger.debug(f"User stats cache miss for user {user_id}, computing...")
        stats = self._compute_stats(user_id)

        # Cache the result
        cache_set(cache_key, stats.to_dict(), ttl=USER_PROFILE_STATS_CACHE_TTL)

        return stats

    def invalidate_cache(self, user_id: int) -> None:
        """
        Invalidate the stats cache for a user.

        Should be called when relevant data changes (new post, reaction, follow).
        """
        from ..cache import cache_delete

        cache_key = f"user_profile_stats:{user_id}"
        cache_delete(cache_key)

    def _compute_stats(self, user_id: int) -> UserProfileStats:
        """
        Compute statistics for a user from the database.

        Aggregates data from:
        - posts table (total posts)
        - reactions table (total reactions received)
        - post_stats_daily table (total views)
        - follows table (follower count)
        """
        from .. import models

        # Total posts (artwork only, not deleted)
        total_posts = (
            self.db.query(func.count(models.Post.id))
            .filter(
                models.Post.owner_id == user_id,
                models.Post.kind == "artwork",
                models.Post.deleted_by_user == False,
            )
            .scalar()
            or 0
        )

        # Total reactions received on all posts
        total_reactions_received = (
            self.db.query(func.count(models.Reaction.id))
            .join(models.Post, models.Post.id == models.Reaction.post_id)
            .filter(
                models.Post.owner_id == user_id,
                models.Post.deleted_by_user == False,
            )
            .scalar()
            or 0
        )

        # Total views across all posts (from daily stats aggregates)
        total_views = (
            self.db.query(func.coalesce(func.sum(models.PostStatsDaily.total_views), 0))
            .join(models.Post, models.Post.id == models.PostStatsDaily.post_id)
            .filter(
                models.Post.owner_id == user_id,
                models.Post.deleted_by_user == False,
            )
            .scalar()
            or 0
        )

        # Follower count
        follower_count = (
            self.db.query(func.count(models.Follow.id))
            .filter(models.Follow.following_id == user_id)
            .scalar()
            or 0
        )

        return UserProfileStats(
            total_posts=total_posts,
            total_reactions_received=total_reactions_received,
            total_views=total_views,
            follower_count=follower_count,
        )

    def _dict_to_stats(self, data: dict) -> UserProfileStats:
        """Convert dictionary back to UserProfileStats object."""
        return UserProfileStats(
            total_posts=data["total_posts"],
            total_reactions_received=data["total_reactions_received"],
            total_views=data["total_views"],
            follower_count=data["follower_count"],
        )


def get_user_profile_stats(db: Session, user_id: int) -> UserProfileStats | None:
    """
    Convenience function to get user profile statistics.

    Args:
        db: Database session
        user_id: Integer ID of the user

    Returns:
        UserProfileStats object or None if user doesn't exist
    """
    service = UserProfileStatsService(db)
    return service.get_user_stats(user_id)


def invalidate_user_profile_stats_cache(db: Session, user_id: int) -> None:
    """
    Convenience function to invalidate user profile stats cache.

    Should be called when relevant data changes.
    """
    service = UserProfileStatsService(db)
    service.invalidate_cache(user_id)

"""
Post statistics service for efficiently adding counts to posts.

Provides efficient batch queries to add reaction_count, comment_count,
and user_has_liked to multiple posts in a single database query.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from ..models import Post

from .. import models


def annotate_posts_with_counts(
    db: Session, posts: list["Post"], current_user_id: UUID | None = None
) -> list["Post"]:
    """
    Add reaction_count, comment_count, and user_has_liked to posts using efficient subqueries.

    This function uses SQL GROUP BY queries to fetch all counts at once,
    then attaches them to the post objects.

    Args:
        db: Database session
        posts: List of Post ORM objects to annotate
        current_user_id: UUID of the current user (optional, for user_has_liked)

    Returns:
        Same list of posts with reaction_count, comment_count, and user_has_liked attributes added
    """
    if not posts:
        return posts

    post_ids = [post.id for post in posts]

    # Get reaction counts for all posts in one query
    reaction_counts = (
        db.query(models.Reaction.post_id, func.count(models.Reaction.id).label("count"))
        .filter(models.Reaction.post_id.in_(post_ids))
        .group_by(models.Reaction.post_id)
        .all()
    )

    # Get comment counts for all posts in one query
    # Only count visible, non-deleted comments
    comment_counts = (
        db.query(models.Comment.post_id, func.count(models.Comment.id).label("count"))
        .filter(
            models.Comment.post_id.in_(post_ids),
            models.Comment.hidden_by_mod == False,
            models.Comment.deleted_by_owner == False,
        )
        .group_by(models.Comment.post_id)
        .all()
    )

    # Get user's likes (👍 reactions) if user is authenticated
    user_liked_posts: set[int] = set()
    if current_user_id:
        user_likes = (
            db.query(models.Reaction.post_id)
            .filter(
                models.Reaction.post_id.in_(post_ids),
                models.Reaction.user_id == current_user_id,
                models.Reaction.emoji == "👍",
            )
            .all()
        )
        user_liked_posts = {row[0] for row in user_likes}

    # Create lookup dictionaries
    reaction_count_map = {post_id: count for post_id, count in reaction_counts}
    comment_count_map = {post_id: count for post_id, count in comment_counts}

    # Attach counts and liked status to posts
    for post in posts:
        post.reaction_count = reaction_count_map.get(post.id, 0)
        post.comment_count = comment_count_map.get(post.id, 0)
        post.user_has_liked = post.id in user_liked_posts

    return posts


def get_view_counts(db: Session, post_ids: list[int]) -> dict[int, int]:
    """
    Get total view counts for posts, batched into two grouped queries.

    Combines recent raw view events (``view_events``, retained ~7 days) with
    historical daily aggregates (``post_stats_daily``). The two sources do not
    overlap — events are deleted only after being rolled up — so summing them
    gives the lifetime total without double counting.

    Args:
        db: Database session
        post_ids: List of post IDs to count views for

    Returns:
        Dict mapping post_id -> total view count (every requested id is present,
        defaulting to 0)
    """
    if not post_ids:
        return {}

    # Recent views from the raw view_events table
    recent_counts = dict(
        db.query(models.ViewEvent.post_id, func.count(models.ViewEvent.id))
        .filter(models.ViewEvent.post_id.in_(post_ids))
        .group_by(models.ViewEvent.post_id)
        .all()
    )

    # Historical views from daily aggregates
    daily_counts = dict(
        db.query(
            models.PostStatsDaily.post_id, func.sum(models.PostStatsDaily.total_views)
        )
        .filter(models.PostStatsDaily.post_id.in_(post_ids))
        .group_by(models.PostStatsDaily.post_id)
        .all()
    )

    return {
        post_id: recent_counts.get(post_id, 0) + int(daily_counts.get(post_id, 0) or 0)
        for post_id in post_ids
    }


def get_user_liked_post_ids(
    db: Session, post_ids: list[int], user_id: UUID
) -> set[int]:
    """
    Get the set of post IDs that a user has liked (👍 reaction).

    Args:
        db: Database session
        post_ids: List of post IDs to check
        user_id: UUID of the user

    Returns:
        Set of post IDs that the user has liked
    """
    if not post_ids or not user_id:
        return set()

    user_likes = (
        db.query(models.Reaction.post_id)
        .filter(
            models.Reaction.post_id.in_(post_ids),
            models.Reaction.user_id == user_id,
            models.Reaction.emoji == "👍",
        )
        .all()
    )
    return {row[0] for row in user_likes}

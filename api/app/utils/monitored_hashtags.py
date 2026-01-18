"""Utility functions for filtering posts by monitored hashtags.

Posts containing monitored hashtags are hidden by default unless the user
has explicitly opted into viewing them via their approved_hashtags setting.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

from sqlalchemy import not_
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.sql import cast
from sqlalchemy import String

from ..constants import MONITORED_HASHTAGS

if TYPE_CHECKING:
    from sqlalchemy.orm import Query

    from .. import models


class HasHashtags(Protocol):
    """Protocol for objects with a hashtags attribute."""

    hashtags: list[str] | None


T = TypeVar("T", bound=HasHashtags)


def apply_monitored_hashtag_filter(
    query: Query,
    post_model: type[models.Post],
    user: models.User | None,
) -> Query:
    """
    Apply monitored hashtag filtering to a SQLAlchemy query.

    Posts containing monitored hashtags that the user has not approved
    will be excluded from the result set.

    Args:
        query: SQLAlchemy query to filter
        post_model: The Post model class
        user: The user making the request (None for unauthenticated)

    Returns:
        Filtered query
    """
    if user is None:
        # Unauthenticated users cannot see any monitored content
        approved_tags: set[str] = set()
    else:
        approved_tags = set(user.approved_hashtags or [])

    # Calculate which monitored hashtags to exclude
    # (all monitored hashtags minus user's approved ones)
    excluded_tags = MONITORED_HASHTAGS - approved_tags

    if not excluded_tags:
        # User has approved all monitored hashtags, no filtering needed
        return query

    # Filter out posts that have any of the excluded monitored hashtags
    # PostgreSQL array overlap operator: hashtags && ARRAY['tag1', 'tag2']
    # We negate this to exclude posts that have ANY of the excluded tags
    excluded_array = cast(list(excluded_tags), ARRAY(String))
    return query.filter(
        not_(post_model.hashtags.overlap(excluded_array))
    )


def filter_posts_by_monitored_hashtags(
    posts: list[T],
    user: models.User | None,
) -> list[T]:
    """
    Filter a list of posts by monitored hashtags (in-memory filtering).

    This is useful when posts have already been fetched and need to be
    filtered based on user preferences. Works with both model objects
    and schema objects (anything with a hashtags attribute).

    Args:
        posts: List of Post objects (model or schema instances)
        user: The user making the request (None for unauthenticated)

    Returns:
        Filtered list of posts
    """
    if user is None:
        approved_tags: set[str] = set()
    else:
        approved_tags = set(user.approved_hashtags or [])

    # Calculate which monitored hashtags to exclude
    excluded_tags = MONITORED_HASHTAGS - approved_tags

    if not excluded_tags:
        # User has approved all monitored hashtags, no filtering needed
        return posts

    # Filter out posts that have any of the excluded monitored hashtags
    return [
        post
        for post in posts
        if not (set(post.hashtags or []) & excluded_tags)
    ]


def post_has_unapproved_monitored_hashtags(
    post: models.Post,
    user: models.User | None,
) -> bool:
    """
    Check if a post contains monitored hashtags that the user hasn't approved.

    Args:
        post: Post model instance
        user: The user to check against (None for unauthenticated)

    Returns:
        True if the post has monitored hashtags the user hasn't approved
    """
    if user is None:
        approved_tags: set[str] = set()
    else:
        approved_tags = set(user.approved_hashtags or [])

    post_tags = set(post.hashtags or [])
    unapproved_monitored = (post_tags & MONITORED_HASHTAGS) - approved_tags

    return bool(unapproved_monitored)

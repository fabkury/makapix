"""Visibility and access control utilities for posts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from .. import models


def can_access_post(post: "models.Post", user: "models.User" | None) -> bool:
    """
    Check if a user can access a post based on visibility rules.

    Access is allowed if:
    - User is a moderator/owner, OR
    - User is the post owner, OR
    - Post is publicly visible (approved for public visibility) and not hidden, OR
    - Post is promoted and not hidden

    Notes:
    - `public_visibility` is the primary "unlisted vs public" gate used across the API
      (feeds/search only show `public_visibility == True`). The canonical permalink
      endpoint `/api/p/{public_sqid}` should therefore allow access when
      `public_visibility` is True.
    - Hidden posts (`hidden_by_user` or `hidden_by_mod`) remain accessible only to the
      owner and moderators/owners.

    Args:
        post: The post to check access for
        user: The current user (None for anonymous users)

    Returns:
        True if access is allowed, False otherwise
    """
    # Deleted posts are never accessible (even to owner/moderator)
    if post.deleted_by_user:
        return False

    # Check if user is moderator/owner
    if user is not None:
        is_moderator = "moderator" in user.roles or "owner" in user.roles
        if is_moderator:
            return True

        # Check if user is the post owner
        if user.id == post.owner_id:
            return True

    # Public visibility:
    # - must be visible
    # - must not be hidden (either by user or moderator)
    # - must be approved for public visibility OR promoted
    if not post.visible:
        return False

    if post.hidden_by_mod or post.hidden_by_user:
        return False

    return bool(post.public_visibility or post.promoted)


def get_accessible_post_or_404(
    db: Session, post_id: int, user: "models.User | None"
) -> "models.Post":
    """Load a post by id and enforce visibility, returning 404 for a missing OR
    inaccessible post.

    Post ids are sequential integers, so any endpoint that loads a post by id
    without this check (comment/reaction reads and writes) leaks the existence
    and content of hidden/unlisted/soft-deleted posts to enumeration, and 500s
    on a nonexistent id via a later FK violation. Using a single 404 for both
    "missing" and "forbidden" also avoids disclosing which posts exist.
    """
    from .. import models

    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if post is None or not can_access_post(post, user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return post

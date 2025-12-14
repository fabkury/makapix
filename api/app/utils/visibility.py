"""Visibility and access control utilities for posts."""

from __future__ import annotations

from typing import TYPE_CHECKING

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


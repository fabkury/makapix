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
    - Post is promoted (base_visible for anonymous users)
    
    Note: "Public post" means "promoted post" - promoted posts are the only ones
    accessible without authentication.
    
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
    
    # Check base visibility (promoted posts are public)
    # base_visible = promoted AND not hidden_by_mod AND not hidden_by_user AND visible
    base_visible = (
        post.promoted
        and not post.hidden_by_mod
        and not post.hidden_by_user
        and post.visible
    )
    
    return base_visible


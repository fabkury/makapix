"""Statistics endpoints for artwork analytics."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..deps import get_db
from ..services.stats import get_post_stats, invalidate_post_stats_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/post", tags=["Statistics"])


@router.get("/{id}/stats", response_model=schemas.PostStatsResponse)
async def get_post_statistics(
    id: int,  # Changed from UUID to int
    refresh: bool = Query(False, description="Force cache refresh"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.PostStatsResponse:
    """
    Get statistics for an artwork.
    
    Returns both "all" (including unauthenticated) and "authenticated-only" statistics
    in a single response. Frontend can toggle between the two without additional API calls.
    
    **Authorization:**
    - Post owner can view statistics for their own posts
    - Moderators and owners can view statistics for any post
    
    **Query Parameters:**
    - `refresh`: If true, invalidates cache and recomputes statistics
    
    **Response includes:**
    - All statistics (including unauthenticated): `total_views`, `unique_viewers`, etc.
    - Authenticated-only statistics: `total_views_authenticated`, `unique_viewers_authenticated`, etc.
    - Timestamps: `first_view_at`, `last_view_at`, `computed_at`
    """
    # Check if post exists
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found"
        )
    
    # Authorization: owner of post OR moderator/owner role
    is_owner = post.owner_id == current_user.id
    is_moderator = "moderator" in current_user.roles or "owner" in current_user.roles
    
    if not is_owner and not is_moderator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view statistics for this post"
        )
    
    # Invalidate cache if requested
    if refresh:
        invalidate_post_stats_cache(db, id)
    
    # Get statistics
    stats = get_post_stats(db, id)
    
    if stats is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute statistics"
        )
    
    # Convert to response schema
    return schemas.PostStatsResponse(
        post_id=stats.post_id,  # post_id is now int, not UUID
        # All statistics
        total_views=stats.total_views,
        unique_viewers=stats.unique_viewers,
        views_by_country=stats.views_by_country,
        views_by_device=stats.views_by_device,
        views_by_type=stats.views_by_type,
        daily_views=[
            schemas.DailyViewCount(
                date=dv.date,
                views=dv.views,
                unique_viewers=dv.unique_viewers
            )
            for dv in stats.daily_views
        ],
        total_reactions=stats.total_reactions,
        reactions_by_emoji=stats.reactions_by_emoji,
        total_comments=stats.total_comments,
        # Authenticated-only statistics
        total_views_authenticated=stats.total_views_authenticated,
        unique_viewers_authenticated=stats.unique_viewers_authenticated,
        views_by_country_authenticated=stats.views_by_country_authenticated,
        views_by_device_authenticated=stats.views_by_device_authenticated,
        views_by_type_authenticated=stats.views_by_type_authenticated,
        daily_views_authenticated=[
            schemas.DailyViewCount(
                date=dv.date,
                views=dv.views,
                unique_viewers=dv.unique_viewers
            )
            for dv in stats.daily_views_authenticated
        ],
        total_reactions_authenticated=stats.total_reactions_authenticated,
        reactions_by_emoji_authenticated=stats.reactions_by_emoji_authenticated,
        total_comments_authenticated=stats.total_comments_authenticated,
        # Timestamps
        first_view_at=datetime.fromisoformat(stats.first_view_at) if stats.first_view_at else None,
        last_view_at=datetime.fromisoformat(stats.last_view_at) if stats.last_view_at else None,
        computed_at=datetime.fromisoformat(stats.computed_at),
    )


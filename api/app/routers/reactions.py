"""Reaction endpoints."""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload
from uuid import UUID

from .. import models, schemas
from ..auth import AnonymousUser, get_current_user, get_current_user_or_anonymous
from ..deps import get_db
from ..services.social_notifications import SocialNotificationService

router = APIRouter(prefix="/post", tags=["Reactions"])


@router.get("/{id}/reactions", response_model=schemas.ReactionTotals)
def get_reactions(
    id: int,  # Post ID (integer)
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | AnonymousUser = Depends(get_current_user_or_anonymous),
) -> schemas.ReactionTotals:
    """
    Get reaction totals for a post.
    
    Returns totals for all reactions and identifies which reactions
    belong to the current user (authenticated or anonymous).
    
    Uses SQL aggregation for efficiency instead of fetching all rows.
    """
    # Aggregate counts by emoji with authenticated/anonymous breakdown
    # This is much more efficient than fetching all reaction rows
    aggregated = db.query(
        models.Reaction.emoji,
        func.count(models.Reaction.id).label('total'),
        func.sum(case((models.Reaction.user_id.isnot(None), 1), else_=0)).label('authenticated'),
        func.sum(case((models.Reaction.user_id.is_(None), 1), else_=0)).label('anonymous'),
    ).filter(
        models.Reaction.post_id == id
    ).group_by(
        models.Reaction.emoji
    ).all()
    
    totals: dict[str, int] = {}
    authenticated_totals: dict[str, int] = {}
    anonymous_totals: dict[str, int] = {}
    
    for row in aggregated:
        emoji = row.emoji
        totals[emoji] = row.total
        if row.authenticated > 0:
            authenticated_totals[emoji] = row.authenticated
        if row.anonymous > 0:
            anonymous_totals[emoji] = row.anonymous
    
    # Get current user's reactions (separate efficient query)
    mine: list[str] = []
    if isinstance(current_user, models.User):
        user_reactions = db.query(models.Reaction.emoji).filter(
            models.Reaction.post_id == id,
            models.Reaction.user_id == current_user.id,
        ).distinct().all()
        mine = [r.emoji for r in user_reactions]
    elif isinstance(current_user, AnonymousUser):
        user_reactions = db.query(models.Reaction.emoji).filter(
            models.Reaction.post_id == id,
            models.Reaction.user_ip == current_user.ip,
        ).distinct().all()
        mine = [r.emoji for r in user_reactions]

    return schemas.ReactionTotals(
        totals=totals,
        authenticated_totals=authenticated_totals,
        anonymous_totals=anonymous_totals,
        mine=mine,
    )


@router.put(
    "/{id}/reactions/{emoji}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def add_reaction(
    id: int,  # Post ID (integer)
    emoji: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | AnonymousUser = Depends(get_current_user_or_anonymous),
) -> None:
    """
    Add reaction to a post.
    
    Supports both authenticated and anonymous users.
    Enforces max 5 reactions per user/IP per post.
    Idempotent - returns success if reaction already exists.
    """
    # Basic emoji validation (ensure it's not empty and reasonable length)
    if not emoji or len(emoji) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid emoji format"
        )
    
    # Check if reaction already exists (idempotent)
    if isinstance(current_user, models.User):
        existing = db.query(models.Reaction).filter(
            models.Reaction.post_id == id,
            models.Reaction.user_id == current_user.id,
            models.Reaction.emoji == emoji,
        ).first()
        
        if existing:
            return  # Already exists, idempotent success
        
        # Count existing reactions by this user on this post
        reaction_count = db.query(func.count(models.Reaction.id)).filter(
            models.Reaction.post_id == id,
            models.Reaction.user_id == current_user.id,
        ).scalar()
    else:  # AnonymousUser
        existing = db.query(models.Reaction).filter(
            models.Reaction.post_id == id,
            models.Reaction.user_ip == current_user.ip,
            models.Reaction.emoji == emoji,
        ).first()
        
        if existing:
            return  # Already exists, idempotent success
        
        # Count existing reactions by this IP on this post
        reaction_count = db.query(func.count(models.Reaction.id)).filter(
            models.Reaction.post_id == id,
            models.Reaction.user_ip == current_user.ip,
        ).scalar()
    
    # Enforce max 5 reactions per user/IP per post
    if reaction_count >= 5:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Maximum reactions per user per post (5) exceeded"
        )
    
    # Create new reaction
    reaction = models.Reaction(
        post_id=id,
        user_id=current_user.id if isinstance(current_user, models.User) else None,
        user_ip=current_user.ip if isinstance(current_user, AnonymousUser) else None,
        emoji=emoji,
    )
    db.add(reaction)
    db.commit()

    # Create notification for post owner (only for authenticated users)
    if isinstance(current_user, models.User):
        post = db.query(models.Post).filter(models.Post.id == id).first()
        if post:
            SocialNotificationService.create_notification(
                db=db,
                user_id=post.owner_id,
                notification_type="reaction",
                post=post,
                actor=current_user,
                emoji=emoji,
            )


@router.delete(
    "/{id}/reactions/{emoji}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_reaction(
    id: int,  # Post ID (integer)
    emoji: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | AnonymousUser = Depends(get_current_user_or_anonymous),
) -> None:
    """
    Remove reaction from a post (idempotent).
    
    Supports both authenticated and anonymous users.
    """
    if isinstance(current_user, models.User):
        db.query(models.Reaction).filter(
            models.Reaction.post_id == id,
            models.Reaction.user_id == current_user.id,
            models.Reaction.emoji == emoji,
        ).delete()
    else:  # AnonymousUser
        db.query(models.Reaction).filter(
            models.Reaction.post_id == id,
            models.Reaction.user_ip == current_user.ip,
            models.Reaction.emoji == emoji,
        ).delete()
    
    db.commit()


@router.get("/{id}/widget-data", response_model=schemas.WidgetData)
def get_widget_data(
    id: int,  # Post ID (integer)
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | AnonymousUser = Depends(get_current_user_or_anonymous),
) -> schemas.WidgetData:
    """
    Get combined widget data (reactions + comments) in a single request.
    
    This is more efficient than making separate requests for reactions and comments.
    """
    # ===== REACTIONS (using SQL aggregation) =====
    aggregated = db.query(
        models.Reaction.emoji,
        func.count(models.Reaction.id).label('total'),
        func.sum(case((models.Reaction.user_id.isnot(None), 1), else_=0)).label('authenticated'),
        func.sum(case((models.Reaction.user_id.is_(None), 1), else_=0)).label('anonymous'),
    ).filter(
        models.Reaction.post_id == id
    ).group_by(
        models.Reaction.emoji
    ).all()
    
    totals: dict[str, int] = {}
    authenticated_totals: dict[str, int] = {}
    anonymous_totals: dict[str, int] = {}
    
    for row in aggregated:
        emoji = row.emoji
        totals[emoji] = row.total
        if row.authenticated > 0:
            authenticated_totals[emoji] = row.authenticated
        if row.anonymous > 0:
            anonymous_totals[emoji] = row.anonymous
    
    # Get current user's reactions
    mine: list[str] = []
    if isinstance(current_user, models.User):
        user_reactions = db.query(models.Reaction.emoji).filter(
            models.Reaction.post_id == id,
            models.Reaction.user_id == current_user.id,
        ).distinct().all()
        mine = [r.emoji for r in user_reactions]
    elif isinstance(current_user, AnonymousUser):
        user_reactions = db.query(models.Reaction.emoji).filter(
            models.Reaction.post_id == id,
            models.Reaction.user_ip == current_user.ip,
        ).distinct().all()
        mine = [r.emoji for r in user_reactions]
    
    reactions = schemas.ReactionTotals(
        totals=totals,
        authenticated_totals=authenticated_totals,
        anonymous_totals=anonymous_totals,
        mine=mine,
    )
    
    # ===== COMMENTS =====
    query = db.query(models.Comment).options(
        joinedload(models.Comment.author)
    ).filter(
        models.Comment.post_id == id
    )
    
    # Hide comments hidden by moderators unless current user is a moderator
    is_moderator = (
        isinstance(current_user, models.User) 
        and ("moderator" in current_user.roles or "owner" in current_user.roles)
    )
    if not is_moderator:
        query = query.filter(models.Comment.hidden_by_mod == False)
    
    # Filter out comments with invalid depth and limit results
    query = query.filter(models.Comment.depth <= 2)
    query = query.order_by(models.Comment.created_at.asc()).limit(50)
    
    comments_raw = query.all()
    
    # Filter out deleted comments using bottom-up approach
    comment_dict = {c.id: c for c in comments_raw}
    children_map: dict[UUID, list[UUID]] = {}
    for comment in comments_raw:
        if comment.parent_id is not None:
            if comment.parent_id not in children_map:
                children_map[comment.parent_id] = []
            children_map[comment.parent_id].append(comment.id)
    
    removed_ids: set[UUID] = set()
    changed = True
    while changed:
        changed = False
        for comment_id, comment in list(comment_dict.items()):
            if comment.deleted_by_owner and comment_id not in removed_ids:
                has_children = False
                if comment_id in children_map:
                    for child_id in children_map[comment_id]:
                        if child_id not in removed_ids:
                            has_children = True
                            break
                if not has_children:
                    removed_ids.add(comment_id)
                    changed = True
    
    comments_raw = [c for c in comments_raw if c.id not in removed_ids]
    
    # Filter out orphaned comments
    comment_ids = {c.id for c in comments_raw}
    valid_comments = []
    for comment in comments_raw:
        if comment.parent_id is None or comment.parent_id in comment_ids:
            valid_comments.append(comment)
    
    comments = [schemas.Comment.model_validate(c) for c in valid_comments]
    
    return schemas.WidgetData(
        reactions=reactions,
        comments=comments,
    )

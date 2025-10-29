"""Reaction endpoints."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import AnonymousUser, get_current_user, get_current_user_or_anonymous
from ..deps import get_db

router = APIRouter(prefix="/posts", tags=["Reactions"])


@router.get("/{id}/reactions", response_model=schemas.ReactionTotals)
def get_reactions(
    id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | AnonymousUser = Depends(get_current_user_or_anonymous),
) -> schemas.ReactionTotals:
    """
    Get reaction totals for a post.
    
    Returns totals for all reactions and identifies which reactions
    belong to the current user (authenticated or anonymous).
    """
    reactions = db.query(models.Reaction).filter(models.Reaction.post_id == id).all()
    
    totals: dict[str, int] = {}
    mine: list[str] = []
    
    for reaction in reactions:
        totals[reaction.emoji] = totals.get(reaction.emoji, 0) + 1
        
        # Check if this reaction belongs to current user
        if isinstance(current_user, models.User) and reaction.user_id == current_user.id:
            mine.append(reaction.emoji)
        elif isinstance(current_user, AnonymousUser) and reaction.user_ip == current_user.ip:
            mine.append(reaction.emoji)
    
    return schemas.ReactionTotals(totals=totals, mine=mine)


@router.put(
    "/{id}/reactions/{emoji}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def add_reaction(
    id: UUID,
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


@router.delete(
    "/{id}/reactions/{emoji}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_reaction(
    id: UUID,
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

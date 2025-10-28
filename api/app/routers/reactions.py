"""Reaction endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, get_current_user_optional
from ..deps import get_db

router = APIRouter(prefix="/posts", tags=["Reactions"])


@router.get("/{id}/reactions", response_model=schemas.ReactionTotals)
def get_reactions(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.ReactionTotals:
    """
    Get reaction totals for a post.
    
    TODO: Optimize with GROUP BY query
    TODO: Cache results with short TTL
    """
    reactions = db.query(models.Reaction).filter(models.Reaction.post_id == id).all()
    
    totals: dict[str, int] = {}
    mine: list[str] = []
    
    for reaction in reactions:
        totals[reaction.emoji] = totals.get(reaction.emoji, 0) + 1
        if current_user and reaction.user_id == current_user.id:
            mine.append(reaction.emoji)
    
    return schemas.ReactionTotals(totals=totals, mine=mine)


@router.put(
    "/{id}/reactions/{emoji}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def add_reaction(
    id: UUID,
    emoji: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Add reaction to a post.
    
    TODO: Validate emoji format
    TODO: Check max_emojis_per_user_per_post limit
    TODO: Handle 409 Conflict if reaction already exists (idempotent)
    """
    # Check if reaction already exists
    existing = db.query(models.Reaction).filter(
        models.Reaction.post_id == id,
        models.Reaction.user_id == current_user.id,
        models.Reaction.emoji == emoji,
    ).first()
    
    if not existing:
        reaction = models.Reaction(
            post_id=id,
            user_id=current_user.id,
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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Remove reaction from a post (idempotent)."""
    db.query(models.Reaction).filter(
        models.Reaction.post_id == id,
        models.Reaction.user_id == current_user.id,
        models.Reaction.emoji == emoji,
    ).delete()
    db.commit()

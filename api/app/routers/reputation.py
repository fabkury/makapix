"""Reputation management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import require_moderator
from ..deps import get_db

router = APIRouter(prefix="/users", tags=["Reputation"])


@router.post(
    "/{id}/reputation",
    response_model=schemas.ReputationAdjustResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Reputation", "Admin"],
)
def adjust_reputation(
    id: UUID,
    payload: schemas.ReputationAdjust,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> schemas.ReputationAdjustResponse:
    """
    Adjust user reputation (moderator only).
    
    TODO: Log in audit log
    TODO: Update User.reputation field
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Add to history
    history = models.ReputationHistory(
        user_id=id,
        delta=payload.delta,
        reason=payload.reason,
    )
    db.add(history)
    
    # Update user total
    user.reputation += payload.delta
    db.commit()
    
    return schemas.ReputationAdjustResponse(new_total=user.reputation)


@router.get("/{id}/reputation", response_model=schemas.ReputationView)
def get_reputation(id: UUID, db: Session = Depends(get_db)) -> schemas.ReputationView:
    """Get user reputation with history."""
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    history = (
        db.query(models.ReputationHistory)
        .filter(models.ReputationHistory.user_id == id)
        .order_by(models.ReputationHistory.created_at.desc())
        .limit(100)
        .all()
    )
    
    return schemas.ReputationView(
        total=user.reputation,
        history=[
            schemas.ReputationHistoryItem(
                delta=h.delta,
                reason=h.reason,
                at=h.created_at,
            )
            for h in history
        ],
    )

"""Badge management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import require_moderator
from ..deps import get_db

router = APIRouter(prefix="/badges", tags=["Badges"])


@router.get("", response_model=dict[str, list[schemas.BadgeDefinition]])
def list_badges() -> dict[str, list[schemas.BadgeDefinition]]:
    """
    List all badge definitions.
    
    TODO: Load from database or configuration file
    """
    # PLACEHOLDER: Static badge list
    badges = [
        schemas.BadgeDefinition(
            badge="early-adopter",
            label="Early Adopter",
            description="Joined during beta",
        ),
        schemas.BadgeDefinition(
            badge="top-contributor",
            label="Top Contributor",
            description="Posted 100+ artworks",
        ),
        schemas.BadgeDefinition(
            badge="moderator",
            label="Moderator",
            description="Community moderator",
        ),
    ]
    
    return {"items": badges}


@router.get("/users/{id}/badges", response_model=dict[str, list[schemas.BadgeGrant]])
def list_user_badges(id: UUID, db: Session = Depends(get_db)) -> dict[str, list[schemas.BadgeGrant]]:
    """List badges for a user."""
    badges = db.query(models.BadgeGrant).filter(models.BadgeGrant.user_id == id).all()
    
    return {"items": [schemas.BadgeGrant.model_validate(b) for b in badges]}


@router.post(
    "/users/{id}/badges",
    status_code=status.HTTP_201_CREATED,
    tags=["Badges", "Admin"],
)
def grant_badge(
    id: UUID,
    payload: schemas.BadgeGrantRequest,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Grant badge to a user (moderator only).
    
    TODO: Validate that badge exists in badge definitions
    TODO: Log in audit log
    TODO: Send notification to user
    """
    # Check if badge already granted
    existing = db.query(models.BadgeGrant).filter(
        models.BadgeGrant.user_id == id,
        models.BadgeGrant.badge == payload.badge,
    ).first()
    
    if not existing:
        badge = models.BadgeGrant(user_id=id, badge=payload.badge)
        db.add(badge)
        db.commit()


@router.delete(
    "/users/{id}/badges/{badge}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Badges", "Admin"],
)
def revoke_badge(
    id: UUID,
    badge: str,
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Revoke badge from a user (moderator only).
    
    TODO: Log in audit log
    """
    db.query(models.BadgeGrant).filter(
        models.BadgeGrant.user_id == id,
        models.BadgeGrant.badge == badge,
    ).delete()
    db.commit()

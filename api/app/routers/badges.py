"""Badge management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import require_moderator
from ..deps import get_db
from ..utils.audit import log_moderation_action

router = APIRouter(prefix="/badge", tags=["Badges"])


@router.get("", response_model=dict[str, list[schemas.BadgeDefinition]])
def list_badges(
    db: Session = Depends(get_db),
) -> dict[str, list[schemas.BadgeDefinition]]:
    """
    List all badge definitions from the database.
    """
    badge_defs = db.query(models.BadgeDefinition).all()

    badges = [
        schemas.BadgeDefinition(
            badge=bd.badge,
            label=bd.label,
            description=bd.description,
            icon_url_64=bd.icon_url_64,
            icon_url_16=bd.icon_url_16,
            is_tag_badge=bd.is_tag_badge,
        )
        for bd in badge_defs
    ]

    return {"items": badges}


@router.get("/tag-badges", response_model=dict[str, list[schemas.TagBadgeInfo]])
def list_tag_badges(
    db: Session = Depends(get_db),
) -> dict[str, list[schemas.TagBadgeInfo]]:
    """
    List all tag badges (badges displayed under username).
    """
    badge_defs = (
        db.query(models.BadgeDefinition)
        .filter(
            models.BadgeDefinition.is_tag_badge == True,
            models.BadgeDefinition.icon_url_16.isnot(None),
        )
        .all()
    )

    badges = [
        schemas.TagBadgeInfo(
            badge=bd.badge,
            label=bd.label,
            icon_url_16=bd.icon_url_16,
        )
        for bd in badge_defs
    ]

    return {"items": badges}


@router.get("/user/{id}/badge", response_model=dict[str, list[schemas.BadgeGrant]])
def list_user_badges(
    id: UUID, db: Session = Depends(get_db)
) -> dict[str, list[schemas.BadgeGrant]]:
    """List badges for a user (by user_key UUID)."""
    # Look up user by user_key
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        return {"items": []}

    badges = (
        db.query(models.BadgeGrant).filter(models.BadgeGrant.user_id == user.id).all()
    )

    return {"items": [schemas.BadgeGrant.model_validate(b) for b in badges]}


@router.post(
    "/user/{id}/badge",
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

    Validates that the badge exists in badge_definitions table before granting.
    """
    from fastapi import HTTPException

    # Look up user by user_key
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate badge exists in definitions
    badge_def = (
        db.query(models.BadgeDefinition)
        .filter(models.BadgeDefinition.badge == payload.badge)
        .first()
    )
    if not badge_def:
        raise HTTPException(status_code=400, detail="Invalid badge")

    # Check if badge already granted
    existing = (
        db.query(models.BadgeGrant)
        .filter(
            models.BadgeGrant.user_id == user.id,
            models.BadgeGrant.badge == payload.badge,
        )
        .first()
    )

    if not existing:
        badge = models.BadgeGrant(user_id=user.id, badge=payload.badge)
        db.add(badge)
        db.commit()

        # Log to audit
        log_moderation_action(
            db=db,
            actor_id=moderator.id,
            action="grant_badge",
            target_type="user",
            target_id=str(id),
            reason_code=payload.reason_code,
            note=payload.note,
        )


@router.delete(
    "/user/{id}/badge/{badge}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Badges", "Admin"],
)
def revoke_badge(
    id: UUID,
    badge: str,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Revoke badge from a user (moderator only).
    """
    from fastapi import HTTPException

    # Look up user by user_key
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.query(models.BadgeGrant).filter(
        models.BadgeGrant.user_id == user.id,
        models.BadgeGrant.badge == badge,
    ).delete()
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="revoke_badge",
        target_type="user",
        target_id=str(id),
    )

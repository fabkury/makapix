"""Self-service endpoints under /me — push tokens & notification preferences (§4).

These are the app-facing registration/preference endpoints. Server-side push
delivery (Firebase Admin SDK) is wired separately in the notification fan-out.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..deps import get_db

router = APIRouter(prefix="/me", tags=["Me"])


@router.post(
    "/push-tokens",
    response_model=schemas.PushTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_push_token(
    payload: schemas.PushTokenRegister,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> models.PushToken:
    """Register a device push token (idempotent on the token value)."""
    existing = (
        db.query(models.PushToken)
        .filter(models.PushToken.token == payload.token)
        .first()
    )
    if existing:
        existing.user_id = current_user.id
        existing.platform = payload.platform
        existing.device_label = payload.device_label
        existing.revoked = False
        existing.failure_count = 0
        existing.last_used_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    token = models.PushToken(
        user_id=current_user.id,
        platform=payload.platform,
        token=payload.token,
        device_label=payload.device_label,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


@router.delete("/push-tokens/{token:path}", status_code=status.HTTP_204_NO_CONTENT)
def delete_push_token(
    token: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Unregister a device push token owned by the current user."""
    db.query(models.PushToken).filter(
        models.PushToken.token == token,
        models.PushToken.user_id == current_user.id,
    ).delete()
    db.commit()


@router.get("/notification-preferences", response_model=schemas.NotificationPreferences)
def get_notification_preferences(
    current_user: models.User = Depends(get_current_user),
) -> schemas.NotificationPreferences:
    return schemas.NotificationPreferences(
        preferences=current_user.notification_prefs or {}
    )


@router.put("/notification-preferences", response_model=schemas.NotificationPreferences)
def set_notification_preferences(
    payload: schemas.NotificationPreferences,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.NotificationPreferences:
    current_user.notification_prefs = dict(payload.preferences)
    db.commit()
    db.refresh(current_user)
    return schemas.NotificationPreferences(
        preferences=current_user.notification_prefs or {}
    )

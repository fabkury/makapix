"""Self-service endpoints under /me — push tokens & notification preferences (§4).

These are the app-facing registration/preference endpoints. Server-side push
delivery (Firebase Admin SDK) is wired separately in the notification fan-out.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..deps import get_db
from ..services.rate_limit import check_rate_limit
from fastapi import HTTPException

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
    # Distinct token values each create a row; throttle per user so it can't be
    # looped to flood the push_tokens table.
    allowed, _ = check_rate_limit(
        f"ratelimit:push_token:{current_user.id}", limit=30, window_seconds=3600
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Push-token registration rate limit exceeded.",
        )

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


@router.get("/blocks", response_model=schemas.Page[schemas.BlockedUserEntry])
def list_my_blocks(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Page[schemas.BlockedUserEntry]:
    """The caller's blocked-users list (docs/ugc-safety/API-CONTRACT.md §4)."""
    from ..pagination import apply_cursor_filter, create_page_response

    query = db.query(models.UserBlock).filter(
        models.UserBlock.blocker_id == current_user.id
    )
    query = apply_cursor_filter(
        query, models.UserBlock, cursor, "created_at", sort_desc=True
    )
    query = query.order_by(models.UserBlock.created_at.desc()).limit(limit + 1)
    blocks = query.all()

    page_data = create_page_response(blocks, limit, cursor)

    blocked_ids = [b.blocked_id for b in page_data["items"]]
    users_by_id: dict[int, models.User] = {}
    if blocked_ids:
        users_by_id = {
            u.id: u
            for u in db.query(models.User).filter(models.User.id.in_(blocked_ids)).all()
        }

    items = []
    for b in page_data["items"]:
        u = users_by_id.get(b.blocked_id)
        if not u:
            continue
        items.append(
            schemas.BlockedUserEntry(
                public_sqid=u.public_sqid or "",
                handle=u.handle,
                avatar_url=u.avatar_url,
                blocked_at=b.created_at,
            )
        )

    return schemas.Page(items=items, next_cursor=page_data["next_cursor"])

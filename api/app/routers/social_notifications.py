"""Social Notification endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..deps import get_db
from ..services.social_notifications import SocialNotificationService

router = APIRouter(prefix="/social-notifications", tags=["Social Notifications"])


@router.get("/", response_model=schemas.Page[schemas.SocialNotification])
def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(None, description="ISO timestamp cursor for pagination"),
    unread_only: bool = Query(False, description="Only return unread notifications"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Page[schemas.SocialNotification]:
    """
    List notifications for the current user.

    Returns notifications in reverse chronological order with cursor-based pagination.
    """
    # Parse cursor timestamp if provided
    cursor_dt = None
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid cursor format. Expected ISO timestamp.",
            )

    notifications, next_cursor = SocialNotificationService.list_notifications(
        db=db,
        user_id=current_user.id,
        limit=limit,
        cursor=cursor_dt,
        unread_only=unread_only,
    )

    return schemas.Page(
        items=[schemas.SocialNotification.model_validate(n) for n in notifications],
        next_cursor=next_cursor.isoformat() if next_cursor else None,
    )


@router.get("/unread-count", response_model=schemas.SocialNotificationUnreadCount)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.SocialNotificationUnreadCount:
    """Get unread notification count for the current user."""
    count = SocialNotificationService.get_unread_count(db, current_user.id)
    return schemas.SocialNotificationUnreadCount(unread_count=count)


@router.post("/mark-read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notifications_read(
    notification_ids: list[UUID],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Mark specific notifications as read.

    Accepts a list of notification IDs to mark as read.
    Only notifications belonging to the current user will be updated.
    """
    if not notification_ids:
        return

    if len(notification_ids) > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 200 notifications can be marked at once.",
        )

    SocialNotificationService.mark_as_read(db, notification_ids, current_user.id)


@router.post("/mark-all-read", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Mark all notifications as read for the current user."""
    SocialNotificationService.mark_all_as_read(db, current_user.id)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Delete a specific notification.

    Returns 404 if the notification doesn't exist or doesn't belong to the user.
    """
    deleted = SocialNotificationService.delete_notification(
        db, notification_id, current_user.id
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

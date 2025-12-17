"""Notifications API endpoints."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, verify_token
from ..deps import get_db
from ..services.notifications import NotificationService
from ..websocket_manager import connection_manager

router = APIRouter(prefix="/notifications", tags=["Notifications"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=schemas.Page[schemas.Notification])
def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Page[schemas.Notification]:
    """
    List notifications for the current user.
    
    Returns notifications in reverse chronological order.
    Supports pagination via cursor.
    """
    query = db.query(models.Notification).filter(
        models.Notification.user_id == current_user.id
    )
    
    if unread_only:
        query = query.filter(models.Notification.is_read == False)
    
    # Apply cursor pagination
    if cursor:
        try:
            # Cursor is ISO timestamp
            query = query.filter(models.Notification.created_at < cursor)
        except:
            pass
    
    # Order by created_at descending
    query = query.order_by(models.Notification.created_at.desc())
    
    # Fetch limit + 1 to determine if there are more results
    notifications = query.limit(limit + 1).all()
    
    has_more = len(notifications) > limit
    items = notifications[:limit]
    
    next_cursor = None
    if has_more and items:
        next_cursor = items[-1].created_at.isoformat()
    
    return schemas.Page(
        items=[schemas.Notification.model_validate(n) for n in items],
        next_cursor=next_cursor
    )


@router.get("/unread-count", response_model=schemas.UnreadCountResponse)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.UnreadCountResponse:
    """Get unread notification count for the current user."""
    count = NotificationService.get_unread_count(db, current_user.id)
    return schemas.UnreadCountResponse(unread_count=count)


@router.post("/mark-read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notifications_read(
    notification_ids: list[UUID],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Mark specific notifications as read."""
    NotificationService.mark_as_read(db, notification_ids, current_user.id)


@router.post("/mark-all-read", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Mark all notifications as read for the current user."""
    NotificationService.mark_all_as_read(db, current_user.id)


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Delete a specific notification."""
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    db.delete(notification)
    db.commit()


@router.get("/preferences", response_model=schemas.NotificationPreferences)
def get_notification_preferences(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.NotificationPreferences:
    """Get notification preferences for the current user."""
    prefs = db.query(models.NotificationPreferences).filter(
        models.NotificationPreferences.user_id == current_user.id
    ).first()
    
    if not prefs:
        # Create default preferences
        prefs = models.NotificationPreferences(user_id=current_user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    
    return schemas.NotificationPreferences.model_validate(prefs)


@router.put("/preferences", response_model=schemas.NotificationPreferences)
def update_notification_preferences(
    preferences: schemas.NotificationPreferences,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.NotificationPreferences:
    """Update notification preferences for the current user."""
    prefs = db.query(models.NotificationPreferences).filter(
        models.NotificationPreferences.user_id == current_user.id
    ).first()
    
    if not prefs:
        prefs = models.NotificationPreferences(user_id=current_user.id)
        db.add(prefs)
    
    # Update preferences
    prefs.notify_on_post_reactions = preferences.notify_on_post_reactions
    prefs.notify_on_post_comments = preferences.notify_on_post_comments
    prefs.notify_on_blog_reactions = preferences.notify_on_blog_reactions
    prefs.notify_on_blog_comments = preferences.notify_on_blog_comments
    prefs.aggregate_same_type = preferences.aggregate_same_type
    
    db.commit()
    db.refresh(prefs)
    
    return schemas.NotificationPreferences.model_validate(prefs)


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str,  # JWT token passed as query parameter
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for real-time notifications.
    
    Clients connect via: ws://api.example.com/api/notifications/ws?token=<jwt_token>
    """
    # Verify token and get user
    try:
        payload = verify_token(token)
        user_id = payload.get("user_id")
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token")
            return
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        await websocket.close(code=1008, reason="Authentication failed")
        return
    
    # Connect user
    connected = await connection_manager.connect(websocket, user_id)
    if not connected:
        await websocket.close(code=1008, reason="Connection limit reached")
        return
    
    try:
        # Keep connection alive and handle incoming messages
        while True:
            # Receive messages (ping/pong for keepalive)
            data = await websocket.receive_text()
            
            # Handle ping/pong
            if data == "ping":
                await websocket.send_text("pong")
            
            # Could add more message types here (e.g., mark as read)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
    finally:
        await connection_manager.disconnect(websocket, user_id)

"""Service for managing notifications."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..cache import get_redis

if TYPE_CHECKING:
    from ..auth import AnonymousUser

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for creating and managing notifications."""
    
    @staticmethod
    def create_notification(
        db: Session,
        user_id: int,
        notification_type: str,
        content_type: str,
        content_id: int,
        actor: models.User | AnonymousUser | None = None,
        emoji: str | None = None,
        comment_id: UUID | None = None,
        comment_body: str | None = None,
        content_title: str | None = None,
        content_url: str | None = None,
    ) -> models.Notification | None:
        """Create a notification and broadcast via WebSocket."""
        
        # Don't notify users about their own actions
        if actor and isinstance(actor, models.User) and actor.id == user_id:
            return None
        
        # Check user preferences
        prefs = db.query(models.NotificationPreferences).filter(
            models.NotificationPreferences.user_id == user_id
        ).first()
        
        if prefs:
            # Check if user wants this type of notification
            # Map content_type to the correct preference key
            if content_type == "blog_post":
                pref_key = f"notify_on_blog_{notification_type}s"
            else:
                pref_key = f"notify_on_{content_type}_{notification_type}s"
            
            if hasattr(prefs, pref_key) and not getattr(prefs, pref_key):
                logger.debug(f"User {user_id} has disabled {pref_key}, skipping notification")
                return None
        
        # Rate limiting: max 720 notifications per hour from same actor
        if actor and isinstance(actor, models.User):
            try:
                redis = get_redis()
                if redis:
                    rate_limit_key = f"notif_rate:{actor.id}:{user_id}"
                    count = redis.incr(rate_limit_key)
                    if count == 1:
                        redis.expire(rate_limit_key, 3600)  # 1 hour
                    if count > 720:
                        logger.warning(f"Rate limit exceeded for notifications from {actor.id} to {user_id}")
                        return None
            except Exception as e:
                logger.error(f"Failed to check rate limit: {e}")
        
        # Rate limiting: max 8640 notifications per day total
        try:
            redis = get_redis()
            if redis:
                daily_rate_limit_key = f"notif_daily_rate:{user_id}"
                count = redis.incr(daily_rate_limit_key)
                if count == 1:
                    redis.expire(daily_rate_limit_key, 86400)  # 24 hours
                if count > 8640:
                    logger.warning(f"Daily rate limit exceeded for user {user_id}")
                    return None
        except Exception as e:
            logger.error(f"Failed to check daily rate limit: {e}")
        
        # Prepare actor info
        actor_id = actor.id if isinstance(actor, models.User) else None
        actor_ip = actor.ip if hasattr(actor, 'ip') else None
        actor_handle = actor.handle if isinstance(actor, models.User) else "Anonymous"
        
        # Prepare comment preview (first 100 chars)
        comment_preview = None
        if comment_body:
            comment_preview = comment_body[:100]
            if len(comment_body) > 100:
                comment_preview += "..."
        
        # Create notification record
        notification = models.Notification(
            user_id=user_id,
            notification_type=notification_type,
            content_type=content_type,
            content_id=content_id,
            actor_id=actor_id,
            actor_ip=actor_ip,
            actor_handle=actor_handle,
            emoji=emoji,
            comment_id=comment_id,
            comment_preview=comment_preview,
            content_title=content_title,
            content_url=content_url,
            is_read=False,
        )
        
        db.add(notification)
        db.commit()
        db.refresh(notification)
        
        # Update Redis counter
        NotificationService._increment_unread_count(user_id)
        
        # Broadcast WebSocket notification
        NotificationService._broadcast_notification(notification)
        
        logger.info(f"Created notification {notification.id} for user {user_id}")
        return notification
    
    @staticmethod
    def _increment_unread_count(user_id: int) -> None:
        """Increment unread count in Redis."""
        try:
            redis = get_redis()
            if redis:
                key = f"user:{user_id}:unread_count"
                redis.incr(key)
                # Set expiry to 7 days
                redis.expire(key, 7 * 24 * 60 * 60)
        except Exception as e:
            logger.error(f"Failed to increment unread count in Redis: {e}")
    
    @staticmethod
    def _broadcast_notification(notification: models.Notification) -> None:
        """Broadcast notification via Redis Pub/Sub to WebSocket connections."""
        try:
            redis = get_redis()
            if redis:
                channel = f"notifications:user:{notification.user_id}"
                payload = {
                    "id": str(notification.id),
                    "notification_type": notification.notification_type,
                    "content_type": notification.content_type,
                    "content_id": notification.content_id,
                    "actor_handle": notification.actor_handle,
                    "emoji": notification.emoji,
                    "comment_preview": notification.comment_preview,
                    "content_title": notification.content_title,
                    "content_url": notification.content_url,
                    "created_at": notification.created_at.isoformat(),
                }
                redis.publish(channel, json.dumps(payload))
                logger.info(f"Broadcast notification for user {notification.user_id} via Redis Pub/Sub")
        except Exception as e:
            logger.error(f"Failed to broadcast notification via Redis: {e}")
    
    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        """Get unread notification count for a user."""
        # Try Redis first
        try:
            redis = get_redis()
            if redis:
                key = f"user:{user_id}:unread_count"
                count = redis.get(key)
                if count is not None:
                    return int(count)
        except Exception as e:
            logger.warning(f"Failed to get unread count from Redis: {e}")
        
        # Fallback to database
        count = db.query(func.count(models.Notification.id)).filter(
            models.Notification.user_id == user_id,
            models.Notification.is_read == False
        ).scalar()
        
        # Update Redis cache
        try:
            redis = get_redis()
            if redis:
                key = f"user:{user_id}:unread_count"
                redis.set(key, count or 0, ex=7 * 24 * 60 * 60)
        except Exception as e:
            logger.warning(f"Failed to cache unread count in Redis: {e}")
        
        return count or 0
    
    @staticmethod
    def mark_as_read(db: Session, notification_ids: list[UUID], user_id: int) -> int:
        """Mark notifications as read. Returns count of updated notifications."""
        count = db.query(models.Notification).filter(
            models.Notification.id.in_(notification_ids),
            models.Notification.user_id == user_id,
            models.Notification.is_read == False
        ).update(
            {
                models.Notification.is_read: True,
                models.Notification.read_at: datetime.now(timezone.utc)
            },
            synchronize_session=False
        )
        
        db.commit()
        
        # Decrement Redis counter
        if count > 0:
            try:
                redis = get_redis()
                if redis:
                    key = f"user:{user_id}:unread_count"
                    redis.decrby(key, count)
            except Exception as e:
                logger.error(f"Failed to decrement unread count in Redis: {e}")
        
        return count
    
    @staticmethod
    def mark_all_as_read(db: Session, user_id: int) -> int:
        """Mark all notifications as read for a user. Returns count of updated notifications."""
        count = db.query(models.Notification).filter(
            models.Notification.user_id == user_id,
            models.Notification.is_read == False
        ).update(
            {
                models.Notification.is_read: True,
                models.Notification.read_at: datetime.now(timezone.utc)
            },
            synchronize_session=False
        )
        
        db.commit()
        
        # Reset Redis counter
        try:
            redis = get_redis()
            if redis:
                key = f"user:{user_id}:unread_count"
                redis.set(key, 0, ex=7 * 24 * 60 * 60)
        except Exception as e:
            logger.error(f"Failed to reset unread count in Redis: {e}")
        
        return count
    
    @staticmethod
    def cleanup_old_notifications(db: Session, days: int = 90) -> int:
        """Delete notifications older than specified days. Returns count of deleted notifications."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        
        count = db.query(models.Notification).filter(
            models.Notification.created_at < cutoff_date
        ).delete(synchronize_session=False)
        
        db.commit()
        
        logger.info(f"Cleaned up {count} notifications older than {days} days")
        return count

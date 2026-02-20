"""
Social Notification Service.

Handles creation, retrieval, and management of social notifications
for reactions and comments on artwork.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..cache import (
    cache_get_int,
    cache_incr,
    cache_set_int,
    rate_limit_check,
)
from ..mqtt.publisher import publish

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Cache key patterns
UNREAD_COUNT_KEY = "social_notif:unread:{user_id}"
RATE_LIMIT_KEY = "social_notif:rate:{actor_id}:{recipient_id}"

# Rate limits
MAX_NOTIFICATIONS_PER_HOUR_PER_PAIR = 720  # From same actor to same recipient


class SocialNotificationService:
    """Service for managing social notifications."""

    @staticmethod
    def create_notification(
        db: Session,
        user_id: int,
        notification_type: str,
        post: models.Post,
        actor: models.User | None = None,
        emoji: str | None = None,
        comment: models.Comment | None = None,
    ) -> models.SocialNotification | None:
        """
        Create a social notification and broadcast via MQTT.

        Args:
            db: Database session
            user_id: ID of user to notify (post owner)
            notification_type: 'reaction' or 'comment'
            post: The post that received the reaction/comment
            actor: The user who performed the action (None for anonymous)
            emoji: The emoji for reaction notifications
            comment: The comment object for comment notifications

        Returns:
            Created notification, or None if skipped (self-action or rate limited)
        """
        # Don't notify users about their own actions
        if actor and actor.id == user_id:
            logger.debug(f"Skipping self-notification for user {user_id}")
            return None

        # Rate limiting for authenticated actors
        if actor:
            rate_key = RATE_LIMIT_KEY.format(actor_id=actor.id, recipient_id=user_id)
            if not rate_limit_check(rate_key, MAX_NOTIFICATIONS_PER_HOUR_PER_PAIR):
                logger.warning(
                    f"Rate limit exceeded for notifications from actor {actor.id} to user {user_id}"
                )
                return None

        # Prepare comment preview
        comment_preview = None
        comment_id = None
        if comment:
            comment_id = comment.id
            if comment.body:
                comment_preview = comment.body[:100]
                if len(comment.body) > 100:
                    comment_preview += "..."

        # Create notification record
        notification = models.SocialNotification(
            user_id=user_id,
            notification_type=notification_type,
            post_id=post.id,
            actor_id=actor.id if actor else None,
            actor_handle=actor.handle if actor else "Anonymous",
            actor_avatar_url=actor.avatar_url if actor else None,
            emoji=emoji,
            comment_id=comment_id,
            comment_preview=comment_preview,
            content_title=post.title,
            content_sqid=post.public_sqid,
            content_art_url=post.art_url,
        )

        db.add(notification)
        db.commit()
        db.refresh(notification)

        logger.info(
            f"Created {notification_type} notification {notification.id} for user {user_id}"
        )

        # Update Redis unread counter
        SocialNotificationService._increment_unread_count(user_id)

        # Broadcast via MQTT for real-time delivery
        SocialNotificationService._broadcast_notification(notification)

        return notification

    @staticmethod
    def create_system_notification(
        db: Session,
        user_id: int,
        notification_type: str,
        actor: models.User,
        *,
        content_title: str | None = None,
    ) -> models.SocialNotification | None:
        """
        Create a system notification (no artwork reference).

        Used for system events like moderator status changes.

        Args:
            db: Database session
            user_id: ID of user to notify
            notification_type: 'moderator_granted', 'moderator_revoked', etc.
            actor: The user who performed the action

        Returns:
            Created notification, or None if skipped (self-action)
        """
        # Don't notify users about their own actions
        if actor.id == user_id:
            logger.debug(f"Skipping self-notification for user {user_id}")
            return None

        # Create notification record (no post reference)
        notification = models.SocialNotification(
            user_id=user_id,
            notification_type=notification_type,
            post_id=None,  # System notifications have no artwork
            actor_id=actor.id,
            actor_handle=actor.handle,
            actor_avatar_url=actor.avatar_url,
            content_title=content_title,
        )

        db.add(notification)
        db.commit()
        db.refresh(notification)

        logger.info(
            f"Created system notification {notification.id} ({notification_type}) for user {user_id}"
        )

        # Update Redis unread counter
        SocialNotificationService._increment_unread_count(user_id)

        # Broadcast via MQTT for real-time delivery
        SocialNotificationService._broadcast_notification(notification)

        return notification

    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        """
        Get unread notification count for a user.

        Uses Redis cache with database fallback.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Unread notification count
        """
        # Try Redis cache first
        cache_key = UNREAD_COUNT_KEY.format(user_id=user_id)
        cached = cache_get_int(cache_key)
        if cached is not None:
            return cached

        # Fallback to database query
        count = (
            db.query(func.count(models.SocialNotification.id))
            .filter(
                models.SocialNotification.user_id == user_id,
                models.SocialNotification.is_read == False,
            )
            .scalar()
            or 0
        )

        # Cache the result
        cache_set_int(cache_key, count)

        return count

    @staticmethod
    def list_notifications(
        db: Session,
        user_id: int,
        limit: int = 50,
        cursor: datetime | None = None,
        unread_only: bool = False,
    ) -> tuple[list[models.SocialNotification], datetime | None]:
        """
        List notifications for a user with cursor-based pagination.

        Args:
            db: Database session
            user_id: User ID
            limit: Maximum number of notifications to return
            cursor: Timestamp cursor for pagination (exclusive)
            unread_only: If True, only return unread notifications

        Returns:
            Tuple of (notifications, next_cursor)
        """
        query = db.query(models.SocialNotification).filter(
            models.SocialNotification.user_id == user_id
        )

        if unread_only:
            query = query.filter(models.SocialNotification.is_read == False)

        if cursor:
            query = query.filter(models.SocialNotification.created_at < cursor)

        # Order by created_at descending (newest first)
        query = query.order_by(models.SocialNotification.created_at.desc())

        # Fetch limit + 1 to determine if there are more results
        notifications = query.limit(limit + 1).all()

        # Determine next cursor
        has_more = len(notifications) > limit
        items = notifications[:limit]

        next_cursor = None
        if has_more and items:
            next_cursor = items[-1].created_at

        return items, next_cursor

    @staticmethod
    def mark_as_read(db: Session, notification_ids: list[UUID], user_id: int) -> int:
        """
        Mark specific notifications as read.

        Args:
            db: Database session
            notification_ids: List of notification IDs to mark as read
            user_id: User ID (for authorization)

        Returns:
            Number of notifications updated
        """
        count = (
            db.query(models.SocialNotification)
            .filter(
                models.SocialNotification.id.in_(notification_ids),
                models.SocialNotification.user_id == user_id,
                models.SocialNotification.is_read == False,
            )
            .update(
                {"is_read": True, "read_at": datetime.utcnow()},
                synchronize_session=False,
            )
        )

        db.commit()

        # Update Redis counter
        if count > 0:
            SocialNotificationService._decrement_unread_count(user_id, count)

        return count

    @staticmethod
    def mark_all_as_read(db: Session, user_id: int) -> int:
        """
        Mark all notifications as read for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Number of notifications updated
        """
        count = (
            db.query(models.SocialNotification)
            .filter(
                models.SocialNotification.user_id == user_id,
                models.SocialNotification.is_read == False,
            )
            .update(
                {"is_read": True, "read_at": datetime.utcnow()},
                synchronize_session=False,
            )
        )

        db.commit()

        # Reset Redis counter to 0
        if count > 0:
            cache_key = UNREAD_COUNT_KEY.format(user_id=user_id)
            cache_set_int(cache_key, 0)

        return count

    @staticmethod
    def delete_notification(db: Session, notification_id: UUID, user_id: int) -> bool:
        """
        Delete a specific notification.

        Args:
            db: Database session
            notification_id: Notification ID
            user_id: User ID (for authorization)

        Returns:
            True if deleted, False if not found
        """
        notification = (
            db.query(models.SocialNotification)
            .filter(
                models.SocialNotification.id == notification_id,
                models.SocialNotification.user_id == user_id,
            )
            .first()
        )

        if not notification:
            return False

        was_unread = not notification.is_read

        db.delete(notification)
        db.commit()

        # Update Redis counter if was unread
        if was_unread:
            SocialNotificationService._decrement_unread_count(user_id, 1)

        return True

    # =========================================================================
    # Private helper methods
    # =========================================================================

    @staticmethod
    def _increment_unread_count(user_id: int) -> None:
        """Increment the unread count in Redis cache."""
        cache_key = UNREAD_COUNT_KEY.format(user_id=user_id)
        cache_incr(cache_key)

    @staticmethod
    def _decrement_unread_count(user_id: int, amount: int = 1) -> None:
        """Decrement the unread count in Redis cache."""
        from ..cache import cache_decr

        cache_key = UNREAD_COUNT_KEY.format(user_id=user_id)
        cache_decr(cache_key, amount)

    @staticmethod
    def _broadcast_notification(notification: models.SocialNotification) -> None:
        """
        Broadcast notification via MQTT for real-time delivery.

        Publishes to topic: makapix/social-notifications/user/{user_id}
        """
        payload = {
            "id": str(notification.id),
            "notification_type": notification.notification_type,
            "post_id": notification.post_id,
            "actor_handle": notification.actor_handle,
            "actor_avatar_url": notification.actor_avatar_url,
            "emoji": notification.emoji,
            "comment_preview": notification.comment_preview,
            "content_title": notification.content_title,
            "content_sqid": notification.content_sqid,
            "content_art_url": notification.content_art_url,
            "created_at": notification.created_at.isoformat(),
        }

        topic = f"makapix/social-notifications/user/{notification.user_id}"

        success = publish(topic, payload, qos=1, retain=False)

        if success:
            logger.debug(
                f"Broadcast notification {notification.id} to MQTT topic {topic}"
            )
        else:
            logger.warning(
                f"Failed to broadcast notification {notification.id} to MQTT"
            )

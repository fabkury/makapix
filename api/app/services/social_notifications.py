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

from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from ..cache import rate_limit_check
from ..services.event_bus import notification_bus

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Cache key patterns
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
        extra_preview: str | None = None,
    ) -> models.SocialNotification | None:
        """
        Create a social notification and dispatch it live over the SSE bus.

        Args:
            db: Database session
            user_id: ID of user to notify (post owner)
            notification_type: 'reaction', 'comment', 'post_promoted', etc.
            post: The post that received the reaction/comment
            actor: The user who performed the action (None for anonymous)
            emoji: The emoji for reaction notifications
            comment: The comment object for comment notifications
            extra_preview: Free-text stored in comment_preview when no
                           comment is provided (e.g. promotion category name)

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
        elif extra_preview:
            comment_preview = extra_preview

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

        # Live delivery (in-process SSE bus)
        SocialNotificationService._dispatch_notification(db, notification)

        return notification

    @staticmethod
    def create_system_notification(
        db: Session,
        user_id: int,
        notification_type: str,
        actor: models.User,
        *,
        content_title: str | None = None,
        post: models.Post | None = None,
        comment: models.Comment | None = None,
        target_user: models.User | None = None,
        reason_code: str | None = None,
    ) -> models.SocialNotification | None:
        """
        Create a system notification.

        Used for system events like moderator status changes. Report
        notifications (docs/report-artwork/) additionally reference what was
        reported: `post` (a comment's parent post for comment reports, with
        the comment excerpt in comment_preview) or `target_user`, plus the
        report's `reason_code`.

        Args:
            db: Database session
            user_id: ID of user to notify
            notification_type: 'moderator_granted', 'moderator_revoked', etc.
            actor: The user who performed the action
            content_title: Free-text title; defaults to the post title when a
                           post is given

        Returns:
            Created notification, or None if skipped (self-action)
        """
        # Don't notify users about their own actions
        if actor.id == user_id:
            logger.debug(f"Skipping self-notification for user {user_id}")
            return None

        comment_preview = None
        if comment is not None and comment.body:
            comment_preview = comment.body[:100]
            if len(comment.body) > 100:
                comment_preview += "..."

        notification = models.SocialNotification(
            user_id=user_id,
            notification_type=notification_type,
            post_id=post.id if post is not None else None,
            actor_id=actor.id,
            actor_handle=actor.handle,
            actor_avatar_url=actor.avatar_url,
            comment_id=comment.id if comment is not None else None,
            comment_preview=comment_preview,
            content_title=(
                content_title
                if content_title is not None
                else (post.title if post is not None else None)
            ),
            content_sqid=post.public_sqid if post is not None else None,
            content_art_url=post.art_url if post is not None else None,
            target_user_id=target_user.id if target_user is not None else None,
            reason_code=reason_code,
        )

        db.add(notification)
        db.commit()
        db.refresh(notification)

        logger.info(
            f"Created system notification {notification.id} ({notification_type}) for user {user_id}"
        )

        # Live delivery (in-process SSE bus)
        SocialNotificationService._dispatch_notification(db, notification)

        return notification

    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        """
        Get unread notification count for a user.

        Computed directly from the database (rides the partial index
        ix_social_notifications_user_unread), block-filtered to match the
        list surface — the count is always consistent, no counter to drift.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Unread notification count
        """
        from ..utils.blocks import apply_block_filter

        query = db.query(func.count(models.SocialNotification.id)).filter(
            models.SocialNotification.user_id == user_id,
            models.SocialNotification.is_read == False,
        )
        query = apply_block_filter(query, models.SocialNotification.actor_id, user_id)
        return query.scalar() or 0

    @staticmethod
    def list_notifications(
        db: Session,
        user_id: int,
        limit: int = 50,
        cursor: tuple[datetime, UUID | None] | None = None,
        unread_only: bool = False,
    ) -> tuple[list[models.SocialNotification], str | None]:
        """
        List notifications for a user with cursor-based pagination.

        Args:
            db: Database session
            user_id: User ID
            limit: Maximum number of notifications to return
            cursor: (created_at, id) keyset cursor, exclusive. A None id
                    means a legacy timestamp-only cursor (strict created_at <).
            unread_only: If True, only return unread notifications

        Returns:
            Tuple of (notifications, opaque next_cursor string)
        """
        query = (
            db.query(models.SocialNotification)
            .options(
                selectinload(models.SocialNotification.actor),
                selectinload(models.SocialNotification.target_user),
            )
            .filter(models.SocialNotification.user_id == user_id)
        )

        # Hide notifications whose actor the viewer has blocked
        # (docs/ugc-safety/ D10); actor-less/system rows are unaffected.
        from ..utils.blocks import apply_block_filter

        query = apply_block_filter(query, models.SocialNotification.actor_id, user_id)

        if unread_only:
            query = query.filter(models.SocialNotification.is_read == False)

        if cursor:
            cursor_ts, cursor_id = cursor
            if cursor_id is None:
                # Legacy timestamp-only cursor (pre-tiebreaker app clients).
                query = query.filter(models.SocialNotification.created_at < cursor_ts)
            else:
                query = query.filter(
                    or_(
                        models.SocialNotification.created_at < cursor_ts,
                        and_(
                            models.SocialNotification.created_at == cursor_ts,
                            models.SocialNotification.id < cursor_id,
                        ),
                    )
                )

        # Newest first; id tiebreaker makes the keyset total (rows sharing a
        # created_at no longer skip across page boundaries).
        query = query.order_by(
            models.SocialNotification.created_at.desc(),
            models.SocialNotification.id.desc(),
        )

        # Fetch limit + 1 to determine if there are more results
        notifications = query.limit(limit + 1).all()

        # Determine next cursor
        has_more = len(notifications) > limit
        items = notifications[:limit]

        next_cursor = None
        if has_more and items:
            from ..pagination import encode_cursor

            next_cursor = encode_cursor(
                str(items[-1].id), items[-1].created_at.isoformat()
            )

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

        db.delete(notification)
        db.commit()

        return True

    # =========================================================================
    # Private helper methods
    # =========================================================================

    @staticmethod
    def _dispatch_notification(
        db: Session, notification: models.SocialNotification
    ) -> None:
        """
        Live-delivery dispatch: in-process SSE bus.

        Runs post-commit in the request thread; a crash here loses only the
        live event — the inbox row survives and the next SSE `connected`
        greeting / list backfill reconciles the client.

        Live delivery is gated on the recipient's blocks (D10): the row is
        always created (unblock reveals history), but a blocked actor's
        activity must not reach the recipient live.
        """
        from ..utils.blocks import viewer_has_blocked

        if notification.actor_id is not None and viewer_has_blocked(
            db, viewer_id=notification.user_id, author_id=notification.actor_id
        ):
            return

        # Full REST shape (resolves actor_public_sqid while the session is
        # open); identical to GET /v1/social-notifications/ items so SSE
        # clients can treat both sources uniformly and dedupe by id.
        payload = schemas.SocialNotification.model_validate(notification).model_dump(
            mode="json"
        )
        notification_bus.publish_threadsafe(notification.user_id, payload)

"""MQTT notification publishing functions."""

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from .. import models
from ..utils.monitored_hashtags import post_has_unapproved_monitored_hashtags
from .publisher import publish
from .schemas import PostNotificationPayload

logger = logging.getLogger(__name__)


def publish_new_post_notification(post_id: int, db: Session) -> None:
    """
    Publish MQTT notification for a new post to all followers of the post owner.

    Args:
        post_id: Integer ID of the newly created post
        db: Database session
    """
    # Fetch post with owner details
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        logger.warning(f"Post {post_id} not found for notification")
        return

    # Fetch owner details
    owner = db.query(models.User).filter(models.User.id == post.owner_id).first()
    if not owner:
        logger.warning(f"Owner {post.owner_id} not found for post {post_id}")
        return

    # Build notification payload
    payload = PostNotificationPayload(
        post_id=post.id,
        owner_id=post.owner_id,
        owner_handle=owner.handle,
        title=post.title,
        art_url=post.art_url,
        canvas=post.canvas,
        promoted_category=post.promoted_category,
        created_at=post.created_at,
    ).model_dump(mode="json")

    # Find all followers of the post owner (with their user data for hashtag filtering)
    followers = (
        db.query(models.User)
        .join(models.Follow, models.Follow.follower_id == models.User.id)
        .filter(models.Follow.following_id == post.owner_id)
        .all()
    )

    # Publish to user-specific topics for each follower
    notified_count = 0
    skipped_count = 0
    for follower in followers:
        # Skip followers who haven't approved the post's monitored hashtags
        if post_has_unapproved_monitored_hashtags(post, follower):
            skipped_count += 1
            logger.debug(
                f"Skipped notification to follower {follower.id} for post {post_id}: "
                "unapproved monitored hashtags"
            )
            continue

        topic = f"makapix/post/new/user/{follower.id}/{post_id}"

        success = publish(topic, payload, qos=1, retain=False)
        if success:
            notified_count += 1
            logger.info(
                f"Published new post notification to follower {follower.id} for post {post_id}"
            )
        else:
            logger.error(
                f"Failed to publish notification to follower {follower.id} for post {post_id}"
            )

    # Also publish to generic topic (for monitoring/debugging)
    generic_topic = f"makapix/post/new/{post_id}"
    publish(generic_topic, payload, qos=1, retain=False)

    logger.info(
        f"Published new post notification for post {post_id}: "
        f"{notified_count} notified, {skipped_count} skipped (monitored hashtags)"
    )


def publish_category_promotion_notification(
    post_id: int, category: str, db: Session
) -> None:
    """
    Publish MQTT notification when a post is promoted to a category.

    This is specifically for "daily's-best" category notifications.
    Posts are notified when promoted, not when created.

    Args:
        post_id: Integer ID of the promoted post
        category: Category name (e.g., "daily's-best")
        db: Database session
    """
    # Fetch post with owner details
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        logger.warning(f"Post {post_id} not found for category notification")
        return

    # Fetch owner details
    owner = db.query(models.User).filter(models.User.id == post.owner_id).first()
    if not owner:
        logger.warning(f"Owner {post.owner_id} not found for post {post_id}")
        return

    # Build notification payload
    payload = PostNotificationPayload(
        post_id=post.id,
        owner_id=post.owner_id,
        owner_handle=owner.handle,
        title=post.title,
        art_url=post.art_url,
        canvas=post.canvas,
        promoted_category=category,
        created_at=post.created_at,
    ).model_dump(mode="json")

    # Find all users following this category (with their user data for hashtag filtering)
    category_followers = (
        db.query(models.User)
        .join(models.CategoryFollow, models.CategoryFollow.user_id == models.User.id)
        .filter(models.CategoryFollow.category == category)
        .all()
    )

    # Publish to category-specific topics for each follower
    notified_count = 0
    skipped_count = 0
    for follower in category_followers:
        # Skip followers who haven't approved the post's monitored hashtags
        if post_has_unapproved_monitored_hashtags(post, follower):
            skipped_count += 1
            logger.debug(
                f"Skipped category notification to follower {follower.id} for "
                f"category {category}, post {post_id}: unapproved monitored hashtags"
            )
            continue

        topic = f"makapix/post/new/category/{category}/{post_id}"

        success = publish(topic, payload, qos=1, retain=False)
        if success:
            notified_count += 1
            logger.info(
                f"Published category promotion notification to follower {follower.id} "
                f"for category {category}, post {post_id}"
            )
        else:
            logger.error(
                f"Failed to publish category notification to follower {follower.id} "
                f"for category {category}, post {post_id}"
            )

    # Also publish to generic category topic
    generic_topic = f"makapix/post/new/category/{category}/{post_id}"
    publish(generic_topic, payload, qos=1, retain=False)

    logger.info(
        f"Published category promotion notification for category {category}, post {post_id}: "
        f"{notified_count} notified, {skipped_count} skipped (monitored hashtags)"
    )

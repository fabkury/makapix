"""MQTT notification publishing functions."""

from __future__ import annotations

import logging
from sqlalchemy.orm import Session
from uuid import UUID

from .. import models
from .publisher import publish
from .schemas import PostNotificationPayload

logger = logging.getLogger(__name__)


def publish_new_post_notification(post_id: UUID, db: Session) -> None:
    """
    Publish MQTT notification for a new post to all followers of the post owner.
    
    Args:
        post_id: UUID of the newly created post
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
    
    # Find all followers of the post owner
    followers = (
        db.query(models.Follow.follower_id)
        .filter(models.Follow.following_id == post.owner_id)
        .all()
    )
    
    # Publish to user-specific topics for each follower
    for follower in followers:
        follower_id = follower.follower_id
        topic = f"makapix/posts/new/user/{follower_id}/{post_id}"
        
        success = publish(topic, payload, qos=1, retain=False)
        if success:
            logger.info(f"Published new post notification to follower {follower_id} for post {post_id}")
        else:
            logger.error(f"Failed to publish notification to follower {follower_id} for post {post_id}")
    
    # Also publish to generic topic (for monitoring/debugging)
    generic_topic = f"makapix/posts/new/{post_id}"
    publish(generic_topic, payload, qos=1, retain=False)
    
    logger.info(f"Published new post notification for post {post_id} to {len(followers)} followers")


def publish_category_promotion_notification(post_id: UUID, category: str, db: Session) -> None:
    """
    Publish MQTT notification when a post is promoted to a category.
    
    This is specifically for "daily's-best" category notifications.
    Posts are notified when promoted, not when created.
    
    Args:
        post_id: UUID of the promoted post
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
    
    # Find all users following this category
    category_followers = (
        db.query(models.CategoryFollow.user_id)
        .filter(models.CategoryFollow.category == category)
        .all()
    )
    
    # Publish to category-specific topics for each follower
    for follower in category_followers:
        follower_id = follower.user_id
        topic = f"makapix/posts/new/category/{category}/{post_id}"
        
        success = publish(topic, payload, qos=1, retain=False)
        if success:
            logger.info(f"Published category promotion notification to follower {follower_id} for category {category}, post {post_id}")
        else:
            logger.error(f"Failed to publish category notification to follower {follower_id} for category {category}, post {post_id}")
    
    # Also publish to generic category topic
    generic_topic = f"makapix/posts/new/category/{category}/{post_id}"
    publish(generic_topic, payload, qos=1, retain=False)
    
    logger.info(f"Published category promotion notification for category {category}, post {post_id} to {len(category_followers)} followers")


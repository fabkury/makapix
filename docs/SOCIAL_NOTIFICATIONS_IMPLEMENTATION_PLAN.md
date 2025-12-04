# Social Notifications System - Detailed Implementation Plan

**Project:** Makapix Club  
**Feature:** Social Notifications for Reactions and Comments  
**Target Scale:** 10,000 Monthly Active Users (MAU)  
**Date:** December 2025

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Database Schema](#database-schema)
4. [Backend Implementation](#backend-implementation)
5. [Frontend Implementation](#frontend-implementation)
6. [MQTT Real-Time Updates](#mqtt-real-time-updates)
7. [Performance Expectations](#performance-expectations)
8. [Implementation Phases](#implementation-phases)
9. [Testing Strategy](#testing-strategy)
10. [Migration Strategy](#migration-strategy)

---

## Executive Summary

This plan details the implementation of a social notifications system for Makapix Club that will notify users when their artwork or blog posts receive reactions or comments. The system leverages existing infrastructure (PostgreSQL, MQTT, Redis) to deliver real-time notifications efficiently while maintaining low operational costs.

### Key Features

- **Unified notifications** for artwork reactions, artwork comments, blog post reactions, and blog post comments
- **Unread counter badge** displayed on user profile button in header (bottom-right overlay)
- **Notifications button** on user profile page with same counter
- **Dedicated notifications page** showing all notifications with highlights for unread items
- **Real-time updates** via MQTT push notifications while user is logged in
- **Mark as read** functionality that automatically marks notifications as read when user views notifications page
- **Performance-optimized** for 10k MAU with sub-100ms response times

---

## System Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    User Action Occurs                        │
│          (Someone reacts/comments on your content)           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               FastAPI Endpoint Handler                       │
│     (reactions.py / comments.py / blog_posts.py)            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│            Create Notification Record in DB                  │
│               (notifications table)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│          Publish MQTT Notification Message                   │
│       (makapix/notifications/user/{user_id})                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         Update Redis Counter (unread count)                  │
│            (user:{user_id}:unread_count)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│           User's Browser Receives MQTT Message               │
│        (Updates badge counter in real-time via WS)           │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| **PostgreSQL** | Store notification records, user preferences, read status |
| **Redis** | Cache unread notification counts for fast access |
| **MQTT** | Real-time push notifications to connected clients |
| **FastAPI** | API endpoints for CRUD operations on notifications |
| **Next.js** | UI components for notification display and interaction |

---

## Database Schema

### New Tables

#### `notifications` Table

Stores all notification records for users.

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Type and source
    notification_type VARCHAR(50) NOT NULL,  -- 'reaction', 'comment'
    content_type VARCHAR(50) NOT NULL,       -- 'post', 'blog_post'
    content_id INTEGER NOT NULL,             -- References posts.id or blog_posts.id
    
    -- Actor (who triggered the notification)
    actor_id INTEGER REFERENCES users(id) ON DELETE SET NULL,  -- NULL for anonymous
    actor_ip VARCHAR(45),                     -- For anonymous actors
    actor_handle VARCHAR(50),                 -- Denormalized for display
    
    -- Notification details
    emoji VARCHAR(20),                        -- For reaction notifications
    comment_id UUID,                          -- For comment notifications (references comments.id or blog_post_comments.id)
    comment_preview TEXT,                     -- First 100 chars of comment
    
    -- Content metadata (denormalized for display)
    content_title VARCHAR(200),
    content_url VARCHAR(1000),                -- art_url or blog post route
    
    -- Status
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    read_at TIMESTAMP WITH TIME ZONE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_notifications_user_created (user_id, created_at DESC),
    INDEX idx_notifications_user_unread (user_id, is_read, created_at DESC),
    INDEX idx_notifications_content (content_type, content_id)
);
```

#### `notification_preferences` Table

Stores user preferences for notification types (future enhancement).

```sql
CREATE TABLE notification_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    
    -- Notification type preferences
    notify_on_post_reactions BOOLEAN NOT NULL DEFAULT TRUE,
    notify_on_post_comments BOOLEAN NOT NULL DEFAULT TRUE,
    notify_on_blog_reactions BOOLEAN NOT NULL DEFAULT TRUE,
    notify_on_blog_comments BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Aggregation settings
    aggregate_same_type BOOLEAN NOT NULL DEFAULT TRUE,  -- Group similar notifications
    
    -- Updated timestamp
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

### Indexes Strategy

1. **Primary access pattern**: Fetch recent notifications for a user
   - `idx_notifications_user_created (user_id, created_at DESC)`

2. **Unread count**: Fast count of unread notifications
   - `idx_notifications_user_unread (user_id, is_read, created_at DESC)`

3. **Content lookup**: Find notifications for specific content
   - `idx_notifications_content (content_type, content_id)`

### Data Retention

- Keep notifications for **90 days** by default
- Implement background job to clean up old notifications
- Users can manually delete individual notifications
- Deleted content cascades to delete related notifications

---

## Backend Implementation

### 1. Database Models

**File:** `api/app/models.py`

Add new models:

```python
class Notification(Base):
    """User notification for social interactions."""
    
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Type and source
    notification_type = Column(String(50), nullable=False)  # 'reaction', 'comment'
    content_type = Column(String(50), nullable=False)       # 'post', 'blog_post'
    content_id = Column(Integer, nullable=False)
    
    # Actor
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_ip = Column(String(45), nullable=True)
    actor_handle = Column(String(50), nullable=True)
    
    # Details
    emoji = Column(String(20), nullable=True)
    comment_id = Column(UUID(as_uuid=True), nullable=True)
    comment_preview = Column(Text, nullable=True)
    
    # Content metadata
    content_title = Column(String(200), nullable=True)
    content_url = Column(String(1000), nullable=True)
    
    # Status
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="notifications")
    actor = relationship("User", foreign_keys=[actor_id])
    
    __table_args__ = (
        Index("ix_notifications_user_created", user_id, created_at.desc()),
        Index("ix_notifications_user_unread", user_id, is_read, created_at.desc()),
        Index("ix_notifications_content", content_type, content_id),
    )


class NotificationPreferences(Base):
    """User preferences for notifications."""
    
    __tablename__ = "notification_preferences"
    
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    
    notify_on_post_reactions = Column(Boolean, nullable=False, default=True)
    notify_on_post_comments = Column(Boolean, nullable=False, default=True)
    notify_on_blog_reactions = Column(Boolean, nullable=False, default=True)
    notify_on_blog_comments = Column(Boolean, nullable=False, default=True)
    
    aggregate_same_type = Column(Boolean, nullable=False, default=True)
    
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="notification_preferences")


# Update User model to add relationship
# In User class, add:
notifications = relationship("Notification", foreign_keys="Notification.user_id", back_populates="user", cascade="all, delete-orphan")
notification_preferences = relationship("NotificationPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan")
```

### 2. Pydantic Schemas

**File:** `api/app/schemas.py`

```python
class NotificationBase(BaseModel):
    """Base notification schema."""
    notification_type: str
    content_type: str
    content_id: int
    actor_handle: str | None = None
    emoji: str | None = None
    comment_preview: str | None = None
    content_title: str | None = None
    content_url: str | None = None
    
    
class Notification(NotificationBase):
    """Full notification schema."""
    id: UUID
    user_id: int
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class NotificationCreate(BaseModel):
    """Schema for creating a notification."""
    user_id: int
    notification_type: str
    content_type: str
    content_id: int
    actor_id: int | None = None
    actor_ip: str | None = None
    actor_handle: str | None = None
    emoji: str | None = None
    comment_id: UUID | None = None
    comment_preview: str | None = None
    content_title: str | None = None
    content_url: str | None = None


class NotificationPreferences(BaseModel):
    """User notification preferences."""
    notify_on_post_reactions: bool = True
    notify_on_post_comments: bool = True
    notify_on_blog_reactions: bool = True
    notify_on_blog_comments: bool = True
    aggregate_same_type: bool = True
    
    model_config = ConfigDict(from_attributes=True)


class UnreadCountResponse(BaseModel):
    """Response for unread notification count."""
    unread_count: int
```

### 3. Notification Service

**File:** `api/app/services/notifications.py` (new file)

```python
"""Service for managing notifications."""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from .. import models, schemas
from ..cache import get_redis
from ..mqtt.publisher import publish

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
    ) -> models.Notification:
        """Create a notification and publish via MQTT."""
        
        # Don't notify users about their own actions
        if actor and isinstance(actor, models.User) and actor.id == user_id:
            return None
        
        # Check user preferences (future enhancement)
        # For now, create all notifications
        
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
        
        # Publish MQTT notification
        NotificationService._publish_mqtt_notification(notification)
        
        logger.info(f"Created notification {notification.id} for user {user_id}")
        return notification
    
    @staticmethod
    def _increment_unread_count(user_id: int) -> None:
        """Increment unread count in Redis."""
        try:
            redis = get_redis()
            key = f"user:{user_id}:unread_count"
            redis.incr(key)
            # Set expiry to 7 days
            redis.expire(key, 7 * 24 * 60 * 60)
        except Exception as e:
            logger.error(f"Failed to increment unread count in Redis: {e}")
    
    @staticmethod
    def _publish_mqtt_notification(notification: models.Notification) -> None:
        """Publish notification via MQTT."""
        try:
            topic = f"makapix/notifications/user/{notification.user_id}"
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
            publish(topic, payload, qos=1, retain=False)
            logger.info(f"Published MQTT notification for user {notification.user_id}")
        except Exception as e:
            logger.error(f"Failed to publish MQTT notification: {e}")
    
    @staticmethod
    def get_unread_count(db: Session, user_id: int) -> int:
        """Get unread notification count for a user."""
        # Try Redis first
        try:
            redis = get_redis()
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
            key = f"user:{user_id}:unread_count"
            redis.set(key, count, ex=7 * 24 * 60 * 60)
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
                "is_read": True,
                "read_at": datetime.utcnow()
            },
            synchronize_session=False
        )
        
        db.commit()
        
        # Decrement Redis counter
        if count > 0:
            try:
                redis = get_redis()
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
                "is_read": True,
                "read_at": datetime.utcnow()
            },
            synchronize_session=False
        )
        
        db.commit()
        
        # Reset Redis counter
        try:
            redis = get_redis()
            key = f"user:{user_id}:unread_count"
            redis.set(key, 0, ex=7 * 24 * 60 * 60)
        except Exception as e:
            logger.error(f"Failed to reset unread count in Redis: {e}")
        
        return count
    
    @staticmethod
    def cleanup_old_notifications(db: Session, days: int = 90) -> int:
        """Delete notifications older than specified days. Returns count of deleted notifications."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        count = db.query(models.Notification).filter(
            models.Notification.created_at < cutoff_date
        ).delete(synchronize_session=False)
        
        db.commit()
        
        logger.info(f"Cleaned up {count} notifications older than {days} days")
        return count
```

### 4. API Router

**File:** `api/app/routers/notifications.py` (new file)

```python
"""Notifications API endpoints."""

from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..deps import get_db
from ..services.notifications import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


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
```

### 5. Integration with Existing Endpoints

#### A. Reactions Endpoint

**File:** `api/app/routers/reactions.py`

Modify the `add_reaction` function to create notifications:

```python
# After creating the reaction, add notification
from ..services.notifications import NotificationService

# ... existing code to create reaction ...

db.add(reaction)
db.commit()

# Get post owner
post = db.query(models.Post).filter(models.Post.id == id).first()
if post:
    # Create notification for post owner
    NotificationService.create_notification(
        db=db,
        user_id=post.owner_id,
        notification_type="reaction",
        content_type="post",
        content_id=post.id,
        actor=current_user,
        emoji=emoji,
        content_title=post.title,
        content_url=post.art_url,
    )
```

#### B. Comments Endpoint

**File:** `api/app/routers/comments.py`

Modify the `create_comment` function:

```python
# After creating the comment, add notification
from ..services.notifications import NotificationService

# ... existing code to create comment ...

db.add(comment)
db.commit()
db.refresh(comment)

# Get post owner
post = db.query(models.Post).filter(models.Post.id == id).first()
if post:
    # Create notification for post owner
    NotificationService.create_notification(
        db=db,
        user_id=post.owner_id,
        notification_type="comment",
        content_type="post",
        content_id=post.id,
        actor=current_user,
        comment_id=comment.id,
        comment_body=payload.body,
        content_title=post.title,
        content_url=post.art_url,
    )
```

#### C. Blog Post Reactions Endpoint

**File:** `api/app/routers/blog_posts.py`

Similar integration for blog post reactions:

```python
# After creating the reaction
NotificationService.create_notification(
    db=db,
    user_id=blog_post.owner_id,
    notification_type="reaction",
    content_type="blog_post",
    content_id=blog_post.id,
    actor=current_user,
    emoji=emoji,
    content_title=blog_post.title,
    content_url=f"/blog/{blog_post.public_sqid or blog_post.id}",
)
```

#### D. Blog Post Comments Endpoint

**File:** `api/app/routers/blog_posts.py`

Similar integration for blog post comments:

```python
# After creating the comment
NotificationService.create_notification(
    db=db,
    user_id=blog_post.owner_id,
    notification_type="comment",
    content_type="blog_post",
    content_id=blog_post.id,
    actor=current_user,
    comment_id=comment.id,
    comment_body=payload.body,
    content_title=blog_post.title,
    content_url=f"/blog/{blog_post.public_sqid or blog_post.id}",
)
```

### 6. Register Router in Main App

**File:** `api/app/main.py`

```python
from .routers import notifications

app.include_router(notifications.router, prefix="/api")
```

---

## Frontend Implementation

### 1. MQTT Client Utility

**File:** `web/src/lib/mqtt-client.ts` (new file)

```typescript
/**
 * MQTT client for real-time notifications.
 */

import mqtt, { MqttClient } from 'mqtt';

export interface NotificationPayload {
  id: string;
  notification_type: 'reaction' | 'comment';
  content_type: 'post' | 'blog_post';
  content_id: number;
  actor_handle: string;
  emoji?: string;
  comment_preview?: string;
  content_title?: string;
  content_url?: string;
  created_at: string;
}

export type NotificationCallback = (notification: NotificationPayload) => void;

export class NotificationMQTTClient {
  private client: MqttClient | null = null;
  private callbacks: NotificationCallback[] = [];
  private connected: boolean = false;

  constructor(private brokerUrl: string) {}

  async connect(userId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.client = mqtt.connect(this.brokerUrl, {
        clientId: `web-${userId}-${Date.now()}`,
        clean: true,
        reconnectPeriod: 5000,
      });

      this.client.on('connect', () => {
        console.log('MQTT connected for notifications');
        this.connected = true;
        
        // Subscribe to user-specific notification topic
        const topic = `makapix/notifications/user/${userId}`;
        this.client?.subscribe(topic, { qos: 1 }, (err) => {
          if (err) {
            console.error('Failed to subscribe to notification topic:', err);
            reject(err);
          } else {
            console.log(`Subscribed to ${topic}`);
            resolve();
          }
        });
      });

      this.client.on('message', (topic, payload) => {
        try {
          const notification = JSON.parse(payload.toString()) as NotificationPayload;
          this.callbacks.forEach(cb => cb(notification));
        } catch (error) {
          console.error('Failed to parse notification:', error);
        }
      });

      this.client.on('error', (error) => {
        console.error('MQTT error:', error);
        this.connected = false;
        reject(error);
      });

      this.client.on('close', () => {
        console.log('MQTT connection closed');
        this.connected = false;
      });
    });
  }

  onNotification(callback: NotificationCallback): () => void {
    this.callbacks.push(callback);
    return () => {
      this.callbacks = this.callbacks.filter(cb => cb !== callback);
    };
  }

  disconnect(): void {
    if (this.client) {
      this.client.end();
      this.client = null;
      this.connected = false;
    }
  }

  isConnected(): boolean {
    return this.connected;
  }
}
```

### 2. React Hook for Notifications

**File:** `web/src/hooks/useNotifications.ts` (new file)

```typescript
/**
 * React hook for managing notifications.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { NotificationMQTTClient, NotificationPayload } from '../lib/mqtt-client';
import { authenticatedFetch } from '../lib/api';

const MQTT_URL = process.env.NEXT_PUBLIC_MQTT_WS_URL || 'ws://localhost:9001';

interface Notification {
  id: string;
  notification_type: 'reaction' | 'comment';
  content_type: 'post' | 'blog_post';
  content_id: number;
  actor_handle: string;
  emoji?: string;
  comment_preview?: string;
  content_title?: string;
  content_url?: string;
  is_read: boolean;
  created_at: string;
}

export function useNotifications(userId: string | null) {
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [connected, setConnected] = useState<boolean>(false);
  
  const clientRef = useRef<NotificationMQTTClient | null>(null);
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Fetch unread count
  const fetchUnreadCount = useCallback(async () => {
    if (!userId) return;
    
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/notifications/unread-count`);
      if (response.ok) {
        const data = await response.json();
        setUnreadCount(data.unread_count);
      }
    } catch (error) {
      console.error('Failed to fetch unread count:', error);
    }
  }, [userId, API_BASE_URL]);

  // Fetch notifications list
  const fetchNotifications = useCallback(async (unreadOnly: boolean = false) => {
    if (!userId) return;
    
    setLoading(true);
    try {
      const url = `${API_BASE_URL}/api/notifications/?limit=50${unreadOnly ? '&unread_only=true' : ''}`;
      const response = await authenticatedFetch(url);
      if (response.ok) {
        const data = await response.json();
        setNotifications(data.items);
      }
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
    } finally {
      setLoading(false);
    }
  }, [userId, API_BASE_URL]);

  // Mark notifications as read
  const markAsRead = useCallback(async (notificationIds: string[]) => {
    if (!userId || notificationIds.length === 0) return;
    
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/notifications/mark-read`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(notificationIds),
      });
      
      if (response.ok) {
        // Update local state
        setNotifications(prev => 
          prev.map(n => 
            notificationIds.includes(n.id) ? { ...n, is_read: true } : n
          )
        );
        setUnreadCount(prev => Math.max(0, prev - notificationIds.length));
      }
    } catch (error) {
      console.error('Failed to mark notifications as read:', error);
    }
  }, [userId, API_BASE_URL]);

  // Mark all as read
  const markAllAsRead = useCallback(async () => {
    if (!userId) return;
    
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/notifications/mark-all-read`, {
        method: 'POST',
      });
      
      if (response.ok) {
        setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
        setUnreadCount(0);
      }
    } catch (error) {
      console.error('Failed to mark all notifications as read:', error);
    }
  }, [userId, API_BASE_URL]);

  // Setup MQTT connection
  useEffect(() => {
    if (!userId) return;

    const client = new NotificationMQTTClient(MQTT_URL);
    clientRef.current = client;

    client.connect(userId)
      .then(() => {
        setConnected(true);
        console.log('Notifications MQTT connected');
      })
      .catch((error) => {
        console.error('Failed to connect notifications MQTT:', error);
        setConnected(false);
      });

    // Handle incoming notifications
    const unsubscribe = client.onNotification((notification: NotificationPayload) => {
      console.log('Received notification:', notification);
      
      // Increment unread count
      setUnreadCount(prev => prev + 1);
      
      // Add to notifications list if loaded
      setNotifications(prev => {
        // Convert payload to full notification
        const newNotification: Notification = {
          id: notification.id,
          notification_type: notification.notification_type,
          content_type: notification.content_type,
          content_id: notification.content_id,
          actor_handle: notification.actor_handle,
          emoji: notification.emoji,
          comment_preview: notification.comment_preview,
          content_title: notification.content_title,
          content_url: notification.content_url,
          is_read: false,
          created_at: notification.created_at,
        };
        return [newNotification, ...prev];
      });
    });

    return () => {
      unsubscribe();
      client.disconnect();
      setConnected(false);
    };
  }, [userId]);

  // Fetch initial unread count
  useEffect(() => {
    fetchUnreadCount();
  }, [fetchUnreadCount]);

  return {
    unreadCount,
    notifications,
    loading,
    connected,
    fetchNotifications,
    fetchUnreadCount,
    markAsRead,
    markAllAsRead,
  };
}
```

### 3. Notification Badge Component

**File:** `web/src/components/NotificationBadge.tsx` (new file)

```typescript
/**
 * Notification badge component that overlays a counter on top of a button.
 */

import React from 'react';

interface NotificationBadgeProps {
  count: number;
  onClick?: () => void;
  children: React.ReactNode;
  className?: string;
}

export function NotificationBadge({ count, onClick, children, className = '' }: NotificationBadgeProps) {
  return (
    <div className={`notification-badge-container ${className}`} onClick={onClick}>
      {children}
      {count > 0 && (
        <div className="notification-badge">
          {count > 99 ? '99+' : count}
        </div>
      )}
      
      <style jsx>{`
        .notification-badge-container {
          position: relative;
          display: inline-block;
          cursor: ${onClick ? 'pointer' : 'default'};
        }
        
        .notification-badge {
          position: absolute;
          bottom: -4px;
          right: -4px;
          background: #ff4444;
          color: white;
          font-size: 10px;
          font-weight: bold;
          padding: 2px 5px;
          border-radius: 10px;
          min-width: 18px;
          height: 18px;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
          border: 2px solid var(--bg-secondary);
          z-index: 10;
        }
      `}</style>
    </div>
  );
}
```

### 4. Update Layout Component

**File:** `web/src/components/Layout.tsx`

Integrate notification badge in the header:

```typescript
import { useNotifications } from '../hooks/useNotifications';
import { NotificationBadge } from './NotificationBadge';

// ... inside Layout component ...

const { unreadCount } = useNotifications(userId);

// ... in the header JSX ...

{isLoggedIn && publicSqid && (
  <NotificationBadge count={unreadCount}>
    <Link href={`/u/${publicSqid}`} className={`user-profile-link ${router.pathname === '/u/[sqid]' && router.query.sqid === publicSqid ? 'active' : ''}`} aria-label="My Profile">
      <div className="user-icon">
        {/* existing avatar code */}
      </div>
    </Link>
  </NotificationBadge>
)}
```

### 5. Update User Profile Page

**File:** `web/src/pages/u/[sqid].tsx`

Add notifications button on profile page:

```typescript
import { useNotifications } from '../../hooks/useNotifications';
import { NotificationBadge } from '../../components/NotificationBadge';

// ... inside component ...

const { unreadCount } = useNotifications(userId);

// ... in the profile header JSX ...

{isOwnProfile && (
  <div className="profile-actions">
    <NotificationBadge count={unreadCount}>
      <button 
        onClick={() => router.push('/notifications')} 
        className="notifications-button"
        aria-label="Notifications"
      >
        🔔 Notifications
      </button>
    </NotificationBadge>
    {/* existing edit button */}
  </div>
)}
```

### 6. Notifications Page

**File:** `web/src/pages/notifications.tsx` (new file)

```typescript
import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';
import { useNotifications } from '../hooks/useNotifications';

interface Notification {
  id: string;
  notification_type: 'reaction' | 'comment';
  content_type: 'post' | 'blog_post';
  content_id: number;
  actor_handle: string;
  emoji?: string;
  comment_preview?: string;
  content_title?: string;
  content_url?: string;
  is_read: boolean;
  created_at: string;
}

export default function NotificationsPage() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  
  const {
    notifications,
    loading,
    fetchNotifications,
    markAllAsRead,
  } = useNotifications(userId);

  useEffect(() => {
    const storedUserId = localStorage.getItem('user_id');
    if (!storedUserId) {
      router.push('/auth');
      return;
    }
    setUserId(storedUserId);
  }, [router]);

  useEffect(() => {
    if (userId) {
      fetchNotifications();
      // Mark all as read when page loads
      const unreadIds = notifications.filter(n => !n.is_read).map(n => n.id);
      if (unreadIds.length > 0) {
        setTimeout(() => markAllAsRead(), 1000);
      }
    }
  }, [userId, fetchNotifications]);

  const getNotificationText = (notification: Notification): string => {
    const contentType = notification.content_type === 'post' ? 'artwork' : 'blog post';
    
    if (notification.notification_type === 'reaction') {
      return `${notification.actor_handle} reacted ${notification.emoji} to your ${contentType}`;
    } else {
      return `${notification.actor_handle} commented on your ${contentType}`;
    }
  };

  const getNotificationUrl = (notification: Notification): string => {
    if (notification.content_type === 'post') {
      return `/post/${notification.content_id}`;
    } else {
      return `/blog/${notification.content_id}`;
    }
  };

  if (!userId) {
    return null;
  }

  return (
    <Layout title="Notifications">
      <div className="notifications-page">
        <div className="notifications-header">
          <h1>Notifications</h1>
          {notifications.filter(n => !n.is_read).length > 0 && (
            <button onClick={markAllAsRead} className="mark-all-read-btn">
              Mark all as read
            </button>
          )}
        </div>

        {loading && notifications.length === 0 ? (
          <div className="loading">Loading notifications...</div>
        ) : notifications.length === 0 ? (
          <div className="empty-state">
            <p>No notifications yet</p>
            <p>When someone reacts or comments on your content, you'll see it here!</p>
          </div>
        ) : (
          <div className="notifications-list">
            {notifications.map((notification) => (
              <div
                key={notification.id}
                className={`notification-item ${!notification.is_read ? 'unread' : ''}`}
                onClick={() => router.push(getNotificationUrl(notification))}
              >
                <div className="notification-content">
                  <div className="notification-text">
                    {getNotificationText(notification)}
                  </div>
                  {notification.content_title && (
                    <div className="notification-title">
                      "{notification.content_title}"
                    </div>
                  )}
                  {notification.comment_preview && (
                    <div className="notification-preview">
                      {notification.comment_preview}
                    </div>
                  )}
                  <div className="notification-time">
                    {new Date(notification.created_at).toLocaleString()}
                  </div>
                </div>
                {!notification.is_read && (
                  <div className="unread-indicator" />
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <style jsx>{`
        .notifications-page {
          max-width: 800px;
          margin: 0 auto;
          padding: 20px;
        }

        .notifications-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
        }

        .notifications-header h1 {
          font-size: 24px;
          font-weight: bold;
          margin: 0;
        }

        .mark-all-read-btn {
          background: var(--primary);
          color: white;
          border: none;
          padding: 8px 16px;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
        }

        .mark-all-read-btn:hover {
          background: var(--primary-hover);
        }

        .loading {
          text-align: center;
          padding: 40px;
          color: var(--text-secondary);
        }

        .empty-state {
          text-align: center;
          padding: 60px 20px;
          color: var(--text-secondary);
        }

        .empty-state p {
          margin: 10px 0;
        }

        .notifications-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .notification-item {
          background: var(--bg-secondary);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 16px;
          cursor: pointer;
          transition: all 0.2s;
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
        }

        .notification-item:hover {
          background: rgba(255, 255, 255, 0.05);
          border-color: rgba(255, 255, 255, 0.2);
        }

        .notification-item.unread {
          background: rgba(0, 122, 255, 0.1);
          border-color: rgba(0, 122, 255, 0.3);
        }

        .notification-content {
          flex: 1;
        }

        .notification-text {
          font-size: 14px;
          color: var(--text-primary);
          margin-bottom: 6px;
        }

        .notification-title {
          font-size: 13px;
          color: var(--text-secondary);
          margin-bottom: 4px;
          font-style: italic;
        }

        .notification-preview {
          font-size: 13px;
          color: var(--text-secondary);
          margin-bottom: 6px;
          padding: 8px;
          background: rgba(0, 0, 0, 0.2);
          border-radius: 4px;
        }

        .notification-time {
          font-size: 12px;
          color: var(--text-tertiary);
        }

        .unread-indicator {
          width: 8px;
          height: 8px;
          background: #007aff;
          border-radius: 50%;
          flex-shrink: 0;
          margin-top: 4px;
        }

        @media (max-width: 768px) {
          .notifications-page {
            padding: 12px;
          }

          .notifications-header h1 {
            font-size: 20px;
          }
        }
      `}</style>
    </Layout>
  );
}
```

---

## MQTT Real-Time Updates

### Topic Structure

```
makapix/notifications/user/{user_id}
```

### Message Payload

```json
{
  "id": "uuid-string",
  "notification_type": "reaction|comment",
  "content_type": "post|blog_post",
  "content_id": 123,
  "actor_handle": "username",
  "emoji": "❤️",
  "comment_preview": "Great work!...",
  "content_title": "My Artwork",
  "content_url": "/api/vault/...",
  "created_at": "2025-12-04T15:30:00Z"
}
```

### MQTT Configuration

- **QoS Level**: 1 (at least once delivery)
- **Retain**: False (ephemeral messages)
- **Clean Session**: True (no persistent sessions)
- **Reconnect Period**: 5 seconds

### Connection Lifecycle

1. User logs in → Frontend connects to MQTT broker
2. Subscribe to `makapix/notifications/user/{user_id}`
3. Receive real-time notifications
4. Update badge counter in UI
5. User logs out → Disconnect from MQTT

---

## Performance Expectations

### Database Performance

#### Query Patterns and Indexes

1. **Get unread count** (Redis-cached)
   - **Without cache**: ~5ms (indexed query on `user_id, is_read`)
   - **With cache**: <1ms
   - **Query**: `SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = false`

2. **List recent notifications**
   - **Response time**: ~10-20ms for 50 notifications
   - **Query**: Uses composite index on `(user_id, created_at DESC)`
   - **Pagination**: Cursor-based for O(1) performance

3. **Mark as read**
   - **Response time**: ~5-10ms per batch
   - **Query**: Bulk update with WHERE IN clause

#### Database Size Estimation

For **10,000 MAU** with 90-day retention:

- **Assumptions**:
  - Average 5 notifications per user per day
  - 90-day retention policy
  - ~500 bytes per notification row (including indexes)

- **Storage calculation**:
  - 10,000 users × 5 notifs/day × 90 days = 4,500,000 notifications
  - 4.5M × 500 bytes = ~2.25 GB

- **With indexes**: ~3-4 GB total

### Redis Performance

#### Cache Strategy

1. **Unread count cache**
   - **Key**: `user:{user_id}:unread_count`
   - **TTL**: 7 days
   - **Update**: Incremented on new notification, decremented on mark-as-read
   - **Fallback**: Query database if cache miss

2. **Memory usage**:
   - 10,000 active users × 50 bytes per key = ~500 KB

### MQTT Performance

#### Connection Load

- **Concurrent connections**: 10,000 users (peak)
- **Message rate**: ~50 messages/second (estimated 5% of users active simultaneously)
- **Bandwidth**: Minimal (messages ~500 bytes each)

#### Mosquitto Configuration

```conf
max_connections 15000
max_inflight_messages 20
max_queued_messages 1000
message_size_limit 10240
```

### API Endpoint Performance

#### Expected Response Times

| Endpoint | Response Time (p50) | Response Time (p99) |
|----------|---------------------|---------------------|
| GET /notifications/ | 20ms | 50ms |
| GET /notifications/unread-count | 2ms (cached) | 15ms (uncached) |
| POST /notifications/mark-read | 10ms | 30ms |
| POST /notifications/mark-all-read | 15ms | 40ms |

### End-User Experience

#### During Peak Load (1,000 concurrent users)

1. **Notification delivery latency**: <500ms from action to recipient's browser
   - Database write: 5-10ms
   - Redis update: 1-2ms
   - MQTT publish: 10-20ms
   - Network + browser rendering: 100-400ms

2. **Badge counter update**: Instant (<100ms) via MQTT push

3. **Page load performance**:
   - Initial page load: 200-300ms (including API calls)
   - Notifications list load: 50-100ms
   - Marking all as read: 50-150ms

#### Resource Usage

On a **2 vCPU, 4GB RAM VPS**:

- **Database**: 20-30% CPU, 1GB RAM
- **Redis**: 5-10% CPU, 200MB RAM
- **MQTT Broker**: 10-15% CPU, 300MB RAM
- **API**: 30-40% CPU, 1GB RAM
- **Total**: Comfortable headroom for 10k MAU

### Scalability Limits

- **Current architecture can handle**: 10,000 MAU comfortably
- **With optimizations (connection pooling, caching)**: 20,000 MAU
- **Breaking point**: ~25,000-30,000 MAU on single VPS

### Bottlenecks to Monitor

1. **Database connections**: Pool size must accommodate concurrent requests
2. **MQTT connections**: Each user = 1 WebSocket connection
3. **Redis memory**: Monitor cache size growth
4. **Network bandwidth**: Minimal but should be monitored

---

## Implementation Phases

### Phase 1: Database and Backend Core (Week 1)

**Tasks**:
1. Create Alembic migration for `notifications` and `notification_preferences` tables
2. Implement `Notification` and `NotificationPreferences` models in SQLAlchemy
3. Create Pydantic schemas for API responses
4. Implement `NotificationService` class with core methods
5. Create `/api/notifications/` router with all endpoints
6. Add unit tests for notification service

**Deliverables**:
- Database tables created
- API endpoints functional
- Unit tests passing

### Phase 2: Integration with Existing Features (Week 1)

**Tasks**:
1. Integrate notification creation in reactions endpoint
2. Integrate notification creation in comments endpoint
3. Integrate notification creation in blog post reactions
4. Integrate notification creation in blog post comments
5. Add Redis caching for unread counts
6. Test end-to-end notification creation flow

**Deliverables**:
- Notifications created on all social actions
- Redis cache working
- Integration tests passing

### Phase 3: MQTT Real-Time System (Week 2)

**Tasks**:
1. Extend MQTT publisher to handle notification messages
2. Create MQTT client utility in frontend
3. Test MQTT message delivery and reconnection
4. Implement fallback for MQTT connection failures

**Deliverables**:
- MQTT notifications working
- Real-time updates in browser
- Graceful degradation if MQTT fails

### Phase 4: Frontend UI Components (Week 2)

**Tasks**:
1. Create `NotificationBadge` component
2. Create `useNotifications` React hook
3. Update Layout component with badge on user profile button
4. Create notifications page (`/notifications`)
5. Add notifications button to user profile page
6. Implement mark-as-read functionality
7. Add loading states and error handling

**Deliverables**:
- Complete UI for notifications
- Badge updates in real-time
- Notifications page functional

### Phase 5: Polish and Optimization (Week 3)

**Tasks**:
1. Implement notification aggregation (combine similar notifications)
2. Add notification preferences UI
3. Optimize database queries with proper indexes
4. Add background job for cleaning old notifications
5. Performance testing and optimization
6. Cross-browser testing
7. Mobile responsive design

**Deliverables**:
- Optimized performance
- User preferences working
- Mobile-friendly UI

### Phase 6: Testing and Deployment (Week 3)

**Tasks**:
1. End-to-end testing
2. Load testing with simulated 10k MAU
3. Monitor performance metrics
4. Fix any bugs found
5. Write user documentation
6. Deploy to production

**Deliverables**:
- Production-ready system
- Performance validated
- Documentation complete

---

## Testing Strategy

### Unit Tests

**Backend**:
- Test `NotificationService` methods
- Test notification creation for each social action
- Test Redis cache operations
- Test mark-as-read logic

**Frontend**:
- Test `useNotifications` hook
- Test `NotificationBadge` component rendering
- Test MQTT client connection and message handling

### Integration Tests

- Test end-to-end flow: reaction → notification created → MQTT published → Redis updated
- Test notification list API with pagination
- Test mark-as-read API
- Test unread count accuracy

### Performance Tests

- Load test API endpoints with 1000 concurrent requests
- Test MQTT broker with 10,000 concurrent connections
- Measure database query performance under load
- Monitor Redis memory usage

### Manual Testing

- Test on different browsers (Chrome, Firefox, Safari, Edge)
- Test on mobile devices (iOS, Android)
- Test real-time updates with multiple users
- Test edge cases (deleted content, banned users, etc.)

---

## Migration Strategy

### Database Migration

**File**: `api/alembic/versions/YYYYMMDD_add_notifications.py`

```python
"""Add notifications system

Revision ID: xxx
Revises: yyy
Create Date: 2025-12-04
"""

def upgrade():
    # Create notifications table
    op.create_table(
        'notifications',
        # ... columns definition ...
    )
    
    # Create notification_preferences table
    op.create_table(
        'notification_preferences',
        # ... columns definition ...
    )
    
    # Create indexes
    op.create_index('idx_notifications_user_created', 'notifications', ['user_id', sa.text('created_at DESC')])
    op.create_index('idx_notifications_user_unread', 'notifications', ['user_id', 'is_read', sa.text('created_at DESC')])
    op.create_index('idx_notifications_content', 'notifications', ['content_type', 'content_id'])

def downgrade():
    op.drop_table('notification_preferences')
    op.drop_table('notifications')
```

### Deployment Steps

1. **Pre-deployment**:
   - Test migration on staging database
   - Verify rollback works
   - Update API documentation

2. **Deployment**:
   - Apply database migration
   - Deploy backend code
   - Deploy frontend code
   - Restart services

3. **Post-deployment**:
   - Monitor error logs
   - Check MQTT connection count
   - Monitor database performance
   - Verify real-time updates working

4. **Rollback Plan**:
   - If critical issues: rollback database migration
   - Remove notification-related code from endpoints
   - Restart services

### Feature Flag (Optional)

Implement feature flag to enable/disable notifications:

```python
# In config
NOTIFICATIONS_ENABLED = os.getenv("NOTIFICATIONS_ENABLED", "true").lower() == "true"

# In service
if not NOTIFICATIONS_ENABLED:
    return
```

---

## Future Enhancements

### Phase 2 Features (Post-MVP)

1. **Notification Preferences**:
   - Allow users to disable specific notification types
   - Email digest of unread notifications
   - Mobile push notifications (via web push API)

2. **Aggregation**:
   - Group similar notifications (e.g., "5 people reacted to your post")
   - Collapse old notifications

3. **Rich Notifications**:
   - Thumbnail preview of artwork
   - Avatar of actor
   - Quick actions (like back, reply)

4. **Analytics**:
   - Track notification open rates
   - A/B test notification formats
   - Monitor engagement metrics

---

## Conclusion

This implementation plan provides a comprehensive roadmap for adding social notifications to Makapix Club. The system is designed to:

- **Scale efficiently** to 10,000 MAU on a single VPS
- **Deliver notifications in real-time** via MQTT with <500ms latency
- **Provide excellent UX** with unread badges and highlighted notifications
- **Maintain low costs** by using existing infrastructure (PostgreSQL, Redis, MQTT)
- **Handle both artwork and blog post** reactions/comments uniformly

The phased approach allows for iterative development and testing, ensuring each component works correctly before moving to the next phase. Performance expectations are realistic and achievable with the planned architecture.

**Estimated Total Implementation Time**: 3-4 weeks (1 senior full-stack engineer)

**Infrastructure Cost**: $0 additional (uses existing VPS resources)

**End Result**: A professional, real-time social notifications system that enhances user engagement and provides immediate feedback for content creators on the Makapix Club platform.

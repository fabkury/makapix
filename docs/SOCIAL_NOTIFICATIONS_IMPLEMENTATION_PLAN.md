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
6. [WebSocket Real-Time Updates](#websocket-real-time-updates)
7. [Performance Expectations](#performance-expectations)
8. [Implementation Phases](#implementation-phases)
9. [Testing Strategy](#testing-strategy)
10. [Migration Strategy](#migration-strategy)

---

## Executive Summary

This plan details the implementation of a social notifications system for Makapix Club that will notify users when their artwork or blog posts receive reactions or comments. The system leverages existing infrastructure (PostgreSQL, Redis) and uses WebSockets over HTTPS for real-time delivery, maintaining low operational costs.

### Key Features

- **Unified notifications** for artwork reactions, artwork comments, blog post reactions, and blog post comments
- **Unread counter badge** displayed on user profile button in header (bottom-right overlay)
- **Notifications button** on user profile page with same counter
- **Dedicated notifications page** showing all notifications with highlights for unread items
- **Real-time updates** via WebSocket push notifications while user is logged in
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
│         Update Redis Counter (unread count)                  │
│            (user:{user_id}:unread_count)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│    Broadcast to WebSocket Connections (via Redis Pub/Sub)   │
│         Send notification to user's active WebSockets        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│           User's Browser Receives WebSocket Message          │
│        (Updates badge counter in real-time)                  │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| **PostgreSQL** | Store notification records, user preferences, read status |
| **Redis** | Cache unread notification counts; Pub/Sub for WebSocket broadcasting |
| **WebSocket** | Real-time push notifications to connected browser clients |
| **FastAPI** | API endpoints for CRUD operations; WebSocket connection manager |
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
import json
from typing import TYPE_CHECKING
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
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
    ) -> models.Notification:
        """Create a notification and broadcast via WebSocket."""
        
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
        
        # Broadcast WebSocket notification
        NotificationService._broadcast_notification(notification)
        
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
    def _broadcast_notification(notification: models.Notification) -> None:
        """Broadcast notification via Redis Pub/Sub to WebSocket connections."""
        try:
            redis = get_redis()
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

### 5. WebSocket Connection Manager

**File:** `api/app/websocket_manager.py` (new file)

```python
"""WebSocket connection manager for real-time notifications."""

from __future__ import annotations
import asyncio
import json
import logging
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect
from ..cache import get_redis

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts notifications."""
    
    def __init__(self):
        # Map of user_id -> set of WebSocket connections
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._pubsub_task = None
        self._running = False
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected. Total connections: {self.get_connection_count()}")
    
    async def disconnect(self, websocket: WebSocket, user_id: int):
        """Remove a WebSocket connection."""
        async with self._lock:
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
        logger.info(f"User {user_id} disconnected. Total connections: {self.get_connection_count()}")
    
    async def send_personal_message(self, message: dict, user_id: int):
        """Send a message to all connections for a specific user."""
        if user_id not in self.active_connections:
            return
        
        # Get copy of connections to avoid modification during iteration
        connections = list(self.active_connections[user_id])
        disconnected = []
        
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected sockets
        if disconnected:
            async with self._lock:
                for ws in disconnected:
                    if user_id in self.active_connections:
                        self.active_connections[user_id].discard(ws)
                if user_id in self.active_connections and not self.active_connections[user_id]:
                    del self.active_connections[user_id]
    
    def get_connection_count(self) -> int:
        """Get total number of active connections."""
        return sum(len(conns) for conns in self.active_connections.values())
    
    async def start_redis_listener(self):
        """Start Redis Pub/Sub listener for notification broadcasts."""
        if self._running:
            return
        
        self._running = True
        self._pubsub_task = asyncio.create_task(self._redis_listener())
        logger.info("Redis Pub/Sub listener started")
    
    async def stop_redis_listener(self):
        """Stop Redis Pub/Sub listener."""
        self._running = False
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
        logger.info("Redis Pub/Sub listener stopped")
    
    async def _redis_listener(self):
        """Listen for Redis Pub/Sub messages and broadcast to WebSocket clients."""
        redis = get_redis()
        pubsub = redis.pubsub()
        
        # Subscribe to all notification channels (pattern matching)
        pubsub.psubscribe("notifications:user:*")
        
        try:
            while self._running:
                message = pubsub.get_message(timeout=1.0)
                if message and message['type'] == 'pmessage':
                    try:
                        # Extract user_id from channel name
                        channel = message['channel'].decode('utf-8')
                        user_id = int(channel.split(':')[-1])
                        
                        # Parse notification payload
                        payload = json.loads(message['data'].decode('utf-8'))
                        
                        # Broadcast to all user's connections
                        await self.send_personal_message(payload, user_id)
                    except Exception as e:
                        logger.error(f"Error processing Redis message: {e}")
                
                # Small sleep to prevent busy-waiting
                await asyncio.sleep(0.01)
        except Exception as e:
            logger.error(f"Redis listener error: {e}")
        finally:
            pubsub.punsubscribe("notifications:user:*")
            pubsub.close()


# Global connection manager instance
connection_manager = ConnectionManager()
```

### 6. WebSocket Endpoint

**File:** `api/app/routers/notifications.py` (add to existing file)

Add WebSocket endpoint to the notifications router:

```python
from fastapi import WebSocket, WebSocketDisconnect
from ..websocket_manager import connection_manager

# ... existing HTTP routes ...

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
        from ..auth import verify_token
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
    await connection_manager.connect(websocket, user_id)
    
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
```

### 7. Integration with Existing Endpoints

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

### 8. Register Router and Start WebSocket Listener

**File:** `api/app/main.py`

```python
from .routers import notifications
from .websocket_manager import connection_manager

app.include_router(notifications.router, prefix="/api")

# Start WebSocket manager on application startup
@app.on_event("startup")
async def startup_event():
    await connection_manager.start_redis_listener()

@app.on_event("shutdown")
async def shutdown_event():
    await connection_manager.stop_redis_listener()
```

---

## Frontend Implementation

### 1. WebSocket Client Utility

**File:** `web/src/lib/websocket-client.ts` (new file)

```typescript
/**
 * WebSocket client for real-time notifications.
 */

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

export class NotificationWebSocketClient {
  private ws: WebSocket | null = null;
  private callbacks: NotificationCallback[] = [];
  private connected: boolean = false;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 10;
  private reconnectDelay: number = 3000;

  constructor(
    private apiBaseUrl: string,
    private token: string
  ) {}

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        // Convert HTTP(S) URL to WS(S) URL
        const wsUrl = this.apiBaseUrl.replace(/^http/, 'ws');
        const url = `${wsUrl}/api/notifications/ws?token=${encodeURIComponent(this.token)}`;
        
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
          console.log('WebSocket connected for notifications');
          this.connected = true;
          this.reconnectAttempts = 0;
          resolve();
          
          // Send periodic ping to keep connection alive
          this.startPing();
        };

        this.ws.onmessage = (event) => {
          try {
            // Handle pong response
            if (event.data === 'pong') {
              return;
            }
            
            const notification = JSON.parse(event.data) as NotificationPayload;
            this.callbacks.forEach(cb => cb(notification));
          } catch (error) {
            console.error('Failed to parse notification:', error);
          }
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          this.connected = false;
          reject(error);
        };

        this.ws.onclose = () => {
          console.log('WebSocket connection closed');
          this.connected = false;
          this.stopPing();
          this.attemptReconnect();
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  private startPing(): void {
    this.reconnectTimer = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send('ping');
      }
    }, 30000); // Ping every 30 seconds
  }

  private stopPing(): void {
    if (this.reconnectTimer) {
      clearInterval(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.min(this.reconnectAttempts, 5);
    
    console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
    
    setTimeout(() => {
      this.connect().catch(err => {
        console.error('Reconnection failed:', err);
      });
    }, delay);
  }

  onNotification(callback: NotificationCallback): () => void {
    this.callbacks.push(callback);
    return () => {
      this.callbacks = this.callbacks.filter(cb => cb !== callback);
    };
  }

  disconnect(): void {
    this.stopPing();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
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
import { NotificationWebSocketClient, NotificationPayload } from '../lib/websocket-client';
import { authenticatedFetch } from '../lib/api';

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
  
  const clientRef = useRef<NotificationWebSocketClient | null>(null);
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

  // Setup WebSocket connection
  useEffect(() => {
    if (!userId) return;

    const token = localStorage.getItem('access_token');
    if (!token) return;

    const client = new NotificationWebSocketClient(API_BASE_URL, token);
    clientRef.current = client;

    client.connect()
      .then(() => {
        setConnected(true);
        console.log('Notifications WebSocket connected');
      })
      .catch((error) => {
        console.error('Failed to connect notifications WebSocket:', error);
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
  }, [userId, API_BASE_URL]);

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

## WebSocket Real-Time Updates

### Connection Flow

```
1. User logs in → Frontend establishes WebSocket connection
2. WebSocket connects to /api/notifications/ws?token=<jwt_token>
3. Backend verifies JWT token and registers connection
4. User receives real-time notification messages
5. Periodic ping/pong keeps connection alive
6. User logs out → WebSocket disconnects
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

### WebSocket Configuration

- **Protocol**: WSS (WebSocket Secure) over HTTPS
- **Authentication**: JWT token passed as query parameter
- **Keepalive**: Ping/pong every 30 seconds
- **Reconnection**: Automatic with exponential backoff (up to 10 attempts)
- **Broadcasting**: Redis Pub/Sub for multi-instance support

### Connection Lifecycle

1. **Connect**: Client establishes WebSocket connection with JWT token
2. **Authenticate**: Server verifies token and registers connection
3. **Subscribe**: Backend subscribes to Redis channel `notifications:user:{user_id}`
4. **Receive**: Client receives real-time notification messages via WebSocket
5. **Keepalive**: Client sends ping every 30s, server responds with pong
6. **Reconnect**: On disconnect, client attempts reconnection with exponential backoff
7. **Disconnect**: On logout or tab close, client closes WebSocket connection

### Broadcasting Architecture

```
Action Occurs → NotificationService.create_notification()
                ↓
            Save to DB
                ↓
            Update Redis counter
                ↓
            Publish to Redis Pub/Sub channel: notifications:user:{user_id}
                ↓
            ConnectionManager Redis listener receives message
                ↓
            Broadcast to all WebSocket connections for user_id
                ↓
            Client receives notification and updates UI
```

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

2. **Pub/Sub for WebSocket broadcasting**
   - **Channels**: `notifications:user:{user_id}` (one per user with active connections)
   - **Messages**: JSON-encoded notification payloads
   - **Persistence**: No persistence needed (ephemeral messages)

3. **Memory usage**:
   - 10,000 active users × 50 bytes per key = ~500 KB (counters)
   - Pub/Sub channels: Minimal overhead (messages not stored)

### WebSocket Performance

#### Connection Load

- **Concurrent connections**: 10,000 users (peak)
- **Message rate**: ~50 messages/second (estimated 5% of users active simultaneously)
- **Bandwidth**: Minimal (messages ~500 bytes each)
- **Keepalive overhead**: Ping/pong every 30s = ~333 messages/second total

#### FastAPI WebSocket Configuration

```python
# In uvicorn/gunicorn settings
workers = 4  # Multi-worker for handling concurrent connections
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120  # WebSocket keepalive timeout
keepalive = 75  # TCP keepalive
```

### API Endpoint Performance

#### Expected Response Times

| Endpoint | Response Time (p50) | Response Time (p99) |
|----------|---------------------|---------------------|
| GET /notifications/ | 20ms | 50ms |
| GET /notifications/unread-count | 2ms (cached) | 15ms (uncached) |
| POST /notifications/mark-read | 10ms | 30ms |
| POST /notifications/mark-all-read | 15ms | 40ms |
| WebSocket connection | 50ms | 100ms |

### End-User Experience

#### During Peak Load (1,000 concurrent users)

1. **Notification delivery latency**: <500ms from action to recipient's browser
   - Database write: 5-10ms
   - Redis update: 1-2ms
   - Redis Pub/Sub: 1-5ms
   - WebSocket broadcast: 5-10ms
   - Network + browser rendering: 100-400ms

2. **Badge counter update**: Instant (<100ms) via WebSocket push

3. **Page load performance**:
   - Initial page load: 200-300ms (including API calls)
   - WebSocket connection: 50-100ms
   - Notifications list load: 50-100ms
   - Marking all as read: 50-150ms

#### Resource Usage

On a **2 vCPU, 4GB RAM VPS**:

- **Database**: 20-30% CPU, 1GB RAM
- **Redis**: 10-15% CPU, 250MB RAM (includes Pub/Sub)
- **API (with WebSockets)**: 35-45% CPU, 1.2GB RAM
- **Total**: Comfortable headroom for 10k MAU

### Scalability Limits

- **Current architecture can handle**: 10,000 MAU comfortably
- **With optimizations (connection pooling, caching)**: 20,000 MAU
- **Breaking point**: ~25,000-30,000 MAU on single VPS

### Bottlenecks to Monitor

1. **Database connections**: Pool size must accommodate concurrent requests
2. **WebSocket connections**: Each user = 1 persistent connection
3. **Redis memory**: Monitor cache size and Pub/Sub message queue
4. **Network bandwidth**: Minimal but should be monitored
5. **File descriptors**: Ensure OS limits support 10k+ concurrent connections

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

### Phase 3: WebSocket Real-Time System (Week 2)

**Tasks**:
1. Implement WebSocket connection manager with Redis Pub/Sub
2. Create WebSocket endpoint in notifications router
3. Create WebSocket client utility in frontend
4. Test WebSocket message delivery and reconnection
5. Implement automatic reconnection with exponential backoff
6. Add WebSocket startup/shutdown handlers

**Deliverables**:
- WebSocket notifications working
- Real-time updates in browser
- Automatic reconnection on disconnect
- Redis Pub/Sub broadcasting functional

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
- Test WebSocket client connection and message handling

### Integration Tests

- Test end-to-end flow: reaction → notification created → Redis Pub/Sub → WebSocket broadcast
- Test notification list API with pagination
- Test mark-as-read API
- Test unread count accuracy

### Performance Tests

- Load test API endpoints with 1000 concurrent requests
- Test WebSocket server with 10,000 concurrent connections
- Measure database query performance under load
- Monitor Redis memory usage and Pub/Sub performance

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
   - Start ConnectionManager Redis listener

3. **Post-deployment**:
   - Monitor error logs
   - Check WebSocket connection count
   - Monitor database performance
   - Verify real-time updates working
   - Monitor Redis Pub/Sub metrics

4. **Rollback Plan**:
   - If critical issues: rollback database migration
   - Remove notification-related code from endpoints
   - Stop ConnectionManager
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
   - Browser push notifications (via Web Push API)

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

## Questions to be answered

Before beginning implementation, the following questions should be carefully considered and answered to ensure the design meets both current and future requirements.

### Performance and Scalability

#### Q1: How will the system perform at different scales (1K MAU, 10K MAU, 100K MAU)?

**Context**: Understanding performance characteristics across different user scales is critical for planning resource allocation and identifying potential bottlenecks.

**Suggested Answer**:

**At 1,000 MAU (Low Scale)**:
- **Database Load**: Minimal. ~450,000 notifications over 90 days (~500MB storage)
- **WebSocket Connections**: Peak ~100 concurrent connections
- **Redis Memory**: <100MB (counters + Pub/Sub overhead)
- **CPU Utilization**: <20% on 2 vCPU
- **Response Times**: 
  - Notification delivery: <200ms
  - API endpoints: p99 <30ms
  - Unread count (cached): <1ms
- **Infrastructure**: Can run comfortably on minimal VPS ($7-10/month)
- **Bottlenecks**: None expected

**At 10,000 MAU (Target Scale)**:
- **Database Load**: Moderate. ~4.5M notifications over 90 days (~3-4GB storage with indexes)
- **WebSocket Connections**: Peak ~1,000 concurrent connections
- **Redis Memory**: ~500MB (counters + Pub/Sub channels)
- **CPU Utilization**: 35-45% on 2 vCPU, 20-30% on 4 vCPU
- **Response Times**:
  - Notification delivery: <500ms
  - API endpoints: p99 <50ms
  - Unread count (cached): <2ms
- **Infrastructure**: Current VPS (2 vCPU, 4GB RAM) adequate with some headroom
- **Bottlenecks**: 
  - Database connection pool may need tuning (recommend pool size 20-30)
  - WebSocket file descriptor limits (ensure ulimit set to >10,000)
  - PostgreSQL shared_buffers should be 1GB minimum

**At 100,000 MAU (Future Scale - Requires Architecture Changes)**:
- **Database Load**: Heavy. ~45M notifications over 90 days (~30-40GB storage)
- **WebSocket Connections**: Peak ~10,000 concurrent connections
- **Redis Memory**: ~5GB
- **Infrastructure**: **Single VPS architecture will not suffice**
- **Required Changes**:
  1. **Multi-instance API servers** behind load balancer
  2. **Database replication** (read replicas for notification queries)
  3. **Redis Cluster** for distributed Pub/Sub
  4. **Dedicated WebSocket servers** (separate from API servers)
  5. **CDN integration** for static assets
  6. **Database partitioning** (partition notifications by user_id ranges)
  7. **Consider message queue** (RabbitMQ/Kafka) instead of Redis Pub/Sub
  8. **Notification aggregation** becomes mandatory (not optional)
- **Estimated Cost**: $200-500/month (multiple servers + managed services)
- **Implementation Effort**: 4-6 weeks of refactoring

**Recommendation**: Implement current architecture for 10K MAU target. Plan migration path to distributed architecture when approaching 25K MAU. Monitor key metrics (database query times, WebSocket connection count, Redis memory) and set alerts at 70% capacity thresholds.

---

#### Q2: What are the critical performance metrics to monitor, and what are the alert thresholds?

**Context**: Proactive monitoring prevents performance degradation and outages.

**Suggested Answer**:

**Database Metrics**:
- **Query response time**: Alert if p95 > 100ms, Critical if p95 > 500ms
- **Connection pool utilization**: Alert at 70%, Critical at 85%
- **Notifications table size**: Alert at 5GB, Plan cleanup/partitioning at 10GB
- **Index size**: Monitor b-tree depth and fragmentation monthly

**Redis Metrics**:
- **Memory usage**: Alert at 80% of max memory, Critical at 90%
- **Pub/Sub channels**: Monitor count, Alert if exceeds 5,000 active channels
- **Cache hit rate (unread counts)**: Alert if drops below 90%
- **Connection count**: Alert at 80% of maxclients

**WebSocket Metrics**:
- **Concurrent connections**: Alert at 7,000 (70% of safe limit on current infra)
- **Connection duration**: Track average lifetime (expect >10 minutes)
- **Reconnection rate**: Alert if >10% of connections reconnect within 60 seconds
- **Message delivery latency**: Alert if p95 > 1 second

**API Metrics**:
- **Endpoint response times**: Alert if p99 exceeds targets by 2x
- **Error rate**: Alert if 5-minute error rate >1%, Critical if >5%
- **Worker queue depth**: Alert if >100 pending tasks

**System Metrics**:
- **CPU utilization**: Alert at 75%, Critical at 90%
- **Memory utilization**: Alert at 85%, Critical at 95%
- **File descriptors**: Alert at 80% of ulimit
- **Disk I/O wait**: Alert if >20% consistently

**Recommendation**: Use Prometheus + Grafana for metrics collection and visualization. Set up PagerDuty or similar for critical alerts. Review dashboards weekly during first month post-deployment.

---

### Architecture Alternatives

#### Q3: Should we use Redis Pub/Sub or a dedicated message queue (RabbitMQ/Kafka) for WebSocket broadcasting?

**Context**: Redis Pub/Sub is simple but has limitations. Dedicated message queues offer more features but add complexity.

**Suggested Answer**:

**Redis Pub/Sub (Current Choice)**:

*Advantages*:
- Already using Redis for caching - no new infrastructure
- Low latency (<5ms typically)
- Simple to implement and maintain
- Sufficient for 10K MAU scale
- No message persistence needed (ephemeral notifications)
- Minimal memory overhead

*Disadvantages*:
- Messages are fire-and-forget (no delivery guarantees beyond QoS)
- Not durable (if Redis crashes, in-flight messages lost)
- Doesn't scale well beyond single Redis instance
- No message replay capability
- Limited observability/debugging tools

**RabbitMQ/Kafka Alternative**:

*Advantages*:
- Strong delivery guarantees
- Message persistence and replay
- Better observability and monitoring
- Scales to 100K+ MAU with clustering
- Dead letter queues for error handling

*Disadvantages*:
- Additional infrastructure to maintain
- Higher latency (20-50ms typical)
- More complex configuration
- Higher memory footprint (~500MB minimum)
- Overkill for current scale

**Recommendation**: **Stick with Redis Pub/Sub** for initial implementation. It's appropriate for the 10K MAU target, keeps infrastructure simple, and maintains cost-effectiveness. Plan migration to RabbitMQ or Kafka only if:
1. Approaching 25K MAU
2. Need message persistence for compliance
3. Experience frequent Redis failures affecting notifications

Document the migration path but don't implement unless needed.

---

#### Q4: Should notifications be delivered only via WebSocket, or should we also implement HTTP polling as a fallback?

**Context**: WebSocket connections can be blocked by corporate firewalls or unstable networks. HTTP polling provides a fallback but increases server load.

**Suggested Answer**:

**WebSocket-Only (Current Plan)**:

*Advantages*:
- Real-time updates with minimal latency
- Efficient (low server overhead per connection)
- Standard protocol supported by all modern browsers
- Aligns with MQTT architecture already in place

*Disadvantages*:
- May be blocked by restrictive firewalls
- Requires persistent connection (battery drain on mobile)
- Users won't get updates if connection fails and doesn't auto-reconnect

**WebSocket + HTTP Polling Fallback**:

*Advantages*:
- Works in all network environments
- Graceful degradation
- Better user experience for users with connectivity issues

*Disadvantages*:
- Polling creates constant server load (1 request/sec × 1000 users = 1000 req/sec)
- More complex client-side logic
- Higher bandwidth usage
- Users might use polling by default, defeating WebSocket benefits

**WebSocket + Notification Badge Refresh on Page Load**:

*Advantages*:
- Simple implementation
- No polling overhead
- Works as passive fallback
- Users get updates when they navigate or refresh

*Disadvantages*:
- Not truly real-time for disconnected users
- Users might miss notifications until next page load

**Recommendation**: **Implement WebSocket-only with automatic reconnection**, plus:
1. Fetch unread count on page load/navigation (already in plan)
2. Implement robust WebSocket reconnection with exponential backoff (already in plan)
3. Show connection status indicator in UI (small icon showing "connected" or "offline")
4. Add optional HTTP polling **only if** we see >5% of users consistently failing WebSocket connections

Monitor WebSocket connection success rate. If >95% of users successfully maintain WebSocket connections, no fallback needed. The occasional user who can't connect will still see notifications on page load/refresh, which is acceptable for a social network (vs. critical systems like chat or trading).

---

#### Q5: Should we implement notification aggregation from the start, or add it later?

**Context**: Aggregation (e.g., "5 people reacted to your post") reduces notification clutter but adds complexity.

**Suggested Answer**:

**No Aggregation (Phase 1)**:

*Advantages*:
- Simpler implementation (3-4 weeks vs 5-6 weeks)
- Each notification has complete context
- Easier to debug and test
- Users see exactly who interacted and when

*Disadvantages*:
- Potentially overwhelming for popular content (100 reactions = 100 notifications)
- Database grows faster
- More notifications to mark as read

**With Aggregation (Phase 2)**:

*Advantages*:
- Better UX for popular creators
- Reduces database growth by 60-80% for popular posts
- Less overwhelming notification list
- Industry standard (Twitter, Instagram, Facebook all aggregate)

*Disadvantages*:
- Significantly more complex logic:
  - Time windows for aggregation (e.g., aggregate reactions within 1 hour)
  - Updating aggregated notifications vs creating new ones
  - Handling edge cases (aggregated notification deleted, then new reaction arrives)
- Race conditions in high-traffic scenarios
- More difficult to implement "mark as read" correctly

**Hybrid Approach**:

*Advantages*:
- Aggregate only for high-volume posts (>10 reactions/hour)
- Simple logic for normal posts, aggregation for edge cases
- Best of both worlds

*Disadvantages*:
- Most complex implementation
- Inconsistent UX

**Recommendation**: **No aggregation in MVP (Phase 1)**. Add it as **Phase 2 enhancement after 2-3 months** of production data. Rationale:
1. Most Makapix posts get <10 reactions total (based on current usage patterns)
2. Overwhelming notifications only affects top 1% of content creators
3. Implementing aggregation correctly takes significant effort
4. Better to launch sooner and gather real usage data
5. Can add aggregation retroactively by running migration to combine old notifications

During Phase 1, monitor notification count distribution. If >10% of users receive >50 notifications/day, prioritize aggregation. Otherwise, it may not be needed even in Phase 2.

---

### Edge Cases and Error Handling

#### Q6: What happens when a user deletes their post/blog while notifications about it exist?

**Context**: Notifications reference content that may be deleted, causing broken links and confusion.

**Suggested Answer**:

**Options**:

1. **Cascade delete notifications** (Current Plan: ON DELETE CASCADE)
   - *Pros*: Clean database, no orphaned records, no broken links
   - *Cons*: Users lose notification history, can't see "you got 50 reactions" even after deletion
   
2. **Soft-delete notifications** (mark as deleted but keep record)
   - *Pros*: Preserves history, users can see they got reactions
   - *Cons*: Broken links, requires filtering in queries, database growth
   
3. **Keep notifications but mark content as deleted**
   - *Pros*: Shows "Someone reacted to your deleted post"
   - *Cons*: Cluttered UI, still broken links

**Recommendation**: **Use cascade delete (current plan) with one addition**: Before deleting content, check if it has >20 reactions or >10 comments. If so, show user a warning: "This content has received significant engagement (X reactions, Y comments). Deleting it will also remove these notifications from your history. Are you sure?"

This balances cleanliness with user awareness. Most content has minimal engagement, so cascade delete is fine. For popular content, user makes informed decision.

**Additional Edge Cases**:

- **User blocks someone who reacted to their post**: 
  - *Suggested Answer*: Keep existing notifications, but prevent new ones from blocked user. Optionally, add filter to hide notifications from blocked users.

- **User deletes their account**:
  - *Suggested Answer*: CASCADE delete all notifications where they are the recipient (user_id). For notifications where they are the actor, set actor_id to NULL and actor_handle to "Deleted User".

- **Content ownership transfer** (if feature added later):
  - *Suggested Answer*: Keep notifications pointing to original owner. New owner starts fresh notification history.

---

#### Q7: How should we handle notification spam or abuse (e.g., user spamming reactions to trigger notifications)?

**Context**: Bad actors could spam reactions/comments to annoy users with notifications.

**Suggested Answer**:

**Rate Limiting Strategies**:

1. **Per-user action rate limits** (apply at reaction/comment creation):
   - Max 30 reactions per minute per user
   - Max 10 comments per minute per user
   - Return 429 Too Many Requests if exceeded
   - Already partially implemented in API rate limiting

2. **Per-content rate limits**:
   - Max 100 reactions per hour per post (prevents coordinated spam)
   - Max 50 comments per hour per post
   
3. **Notification rate limits** (apply at notification creation):
   - Max 50 notifications sent to any user per hour from same actor
   - Max 200 notifications sent to any user per day total
   - After limit, silently drop notification creation (don't error, just skip)

4. **Pattern detection**:
   - If user removes/adds same reaction >5 times in 10 minutes → flag as spam
   - If user posts same comment text >3 times → flag as spam
   - Auto-hide flagged notifications from recipient

**User Controls**:

1. **Notification preferences**:
   - Allow users to disable notifications from specific users (soft block)
   - Allow disabling notifications entirely (per notification type)
   
2. **Report/Block**:
   - Let users report spam notifications
   - Automatic throttling after 3 reports from different users

**Recommendation**: **Implement basic rate limiting in Phase 1**:
- 30 reactions/min per user (existing API rate limit)
- 10 comments/min per user (existing API rate limit)
- Skip notification creation if same actor sends >50 notifications to same user in 1 hour

**Add advanced spam detection in Phase 2** (after real abuse patterns observed):
- Pattern detection
- User-specific notification preferences
- Report system

Most users won't abuse the system. Start simple, add complexity only when needed.

---

#### Q8: What happens if Redis goes down? How do we handle cache failures gracefully?

**Context**: Redis is used for unread counts (cache) and Pub/Sub (WebSocket broadcasting). Failures affect user experience.

**Suggested Answer**:

**Redis Failure Scenarios**:

1. **Redis cache (unread counts) unavailable**:
   - *Current Plan*: Fallback to database query (already implemented in `get_unread_count()`)
   - *Impact*: Slower responses (5-10ms vs <1ms) but functional
   - *Mitigation*: None needed, graceful degradation already implemented

2. **Redis Pub/Sub unavailable**:
   - *Impact*: WebSocket notifications won't broadcast, users don't get real-time updates
   - *Current Plan*: No fallback, notifications still created in DB
   - *User Experience*: Users see notifications on next page load/refresh (acceptable degradation)
   
3. **Redis completely down**:
   - *Impact*: Both cache and Pub/Sub fail
   - *Mitigation*: 
     - Database queries still work (slower but functional)
     - WebSocket connections stay alive but receive no messages
     - Users see notifications when they navigate/refresh

**Recommendations**:

1. **Immediate** (Phase 1):
   - Wrap all Redis calls in try/except (already in plan)
   - Log Redis failures to monitoring system
   - Add Redis health check endpoint: `GET /api/health/redis`
   - Set up alerts for Redis downtime

2. **Phase 2** (if Redis becomes critical bottleneck):
   - Redis Sentinel for automatic failover (minimal setup, ~30s failover time)
   - Keep last 1000 notifications per user in memory cache (fallback for unread count)
   
3. **Future** (if approaching 100K MAU):
   - Redis Cluster for high availability
   - Consider message queue for Pub/Sub (RabbitMQ has better HA)

**Testing Recommendation**: During development, regularly test with Redis disabled to ensure graceful degradation. Add integration test that verifies system works (with degraded UX) when Redis is down.

---

#### Q9: How do we handle WebSocket connection limits and memory pressure?

**Context**: Each WebSocket connection consumes memory and a file descriptor. Linux systems have limits (default ulimit often 1024).

**Suggested Answer**:

**Connection Limits**:

1. **Operating System Level**:
   - Default ulimit (file descriptors): Often 1024 (too low)
   - **Required change**: Set ulimit to 65536 in systemd service files
   - Command: `ulimit -n 65536` in startup scripts
   - Edit `/etc/security/limits.conf`:
     ```
     * soft nofile 65536
     * hard nofile 65536
     ```

2. **Application Level**:
   - FastAPI/Uvicorn default: No explicit limit (uses OS limits)
   - **Recommended**: Set max_connections in ConnectionManager
   - Implement connection limit: Max 15,000 concurrent WebSocket connections
   - Return 503 Service Unavailable if limit reached

3. **Memory Management**:
   - Each WebSocket connection: ~40KB memory (Python + buffers)
   - 10,000 connections = ~400MB
   - Current 4GB RAM VPS: Plenty of headroom
   - Alert at 12,000 connections (approaching limit)

**Connection Cleanup**:

1. **Stale connection detection**:
   - Implement ping/pong timeout (already in plan, 30s interval)
   - If client doesn't respond to ping within 90s, disconnect
   - Prevents accumulation of zombie connections

2. **Graceful degradation**:
   - If approaching connection limit, close oldest idle connections
   - Clients will auto-reconnect with exponential backoff

**Load Shedding**:
- If server CPU >90% for >60 seconds:
  - Stop accepting new WebSocket connections
  - Return 503 with Retry-After header
  - Existing connections remain active
  - Resume accepting connections when CPU <70%

**Recommendations**:

1. **Immediate** (Phase 1):
   - Increase ulimit to 65536 in deployment configuration
   - Implement max_connections = 15000 in ConnectionManager
   - Add connection count metric to monitoring dashboard
   - Set alert at 12,000 connections

2. **Phase 2**:
   - Implement load shedding if CPU utilization too high
   - Add connection pool management (prioritize active users)

3. **Future** (if needed):
   - Dedicated WebSocket servers (separate from API servers)
   - HAProxy for WebSocket load balancing
   - Sticky sessions to keep user on same WebSocket server

**Testing**: Use locust or similar to load test with 15,000 concurrent WebSocket connections in staging environment before production deploy.

---

### Physical Player Integration

#### Q10: If we want to extend notifications to physical players (e.g., show notification on p3a device), would the current architecture support this, or would it need significant refactoring?

**Context**: Physical players currently use MQTT for receiving commands and displaying artwork. Notifications could potentially be delivered to these devices (e.g., LED notification indicator, screen message).

**Suggested Answer**:

**Current Architecture Analysis**:

The current plan uses:
- **WebSocket over HTTPS** for web client notifications
- **Redis Pub/Sub** for broadcasting to web clients
- Physical players already use **MQTT** for commands (per MQTT_PROTOCOL.md)

**Integration Options**:

**Option 1: Dual-Channel Approach** (Easiest, Recommended)

Architecture:
- Web clients: WebSocket + Redis Pub/Sub (current plan)
- Physical players: MQTT (existing infrastructure)
- NotificationService publishes to both:
  - Redis Pub/Sub channel for WebSocket clients
  - MQTT topic for physical players

Implementation:
```python
# In NotificationService._broadcast_notification()
# Existing code publishes to Redis
redis.publish(channel, json.dumps(payload))

# Add MQTT publishing
mqtt_client.publish(
    topic=f"makapix/player/{player_key}/notification",
    payload=json.dumps(payload),
    qos=1
)
```

Changes needed:
- Add MQTT client to NotificationService (5 lines)
- Physical players subscribe to `makapix/player/{player_key}/notification` topic
- Players handle notification messages (display LED, show on screen, play sound)

Effort: **1-2 days** to implement server-side, player firmware update needed

**Option 2: Unified MQTT Approach** (Major Refactor)

Architecture:
- Both web clients and physical players use MQTT
- Web clients connect via MQTT over WebSocket (port 9001)
- Remove WebSocket manager, use MQTT broker for all real-time messaging

Changes needed:
- Replace WebSocket client with MQTT.js library in frontend
- Remove ConnectionManager and WebSocket endpoint
- All clients subscribe to MQTT topics
- MQTT broker handles all pub/sub

Effort: **2-3 weeks** refactoring, complete rewrite of WebSocket layer

**Option 3: Notification Service Abstraction** (Over-Engineered)

Architecture:
- Abstract notification delivery behind interface
- Multiple delivery backends: WebSocket, MQTT, FCM (mobile push), Email
- Factory pattern to choose delivery method per user preference

Changes needed:
- Create NotificationDeliveryService abstraction
- Implement WebSocketDelivery, MQTTDelivery adapters
- Routing logic to choose delivery method

Effort: **1 week**, adds significant complexity for unclear benefit

**Recommendation**: **Option 1: Dual-Channel Approach**

Rationale:
1. **Minimal changes**: Uses existing MQTT infrastructure, adds ~20 lines of code
2. **Protocol-appropriate**: WebSocket for web is standard, MQTT for IoT devices is standard
3. **Independently scalable**: Can scale WebSocket and MQTT separately
4. **Graceful degradation**: If MQTT fails, web notifications still work (and vice versa)
5. **Future-proof**: Easy to add more channels later (FCM, email, etc.)

Physical player notification handling:
```javascript
// In player firmware (ESP32 example)
void onMQTTMessage(String topic, String payload) {
    if (topic.endsWith("/notification")) {
        JSONObject notification = parseJSON(payload);
        
        // Simple notification indicator
        digitalWrite(LED_PIN, HIGH);  // Turn on LED
        delay(3000);
        digitalWrite(LED_PIN, LOW);   // Turn off after 3s
        
        // OR: Show on screen
        displayNotification(
            notification["actor_handle"] + " reacted to your post",
            notification["emoji"]
        );
    }
}
```

**Architecture Diagram with Physical Players**:

```
User Action (Reaction/Comment)
        ↓
NotificationService.create_notification()
        ↓
    Save to DB
        ↓
    Update Redis Counter
        ↓
        ├─────────────────┬─────────────────┐
        ↓                 ↓                 ↓
  Redis Pub/Sub     MQTT Publish    (Future: FCM, Email)
        ↓                 ↓
  WebSocket Server  MQTT Broker
        ↓                 ↓
   Web Browsers    Physical Players
```

**Additional Considerations for Physical Players**:

1. **Notification Preferences**:
   - Let users disable notifications to physical players (conserve battery/display)
   - Per-player settings: "Show notifications on p3a", "Show on web only"
   
2. **Rate Limiting**:
   - Physical players have limited processing power
   - Aggregate notifications before sending (max 1/minute to player)
   
3. **Offline Handling**:
   - Physical players may be offline
   - MQTT QoS 1 ensures delivery when player reconnects
   - Consider max queue depth (discard old notifications if >10 pending)

4. **Battery Considerations**:
   - Frequent MQTT messages drain battery
   - Implement "quiet hours" or batch notifications

**Implementation in Phases**:

Phase 1 (Web Only):
- Implement WebSocket notifications as planned
- No physical player integration

Phase 2 (Add Physical Players):
- Add MQTT publishing to NotificationService
- Update player firmware to handle notification messages
- Add user preferences for player notifications
- Test with p3a devices

**Conclusion**: Current architecture is **extensible to physical players with minimal effort** (1-2 days server-side). No refactoring needed. The dual-channel approach (WebSocket for web, MQTT for players) is optimal.

---

### Additional Considerations

#### Q11: Should we implement email notifications as an optional fallback or supplement to in-app notifications?

**Context**: Users who aren't actively browsing the site might miss important notifications. Email digests could improve engagement.

**Suggested Answer**:

**Email Notification Options**:

1. **No Email** (Current Plan)
   - *Pros*: Simple, no email infrastructure needed, no spam concerns
   - *Cons*: Users miss notifications when not on site, lower re-engagement

2. **Real-time Email** (Every notification)
   - *Pros*: Immediate awareness, high engagement
   - *Cons*: Extremely annoying, high unsubscribe rate, expensive (SendGrid charges per email)

3. **Daily Digest Email**
   - *Pros*: One email per day with summary, less annoying, effective re-engagement
   - *Cons*: Delayed notifications, requires email queue management
   
4. **Weekly Digest Email**
   - *Pros*: Minimal annoyance, very cheap
   - *Cons*: Too slow for timely engagement

**Recommendation**: **Start with no email (Phase 1)**, add **daily digest email in Phase 2** with these features:

1. **User preferences**:
   - Email notifications: On/Off (default Off)
   - Frequency: Daily / Weekly / Never
   - Minimum threshold: "Only if I have >5 unread notifications"

2. **Email content**:
   - Subject: "You have 12 new notifications on Makapix"
   - Body: Top 5 notifications with thumbnails and links
   - CTA: "View all notifications" button linking to /notifications page

3. **Implementation**:
   - Celery beat task runs daily at 8am user's timezone
   - Query users with email_notifications=true AND unread_count>threshold
   - Send digest via SendGrid (free tier: 100 emails/day sufficient for testing)
   - Track open rate and unsubscribe rate

4. **Cost**:
   - SendGrid free tier: 100/day (sufficient for early stages)
   - Paid tier at scale: $15/month for 50K emails (assumes 10K users, 50% opt-in, daily emails)

**Phase 1**: Skip email entirely. Monitor user engagement without it.

**Phase 2**: After 2-3 months, analyze data:
- What % of users log in daily? (If >70%, email not needed)
- What's average time to see notification? (If <24 hours, email not urgent)
- Are users requesting email notifications? (Listen to feedback)

Only implement email if data shows it would significantly improve engagement.

---

#### Q12: How should we handle notification localization/internationalization for future multi-language support?

**Context**: Makapix may expand to non-English speaking markets. Notifications contain user-facing text.

**Suggested Answer**:

**Current Plan**: English-only hardcoded strings

**Future i18n Considerations**:

1. **Notification text generation**:
   - Current: `"{actor_handle} reacted {emoji} to your artwork"`
   - i18n approach: Template with variables
   ```python
   notification_template = {
       "en": "{actor} reacted {emoji} to your {content_type}",
       "es": "{actor} reaccionó {emoji} a tu {content_type}",
       "pt": "{actor} reagiu {emoji} ao seu {content_type}",
   }
   ```

2. **Storage strategy**:
   
   **Option A: Store template key + parameters** (Recommended)
   ```json
   {
       "template": "notification.reaction.post",
       "params": {
           "actor": "john",
           "emoji": "❤️",
           "content_type": "artwork"
       }
   }
   ```
   - Render in user's preferred language at display time
   - Can change wording without database migration
   - Minimal storage overhead
   
   **Option B: Store pre-rendered text per language**
   ```json
   {
       "text_en": "john reacted ❤️ to your artwork",
       "text_es": "john reaccionó ❤️ a tu obra",
       "text_pt": "john reagiu ❤️ à sua obra"
   }
   ```
   - Faster display (no rendering)
   - Much larger database
   - Can't fix typos retroactively

3. **Database schema changes**:
   ```sql
   -- Option A approach
   ALTER TABLE notifications ADD COLUMN template_key VARCHAR(100);
   ALTER TABLE notifications ADD COLUMN template_params JSONB;
   
   -- Store rendered text as fallback only
   ALTER TABLE notifications ADD COLUMN text_rendered TEXT;
   ```

**Recommendation**: **Implement i18n-ready architecture in Phase 1** even if only supporting English:

1. **Use template approach** from day one:
   ```python
   # notification_templates.py
   TEMPLATES = {
       "reaction.post": {
           "en": "{actor} reacted {emoji} to your artwork"
       },
       "comment.post": {
           "en": "{actor} commented on your artwork"
       }
   }
   
   # Store in database
   notification.template_key = "reaction.post"
   notification.template_params = {"actor": actor_handle, "emoji": emoji}
   ```

2. **Render at display time**:
   ```python
   def render_notification(notification, user_language="en"):
       template = TEMPLATES[notification.template_key][user_language]
       return template.format(**notification.template_params)
   ```

3. **Cost of i18n-ready**:
   - Additional development time: 2-3 hours (minimal)
   - Storage overhead: ~100 bytes per notification (minimal)
   - Complexity: Low (template system is simple)

4. **Benefits**:
   - Easy to add languages later (just add template translations)
   - Can A/B test notification wording
   - Can fix typos/improve copy without database migration
   - Professional architecture from the start

**Phase 1**: Implement template system with English only

**Phase 2**: Add Spanish and Portuguese translations (largest Makapix markets after English)

**Future**: Community-contributed translations via Crowdin or similar

---

#### Q13: Should we implement notification preferences per notification type, or is a global on/off sufficient?

**Context**: Users may want some notifications (comments) but not others (reactions). Granular control improves UX but adds complexity.

**Suggested Answer**:

**Preference Granularity Options**:

1. **Global On/Off Only**:
   - Single toggle: "Enable notifications"
   - Simplest UX, minimal code
   - All-or-nothing (annoying for users)

2. **Per-Type Preferences** (Current Plan):
   ```python
   notify_on_post_reactions: bool
   notify_on_post_comments: bool
   notify_on_blog_reactions: bool
   notify_on_blog_comments: bool
   ```
   - Moderate complexity
   - Users control what they care about
   - 4 toggles (manageable)

3. **Per-Type + Per-Content Preferences**:
   - "Notify me about reactions on this specific post"
   - Very complex
   - Useful for creators who want to track specific content

4. **Advanced Filtering**:
   - "Only notify if reaction is ❤️ or 🔥"
   - "Only notify if commenter is someone I follow"
   - Very powerful but complex

**Recommendation**: **Implement per-type preferences (current plan) in Phase 1**, with these additions:

1. **Default Preferences** (for new users):
   ```python
   notify_on_post_reactions = True
   notify_on_post_comments = True
   notify_on_blog_reactions = True
   notify_on_blog_comments = True
   aggregate_same_type = True  # When implemented
   ```

2. **UI for Preferences**:
   - Settings page: `/settings/notifications`
   - 4 clear toggles with descriptions
   - Preview: "You'll receive notifications when..."
   
3. **Smart Defaults**:
   - If user has >100 followers, suggest enabling aggregation
   - If user receives >50 notifications/day, prompt to adjust preferences

4. **Phase 2 additions** (if user feedback requests):
   - Per-content muting: "Mute notifications for this post"
   - Per-user muting: "Don't notify me about actions from @spammer"
   - Quiet hours: "Don't send notifications 10pm-8am"

**Testing Preferences**:
- Ensure preferences are checked before creating notification
- Cache preferences in Redis for performance
- Invalidate cache when user updates preferences

**Migration Path**:
- When user first signs up: Insert default preferences row
- For existing users: Backfill preferences on first notification (lazy migration)

---

#### Q14: How do we ensure notification delivery consistency in a multi-instance API server environment (future scaling)?

**Context**: At 100K MAU, we'll need multiple API server instances. Current Redis Pub/Sub approach may have issues.

**Suggested Answer**:

**Current Single-Instance Architecture**:
- One API server, one WebSocket manager, one Redis Pub/Sub listener
- Notification created → Redis publish → WebSocket manager receives → Broadcasts to clients
- Works perfectly at 10K MAU

**Multi-Instance Challenges**:

1. **Problem**: User connected to Server A, notification created on Server B
   - Server B publishes to Redis Pub/Sub
   - Both Server A and Server B receive message
   - **Only Server A has the user's WebSocket connection**
   - **Server B can't deliver** (no connection)

2. **Solution Options**:

**Option A: Sticky Sessions** (Recommended for Phase 2)
- Load balancer assigns user to same server instance
- User always connects to Server A
- All their notifications route to Server A
- Implementation: HAProxy/nginx hash based on user_id
- Limitation: If Server A crashes, user's connections lost

**Option B: Broadcast to All Instances**
- Redis Pub/Sub broadcasts to all instances (already happens)
- Each instance checks if it has user's WebSocket
- Only instance with connection delivers message
- Current architecture already supports this!
- No code changes needed

**Option C: Redis Cluster with Sharding**
- Shard WebSocket connections by user_id
- Pub/Sub messages routed only to correct shard
- Complex setup, probably overkill

**Recommendation**: **Current architecture already supports multi-instance with no changes needed!**

Here's why:
```python
# In ConnectionManager._redis_listener()
async def _redis_listener(self):
    pubsub.psubscribe("notifications:user:*")
    
    while running:
        message = pubsub.get_message()
        user_id = extract_user_id(message)
        
        # This check handles multi-instance naturally
        if user_id in self.active_connections:
            await self.send_personal_message(message, user_id)
        # else: This instance doesn't have user's connection, ignore
```

**Multi-Instance Behavior**:
1. Notification created on Server B
2. Server B publishes to Redis: `notifications:user:123`
3. ALL instances receive message (Server A, B, C)
4. Server A has user 123's connection → delivers message
5. Server B, C don't have connection → silently ignore

**Result**: No lost messages, no duplicate delivery, no code changes needed!

**Only Concern**: Redis Pub/Sub scalability
- Pattern subscription (`notifications:user:*`) on all instances
- Each instance receives ALL messages (even for users not connected to it)
- At 10K concurrent users, 100 notifications/sec, 10 instances:
  - Each instance receives 100 msg/sec
  - Processes ~10 (its own users)
  - Ignores ~90 (other instances' users)
  - Still very efficient (Redis handles 100K+ msg/sec easily)

**Future Optimization** (only if Redis becomes bottleneck at 100K+ MAU):
- Implement sticky sessions to reduce unnecessary message broadcasting
- OR: Migrate to RabbitMQ with topic exchanges (more efficient routing)

**Recommendation**: No changes needed for multi-instance support. Current architecture handles it correctly. Monitor Redis CPU and network at scale, optimize only if bottleneck appears.

---

#### Q15: What security considerations should we address for the notification system?

**Context**: Notifications could be exploited for harassment, information disclosure, or DoS attacks.

**Suggested Answer**:

**Security Threats**:

1. **Notification Spam**:
   - Attacker creates 1000 accounts, spams reactions on victim's post
   - Victim receives 1000 notifications
   - *Mitigation*: Covered in Q7 (rate limiting)

2. **Information Disclosure**:
   - Notifications reveal that content exists before deletion
   - *Example*: User posts then deletes immediately, but notifications already sent
   - *Mitigation*: Acceptable tradeoff (content was public briefly)

3. **Enumeration Attack**:
   - Attacker tries to discover private content by triggering notifications
   - *Example*: Try to react to post IDs 1-10000, see which ones generate notifications
   - *Mitigation*: Already handled by existing post access controls

4. **WebSocket Hijacking**:
   - Attacker steals JWT token, connects to victim's notification WebSocket
   - Receives victim's notifications in real-time
   - *Mitigation*: 
     - Short-lived JWT tokens (15 min expiry)
     - HttpOnly cookies for token storage
     - Token refresh mechanism

5. **XSS via Notification Content**:
   - Attacker posts comment: `<script>alert('xss')</script>`
   - Notification shows comment preview with script
   - Script executes in victim's browser
   - *Mitigation*:
     - Sanitize all user-generated content before storing
     - Escape HTML when rendering notifications
     - Use React (already does escaping by default)

6. **DoS via WebSocket Connections**:
   - Attacker opens 10000 WebSocket connections
   - Exhausts server resources
   - *Mitigation*: Covered in Q9 (connection limits, rate limiting)

7. **Redis Command Injection**:
   - Attacker manipulates user_id to inject Redis commands
   - *Example*: user_id = "123; FLUSHALL"
   - *Mitigation*: Use parameterized Redis operations (already in plan)

**Security Checklist for Implementation**:

- [ ] **Input Validation**:
  - Validate all user_id, content_id parameters (must be integers)
  - Validate emoji (max 20 chars, UTF-8)
  - Validate comment_preview (max 100 chars, sanitized HTML)

- [ ] **Authentication**:
  - Verify JWT token on WebSocket connection
  - Reject expired or invalid tokens
  - Use secure token storage (HttpOnly cookies)

- [ ] **Authorization**:
  - User can only access their own notifications (check user_id)
  - User can only mark their own notifications as read
  - User cannot create notifications for others (server-side only)

- [ ] **Rate Limiting** (implement in Phase 1):
  ```python
  # In notification creation
  rate_limit_key = f"notif_rate:{actor_id}:{recipient_id}"
  if redis.incr(rate_limit_key) > 50:  # Max 50/hour per pair
      logger.warning(f"Rate limit exceeded for notifications")
      return None
  redis.expire(rate_limit_key, 3600)
  ```

- [ ] **XSS Prevention**:
  - Sanitize comment_body before storing preview:
  ```python
  import bleach
  comment_preview = bleach.clean(comment_body[:100], strip=True)
  ```
  - Frontend uses React (auto-escapes)

- [ ] **SQL Injection Prevention**:
  - Use SQLAlchemy parameterized queries (already in plan)
  - Never concatenate user input into SQL

- [ ] **Audit Logging**:
  - Log all notification creations (who, what, when)
  - Log suspicious patterns (high rate, spam)
  - Retain logs for 90 days

- [ ] **Privacy**:
  - Don't leak notification content to unauthorized users
  - Don't reveal whether user has notifications (unless authenticated)
  - Respect user blocks (covered in Q6)

**Security Testing**:

1. **Penetration Testing**:
   - Test with OWASP ZAP or Burp Suite
   - Try common attacks: XSS, SQL injection, CSRF

2. **Load Testing for DoS**:
   - Test rate limiting with locust
   - Verify server doesn't crash under load

3. **Code Review**:
   - Review all database queries for SQL injection
   - Review all user input handling for XSS

**Recommendation**: Implement security measures in Phase 1. Don't defer to "later". Security is foundational.

---

## Conclusion

This implementation plan provides a comprehensive roadmap for adding social notifications to Makapix Club. The system is designed to:

- **Scale efficiently** to 10,000 MAU on a single VPS
- **Deliver notifications in real-time** via WebSocket with <500ms latency
- **Provide excellent UX** with unread badges and highlighted notifications
- **Maintain low costs** by using existing infrastructure (PostgreSQL, Redis) with WebSockets
- **Handle both artwork and blog post** reactions/comments uniformly

The phased approach allows for iterative development and testing, ensuring each component works correctly before moving to the next phase. Performance expectations are realistic and achievable with the planned architecture.

**Estimated Total Implementation Time**: 3-4 weeks (1 senior full-stack engineer)

**Infrastructure Cost**: $0 additional (uses existing VPS resources, no MQTT broker needed)

**End Result**: A professional, real-time social notifications system that enhances user engagement and provides immediate feedback for content creators on the Makapix Club platform.

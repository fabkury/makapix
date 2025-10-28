from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import relationship

from .db import Base


# ============================================================================
# CORE ENTITIES
# ============================================================================


class User(Base):
    """User account with authentication and profile information."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    handle = Column(String(50), unique=True, nullable=False, index=True)
    display_name = Column(String(100), nullable=False)
    bio = Column(Text, nullable=True)
    website = Column(String(500), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    
    # Reputation & roles
    reputation = Column(Integer, nullable=False, default=0, index=True)
    roles = Column(JSON, nullable=False, default=list)  # ["user", "moderator", "owner"]
    
    # Visibility & moderation flags
    hidden_by_user = Column(Boolean, nullable=False, default=False)
    hidden_by_mod = Column(Boolean, nullable=False, default=False, index=True)
    non_conformant = Column(Boolean, nullable=False, default=False, index=True)
    deactivated = Column(Boolean, nullable=False, default=False, index=True)
    banned_until = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    # Relationships
    posts = relationship("Post", back_populates="owner", foreign_keys="Post.owner_id")
    comments = relationship("Comment", back_populates="author", foreign_keys="Comment.author_id")
    playlists = relationship("Playlist", back_populates="owner")
    devices = relationship("Device", back_populates="user", cascade="all, delete-orphan")
    badges = relationship("BadgeGrant", back_populates="user", cascade="all, delete-orphan")
    reputation_history = relationship("ReputationHistory", back_populates="user", cascade="all, delete-orphan")


class Post(Base):
    """User-created post with art metadata."""

    __tablename__ = "posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    kind = Column(String(20), nullable=False, default="art")  # Currently only "art"
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Content
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    hashtags = Column(ARRAY(String), nullable=False, default=list)
    
    # Art metadata
    art_url = Column(String(1000), nullable=False)
    canvas = Column(String(50), nullable=False)  # e.g., "64x64", "128x128"
    file_kb = Column(Integer, nullable=False)
    
    # Visibility & moderation
    visible = Column(Boolean, nullable=False, default=True, index=True)
    hidden_by_user = Column(Boolean, nullable=False, default=False)
    hidden_by_mod = Column(Boolean, nullable=False, default=False, index=True)
    non_conformant = Column(Boolean, nullable=False, default=False, index=True)
    
    # Promotion
    promoted = Column(Boolean, nullable=False, default=False, index=True)
    promoted_category = Column(String(50), nullable=True)  # frontpage, editor-pick, weekly-pack
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="posts", foreign_keys=[owner_id])
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    reactions = relationship("Reaction", back_populates="post", cascade="all, delete-orphan")
    admin_notes = relationship("AdminNote", back_populates="post", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_posts_hashtags", "hashtags", postgresql_using="gin"),
        Index("ix_posts_owner_created", owner_id, created_at.desc()),
    )


class Comment(Base):
    """Comment on a post, supporting two-level nesting."""

    __tablename__ = "comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id"), nullable=False, index=True)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("comments.id"), nullable=True, index=True)
    
    depth = Column(Integer, nullable=False, default=0)  # 0 = top-level, max 2
    body = Column(Text, nullable=False)
    
    # Moderation
    hidden_by_mod = Column(Boolean, nullable=False, default=False, index=True)
    deleted_by_owner = Column(Boolean, nullable=False, default=False)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    # Relationships
    post = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments", foreign_keys=[author_id])
    parent = relationship("Comment", remote_side=[id], backref="replies")

    __table_args__ = (
        Index("ix_comments_post_created", post_id, created_at.desc()),
    )


class Playlist(Base):
    """Curated collection of posts."""

    __tablename__ = "playlists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    post_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    
    # Visibility
    visible = Column(Boolean, nullable=False, default=True, index=True)
    hidden_by_user = Column(Boolean, nullable=False, default=False)
    hidden_by_mod = Column(Boolean, nullable=False, default=False, index=True)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="playlists")


# ============================================================================
# SOCIAL FEATURES
# ============================================================================


class Reaction(Base):
    """Emoji reaction to a post."""

    __tablename__ = "reactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    emoji = Column(String(20), nullable=False)
    
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    post = relationship("Post", back_populates="reactions")

    __table_args__ = (
        UniqueConstraint("post_id", "user_id", "emoji", name="uq_reaction_post_user_emoji"),
        Index("ix_reactions_post_emoji", post_id, emoji),
    )


class Follow(Base):
    """User following relationship."""

    __tablename__ = "follows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    follower_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    following_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    __table_args__ = (
        UniqueConstraint("follower_id", "following_id", name="uq_follow_follower_following"),
        Index("ix_follows_following_created", following_id, created_at.desc()),
    )


# ============================================================================
# BADGES & REPUTATION
# ============================================================================


class BadgeGrant(Base):
    """Badge awarded to a user."""

    __tablename__ = "badge_grants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    badge = Column(String(50), nullable=False)  # e.g., "early-adopter", "top-contributor"
    
    granted_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    user = relationship("User", back_populates="badges")

    __table_args__ = (
        UniqueConstraint("user_id", "badge", name="uq_badge_grant_user_badge"),
    )


class ReputationHistory(Base):
    """History of reputation changes."""

    __tablename__ = "reputation_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    delta = Column(Integer, nullable=False)
    reason = Column(String(200), nullable=True)
    
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    user = relationship("User", back_populates="reputation_history")


# ============================================================================
# MODERATION
# ============================================================================


class Report(Base):
    """User-submitted report for content moderation."""

    __tablename__ = "reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    reporter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    target_type = Column(String(20), nullable=False, index=True)  # user, post, comment
    target_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    reason_code = Column(String(50), nullable=False)  # spam, abuse, copyright, other
    notes = Column(Text, nullable=True)
    
    status = Column(String(20), nullable=False, default="open", index=True)  # open, triaged, resolved
    action_taken = Column(String(20), nullable=True)  # hide, delete, ban, none
    
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    __table_args__ = (
        Index("ix_reports_status_created", status, created_at.desc()),
        Index("ix_reports_target", target_type, target_id),
    )


class AdminNote(Base):
    """Internal admin note on a post."""

    __tablename__ = "admin_notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id"), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    note = Column(Text, nullable=False)
    
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    post = relationship("Post", back_populates="admin_notes")


# ============================================================================
# DEVICES & AUTH
# ============================================================================


class Device(Base):
    """IoT device for MQTT access."""

    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    user = relationship("User", back_populates="devices")


# ============================================================================
# SYSTEM
# ============================================================================


class ConformanceCheck(Base):
    """GitHub Pages conformance check status."""

    __tablename__ = "conformance_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True)
    
    status = Column(String(50), nullable=False, default="ok")  # ok, missing_manifest, invalid_manifest, hotlinks_broken
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    next_check_at = Column(DateTime(timezone=True), nullable=True, index=True)


class RelayJob(Base):
    """GitHub Pages relay job status."""

    __tablename__ = "relay_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    status = Column(String(20), nullable=False, default="queued", index=True)  # queued, running, committed, failed
    repo = Column(String(200), nullable=True)
    commit = Column(String(100), nullable=True)
    error = Column(Text, nullable=True)
    
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


class AuditLog(Base):
    """Audit log for admin actions."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(20), nullable=True)
    target_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    __table_args__ = (
        Index("ix_audit_logs_actor_created", actor_id, created_at.desc()),
    )

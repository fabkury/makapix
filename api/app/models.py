from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
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
    bio = Column(Text, nullable=True)
    website = Column(String(500), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    email = Column(String(255), unique=True, nullable=False, index=True)  # Email must be unique
    email_verified = Column(Boolean, nullable=False, default=False, index=True)
    
    # Reputation & roles
    reputation = Column(Integer, nullable=False, default=0, index=True)
    roles = Column(JSON, nullable=False, default=list)  # ["user", "moderator", "owner"]
    
    # Visibility & moderation flags
    hidden_by_user = Column(Boolean, nullable=False, default=False)
    hidden_by_mod = Column(Boolean, nullable=False, default=False, index=True)
    non_conformant = Column(Boolean, nullable=False, default=False, index=True)
    deactivated = Column(Boolean, nullable=False, default=False, index=True)
    banned_until = Column(DateTime(timezone=True), nullable=True, index=True)
    
    # Publishing privileges
    auto_public_approval = Column(Boolean, nullable=False, default=False, index=True)  # Auto-approve public visibility for uploads
    
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
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    auth_identities = relationship("AuthIdentity", back_populates="user", cascade="all, delete-orphan")
    email_verification_tokens = relationship("EmailVerificationToken", back_populates="user", cascade="all, delete-orphan")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    """Refresh token for JWT authentication."""

    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    revoked = Column(Boolean, nullable=False, default=False, index=True)
    
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")


class AuthIdentity(Base):
    """Authentication identity for a user (password, OAuth provider, etc.)."""

    __tablename__ = "auth_identities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    # Provider identification
    provider = Column(String(50), nullable=False, index=True)  # "password", "github", "reddit", etc.
    provider_user_id = Column(String(255), nullable=False, index=True)  # Username for password, OAuth ID for OAuth
    
    # Authentication secret (hashed password for password provider, null for OAuth)
    secret_hash = Column(String(255), nullable=True)
    
    # Optional metadata
    email = Column(String(255), nullable=True, index=True)
    provider_metadata = Column(JSON, nullable=True)  # Provider-specific data (e.g., GitHub username, avatar URL)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="auth_identities")

    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_auth_identity_provider_user"),
        Index("ix_auth_identities_user_provider", user_id, provider),
    )


class EmailVerificationToken(Base):
    """Email verification token for verifying user email addresses."""

    __tablename__ = "email_verification_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False)  # Email being verified
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    user = relationship("User", back_populates="email_verification_tokens")


class PasswordResetToken(Base):
    """Password reset token for resetting user passwords."""

    __tablename__ = "password_reset_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    user = relationship("User", back_populates="password_reset_tokens")


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
    expected_hash = Column(String(64), nullable=True, index=True)  # SHA256 hash for mismatch detection
    mime_type = Column(String(50), nullable=True)  # MIME type (image/png, image/jpeg, image/gif)
    
    # Visibility & moderation
    visible = Column(Boolean, nullable=False, default=True, index=True)
    hidden_by_user = Column(Boolean, nullable=False, default=False)
    hidden_by_mod = Column(Boolean, nullable=False, default=False, index=True)
    non_conformant = Column(Boolean, nullable=False, default=False, index=True)
    public_visibility = Column(Boolean, nullable=False, default=False, index=True)  # Controls visibility in Recent Artworks, search, etc.
    
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
        Index("ix_posts_non_conformant_created", non_conformant, created_at.desc()),
    )


class Comment(Base):
    """Comment on a post, supporting two-level nesting."""

    __tablename__ = "comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id"), nullable=False, index=True)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    author_ip = Column(String(45), nullable=True, index=True)  # For anonymous users
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
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    user_ip = Column(String(45), nullable=True, index=True)  # For anonymous users
    emoji = Column(String(20), nullable=False)
    
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    post = relationship("Post", back_populates="reactions")

    __table_args__ = (
        # Note: Unique constraints handled by partial indexes in migration
        # to support both user_id and user_ip cases
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


class CategoryFollow(Base):
    """User following a category (e.g., daily's-best)."""

    __tablename__ = "category_follows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)  # e.g., "daily's-best"
    
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_category_follow_user_category"),
        Index("ix_category_follows_category_created", category, created_at.desc()),
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
    cert_serial_number = Column(String(100), nullable=True, unique=True, index=True)  # For certificate revocation
    
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
    bundle_path = Column(String(500), nullable=True)
    manifest_data = Column(JSON, nullable=True)
    
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


class GitHubInstallation(Base):
    """GitHub App installation binding."""

    __tablename__ = "github_installations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    installation_id = Column(BigInteger, nullable=False, unique=True, index=True)
    account_login = Column(String(100), nullable=False)
    account_type = Column(String(20), nullable=False)
    target_repo = Column(String(200), nullable=True)
    access_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", backref="github_installation")


class AuditLog(Base):
    """Audit log for admin actions."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(20), nullable=True)
    target_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    reason_code = Column(String(50), nullable=True)  # e.g., "spam", "abuse", "copyright", "other"
    note = Column(Text, nullable=True)  # Additional context/notes
    
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    __table_args__ = (
        Index("ix_audit_logs_actor_created", actor_id, created_at.desc()),
    )


# ============================================================================
# VIEW TRACKING & STATISTICS
# ============================================================================


class ViewEvent(Base):
    """Raw view event for tracking artwork views."""

    __tablename__ = "view_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    viewer_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Viewer identification (for unique viewer tracking)
    viewer_ip_hash = Column(String(64), nullable=False)  # SHA256 hash of IP address
    
    # Geographic data
    country_code = Column(String(2), nullable=True, index=True)  # ISO 3166-1 alpha-2 (e.g., "US", "BR")
    
    # Device & source information
    device_type = Column(String(20), nullable=False, index=True)  # desktop, mobile, tablet, player
    view_source = Column(String(20), nullable=False)  # web, api, widget, player
    view_type = Column(String(20), nullable=False, index=True)  # intentional, listing, search, widget
    
    # Additional metadata
    user_agent_hash = Column(String(64), nullable=True)  # For device fingerprinting
    referrer_domain = Column(String(255), nullable=True)  # Extracted referrer domain
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    post = relationship("Post", backref="view_events")

    __table_args__ = (
        Index("ix_view_events_post_created", post_id, created_at.desc()),
    )


class PostStatsDaily(Base):
    """Daily aggregated statistics for a post (permanent storage)."""

    __tablename__ = "post_stats_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # Aggregated counts
    total_views = Column(Integer, nullable=False, default=0)
    unique_viewers = Column(Integer, nullable=False, default=0)
    
    # Breakdown by dimension (stored as JSONB for flexibility)
    views_by_country = Column(JSON, nullable=False, default=dict)  # {"US": 50, "BR": 30, ...}
    views_by_device = Column(JSON, nullable=False, default=dict)  # {"desktop": 40, "mobile": 35, ...}
    views_by_type = Column(JSON, nullable=False, default=dict)  # {"intentional": 60, "listing": 15, ...}
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    post = relationship("Post", backref="stats_daily")

    __table_args__ = (
        UniqueConstraint("post_id", "date", name="uq_post_stats_daily_post_date"),
        Index("ix_post_stats_daily_post_date", post_id, date),
    )


class PostStatsCache(Base):
    """Cached computed statistics for a post."""

    __tablename__ = "post_stats_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # Full computed statistics as JSON
    stats_json = Column(JSON, nullable=False)
    
    # Timestamps
    computed_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    post = relationship("Post", backref="stats_cache")

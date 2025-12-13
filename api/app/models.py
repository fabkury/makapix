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
from sqlalchemy.orm import relationship, backref

from .db import Base


# ============================================================================
# CORE ENTITIES
# ============================================================================


class User(Base):
    """User account with authentication and profile information."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    user_key = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )  # UUID used for legacy URLs
    public_sqid = Column(
        String(16), unique=True, nullable=True, index=True
    )  # Sqids-encoded public ID (set after insert)
    handle = Column(String(50), unique=True, nullable=False, index=True)
    bio = Column(Text, nullable=True)
    website = Column(String(500), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    email = Column(
        String(255), unique=True, nullable=False, index=True
    )  # Email must be unique
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
    auto_public_approval = Column(
        Boolean, nullable=False, default=False, index=True
    )  # Auto-approve public visibility for uploads

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    # Relationships
    posts = relationship("Post", back_populates="owner", foreign_keys="Post.owner_id")
    comments = relationship(
        "Comment", back_populates="author", foreign_keys="Comment.author_id"
    )
    blog_posts = relationship(
        "BlogPost", back_populates="owner", foreign_keys="BlogPost.owner_id"
    )
    blog_post_comments = relationship(
        "BlogPostComment",
        back_populates="author",
        foreign_keys="BlogPostComment.author_id",
    )
    playlists = relationship("Playlist", back_populates="owner")
    players = relationship(
        "Player", back_populates="owner", cascade="all, delete-orphan"
    )
    badges = relationship(
        "BadgeGrant", back_populates="user", cascade="all, delete-orphan"
    )
    reputation_history = relationship(
        "ReputationHistory", back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    auth_identities = relationship(
        "AuthIdentity", back_populates="user", cascade="all, delete-orphan"
    )
    email_verification_tokens = relationship(
        "EmailVerificationToken", back_populates="user", cascade="all, delete-orphan"
    )
    password_reset_tokens = relationship(
        "PasswordResetToken", back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    """Refresh token for JWT authentication."""

    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Provider identification
    provider = Column(
        String(50), nullable=False, index=True
    )  # "password", "github", "reddit", etc.
    provider_user_id = Column(
        String(255), nullable=False, index=True
    )  # Username for password, OAuth ID for OAuth

    # Authentication secret (hashed password for password provider, null for OAuth)
    secret_hash = Column(String(255), nullable=True)

    # Optional metadata
    email = Column(String(255), nullable=True, index=True)
    provider_metadata = Column(
        JSON, nullable=True
    )  # Provider-specific data (e.g., GitHub username, avatar URL)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="auth_identities")

    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_user_id", name="uq_auth_identity_provider_user"
        ),
        Index("ix_auth_identities_user_provider", user_id, provider),
    )


class EmailVerificationToken(Base):
    """Email verification token for verifying user email addresses."""

    __tablename__ = "email_verification_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
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

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    storage_key = Column(
        UUID(as_uuid=True), unique=True, nullable=False, index=True
    )  # UUID used for vault lookup
    public_sqid = Column(
        String(16), unique=True, nullable=True, index=True
    )  # Sqids-encoded public ID (set after insert)
    # "artwork" posts contain an artwork asset; "playlist" posts contain ordered references
    # to other posts via playlist_items.
    kind = Column(String(20), nullable=False, default="artwork")
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Content
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    hashtags = Column(ARRAY(String), nullable=False, default=list)

    # Art metadata
    # NOTE: These are nullable to allow kind="playlist" rows in this table.
    art_url = Column(String(1000), nullable=True)
    canvas = Column(
        String(50), nullable=True
    )  # e.g., "64x64", "128x128" - kept for backward compatibility
    width = Column(Integer, nullable=True, index=True)  # Canvas width in pixels
    height = Column(Integer, nullable=True, index=True)  # Canvas height in pixels
    file_bytes = Column(Integer, nullable=True)  # Exact file size in bytes
    frame_count = Column(
        Integer, nullable=False, default=1
    )  # Number of animation frames
    min_frame_duration_ms = Column(
        Integer, nullable=True
    )  # Minimum non-zero frame duration (ms), NULL for static
    has_transparency = Column(
        Boolean, nullable=False, default=False
    )  # Whether image has alpha channel
    expected_hash = Column(
        String(64), nullable=True, index=True
    )  # SHA256 hash for mismatch detection
    mime_type = Column(
        String(50), nullable=True
    )  # MIME type (image/png, image/jpeg, image/gif)

    # Visibility & moderation
    visible = Column(Boolean, nullable=False, default=True, index=True)
    hidden_by_user = Column(Boolean, nullable=False, default=False)
    hidden_by_mod = Column(Boolean, nullable=False, default=False, index=True)
    non_conformant = Column(Boolean, nullable=False, default=False, index=True)
    public_visibility = Column(
        Boolean, nullable=False, default=False, index=True
    )  # Controls visibility in Recent Artworks, search, etc.

    # Promotion
    promoted = Column(Boolean, nullable=False, default=False, index=True)
    promoted_category = Column(
        String(50), nullable=True
    )  # frontpage, editor-pick, weekly-pack

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    # Modified-at timestamps (required by player protocol)
    metadata_modified_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    artwork_modified_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # Display timing (milliseconds)
    dwell_time_ms = Column(Integer, nullable=False, default=30000)

    # Relationships
    owner = relationship("User", back_populates="posts", foreign_keys=[owner_id])
    comments = relationship(
        "Comment", back_populates="post", cascade="all, delete-orphan"
    )
    reactions = relationship(
        "Reaction", back_populates="post", cascade="all, delete-orphan"
    )
    admin_notes = relationship(
        "AdminNote", back_populates="post", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_posts_hashtags", "hashtags", postgresql_using="gin"),
        Index("ix_posts_owner_created", owner_id, created_at.desc()),
        Index("ix_posts_non_conformant_created", non_conformant, created_at.desc()),
    )


class PlaylistPost(Base):
    """Playlist post marker table (1:1 with posts rows where kind='playlist')."""

    __tablename__ = "playlist_posts"

    post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    legacy_playlist_id = Column(UUID(as_uuid=True), unique=True, nullable=True, index=True)

    # Relationships
    post = relationship("Post", backref="playlist_post", foreign_keys=[post_id])


class PlaylistItem(Base):
    """Ordered playlist items referencing artwork posts (and optionally dwell overrides)."""

    __tablename__ = "playlist_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    playlist_post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    artwork_post_id = Column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    dwell_time_ms = Column(Integer, nullable=False, default=30000)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    # Relationships
    playlist_post = relationship("Post", foreign_keys=[playlist_post_id])
    artwork_post = relationship("Post", foreign_keys=[artwork_post_id])

    __table_args__ = (
        UniqueConstraint("playlist_post_id", "position", name="uq_playlist_items_playlist_position"),
        Index("ix_playlist_items_playlist_position", playlist_post_id, position),
    )


class Comment(Base):
    """Comment on a post, supporting two-level nesting."""

    __tablename__ = "comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    author_ip = Column(String(45), nullable=True, index=True)  # For anonymous users
    parent_id = Column(
        UUID(as_uuid=True), ForeignKey("comments.id"), nullable=True, index=True
    )

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

    __table_args__ = (Index("ix_comments_post_created", post_id, created_at.desc()),)


class Playlist(Base):
    """Curated collection of posts."""

    __tablename__ = "playlists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    post_ids = Column(ARRAY(Integer), nullable=False, default=list)

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
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
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
    follower_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    following_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    __table_args__ = (
        UniqueConstraint(
            "follower_id", "following_id", name="uq_follow_follower_following"
        ),
        Index("ix_follows_following_created", following_id, created_at.desc()),
    )


class CategoryFollow(Base):
    """User following a category (e.g., daily's-best)."""

    __tablename__ = "category_follows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)  # e.g., "daily's-best"

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "category", name="uq_category_follow_user_category"
        ),
        Index("ix_category_follows_category_created", category, created_at.desc()),
    )


# ============================================================================
# BADGES & REPUTATION
# ============================================================================


class BadgeGrant(Base):
    """Badge awarded to a user."""

    __tablename__ = "badge_grants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    badge = Column(
        String(50), nullable=False
    )  # e.g., "early-adopter", "top-contributor"

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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
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
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    target_type = Column(String(20), nullable=False, index=True)  # user, post, comment
    target_id = Column(
        String(50), nullable=False, index=True
    )  # String to support both UUID and integer IDs

    reason_code = Column(String(50), nullable=False)  # spam, abuse, copyright, other
    notes = Column(Text, nullable=True)

    status = Column(
        String(20), nullable=False, default="open", index=True
    )  # open, triaged, resolved
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
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    note = Column(Text, nullable=False)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    post = relationship("Post", back_populates="admin_notes")


# ============================================================================
# PLAYERS & AUTH
# ============================================================================


class Player(Base):
    """Physical or virtual player that displays artworks."""

    __tablename__ = "players"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    player_key = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )

    # Owner (nullable until registered)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Player identification
    name = Column(String(100), nullable=True)
    device_model = Column(String(100), nullable=True)
    firmware_version = Column(String(50), nullable=True)

    # Registration state
    registration_status = Column(
        String(20), nullable=False, default="pending"
    )  # pending, registered
    registration_code = Column(String(6), unique=True, nullable=True, index=True)
    registration_code_expires_at = Column(DateTime(timezone=True), nullable=True)
    registered_at = Column(DateTime(timezone=True), nullable=True)

    # Connection state (updated via MQTT status messages)
    connection_status = Column(
        String(20), nullable=False, default="offline"
    )  # offline, online
    last_seen_at = Column(DateTime(timezone=True), nullable=True)

    # Current state (for UI display - player manages its own queue internally)
    current_post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)

    # Certificate tracking
    cert_serial_number = Column(String(100), nullable=True, unique=True, index=True)
    cert_issued_at = Column(DateTime(timezone=True), nullable=True)
    cert_expires_at = Column(DateTime(timezone=True), nullable=True)
    cert_pem = Column(Text, nullable=True)  # Client certificate PEM
    key_pem = Column(Text, nullable=True)  # Private key PEM

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    # Relationships
    owner = relationship("User", back_populates="players")
    current_post = relationship("Post", foreign_keys=[current_post_id])


class PlayerCommandLog(Base):
    """Log of commands sent to players.

    Command types:
    - swap_next: Show next artwork
    - swap_back: Show previous artwork
    - show_artwork: Show specific artwork
    - add_device: Device registered to user (logged at registration time)
    - remove_device: Device removed by user (logged at deletion time)
    """

    __tablename__ = "player_command_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable to preserve logs when player is deleted (SET NULL on delete)
    player_id = Column(
        UUID(as_uuid=True),
        ForeignKey("players.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    command_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=True)  # Command-specific data

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationship (optional since player_id can be null)
    player = relationship("Player", backref="command_logs")


# ============================================================================
# SYSTEM
# ============================================================================


class ConformanceCheck(Base):
    """GitHub Pages conformance check status."""

    __tablename__ = "conformance_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True
    )

    status = Column(
        String(50), nullable=False, default="ok"
    )  # ok, missing_manifest, invalid_manifest, hotlinks_broken
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    next_check_at = Column(DateTime(timezone=True), nullable=True, index=True)


class RelayJob(Base):
    """GitHub Pages relay job status."""

    __tablename__ = "relay_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    status = Column(
        String(20), nullable=False, default="queued", index=True
    )  # queued, running, committed, failed
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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
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
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(20), nullable=True)
    target_id = Column(
        String(50), nullable=True, index=True
    )  # String to support both UUID and integer IDs

    reason_code = Column(
        String(50), nullable=True
    )  # e.g., "spam", "abuse", "copyright", "other"
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
    post_id = Column(
        Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    viewer_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Viewer identification (for unique viewer tracking)
    viewer_ip_hash = Column(String(64), nullable=False)  # SHA256 hash of IP address

    # Geographic data
    country_code = Column(
        String(2), nullable=True, index=True
    )  # ISO 3166-1 alpha-2 (e.g., "US", "BR")

    # Device & source information
    device_type = Column(
        String(20), nullable=False, index=True
    )  # desktop, mobile, tablet, player
    view_source = Column(String(20), nullable=False)  # web, api, widget, player
    view_type = Column(
        String(20), nullable=False, index=True
    )  # intentional, listing, search, widget

    # Additional metadata
    user_agent_hash = Column(String(64), nullable=True)  # For device fingerprinting
    referrer_domain = Column(String(255), nullable=True)  # Extracted referrer domain

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    post = relationship(
        "Post",
        backref=backref("view_events", passive_deletes=True),
        passive_deletes=True,
    )

    __table_args__ = (Index("ix_view_events_post_created", post_id, created_at.desc()),)


class PostStatsDaily(Base):
    """Daily aggregated statistics for a post (permanent storage)."""

    __tablename__ = "post_stats_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(
        Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date = Column(Date, nullable=False, index=True)

    # Aggregated counts
    total_views = Column(Integer, nullable=False, default=0)
    unique_viewers = Column(Integer, nullable=False, default=0)

    # Breakdown by dimension (stored as JSONB for flexibility)
    views_by_country = Column(
        JSON, nullable=False, default=dict
    )  # {"US": 50, "BR": 30, ...}
    views_by_device = Column(
        JSON, nullable=False, default=dict
    )  # {"desktop": 40, "mobile": 35, ...}
    views_by_type = Column(
        JSON, nullable=False, default=dict
    )  # {"intentional": 60, "listing": 15, ...}

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    post = relationship(
        "Post",
        backref=backref("stats_daily", passive_deletes=True),
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("post_id", "date", name="uq_post_stats_daily_post_date"),
        Index("ix_post_stats_daily_post_date", post_id, date),
    )


class PostStatsCache(Base):
    """Cached computed statistics for a post."""

    __tablename__ = "post_stats_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(
        Integer,
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Full computed statistics as JSON
    stats_json = Column(JSON, nullable=False)

    # Timestamps
    computed_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    post = relationship(
        "Post",
        backref=backref("stats_cache", passive_deletes=True),
        passive_deletes=True,
    )


# ============================================================================
# SITEWIDE METRICS & STATISTICS
# ============================================================================


class SiteEvent(Base):
    """Raw sitewide event for tracking site metrics (7-day retention)."""

    __tablename__ = "site_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    event_type = Column(
        String(50), nullable=False, index=True
    )  # page_view, signup, upload, api_call, error
    page_path = Column(String(500), nullable=True)  # /recent, /posts/[id], etc.

    # Visitor identification
    visitor_ip_hash = Column(String(64), nullable=False)  # SHA256 hash of IP address
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Device & geographic information
    device_type = Column(
        String(20), nullable=False, index=True
    )  # desktop, mobile, tablet
    country_code = Column(String(2), nullable=True, index=True)  # ISO 3166-1 alpha-2
    referrer_domain = Column(String(255), nullable=True)  # Extracted referrer domain

    # Event-specific data (JSON for flexibility)
    event_data = Column(
        JSON, nullable=True
    )  # {endpoint, status_code, error_message, etc.}

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    user = relationship(
        "User",
        backref=backref("site_events", passive_deletes=True),
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_site_events_type_created", event_type, created_at.desc()),
        Index("ix_site_events_created", created_at.desc()),
    )


class SiteStatsDaily(Base):
    """Daily aggregated sitewide statistics (permanent storage)."""

    __tablename__ = "site_stats_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)

    # Core metrics
    total_page_views = Column(Integer, nullable=False, default=0)
    unique_visitors = Column(Integer, nullable=False, default=0)
    new_signups = Column(Integer, nullable=False, default=0)
    new_posts = Column(Integer, nullable=False, default=0)
    total_api_calls = Column(Integer, nullable=False, default=0)
    total_errors = Column(Integer, nullable=False, default=0)

    # Breakdown by dimension (stored as JSON for flexibility)
    views_by_page = Column(
        JSON, nullable=False, default=dict
    )  # {"/recent": 500, "/posts": 300, ...}
    views_by_country = Column(
        JSON, nullable=False, default=dict
    )  # {"US": 200, "BR": 150, ...}
    views_by_device = Column(
        JSON, nullable=False, default=dict
    )  # {"desktop": 400, "mobile": 350, ...}
    errors_by_type = Column(
        JSON, nullable=False, default=dict
    )  # {"404": 50, "500": 5, ...}
    top_referrers = Column(
        JSON, nullable=False, default=dict
    )  # {"google.com": 100, "twitter.com": 50, ...}

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_site_stats_daily_date", date),)


# ============================================================================
# BLOG POSTS
# ============================================================================


class BlogPost(Base):
    """Markdown-based blog post."""

    __tablename__ = "blog_posts"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    blog_post_key = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )  # UUID used for legacy URLs
    public_sqid = Column(
        String(16), unique=True, nullable=True, index=True
    )  # Sqids-encoded public ID (set after insert)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Content
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)  # Markdown content, up to 10,000 chars
    image_urls = Column(
        ARRAY(String), nullable=False, default=list
    )  # Up to 10 image URLs

    # Visibility & moderation
    visible = Column(Boolean, nullable=False, default=True, index=True)
    hidden_by_user = Column(Boolean, nullable=False, default=False)
    hidden_by_mod = Column(Boolean, nullable=False, default=False, index=True)
    public_visibility = Column(
        Boolean, nullable=False, default=False, index=True
    )  # Controls visibility in blog feed

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(
        DateTime(timezone=True), nullable=True, onupdate=func.now(), index=True
    )
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    owner = relationship("User", back_populates="blog_posts", foreign_keys=[owner_id])
    comments = relationship(
        "BlogPostComment", back_populates="blog_post", cascade="all, delete-orphan"
    )
    reactions = relationship(
        "BlogPostReaction", back_populates="blog_post", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_blog_posts_owner_created", owner_id, created_at.desc()),
        Index("ix_blog_posts_public_updated", public_visibility, updated_at.desc()),
        Index("ix_blog_posts_public_created", public_visibility, created_at.desc()),
    )


class BlogPostComment(Base):
    """Comment on a blog post, supporting three-level nesting."""

    __tablename__ = "blog_post_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    blog_post_id = Column(
        Integer, ForeignKey("blog_posts.id"), nullable=False, index=True
    )
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    author_ip = Column(String(45), nullable=True, index=True)  # For anonymous users
    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("blog_post_comments.id"),
        nullable=True,
        index=True,
    )

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
    blog_post = relationship("BlogPost", back_populates="comments")
    author = relationship(
        "User", back_populates="blog_post_comments", foreign_keys=[author_id]
    )
    parent = relationship("BlogPostComment", remote_side=[id], backref="replies")

    __table_args__ = (
        Index(
            "ix_blog_post_comments_blog_post_created", blog_post_id, created_at.desc()
        ),
    )


class BlogPostReaction(Base):
    """Emoji reaction to a blog post."""

    __tablename__ = "blog_post_reactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    blog_post_id = Column(
        Integer, ForeignKey("blog_posts.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    user_ip = Column(String(45), nullable=True, index=True)  # For anonymous users
    emoji = Column(String(20), nullable=False)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    blog_post = relationship("BlogPost", back_populates="reactions")

    __table_args__ = (
        Index("ix_blog_post_reactions_blog_post_emoji", blog_post_id, emoji),
    )


class BlogPostViewEvent(Base):
    """Raw view event for tracking blog post views."""

    __tablename__ = "blog_post_view_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    blog_post_id = Column(
        Integer, ForeignKey("blog_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    viewer_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Viewer identification (for unique viewer tracking)
    viewer_ip_hash = Column(String(64), nullable=False)  # SHA256 hash of IP address

    # Geographic data
    country_code = Column(
        String(2), nullable=True, index=True
    )  # ISO 3166-1 alpha-2 (e.g., "US", "BR")

    # Device & source information
    device_type = Column(
        String(20), nullable=False, index=True
    )  # desktop, mobile, tablet, player
    view_source = Column(String(20), nullable=False)  # web, api, widget, player
    view_type = Column(
        String(20), nullable=False, index=True
    )  # intentional, listing, search, widget

    # Additional metadata
    user_agent_hash = Column(String(64), nullable=True)  # For device fingerprinting
    referrer_domain = Column(String(255), nullable=True)  # Extracted referrer domain

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    # Relationships
    blog_post = relationship(
        "BlogPost",
        backref=backref("view_events", passive_deletes=True),
        passive_deletes=True,
    )

    __table_args__ = (Index("ix_blog_post_view_events_post_created", blog_post_id, created_at.desc()),)


class BlogPostStatsDaily(Base):
    """Daily aggregated statistics for a blog post (permanent storage)."""

    __tablename__ = "blog_post_stats_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    blog_post_id = Column(
        Integer, ForeignKey("blog_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date = Column(Date, nullable=False, index=True)

    # Aggregated counts
    total_views = Column(Integer, nullable=False, default=0)
    unique_viewers = Column(Integer, nullable=False, default=0)

    # Breakdown by dimension (stored as JSONB for flexibility)
    views_by_country = Column(
        JSON, nullable=False, default=dict
    )  # {"US": 50, "BR": 30, ...}
    views_by_device = Column(
        JSON, nullable=False, default=dict
    )  # {"desktop": 40, "mobile": 35, ...}
    views_by_type = Column(
        JSON, nullable=False, default=dict
    )  # {"intentional": 60, "listing": 15, ...}

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    blog_post = relationship(
        "BlogPost",
        backref=backref("stats_daily", passive_deletes=True),
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("blog_post_id", "date", name="uq_blog_post_stats_daily_post_date"),
        Index("ix_blog_post_stats_daily_post_date", blog_post_id, date),
    )

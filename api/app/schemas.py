from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    RootModel,
    computed_field,
    model_validator,
)

from .settings import MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES

# ============================================================================
# BASE SCHEMAS
# ============================================================================


class Problem(BaseModel):
    """RFC 7807 Problem Details for HTTP APIs."""

    type: str = Field(default="about:blank")
    title: str
    status: int
    detail: str | None = None
    errors: dict[str, list[str]] | None = None


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Generic paginated response."""

    items: list[T]
    next_cursor: str | None = None


class Roles(RootModel[list[Literal["user", "moderator", "owner"]]]):
    """User roles list."""

    pass


# ============================================================================
# LICENSE SCHEMAS
# ============================================================================


class License(BaseModel):
    """Creative Commons license information."""

    id: int
    identifier: str
    title: str
    canonical_url: str
    badge_path: str

    model_config = ConfigDict(from_attributes=True)


class LicenseList(BaseModel):
    """List of licenses."""

    items: list[License]


# ============================================================================
# HEALTH & CONFIG
# ============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["ok"] = "ok"
    uptime_s: float | None = None


class Config(BaseModel):
    """Public system configuration."""

    max_comment_depth: int = 2
    max_comments_per_post: int = 1000
    max_emojis_per_user_per_post: int = 5
    max_hashtags_per_post: int = 64
    allowed_dimensions: list[tuple[int, int]] = [
        (8, 8),
        (8, 16),
        (16, 8),
        (8, 32),
        (32, 8),
        (16, 16),
        (16, 32),
        (32, 16),
        (32, 32),
        (32, 64),
        (64, 32),
        (64, 64),
        (64, 128),
        (128, 64),
    ]
    # Note: Sizes from 128x128 to 256x256 (inclusive) are also allowed but not listed here
    # All 90-degree rotations of the listed sizes are allowed (e.g., 8x16 and 16x8 are both valid)
    # Artwork size limits are expressed in raw bytes (never KiB).
    max_art_file_bytes_default: int = MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES


# ============================================================================
# USER SCHEMAS
# ============================================================================


class BadgeGrant(BaseModel):
    """Badge granted to a user."""

    badge: str
    granted_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserPublic(BaseModel):
    """Public user profile."""

    id: int
    user_key: UUID  # UUID for legacy URLs (/users/{user_key})
    public_sqid: str | None = (
        None  # Sqids-encoded public ID for canonical URLs (/u/{public_sqid})
    )
    handle: str
    bio: str | None = None
    tagline: str | None = (
        None  # Short one-liner displayed under username (max 48 chars)
    )
    website: str | None = None
    # Avatar URL may be an external absolute URL (GitHub) or a site-relative vault URL
    # (e.g. /api/vault/avatar/...). We store raw strings to support relative URLs.
    avatar_url: str | None = None
    badges: list[BadgeGrant] = []
    reputation: int
    hidden_by_user: bool
    hidden_by_mod: bool
    non_conformant: bool
    deactivated: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserFull(UserPublic):
    """Full user profile (for authenticated user or admin)."""

    email: str | None = None
    email_verified: bool = False
    welcome_completed: bool = (
        False  # True if user has completed onboarding welcome flow
    )
    banned_until: datetime | None = None
    roles: list[Literal["user", "moderator", "owner"]] = Field(default_factory=list)
    auto_public_approval: bool = (
        False  # Privilege to auto-approve public visibility for uploads
    )
    approved_hashtags: list[str] = Field(default_factory=list)


class UserCreate(BaseModel):
    """Create user request."""

    handle: str = Field(..., min_length=1, max_length=32)
    bio: str | None = Field(None, max_length=1000)
    website: str | None = Field(None, max_length=500)


class UserUpdate(BaseModel):
    """Update user request."""

    handle: str | None = Field(None, min_length=1, max_length=32)
    bio: str | None = Field(None, max_length=1000)
    tagline: str | None = Field(None, max_length=48)  # Short one-liner
    website: str | None = Field(None, max_length=500)
    avatar_url: str | None = None
    hidden_by_user: bool | None = None
    approved_hashtags: list[str] | None = None


class ConformanceStatus(BaseModel):
    """GitHub Pages conformance check status."""

    conformance: Literal[
        "ok", "missing_manifest", "invalid_manifest", "hotlinks_broken"
    ]
    last_checked_at: datetime | None = None
    next_check_at: datetime | None = None


class ReputationHistoryItem(BaseModel):
    """Single reputation change."""

    delta: int
    reason: str | None
    at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReputationView(BaseModel):
    """User reputation with history."""

    total: int
    history: list[ReputationHistoryItem]


# ============================================================================
# POST SCHEMAS
# ============================================================================


class Post(BaseModel):
    """Post with art metadata."""

    id: int  # Auto-increment integer primary key
    storage_key: UUID  # UUID used for vault lookup
    public_sqid: str  # Sqids-encoded public ID (max 16 chars)
    kind: Literal["artwork"]
    owner_id: int
    title: str
    description: str | None = None
    hashtags: list[str] = []
    art_url: str  # Can be relative URL for vault-hosted images or full URL for external
    width: int  # Canvas width in pixels
    height: int  # Canvas height in pixels
    file_bytes: int  # Exact file size in bytes
    frame_count: int = 1  # Number of animation frames
    min_frame_duration_ms: int | None = (
        None  # Minimum non-zero frame duration (ms), NULL for static
    )
    max_frame_duration_ms: int | None = (
        None  # Maximum frame duration (ms), NULL for static
    )
    unique_colors: int | None = None  # Max unique colors in any single frame
    transparency_meta: bool = False  # File metadata claims transparency capability
    alpha_meta: bool = False  # File metadata claims alpha channel
    transparency_actual: bool = False  # True if any pixel anywhere has alpha != 255
    alpha_actual: bool = False  # True if any pixel anywhere has alpha not in {0, 255}
    # Required by player protocol (also useful for web clients)
    metadata_modified_at: datetime
    artwork_modified_at: datetime
    dwell_time_ms: int = 30000
    visible: bool
    hidden_by_user: bool
    hidden_by_mod: bool
    non_conformant: bool
    public_visibility: bool = (
        False  # Controls visibility in Recent Artworks, search, etc.
    )
    deleted_by_user: bool = False  # User requested deletion
    deleted_by_user_date: datetime | None = (
        None  # When user deleted (for 7-day cleanup)
    )
    promoted: bool
    promoted_category: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    owner: UserPublic | None = None
    reaction_count: int = 0
    comment_count: int = 0
    user_has_liked: bool = False  # Whether the current user has liked (👍) this post
    formats_available: list[str] = []  # Available formats after SSAFPP processing
    file_format: str | None = None  # Original file format: png, gif, webp, bmp
    license_id: int | None = None  # FK to licenses table
    license: License | None = None  # Creative Commons license info

    model_config = ConfigDict(from_attributes=True)


class PostCreate(BaseModel):
    """Create post request."""

    kind: Literal["artwork"] = "artwork"
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    hashtags: list[str] = Field(default_factory=list, max_length=64)
    art_url: str  # Can be relative URL for vault-hosted images or full URL for external
    width: int = Field(..., gt=0, le=256)
    height: int = Field(..., gt=0, le=256)
    file_bytes: int = Field(..., gt=0, le=MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES)
    hash: str = Field(..., min_length=64, max_length=64)


class PostUpdate(BaseModel):
    """Update post request."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    hashtags: list[str] | None = Field(None, max_length=64)
    hidden_by_user: bool | None = None
    hidden_by_mod: bool | None = None


class PostRead(Post):
    """Alias for consistency."""

    pass


class ArtworkUploadResponse(BaseModel):
    """Response for artwork upload endpoint."""

    post: Post
    message: str = "Artwork uploaded successfully"


class PublicVisibilityResponse(BaseModel):
    """Response for public visibility toggle."""

    post_id: int  # Changed from UUID to int
    public_visibility: bool


class AutoApprovalResponse(BaseModel):
    """Response for auto-approval privilege toggle."""

    user_id: int
    auto_public_approval: bool


# ============================================================================
# PLAYLIST SCHEMAS
# ============================================================================


class Playlist(BaseModel):
    """Playlist of posts."""

    id: UUID
    owner_id: int
    title: str
    description: str | None = None
    post_ids: list[int] = []  # Changed from UUID to int
    visible: bool
    hidden_by_user: bool
    hidden_by_mod: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PlaylistCreate(BaseModel):
    """Create playlist request."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    post_ids: list[int] = Field(
        default_factory=list, max_length=100
    )  # Changed from UUID to int


class PlaylistUpdate(BaseModel):
    """Update playlist request."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    post_ids: list[int] | None = Field(None, max_length=100)  # Changed from UUID to int
    hidden_by_user: bool | None = None
    hidden_by_mod: bool | None = None


# ============================================================================
# COMMENT SCHEMAS
# ============================================================================


class Comment(BaseModel):
    """Comment on a post."""

    id: UUID
    post_id: int  # Changed from UUID to int (FK to posts.id)
    author_id: int | None = None  # None for anonymous comments (FK to users.id)
    author_ip: str | None = None  # For anonymous users (visible to moderators)
    parent_id: UUID | None = None
    depth: int = Field(..., ge=0, le=2)
    body: str
    hidden_by_mod: bool
    deleted_by_owner: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    _author_handle_cache: str | None = None
    _author_display_name_cache: str | None = None

    @model_validator(mode="wrap")
    @classmethod
    def extract_author_info(cls, data, handler):
        """Extract author info from the ORM model during validation."""
        # Call the default validation
        instance = handler(data)

        # If data is an ORM model with author relationship loaded, extract info
        if hasattr(data, "author") and data.author:
            instance._author_handle_cache = data.author.handle
            instance._author_display_name_cache = (
                data.author.handle
            )  # Use handle as display name

        return instance

    @computed_field
    @property
    def author_handle(self) -> str:
        """
        Handle for the comment author.

        Returns guest name for anonymous users, or the cached handle
        from the author relationship for authenticated users.
        """
        if self.author_id is None and self.author_ip:
            # Generate guest name from IP
            import hashlib

            hash_digest = hashlib.sha256(self.author_ip.encode()).hexdigest()
            return f"Guest_{hash_digest[:6]}"

        # Return cached handle if available
        if self._author_handle_cache:
            return self._author_handle_cache

        return "unknown"  # Fallback if user not found or not loaded

    @computed_field
    @property
    def author_display_name(self) -> str:
        """
        Display name for the comment author.

        Returns guest name for anonymous users, or the cached display name
        from the author relationship for authenticated users.
        """
        if self.author_id is None and self.author_ip:
            # Generate guest name from IP
            import hashlib

            hash_digest = hashlib.sha256(self.author_ip.encode()).hexdigest()
            return f"Guest_{hash_digest[:6]}"

        # Return cached display name if available
        if self._author_display_name_cache:
            return self._author_display_name_cache

        # Fall back to handle
        if self._author_handle_cache:
            return self._author_handle_cache

        return "Unknown"  # Fallback if user not found or not loaded

    @computed_field
    @property
    def author_display_name(self) -> str:
        """
        Display name for the comment author (used by widget).

        Currently returns the handle, but could return a display name
        if we add that field to users in the future.
        """
        return self.author_handle


class CommentCreate(BaseModel):
    """Create comment request."""

    body: str = Field(..., min_length=1, max_length=2000)
    parent_id: UUID | None = None


class CommentUpdate(BaseModel):
    """Update comment request."""

    body: str = Field(..., min_length=1, max_length=2000)


# ============================================================================
# BLOG POST SCHEMAS
# ============================================================================


class BlogPost(BaseModel):
    """Blog post with Markdown content."""

    id: int
    blog_post_key: UUID
    public_sqid: str | None = None
    owner_id: int
    title: str
    body: str  # Markdown content
    image_urls: list[str] = []
    visible: bool
    hidden_by_user: bool
    hidden_by_mod: bool
    public_visibility: bool = False
    created_at: datetime
    updated_at: datetime | None = None
    published_at: datetime | None = None
    owner: UserPublic | None = None
    # Stats added by annotate_blog_posts_with_counts (optional for backwards compat)
    reaction_count: int = 0
    comment_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class BlogPostCreate(BaseModel):
    """Create blog post request."""

    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=10000)
    image_urls: list[str] = Field(default_factory=list, max_length=10)


class BlogPostUpdate(BaseModel):
    """Update blog post request."""

    title: str | None = Field(None, min_length=1, max_length=200)
    body: str | None = Field(None, min_length=1, max_length=10000)
    image_urls: list[str] | None = Field(None, max_length=10)
    hidden_by_user: bool | None = None


class BlogPostRead(BlogPost):
    """Alias for consistency."""

    pass


class BlogPostFeedItem(BaseModel):
    """Blog post item for feed display."""

    id: int
    public_sqid: str | None = None
    title: str
    updated_at: datetime | None = None
    reaction_count: int = 0
    comment_count: int = 0
    body_preview: str  # Truncated body text


class BlogPostComment(BaseModel):
    """Comment on a blog post."""

    id: UUID
    blog_post_id: int
    author_id: int | None = None  # None for anonymous comments (FK to users.id)
    author_ip: str | None = None  # For anonymous users (visible to moderators)
    parent_id: UUID | None = None
    depth: int = Field(..., ge=0, le=3)
    body: str
    hidden_by_mod: bool
    deleted_by_owner: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    _author_handle_cache: str | None = None
    _author_display_name_cache: str | None = None

    @model_validator(mode="wrap")
    @classmethod
    def extract_author_info(cls, data, handler):
        """Extract author info from the ORM model during validation."""
        instance = handler(data)

        if hasattr(data, "author") and data.author:
            instance._author_handle_cache = data.author.handle
            instance._author_display_name_cache = data.author.handle

        return instance

    @computed_field
    @property
    def author_handle(self) -> str:
        """Handle for the comment author."""
        if self.author_id is None and self.author_ip:
            import hashlib

            hash_digest = hashlib.sha256(self.author_ip.encode()).hexdigest()
            return f"Guest_{hash_digest[:6]}"

        if self._author_handle_cache:
            return self._author_handle_cache

        return "unknown"

    @computed_field
    @property
    def author_display_name(self) -> str:
        """Display name for the comment author."""
        if self.author_id is None and self.author_ip:
            import hashlib

            hash_digest = hashlib.sha256(self.author_ip.encode()).hexdigest()
            return f"Guest_{hash_digest[:6]}"

        if self._author_display_name_cache:
            return self._author_display_name_cache

        if self._author_handle_cache:
            return self._author_handle_cache

        return "Unknown"


class BlogPostCommentCreate(BaseModel):
    """Create blog post comment request."""

    body: str = Field(..., min_length=1, max_length=2000)
    parent_id: UUID | None = None


class BlogPostCommentUpdate(BaseModel):
    """Update blog post comment request."""

    body: str = Field(..., min_length=1, max_length=2000)


class BlogPostReactionTotals(BaseModel):
    """Reaction totals for a blog post."""

    totals: dict[str, int]  # combined emoji totals (authenticated + anonymous)
    authenticated_totals: dict[str, int]
    anonymous_totals: dict[str, int]
    mine: list[str]  # emoji list for current user


class BlogPostImageUploadResponse(BaseModel):
    """Response for blog post image upload."""

    image_url: str
    image_id: UUID


# ============================================================================
# REACTION SCHEMAS
# ============================================================================


class ReactionTotals(BaseModel):
    """Reaction totals for a post."""

    totals: dict[str, int]  # combined emoji totals (authenticated + anonymous)
    authenticated_totals: dict[str, int]
    anonymous_totals: dict[str, int]
    mine: list[str]  # emoji list for current user


class WidgetData(BaseModel):
    """Combined widget data (reactions + comments) for efficient loading."""

    reactions: ReactionTotals
    comments: list["Comment"]
    views_count: int = 0


# ============================================================================
# REPORT SCHEMAS
# ============================================================================


class Report(BaseModel):
    """Content moderation report."""

    id: UUID
    target_type: Literal["user", "post", "comment"]
    target_id: str  # String to support both UUID and integer IDs
    reason_code: Literal["spam", "abuse", "copyright", "other"]
    notes: str | None = None
    status: Literal["open", "triaged", "resolved"]
    action_taken: Literal["hide", "delete", "ban", "none"] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportCreate(BaseModel):
    """Create report request."""

    target_type: Literal["user", "post", "comment"]
    target_id: str  # String to support both UUID and integer IDs
    reason_code: Literal["spam", "abuse", "copyright", "other"]
    notes: str | None = Field(None, max_length=2000)


class ReportUpdate(BaseModel):
    """Update report request (admin only)."""

    status: Literal["triaged", "resolved"] | None = None
    action_taken: Literal["hide", "delete", "ban", "none"] | None = None
    notes: str | None = Field(None, max_length=2000)


# ============================================================================
# BADGE SCHEMAS
# ============================================================================


class BadgeDefinition(BaseModel):
    """Badge definition with full metadata."""

    badge: str
    label: str
    description: str | None = None
    icon_url_64: str  # 64x64 icon URL for profile display
    icon_url_16: str | None = None  # 16x16 icon URL for tag badges
    is_tag_badge: bool = False  # If true, displayed under username

    model_config = ConfigDict(from_attributes=True)


class TagBadgeInfo(BaseModel):
    """Tag badge information for display under username."""

    badge: str
    label: str
    icon_url_16: str  # 16x16 icon URL


class BadgeGrantRequest(BaseModel):
    """Grant badge request."""

    badge: str
    reason_code: str | None = Field(None, max_length=50)
    note: str | None = Field(None, max_length=1000)


# ============================================================================
# REPUTATION SCHEMAS
# ============================================================================


class ReputationAdjust(BaseModel):
    """Adjust reputation request."""

    delta: int
    reason: str | None = Field(None, max_length=200)
    reason_code: str | None = Field(None, max_length=50)
    note: str | None = Field(None, max_length=1000)


class ReputationAdjustResponse(BaseModel):
    """Reputation adjustment response."""

    new_total: int


# ============================================================================
# PLAYER SCHEMAS
# ============================================================================


class PlayerPublic(BaseModel):
    """Public player information."""

    id: UUID
    player_key: UUID
    name: str | None
    device_model: str | None
    firmware_version: str | None
    registration_status: str
    connection_status: str
    last_seen_at: datetime | None
    current_post_id: int | None
    cert_expires_at: datetime | None
    registered_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlayerProvisionRequest(BaseModel):
    """Player provisioning request (device calls this)."""

    device_model: str | None = None
    firmware_version: str | None = None


class PlayerProvisionResponse(BaseModel):
    """Player provisioning response."""

    player_key: UUID
    registration_code: str
    registration_code_expires_at: datetime
    mqtt_broker: dict[str, Any]


class PlayerRegisterRequest(BaseModel):
    """Player registration request."""

    registration_code: str = Field(..., min_length=6, max_length=6)
    name: str = Field(..., min_length=1, max_length=100)


class PlayerUpdateRequest(BaseModel):
    """Update player request."""

    name: str | None = Field(None, min_length=1, max_length=100)


class PlayerCommandRequest(BaseModel):
    """Player command request."""

    command_type: Literal[
        "swap_next", "swap_back", "show_artwork", "play_channel", "play_playset"
    ]
    post_id: int | None = None  # Required for show_artwork
    # Channel identification (for play_channel)
    channel_name: str | None = None  # 'promoted', 'all', or 'by_user'
    hashtag: str | None = None  # hashtag without #
    user_sqid: str | None = None  # user's sqid for profile channels
    user_handle: str | None = None  # user's handle (for by_user channel)
    # Playset identification (for play_playset)
    playset_name: str | None = None  # e.g., 'followed_artists'


class PlayerCommandResponse(BaseModel):
    """Player command response."""

    command_id: UUID
    status: Literal["sent"]


class PlayerCommandAllResponse(BaseModel):
    """Response for sending command to all players."""

    sent_count: int
    commands: list[PlayerCommandResponse]


class PlayerRenewCertResponse(BaseModel):
    """Certificate renewal response."""

    cert_expires_at: datetime
    message: str = "Certificate renewed successfully"


class OnlinePlayerInfo(BaseModel):
    """Online player information for moderator dashboard."""

    id: UUID
    name: str | None = None
    device_model: str | None = None
    firmware_version: str | None = None
    last_seen_at: datetime | None = None
    owner_handle: str | None = None


class OnlinePlayersResponse(BaseModel):
    """Response with list of currently online players."""

    online_players: list[OnlinePlayerInfo]
    total_online: int


class TLSCertBundle(BaseModel):
    """TLS certificate bundle for player."""

    ca_pem: str
    cert_pem: str
    key_pem: str
    broker: dict[str, Any]  # {host, port}


# ============================================================================
# AUTH SCHEMAS
# ============================================================================


class OAuthTokens(BaseModel):
    """OAuth token response.

    Note: refresh_token is now stored in HttpOnly cookie and not returned in response body.
    This field is optional for backward compatibility during migration.
    """

    token: str
    refresh_token: str | None = (
        None  # Now stored in HttpOnly cookie, not returned in body
    )
    user_id: int
    user_key: UUID  # UUID for legacy URL building
    public_sqid: str | None = None  # Sqids for canonical URLs
    user_handle: str | None = None  # Handle for display
    expires_at: datetime
    needs_welcome: bool = False  # Whether user needs to go through welcome flow


class GithubExchangeRequest(BaseModel):
    """GitHub OAuth code exchange request."""

    code: str
    redirect_uri: str
    installation_id: int | None = None
    setup_action: str | None = None


class RefreshTokenRequest(BaseModel):
    """Token refresh request.

    DEPRECATED: Refresh tokens are now read from HttpOnly cookies, not request body.
    This schema is kept for backward compatibility but is no longer used by the refresh endpoint.
    """

    refresh_token: str


class ProfileConnectRequest(BaseModel):
    """Profile connection request."""

    repo_name: str


class GitHubAppBindRequest(BaseModel):
    """GitHub App binding request."""

    installation_id: int


class MeResponse(BaseModel):
    """Current user response."""

    user: UserFull
    roles: list[Literal["user", "moderator", "owner"]]


class RegisterRequest(BaseModel):
    """User registration request - only email required."""

    email: str = Field(..., max_length=255)


class RegisterResponse(BaseModel):
    """User registration response - email verification required."""

    message: str = "Please check your email to verify your account"
    user_id: int
    email: str
    handle: str  # User's generated handle


class LoginRequest(BaseModel):
    """User login request - email and password."""

    email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=100)


class AuthIdentityResponse(BaseModel):
    """Authentication identity response."""

    id: UUID
    provider: str
    provider_user_id: str
    email: str | None = None
    provider_metadata: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthIdentitiesList(BaseModel):
    """List of authentication identities."""

    identities: list[AuthIdentityResponse]


class LinkProviderRequest(BaseModel):
    """Link OAuth provider request (used internally, not exposed as endpoint)."""

    provider: str
    provider_user_id: str
    email: str | None = None
    provider_metadata: dict[str, Any] | None = None


class VerifyEmailRequest(BaseModel):
    """Email verification request."""

    token: str = Field(..., min_length=1)


class VerifyEmailResponse(BaseModel):
    """Email verification response."""

    message: str = "Email verified successfully"
    verified: bool = True
    handle: str  # User's current handle
    can_change_password: bool = True  # Invite user to optionally change password
    can_change_handle: bool = True  # Invite user to optionally change handle
    needs_welcome: bool = True  # Whether user needs to go through welcome flow
    public_sqid: str | None = None  # User's public Sqids ID for redirect


class ResendVerificationRequest(BaseModel):
    """Resend verification email request."""

    email: str | None = Field(None, max_length=255)  # Optional: verify different email


class ResendVerificationResponse(BaseModel):
    """Resend verification email response."""

    message: str = "Verification email sent"
    email: str


class ChangePasswordRequest(BaseModel):
    """Change password request."""

    current_password: str = Field(..., min_length=1, max_length=100)
    new_password: str = Field(..., min_length=8, max_length=100)


class ChangePasswordResponse(BaseModel):
    """Change password response."""

    message: str = "Password changed successfully"


class ChangeHandleRequest(BaseModel):
    """Change handle request."""

    new_handle: str = Field(..., min_length=1, max_length=32)


class ChangeHandleResponse(BaseModel):
    """Change handle response."""

    message: str = "Handle changed successfully"
    handle: str


class CheckHandleAvailabilityRequest(BaseModel):
    """Check handle availability request."""

    handle: str = Field(..., min_length=1, max_length=32)


class CheckHandleAvailabilityResponse(BaseModel):
    """Check handle availability response."""

    handle: str
    available: bool
    message: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request - initiates password reset."""

    email: str = Field(..., max_length=255)


class ForgotPasswordResponse(BaseModel):
    """Forgot password response."""

    message: str = (
        "If an account exists with this email, a password reset link has been sent."
    )


class ResetPasswordRequest(BaseModel):
    """Reset password request - completes password reset with token."""

    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)


class ResetPasswordResponse(BaseModel):
    """Reset password response."""

    message: str = (
        "Password reset successfully. You can now log in with your new password."
    )


# ============================================================================
# ADMIN SCHEMAS
# ============================================================================


class BanUserRequest(BaseModel):
    """Ban user request."""

    reason: str | None = Field(None, max_length=500)
    duration_days: int | None = Field(None, gt=0, le=365)
    reason_code: str | None = Field(None, max_length=50)
    note: str | None = Field(None, max_length=1000)


class BanResponse(BaseModel):
    """Ban response."""

    status: Literal["banned"]
    until: datetime | None


class PromotePostRequest(BaseModel):
    """Promote post request."""

    category: Literal["frontpage", "editor-pick", "weekly-pack", "daily's-best"]
    reason_code: str | None = Field(None, max_length=50)
    note: str | None = Field(None, max_length=1000)


class PromotePostResponse(BaseModel):
    """Promote post response."""

    promoted: bool
    category: str


class CategoryFollow(BaseModel):
    """Category follow relationship."""

    user_id: int
    category: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CategoryFollowCreate(BaseModel):
    """Follow a category request."""

    category: str = Field(..., min_length=1, max_length=50)


class CategoryFollowList(BaseModel):
    """List of followed categories."""

    items: list[CategoryFollow]


class AdminNoteCreate(BaseModel):
    """Create admin note request."""

    note: str = Field(..., min_length=1, max_length=5000)


class AdminNoteItem(BaseModel):
    """Admin note item."""

    id: UUID
    note: str
    created_by: int  # FK to users.id
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminNoteList(BaseModel):
    """Admin notes list."""

    items: list[AdminNoteItem]


class HideRequest(BaseModel):
    """Hide content request."""

    by: Literal["user", "mod"] | None = "user"
    reason: str | None = Field(None, max_length=500)
    reason_code: str | None = Field(None, max_length=50)
    note: str | None = Field(None, max_length=1000)


class PromoteModeratorResponse(BaseModel):
    """Promote moderator response."""

    user_id: int
    role: Literal["moderator"]


class AuditLogEntry(BaseModel):
    """Audit log entry."""

    id: UUID
    actor_id: int  # FK to users.id
    action: str
    target_type: str | None
    target_id: str | None  # String to support both UUID and integer IDs
    reason_code: str | None = None
    note: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# SEARCH & FEED SCHEMAS
# ============================================================================


class HashtagItem(BaseModel):
    """Hashtag with post count."""

    tag: str
    count: int


class HashtagList(BaseModel):
    """Hashtag list."""

    items: list[HashtagItem]
    next_cursor: str | None = None


class HashtagStats(BaseModel):
    """Hashtag with detailed statistics."""

    tag: str
    reaction_count: int
    comment_count: int
    artwork_count: int


class HashtagStatsList(BaseModel):
    """Hashtag statistics list."""

    items: list[HashtagStats]
    next_cursor: str | None = None


class TopHashtagsResponse(BaseModel):
    """Top hashtags for header trending display."""

    hashtags: list[str]
    cached_until: datetime


class SearchResultUser(BaseModel):
    """Search result: user."""

    type: Literal["users"] = "users"
    user: UserPublic


class SearchResultPost(BaseModel):
    """Search result: post."""

    type: Literal["posts"] = "posts"
    post: Post


class SearchResultPlaylist(BaseModel):
    """Search result: playlist."""

    type: Literal["playlists"] = "playlists"
    playlist: Playlist


class SearchResults(BaseModel):
    """Mixed search results."""

    items: list[SearchResultUser | SearchResultPost | SearchResultPlaylist]
    next_cursor: str | None = None


# ============================================================================
# RELAY & VALIDATION SCHEMAS
# ============================================================================


class RelayJob(BaseModel):
    """Relay job status."""

    status: Literal["queued", "running", "committed", "failed"]
    repo: str | None = None
    commit: str | None = None
    error: str | None = None


class RelayUploadResponse(BaseModel):
    """Relay upload response."""

    status: Literal["committed", "queued", "failed"]
    repo: str | None = None
    commit: str | None = None
    job_id: UUID | None = None
    error: str | None = None


class RepositoryInfo(BaseModel):
    """GitHub repository information."""

    name: str
    full_name: str
    description: str | None = None
    private: bool
    html_url: str


class RepositoryListResponse(BaseModel):
    """Repository list response."""

    repositories: list[RepositoryInfo]


class CreateRepositoryRequest(BaseModel):
    """Create repository request."""

    name: str


class CreateRepositoryResponse(BaseModel):
    """Create repository response."""

    name: str
    full_name: str
    html_url: str


class ManifestValidateRequest(BaseModel):
    """Manifest validation request."""

    url: HttpUrl


class ManifestValidationResult(BaseModel):
    """Manifest validation result."""

    valid: bool
    issues: list[str] = []
    summary: dict[str, Any] | None = None  # {art_count, canvases, avg_kb}


class ConformanceRecheckResponse(BaseModel):
    """Conformance recheck response."""

    job_id: UUID


# ============================================================================
# MQTT SCHEMAS
# ============================================================================


class MQTTBootstrap(BaseModel):
    """MQTT broker bootstrap info."""

    host: str
    port: int
    tls: bool
    topics: dict[str, str]  # {new_posts: "posts/new/#"}


class MQTTPublishResponse(BaseModel):
    """MQTT publish response."""

    status: Literal["sent"]
    topic: str


# ============================================================================
# RATE LIMIT SCHEMAS
# ============================================================================


class RateLimitBucket(BaseModel):
    """Rate limit bucket status."""

    remaining: int
    reset_in_s: int


class RateLimitStatus(BaseModel):
    """Rate limit status."""

    buckets: dict[str, RateLimitBucket]


# ============================================================================
# STATISTICS SCHEMAS
# ============================================================================


class DailyViewCount(BaseModel):
    """Daily view count for trends."""

    date: str  # ISO format date (YYYY-MM-DD)
    views: int
    unique_viewers: int


class PostStatsResponse(BaseModel):
    """Statistics for a single post.

    Includes both "all" (including unauthenticated) and "authenticated-only" statistics.
    Frontend can toggle between the two without additional API calls.
    """

    post_id: int  # Changed from UUID to int
    # "All" statistics (including unauthenticated)
    total_views: int
    unique_viewers: int
    views_by_country: dict[str, int]  # Top 10 countries: {"US": 50, "BR": 30, ...}
    views_by_device: dict[
        str, int
    ]  # {"desktop": 40, "mobile": 35, "tablet": 10, "player": 5}
    views_by_type: dict[str, int]  # {"intentional": 60, "listing": 30, "search": 10}
    daily_views: list[DailyViewCount]  # Last 30 days
    total_reactions: int
    reactions_by_emoji: dict[str, int]  # {"❤️": 10, "🔥": 5, ...}
    total_comments: int
    # Authenticated-only statistics
    total_views_authenticated: int
    unique_viewers_authenticated: int
    views_by_country_authenticated: dict[str, int]  # Top 10 countries
    views_by_device_authenticated: dict[str, int]  # {"desktop": 40, "mobile": 35, ...}
    views_by_type_authenticated: dict[
        str, int
    ]  # {"intentional": 60, "listing": 30, ...}
    daily_views_authenticated: list[DailyViewCount]  # Last 30 days
    total_reactions_authenticated: int
    reactions_by_emoji_authenticated: dict[str, int]  # {"❤️": 10, "🔥": 5, ...}
    total_comments_authenticated: int
    # Timestamps
    first_view_at: datetime | None
    last_view_at: datetime | None
    computed_at: datetime


class BlogPostStatsResponse(BaseModel):
    """Statistics for a single blog post.

    Includes both "all" (including unauthenticated) and "authenticated-only" statistics.
    Frontend can toggle between the two without additional API calls.
    """

    blog_post_id: int
    # "All" statistics (including unauthenticated)
    total_views: int
    unique_viewers: int
    views_by_country: dict[str, int]  # Top 10 countries: {"US": 50, "BR": 30, ...}
    views_by_device: dict[
        str, int
    ]  # {"desktop": 40, "mobile": 35, "tablet": 10, "player": 5}
    views_by_type: dict[str, int]  # {"intentional": 60, "listing": 30, "search": 10}
    daily_views: list[DailyViewCount]  # Last 30 days
    total_reactions: int
    reactions_by_emoji: dict[str, int]  # {"❤️": 10, "🔥": 5, ...}
    total_comments: int
    # Authenticated-only statistics
    total_views_authenticated: int
    unique_viewers_authenticated: int
    views_by_country_authenticated: dict[str, int]  # Top 10 countries
    views_by_device_authenticated: dict[str, int]  # {"desktop": 40, "mobile": 35, ...}
    views_by_type_authenticated: dict[
        str, int
    ]  # {"intentional": 60, "listing": 30, ...}
    daily_views_authenticated: list[DailyViewCount]  # Last 30 days
    total_reactions_authenticated: int
    reactions_by_emoji_authenticated: dict[str, int]  # {"❤️": 10, "🔥": 5, ...}
    total_comments_authenticated: int
    # Timestamps
    first_view_at: datetime | None
    last_view_at: datetime | None
    computed_at: datetime


class DailyCount(BaseModel):
    """Daily count for trends."""

    date: str  # ISO format date (YYYY-MM-DD)
    count: int


class HourlyCount(BaseModel):
    """Hourly count for granular trends."""

    hour: str  # ISO format datetime of hour start
    count: int


class SitewideStatsResponse(BaseModel):
    """Comprehensive sitewide statistics (moderator only).

    Includes both "all" (including unauthenticated) and "authenticated-only" statistics.
    """

    # Summary metrics (30 days) - all
    total_page_views_30d: int
    unique_visitors_30d: int
    new_signups_30d: int
    new_posts_30d: int
    total_api_calls_30d: int
    total_errors_30d: int

    # Summary metrics (30 days) - authenticated only
    total_page_views_30d_authenticated: int
    unique_visitors_30d_authenticated: int

    # Trends (30 days) - all
    daily_views: list[DailyCount]
    daily_signups: list[DailyCount]
    daily_posts: list[DailyCount]

    # Trends (30 days) - authenticated only
    daily_views_authenticated: list[DailyCount]

    # Granular data (last 24h from events) - all
    hourly_views: list[HourlyCount]

    # Granular data (last 24h from events) - authenticated only
    hourly_views_authenticated: list[HourlyCount]

    # Breakdowns - all
    views_by_page: dict[str, int]  # Top 20 pages: {"/recent": 500, "/posts": 300, ...}
    views_by_country: dict[str, int]  # Top 10 countries: {"US": 200, "BR": 150, ...}
    views_by_device: dict[str, int]  # {"desktop": 400, "mobile": 350, ...}
    top_referrers: dict[str, int]  # Top 10 referrers: {"google.com": 100, ...}

    # Breakdowns - authenticated only
    views_by_page_authenticated: dict[str, int]  # Top 20 pages
    views_by_country_authenticated: dict[str, int]  # Top 10 countries
    views_by_device_authenticated: dict[str, int]
    top_referrers_authenticated: dict[str, int]  # Top 10 referrers

    # Error tracking
    errors_by_type: dict[str, int]  # {"404": 50, "500": 5, ...}

    # Player Activity (artwork views from player devices)
    total_player_artwork_views_30d: int = 0
    active_players_30d: int = 0
    daily_player_views: list[DailyCount] = []
    views_by_player: dict[str, int] = {}  # player_name -> view count

    computed_at: datetime


# ============================================================================
# ARTIST DASHBOARD SCHEMAS
# ============================================================================


class ArtistStatsResponse(BaseModel):
    """Aggregated statistics for an artist across all their posts."""

    user_id: int
    user_key: str
    total_posts: int
    # Aggregated view statistics (all)
    total_views: int
    unique_viewers: int
    views_by_country: dict[str, int]  # Top 10 countries
    views_by_device: dict[str, int]  # desktop, mobile, tablet, player
    # Aggregated reactions and comments
    total_reactions: int
    reactions_by_emoji: dict[str, int]
    total_comments: int
    # Authenticated-only statistics
    total_views_authenticated: int
    unique_viewers_authenticated: int
    views_by_country_authenticated: dict[str, int]
    views_by_device_authenticated: dict[str, int]
    total_reactions_authenticated: int
    reactions_by_emoji_authenticated: dict[str, int]
    total_comments_authenticated: int
    # Timestamps
    first_post_at: datetime | None
    latest_post_at: datetime | None
    computed_at: datetime


class PostStatsListItem(BaseModel):
    """Simplified post statistics for list view in artist dashboard."""

    post_id: int
    public_sqid: str
    title: str
    created_at: datetime
    # View statistics (all)
    total_views: int
    unique_viewers: int
    # Reactions and comments
    total_reactions: int
    total_comments: int
    # Authenticated-only statistics
    total_views_authenticated: int
    unique_viewers_authenticated: int
    total_reactions_authenticated: int
    total_comments_authenticated: int


class ArtistDashboardResponse(BaseModel):
    """Complete artist dashboard with aggregated stats and post list."""

    artist_stats: ArtistStatsResponse
    posts: list[PostStatsListItem]
    total_posts: int
    page: int
    page_size: int
    has_more: bool


# ============================================================================
# LEGACY SCHEMAS (for backwards compatibility)
# ============================================================================


class HashUrlRequest(BaseModel):
    """Hash URL task request."""

    url: HttpUrl


class HashUrlResponse(BaseModel):
    """Hash URL task response."""

    task_id: str


# ============================================================================
# SOCIAL NOTIFICATIONS
# ============================================================================


class SocialNotificationBase(BaseModel):
    """Base schema for social notifications."""

    notification_type: (
        str  # 'reaction', 'comment', 'moderator_granted', 'moderator_revoked'
    )
    post_id: int | None = None  # Nullable for system notifications
    actor_handle: str | None = None
    actor_avatar_url: str | None = None  # For system notifications
    emoji: str | None = None
    comment_preview: str | None = None
    content_title: str | None = None
    content_sqid: str | None = None
    content_art_url: str | None = None


class SocialNotification(SocialNotificationBase):
    """Full social notification schema."""

    id: UUID
    user_id: int
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SocialNotificationCreate(BaseModel):
    """Schema for creating a social notification (internal use)."""

    user_id: int
    notification_type: str
    post_id: int | None = None  # Nullable for system notifications
    actor_id: int | None = None
    actor_handle: str | None = None
    actor_avatar_url: str | None = None  # For system notifications
    emoji: str | None = None
    comment_id: UUID | None = None
    comment_preview: str | None = None
    content_title: str | None = None
    content_sqid: str | None = None
    content_art_url: str | None = None


class SocialNotificationUnreadCount(BaseModel):
    """Response for unread notification count."""

    unread_count: int


# ============================================================================
# POST MANAGEMENT DASHBOARD (PMD) SCHEMAS
# ============================================================================


class PMDPostItem(BaseModel):
    """Single post item for PMD table."""

    id: int
    public_sqid: str
    title: str
    description: str | None = None
    created_at: datetime
    width: int
    height: int
    frame_count: int
    file_format: str | None = None
    file_bytes: int | None = None
    art_url: str
    hidden_by_user: bool
    reaction_count: int
    comment_count: int
    view_count: int

    model_config = ConfigDict(from_attributes=True)


class PMDPostsResponse(BaseModel):
    """Response for PMD posts list."""

    items: list[PMDPostItem]
    next_cursor: str | None = None
    total_count: int


class BatchActionType(str, Enum):
    """Batch action types for PMD."""

    HIDE = "hide"
    UNHIDE = "unhide"
    DELETE = "delete"


class BatchActionRequest(BaseModel):
    """Request for batch post action."""

    action: BatchActionType
    post_ids: list[int] = Field(..., min_length=1, max_length=128)


class BatchActionResponse(BaseModel):
    """Response for batch post action."""

    success: bool
    affected_count: int
    message: str


class CreateBDRRequest(BaseModel):
    """Request to create a batch download request."""

    post_ids: list[int] = Field(..., min_length=1, max_length=128)
    include_comments: bool = False
    include_reactions: bool = False
    send_email: bool = False


class CreateBDRResponse(BaseModel):
    """Response for batch download request creation."""

    id: str
    status: str
    artwork_count: int
    created_at: datetime
    message: str


class BDRItem(BaseModel):
    """Batch download request item."""

    id: str
    status: str  # pending, processing, ready, failed, expired
    artwork_count: int
    created_at: datetime
    completed_at: datetime | None = None
    expires_at: datetime | None = None
    error_message: str | None = None
    download_url: str | None = None


class BDRListResponse(BaseModel):
    """Response for batch download request list."""

    items: list[BDRItem]


# ============================================================================
# USER PROFILE SCHEMAS
# ============================================================================


class UserProfileStats(BaseModel):
    """User profile statistics."""

    total_posts: int  # Total artwork posts
    total_reactions_received: int  # Total reactions on all posts
    total_views: int  # Total views across all posts
    follower_count: int  # Number of followers


class UserHighlightItem(BaseModel):
    """Single highlight item for user profile."""

    id: int
    post_id: int
    position: int
    post_public_sqid: str
    post_title: str
    post_art_url: str
    post_width: int
    post_height: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserHighlightsResponse(BaseModel):
    """Response for user highlights list."""

    items: list[UserHighlightItem]
    total: int


class AddHighlightRequest(BaseModel):
    """Request to add a post to highlights."""

    post_id: int


class AddHighlightResponse(BaseModel):
    """Response for add highlight request."""

    id: int
    position: int


class ReorderHighlightsRequest(BaseModel):
    """Request to reorder highlights."""

    post_ids: list[int] = Field(..., min_length=1, max_length=128)


class UserProfileEnhanced(BaseModel):
    """Enhanced user profile with stats and tag badges for profile page."""

    # Basic user info
    id: int
    user_key: UUID
    public_sqid: str | None = None
    handle: str
    bio: str | None = None
    tagline: str | None = None
    website: str | None = None
    avatar_url: str | None = None
    badges: list[BadgeGrant] = []
    reputation: int
    hidden_by_user: bool
    hidden_by_mod: bool
    non_conformant: bool
    deactivated: bool
    created_at: datetime

    # Enhanced fields
    tag_badges: list[TagBadgeInfo] = []  # Tag badges to display under username
    stats: UserProfileStats  # Aggregated statistics
    is_following: bool = False  # Whether current user follows this user
    is_own_profile: bool = False  # Whether this is the viewer's own profile
    highlights: list[UserHighlightItem] = []  # Featured posts

    model_config = ConfigDict(from_attributes=True)


class FollowResponse(BaseModel):
    """Response for follow/unfollow actions."""

    following: bool
    follower_count: int


class FollowersResponse(BaseModel):
    """Response for listing followers."""

    items: list[UserPublic]
    next_cursor: str | None = None
    total: int


class FollowingResponse(BaseModel):
    """Response for listing following."""

    items: list[UserPublic]
    next_cursor: str | None = None
    total: int


class ReactedPostItem(BaseModel):
    """A post the user reacted to."""

    id: int
    public_sqid: str
    title: str
    art_url: str
    width: int
    height: int
    owner_handle: str
    reacted_at: datetime
    emoji: str  # The emoji used in the reaction


class ReactedPostsResponse(BaseModel):
    """Response for user's reacted posts."""

    items: list[ReactedPostItem]
    next_cursor: str | None = None


# ============================================================================
# USER MANAGEMENT DASHBOARD (UMD) SCHEMAS
# ============================================================================


class UMDUserData(BaseModel):
    """Complete user data for UMD page."""

    id: int
    user_key: UUID
    public_sqid: str
    handle: str
    avatar_url: str | None = None
    reputation: int
    badges: list[BadgeGrant] = []
    auto_public_approval: bool
    hidden_by_mod: bool
    banned_until: datetime | None = None
    roles: list[str] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ViolationItem(BaseModel):
    """Single violation record."""

    id: int
    reason: str
    moderator_id: int
    moderator_handle: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ViolationsResponse(BaseModel):
    """Paginated violations list."""

    items: list[ViolationItem]
    total: int
    next_cursor: str | None = None


class IssueViolationRequest(BaseModel):
    """Issue violation request."""

    reason: str = Field(..., min_length=8, max_length=2000)


class UMDCommentItem(BaseModel):
    """Comment item for UMD."""

    id: UUID
    post_id: int
    post_public_sqid: str
    post_title: str
    post_art_url: str | None = None
    body: str
    hidden_by_mod: bool
    created_at: datetime


class UMDCommentsResponse(BaseModel):
    """Paginated comments for UMD."""

    items: list[UMDCommentItem]
    total: int
    next_cursor: str | None = None


class UMDReputationAdjustRequest(BaseModel):
    """Reputation adjustment for UMD."""

    delta: int = Field(..., ge=-1000, le=1000)
    reason: str = Field(..., min_length=8, max_length=500)


class EmailRevealResponse(BaseModel):
    """Email reveal response."""

    email: str
    message: str = "Email revealed and logged to audit"


class UMDBadgeListResponse(BaseModel):
    """List of available badges for UMD."""

    badges: list[BadgeDefinition]

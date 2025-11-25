from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, RootModel, computed_field, model_validator


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
    allowed_canvases: list[str] = ["16x16", "32x32", "64x64", "128x128", "256x256"]
    max_art_file_kb_default: int = 15 * 1024  # 15 MB


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

    id: UUID
    handle: str
    bio: str | None = None
    website: str | None = None
    avatar_url: HttpUrl | None = None
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
    banned_until: datetime | None = None
    roles: list[Literal["user", "moderator", "owner"]] = Field(default_factory=list)
    auto_public_approval: bool = False  # Privilege to auto-approve public visibility for uploads


class UserCreate(BaseModel):
    """Create user request."""

    handle: str = Field(..., min_length=2, max_length=50)
    bio: str | None = Field(None, max_length=1000)
    website: str | None = Field(None, max_length=500)


class UserUpdate(BaseModel):
    """Update user request."""

    handle: str | None = Field(None, min_length=2, max_length=50)
    bio: str | None = Field(None, max_length=1000)
    website: str | None = Field(None, max_length=500)
    avatar_url: HttpUrl | None = None
    hidden_by_user: bool | None = None


class ConformanceStatus(BaseModel):
    """GitHub Pages conformance check status."""

    conformance: Literal["ok", "missing_manifest", "invalid_manifest", "hotlinks_broken"]
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

    id: UUID
    kind: Literal["art"]
    owner_id: UUID
    title: str
    description: str | None = None
    hashtags: list[str] = []
    art_url: str  # Can be relative URL for vault-hosted images or full URL for external
    canvas: str
    file_kb: int
    visible: bool
    hidden_by_user: bool
    hidden_by_mod: bool
    non_conformant: bool
    public_visibility: bool = False  # Controls visibility in Recent Artworks, search, etc.
    promoted: bool
    promoted_category: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    owner: UserPublic | None = None

    model_config = ConfigDict(from_attributes=True)


class PostCreate(BaseModel):
    """Create post request."""

    kind: Literal["art"] = "art"
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    hashtags: list[str] = Field(default_factory=list, max_length=10)
    art_url: str  # Can be relative URL for vault-hosted images or full URL for external
    canvas: str = Field(..., pattern=r"^\d+x\d+$")
    file_kb: int = Field(..., gt=0, le=15 * 1024)  # 15 MB max


class PostUpdate(BaseModel):
    """Update post request."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    hashtags: list[str] | None = Field(None, max_length=10)
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

    post_id: UUID
    public_visibility: bool


class AutoApprovalResponse(BaseModel):
    """Response for auto-approval privilege toggle."""

    user_id: UUID
    auto_public_approval: bool


# ============================================================================
# PLAYLIST SCHEMAS
# ============================================================================


class Playlist(BaseModel):
    """Playlist of posts."""

    id: UUID
    owner_id: UUID
    title: str
    description: str | None = None
    post_ids: list[UUID] = []
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
    post_ids: list[UUID] = Field(default_factory=list, max_length=100)


class PlaylistUpdate(BaseModel):
    """Update playlist request."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    post_ids: list[UUID] | None = Field(None, max_length=100)
    hidden_by_user: bool | None = None
    hidden_by_mod: bool | None = None


# ============================================================================
# COMMENT SCHEMAS
# ============================================================================


class Comment(BaseModel):
    """Comment on a post."""

    id: UUID
    post_id: UUID
    author_id: UUID | None = None  # None for anonymous comments
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
    
    @model_validator(mode='wrap')
    @classmethod
    def extract_author_handle(cls, data, handler):
        """Extract author handle from the ORM model during validation."""
        # Call the default validation
        instance = handler(data)
        
        # If data is an ORM model with author relationship loaded, extract handle
        if hasattr(data, 'author') and data.author:
            instance._author_handle_cache = data.author.handle
        
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
            return f"guest-{hash_digest[:6]}"
        
        # Return cached handle if available
        if self._author_handle_cache:
            return self._author_handle_cache
        
        return "unknown"  # Fallback if user not found or not loaded


class CommentCreate(BaseModel):
    """Create comment request."""

    body: str = Field(..., min_length=1, max_length=2000)
    parent_id: UUID | None = None


class CommentUpdate(BaseModel):
    """Update comment request."""

    body: str = Field(..., min_length=1, max_length=2000)


# ============================================================================
# REACTION SCHEMAS
# ============================================================================


class ReactionTotals(BaseModel):
    """Reaction totals for a post."""

    totals: dict[str, int]  # combined emoji totals (authenticated + anonymous)
    authenticated_totals: dict[str, int]
    anonymous_totals: dict[str, int]
    mine: list[str]  # emoji list for current user


# ============================================================================
# REPORT SCHEMAS
# ============================================================================


class Report(BaseModel):
    """Content moderation report."""

    id: UUID
    target_type: Literal["user", "post", "comment"]
    target_id: UUID
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
    target_id: UUID
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
    """Badge definition."""

    badge: str
    label: str
    icon_url: HttpUrl | None = None
    description: str


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
# DEVICE SCHEMAS
# ============================================================================


class Device(BaseModel):
    """IoT device."""

    id: UUID
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeviceCreate(BaseModel):
    """Create device request."""

    name: str = Field(..., min_length=1, max_length=100)


class TLSCertBundle(BaseModel):
    """TLS certificate bundle for device."""

    ca_pem: str
    cert_pem: str
    key_pem: str
    broker: dict[str, Any]  # {host, port}


# ============================================================================
# AUTH SCHEMAS
# ============================================================================


class OAuthTokens(BaseModel):
    """OAuth token response."""

    token: str
    user_id: UUID
    expires_at: datetime


class GithubExchangeRequest(BaseModel):
    """GitHub OAuth code exchange request."""

    code: str
    redirect_uri: str
    installation_id: int | None = None
    setup_action: str | None = None


class RefreshTokenRequest(BaseModel):
    """Token refresh request."""

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
    user_id: UUID
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

    new_handle: str = Field(..., min_length=2, max_length=50)


class ChangeHandleResponse(BaseModel):
    """Change handle response."""

    message: str = "Handle changed successfully"
    handle: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request - initiates password reset."""

    email: str = Field(..., max_length=255)


class ForgotPasswordResponse(BaseModel):
    """Forgot password response."""

    message: str = "If an account exists with this email, a password reset link has been sent."


class ResetPasswordRequest(BaseModel):
    """Reset password request - completes password reset with token."""

    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)


class ResetPasswordResponse(BaseModel):
    """Reset password response."""

    message: str = "Password reset successfully. You can now log in with your new password."


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

    user_id: UUID
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
    created_by: UUID
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

    user_id: UUID
    role: Literal["moderator"]


class AuditLogEntry(BaseModel):
    """Audit log entry."""

    id: UUID
    actor_id: UUID
    action: str
    target_type: str | None
    target_id: UUID | None
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
# LEGACY SCHEMAS (for backwards compatibility)
# ============================================================================


class HashUrlRequest(BaseModel):
    """Hash URL task request."""

    url: HttpUrl


class HashUrlResponse(BaseModel):
    """Hash URL task response."""

    task_id: str

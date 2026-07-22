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


class MkpxUploadConfig(BaseModel):
    """Capability advertisement for .mkpx layers-file attachments.

    Absent from the config (or enabled=False) means the feature is off and
    clients must hide all mkpx UI (docs/mkpx-upload/API-CONTRACT.md §1).
    """

    enabled: bool
    max_file_bytes: int


class UploadConfig(BaseModel):
    """Server-authoritative artwork upload & conformance rules.

    Clients (web, native app, players) fetch this from `/config` and pre-validate
    artwork against it instead of hardcoding the rules. Sourced from `vault.py`.
    """

    formats: list[str]
    max_file_bytes: int
    free_form_min: int
    free_form_max: int
    # Allowed sizes below the free-form band; both 90-degree orientations are
    # listed explicitly, so a client can match against this list directly.
    small_whitelist: list[tuple[int, int]]
    rotations_allowed: bool = True
    mkpx: MkpxUploadConfig | None = None


class ReportReasonEntry(BaseModel):
    """One selectable report reason (docs/ugc-safety/API-CONTRACT.md §1)."""

    code: str
    label: str


class ModerationConfig(BaseModel):
    """UGC-safety capability advertisement (docs/ugc-safety/).

    Presence of this block in `/config` is the clients' feature-discovery
    signal (D17): key on dev = dev go, key on prod = production launch.
    """

    report_reasons: list[ReportReasonEntry]
    contact_email: str
    guidelines_url: str
    moderation_policy_url: str
    # Terms of Service page (D26); additive 2026-07-06. Clients MAY point
    # their rules-acceptance gate here instead of guidelines_url.
    terms_url: str
    max_blocks_per_user: int


class Config(BaseModel):
    """Public system configuration."""

    max_comment_depth: int = 2
    max_comments_per_post: int = 1000
    max_emojis_per_user_per_post: int = 5
    max_hashtags_per_post: int = 64
    # Presence of this key is the clients' mod-hashtags feature-discovery
    # signal (docs/mod-hashtags/API-CONTRACT.md §2).
    max_mod_hashtags_per_post: int = 16
    # NOTE: populated from vault.ALLOWED_SMALL_DIMENSIONS by the /config endpoint
    # (single source of truth). The default below mirrors it for constructibility.
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
    # Machine-readable upload/conformance rules; populated by the /config endpoint.
    upload: UploadConfig | None = None
    # UGC-safety block (docs/ugc-safety/); its presence is the clients'
    # feature gate + launch signal (D17). Populated by the /config endpoint.
    moderation: ModerationConfig | None = None


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


class UserVerifyResponse(BaseModel):
    """Minimal public user info returned by the SQID verification endpoint."""

    handle: str
    reputation: int
    artwork_count: int
    avatar_url: str | None = None


class HashtagVerifyResponse(BaseModel):
    """Public info returned by the hashtag channel verification endpoint."""

    tag: str
    artwork_count: int
    artwork_count_capped: bool
    latest_artwork_url: str | None = None
    latest_artwork_sqid: str | None = None
    latest_artwork_width: int | None = None
    latest_artwork_height: int | None = None


class ReactionsVerifyResponse(BaseModel):
    """Public info returned by the reactions channel verification endpoint."""

    handle: str
    artwork_count: int
    artwork_count_capped: bool
    latest_artwork_url: str | None = None
    latest_artwork_sqid: str | None = None
    latest_artwork_width: int | None = None
    latest_artwork_height: int | None = None


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
    # NOTE: avatar_url is intentionally NOT settable here. Avatars are mutated
    # only via POST/DELETE /user/{id}/avatar, which enforce format/size limits
    # and store the bytes in our vault. Allowing a free-form URL through PATCH
    # would let a user point their avatar at any external/off-site resource,
    # bypassing the upload pipeline.
    hidden_by_user: bool | None = None
    approved_hashtags: list[str] | None = None


class AvatarFromPostRequest(BaseModel):
    """Set a user's avatar from an existing artwork post ("use as profile photo")."""

    post_sqid: str = Field(..., min_length=1, max_length=16)


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


class PostFile(BaseModel):
    """File variant for a post.

    Non-native variants are server-side re-encodes of the native file.
    Animated variants can contain fewer frames than the post's frame_count
    (consecutive duplicate frames merge on encode, durations are summed;
    playback is visually identical).
    """

    format: str
    file_bytes: int
    is_native: bool

    model_config = ConfigDict(from_attributes=True)


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
    # Moderator-owned subset of `hashtags`; only moderators can change these
    # (docs/mod-hashtags/API-CONTRACT.md)
    mod_hashtags: list[str] = []
    # Vault URL: relative /api/vault/... or absolute on the vault subdomain
    art_url: str
    width: int  # Canvas width in pixels
    height: int  # Canvas height in pixels
    # Frames in the native file (the one art_url points to). Converted
    # renditions may contain fewer: encoders merge consecutive duplicate
    # frames, summing durations (docs/player/displaying-artwork.md)
    frame_count: int = 1
    min_frame_duration_ms: int | None = (
        None  # Minimum non-zero frame duration (ms), NULL for static
    )
    max_frame_duration_ms: int | None = (
        None  # Maximum frame duration (ms), NULL for static
    )
    # Clamped loop duration (ms), NULL for static: per frame missing/<=10ms
    # counts as 100ms, whole-loop totals <=30ms stored as 30ms (message 0010)
    total_duration_ms: int | None = None
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
    view_count: int = 0  # Public lifetime view count (excludes the owner's own views)
    user_has_liked: bool = False  # Whether the current user has liked (👍) this post
    files: list[PostFile] = []  # File variants (native + converted formats)
    license_id: int | None = None  # FK to licenses table
    license: License | None = None  # Creative Commons license info
    # Attached .mkpx layers file (docs/mkpx-upload/). mkpx_attached_at changes on
    # every attach/replace and doubles as the client cache-invalidation stamp.
    has_mkpx: bool = False
    mkpx_file_bytes: int | None = None
    mkpx_attached_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PostUpdate(BaseModel):
    """Update post request."""

    title: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = Field(None, max_length=5000)
    hashtags: list[str] | None = Field(None, max_length=64)
    hidden_by_user: bool | None = None
    hidden_by_mod: bool | None = None


class ModHashtagsUpdate(BaseModel):
    """Replace a post's moderator-owned hashtags (moderator only).

    The raw-list bound is deliberately loose; the real cap
    (MAX_MOD_HASHTAGS_PER_POST) is enforced post-normalization in the endpoint
    so duplicates/#-variants don't trip a schema-level 422.
    """

    hashtags: list[str] = Field(..., max_length=64)
    # Conventional values: spam|abuse|copyright|other (free string, audit log)
    reason_code: str | None = Field(None, max_length=50)
    note: str | None = Field(None, max_length=500)


class PostRead(Post):
    """Alias for consistency."""

    pass


class ViewRegisterPayload(BaseModel):
    """
    Optional body for POST /post/{id}/view.

    When absent (body-less request), the view is recorded as
    view_type=INTENTIONAL, view_source=WEB with no channel metadata
    (used by the Selected Post Overlay).

    When present, the view is recorded as view_type=LISTING (auto-play)
    with the supplied channel metadata (used by the Web Player).
    """

    channel: Literal["all", "promoted", "by_user", "hashtag", "reactions"] | None = None
    channel_context: str | None = Field(None, max_length=100)
    play_order: Literal[0, 1, 2] | None = None


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

    # 128 to match the Post.title column a playlist is stored in (a >128 title
    # previously passed schema validation then failed at the DB).
    title: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(None, max_length=1000)
    post_ids: list[int] = Field(
        default_factory=list, max_length=100
    )  # Changed from UUID to int


class PlaylistUpdate(BaseModel):
    """Update playlist request."""

    title: str | None = Field(None, min_length=1, max_length=128)
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
    # Anonymous commenter IP: populated from the ORM to derive the Guest_xxxxxx
    # handle below, but excluded from serialization so it never leaks to the
    # public comment list / widget. Moderators read raw IPs via the admin pulse.
    author_ip: str | None = Field(default=None, exclude=True)
    parent_id: UUID | None = None
    depth: int = Field(..., ge=0, le=2)
    body: str
    hidden_by_mod: bool
    deleted_by_owner: bool
    deleted_by_mod: bool = False
    created_at: datetime
    updated_at: datetime | None = None
    like_count: int = 0
    liked_by_me: bool = False

    model_config = ConfigDict(from_attributes=True)

    _author_handle_cache: str | None = None
    _author_avatar_url_cache: str | None = None
    _author_public_sqid_cache: str | None = None

    @model_validator(mode="wrap")
    @classmethod
    def extract_author_info(cls, data, handler):
        """Extract author info from the ORM model during validation."""
        # Call the default validation
        instance = handler(data)

        # If data is an ORM model with author relationship loaded, extract info
        if hasattr(data, "author") and data.author:
            instance._author_handle_cache = data.author.handle
            instance._author_avatar_url_cache = data.author.avatar_url
            instance._author_public_sqid_cache = data.author.public_sqid

        # Extract like count and liked_by_me from transient attributes
        if hasattr(data, "_like_count"):
            instance.like_count = data._like_count
        if hasattr(data, "_liked_by_me"):
            instance.liked_by_me = data._liked_by_me

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
        Display name for the comment author (used by widget).

        Currently returns the handle, but could return a display name
        if we add that field to users in the future.
        """
        return self.author_handle

    @computed_field
    @property
    def author_avatar_url(self) -> str | None:
        """
        Avatar URL for the comment author.

        Returns None for guest/anonymous users.
        """
        if self.author_id is None:
            return None
        return self._author_avatar_url_cache

    @computed_field
    @property
    def author_public_sqid(self) -> str | None:
        """
        Public sqid for the comment author (docs/comment-author-sqid/).

        Lets clients navigate to /user/u/{sqid}/profile and target the
        author in reports/blocks. None for guest/anonymous comments.
        """
        if self.author_id is None:
            return None
        return self._author_public_sqid_cache


class CommentCreate(BaseModel):
    """Create comment request."""

    body: str = Field(..., min_length=1, max_length=2000)
    parent_id: UUID | None = None


class CommentUpdate(BaseModel):
    """Update comment request."""

    body: str = Field(..., min_length=1, max_length=2000)


class CommentLikeUserItem(BaseModel):
    """User who liked a comment."""

    created_at: datetime
    user_handle: str
    user_avatar_url: str | None = None
    user_public_sqid: str | None = None


class CommentLikeUsersResponse(BaseModel):
    """Response for listing users who liked a comment."""

    items: list[CommentLikeUserItem]
    total: int


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
    deleted_by_mod: bool = False
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


class ReactionUserItem(BaseModel):
    """A single user's reaction with user details."""

    emoji: str
    created_at: datetime
    user_handle: str
    user_avatar_url: str | None = None
    user_public_sqid: str | None = None


class ReactionUsersResponse(BaseModel):
    """List of users who reacted to a post."""

    items: list[ReactionUserItem]
    total: int


class PulseItem(BaseModel):
    """One event in the moderator dashboard's Pulse activity firehose."""

    type: Literal[
        "post", "comment", "post_reaction", "comment_like", "player", "profile"
    ]
    id: str  # source-row id (int or UUID), stringified
    created_at: datetime  # event time (player events use registered_at)

    # Actor (who did it)
    actor_handle: str | None = None  # null for anonymous actors
    actor_public_sqid: str | None = None
    actor_avatar_url: str | None = None
    anonymous_id: str | None = None  # truncated IP; null for authenticated

    # Post context (all types except player)
    post_id: int | None = None
    post_public_sqid: str | None = None
    post_title: str | None = None
    post_art_url: str | None = None

    # Type-specific detail
    emoji: str | None = None  # post_reaction
    comment_preview: str | None = None  # comment body / liked comment body
    is_reply: bool = False  # comment: replies to another comment
    player_name: str | None = None  # player
    player_model: str | None = None  # player

    # Moderation state of the underlying content, e.g. "hidden_by_mod"
    flags: list[str] = Field(default_factory=list)
    # comment: a preserved pre-deletion body exists (purgeable)
    has_original_body: bool = False


class WidgetData(BaseModel):
    """Combined widget data (reactions + comments) for efficient loading."""

    reactions: ReactionTotals
    comments: list["Comment"]
    views_count: int = 0


# ============================================================================
# REPORT SCHEMAS
# ============================================================================


# Report reason codes (docs/ugc-safety/ D3). `abuse` is legacy read-only (D21).
REPORT_REASONS: list[tuple[str, str]] = [
    ("spam", "Spam or misleading"),
    ("harassment", "Harassment or bullying"),
    ("hate", "Hate or discrimination"),
    ("sexual_explicit", "Sexual or explicit content"),
    ("violence_gore", "Violence or gore"),
    ("illegal_csam", "Illegal content or child endangerment"),
    ("self_harm", "Self-harm or suicide"),
    ("copyright", "Copyright or IP violation"),
    ("other", "Something else"),
]

ReportReasonCode = Literal[
    "spam",
    "harassment",
    "hate",
    "sexual_explicit",
    "violence_gore",
    "illegal_csam",
    "self_harm",
    "copyright",
    "other",
]


class Report(BaseModel):
    """Content moderation report."""

    id: UUID
    target_type: Literal["user", "post", "comment"]
    # post -> int id, comment -> UUID, user -> public_sqid (D9)
    target_id: str
    reason_code: str  # D3 set; legacy rows may carry "abuse" (D21)
    notes: str | None = None
    mod_notes: str | None = None  # moderator notes (D25); mod listings only
    status: Literal["open", "triaged", "resolved"]
    # "delete" is a legacy value on old rows — it never hard-deleted anything,
    # it was the old name for "take_down" (post: visible=False; comment: body
    # replaced). New resolutions store "take_down".
    action_taken: Literal["hide", "take_down", "delete", "ban", "none"] | None = None
    reporter_handle: str | None = None  # populated in moderator listings only
    created_at: datetime
    updated_at: datetime | None = None  # NULL until first update

    model_config = ConfigDict(from_attributes=True)


class ReportCreate(BaseModel):
    """Create report request. Auth optional (anonymous reports, D2)."""

    target_type: Literal["user", "post", "comment"]
    target_id: str  # post -> int id, comment -> UUID, user -> public_sqid (D9)
    reason_code: ReportReasonCode
    notes: str | None = Field(None, max_length=2000)


class ReportUpdate(BaseModel):
    """Update report request (moderator only).

    `notes` are the moderator's notes — stored in `mod_notes`; the reporter's
    original text is immutable (D25).
    """

    status: Literal["triaged", "resolved"] | None = None
    # "delete" is a deprecated alias for "take_down" (normalized in the router).
    # Neither hard-deletes: post -> visible=False, comment -> body replaced.
    action_taken: Literal["hide", "take_down", "delete", "ban", "none"] | None = None
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

    # Optional features (None until the player declares its capabilities)
    capabilities: dict[str, Any] | None = None
    is_paused: bool | None = None
    brightness: int | None = None
    rotation: int | None = None
    mirror: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PlayerSetPauseRequest(BaseModel):
    paused: bool


class PlayerSetBrightnessRequest(BaseModel):
    value: int


class PlayerSetRotationRequest(BaseModel):
    value: int


class PlayerSetMirrorRequest(BaseModel):
    value: str


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
    # HTTPS player API discovery, e.g. {"base_url": "...", "auth": "bearer"}.
    https_api: dict[str, Any] | None = None


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
    channel_name: str | None = None  # 'promoted', 'all', 'by_user', or 'reactions'
    hashtag: str | None = None  # hashtag without #
    user_sqid: str | None = None  # user's sqid for profile / reactions channels
    user_handle: str | None = None  # user's handle (for by_user / reactions channels)
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


class PlayerSelfRenewResponse(BaseModel):
    """Device-initiated certificate renewal result.

    Returns the freshly minted client cert + key and the current CA bundle, so a
    single call refreshes both the client certificate and the trust anchor.
    """

    cert_pem: str
    key_pem: str
    ca_pem: str
    cert_expires_at: datetime
    message: str = "Certificate renewed successfully"


class PlayerTokenResponse(BaseModel):
    """Device bearer token issued or rotated for the HTTPS player API."""

    api_token: str
    rotated_at: datetime


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
    # HTTPS player API discovery, e.g. {"base_url": "...", "auth": "bearer"}.
    https_api: dict[str, Any] | None = None
    # Device bearer token, returned once on first fetch (mint-once).
    api_token: str | None = None


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


class RefreshTokenRequest(BaseModel):
    """Token refresh request.

    DEPRECATED: Refresh tokens are now read from HttpOnly cookies, not request body.
    This schema is kept for backward compatibility but is no longer used by the refresh endpoint.
    """

    refresh_token: str


class MeCapabilities(BaseModel):
    """What the current user is allowed to do (lets the app gate UI upfront)."""

    can_post_public: bool
    can_moderate: bool
    can_own_players: bool


class MeStorageQuota(BaseModel):
    used_bytes: int
    limit_bytes: int


class MeUploadsQuota(BaseModel):
    window: str  # human label, e.g. "1h"
    limit: int
    remaining: int
    reset_at: datetime | None = None


class MePlayersQuota(BaseModel):
    used: int
    limit: int


class MeQuotas(BaseModel):
    storage: MeStorageQuota
    uploads: MeUploadsQuota
    players: MePlayersQuota


class MeModeration(BaseModel):
    banned_until: datetime | None = None
    deactivated: bool = False


class MeResponse(BaseModel):
    """Current user response."""

    user: UserFull
    roles: list[Literal["user", "moderator", "owner"]]
    # Capability/quota block so the app can enable/disable features and show
    # remaining quota before hitting a 4xx (change-request §3.5). Optional for
    # backward compatibility; always populated by GET /auth/me.
    capabilities: MeCapabilities | None = None
    quotas: MeQuotas | None = None
    moderation: MeModeration | None = None
    needs_welcome: bool = False


class RegisterRequest(BaseModel):
    """User registration request.

    `email` is required. `password` is optional:
      - present (native app flow): the chosen password backs the password identity
        and verification is a single 6-digit OTP email — no link/temp-password email.
      - absent (website flow): the server generates a random password and emails a
        verification link. Unchanged.
    """

    email: str = Field(..., max_length=255)
    password: str | None = Field(None, max_length=100)


class RegisterResponse(BaseModel):
    """User registration response - email verification required."""

    message: str = "Please check your email to verify your account"
    user_id: int
    email: str
    handle: str  # User's generated handle
    # How the client should verify: "otp" when a chosen password was supplied
    # (native flow, single 6-digit email), else "link" (website flow). Defaults to
    # "link" so existing callers that omit a password see no change.
    verification_method: Literal["otp", "link"] = "link"


class LoginRequest(BaseModel):
    """User login request - email and password."""

    email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=100)


class TokenRequest(BaseModel):
    """OAuth2-style token request for non-browser (native) clients.

    Unlike /auth/login (which puts the refresh token in an HttpOnly cookie), this
    endpoint returns the refresh token in the body so a native client can store it
    in secure storage. `grant_type` selects the flow:
      - "password":           email + password
      - "refresh_token":      refresh_token (rotates, same engine as the cookie flow)
      - "authorization_code": code + code_verifier (server-brokered OAuth; B3)
      - "apple_identity_token": identity_token + nonce (Sign in with Apple;
        docs/apple-signin/API-CONTRACT.md)
    """

    grant_type: Literal[
        "password", "refresh_token", "authorization_code", "apple_identity_token"
    ]
    email: str | None = Field(None, max_length=255)
    password: str | None = Field(None, max_length=100)
    refresh_token: str | None = None
    code: str | None = None
    code_verifier: str | None = None
    # --- apple_identity_token grant ---
    identity_token: str | None = None
    nonce: str | None = Field(None, max_length=255)
    # Accepted but unused in v1 (the optional server↔Apple exchange is skipped).
    authorization_code: str | None = None
    # Apple sends name/email ONLY on the first sign-in; persisted then or never.
    given_name: str | None = Field(None, max_length=100)
    family_name: str | None = Field(None, max_length=100)


class TokenResponse(BaseModel):
    """OAuth2-style token response with the refresh token in the body."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int  # access-token lifetime in seconds
    refresh_token: str
    user: UserFull


class EmailOtpRequest(BaseModel):
    """Request a numeric email-verification OTP."""

    email: str = Field(..., max_length=255)


class EmailOtpVerify(BaseModel):
    """Verify an email-verification OTP."""

    email: str = Field(..., max_length=255)
    code: str = Field(..., min_length=6, max_length=6)


class PasswordOtpRequest(BaseModel):
    """Request a numeric password-reset OTP."""

    email: str = Field(..., max_length=255)


class PasswordOtpConfirm(BaseModel):
    """Reset a password with a numeric OTP."""

    email: str = Field(..., max_length=255)
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=1, max_length=100)


class OtpMessageResponse(BaseModel):
    """Generic acknowledgement for OTP request endpoints (existence-neutral)."""

    message: str


class PushTokenRegister(BaseModel):
    """Register (or refresh) a mobile push token (§4)."""

    platform: Literal["fcm", "apns"]
    token: str = Field(..., min_length=1, max_length=512)
    device_label: str | None = Field(None, max_length=120)


class PushTokenResponse(BaseModel):
    id: UUID
    platform: str
    device_label: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationPreferences(BaseModel):
    """Per-notification-type push preferences ({type: bool}); absent => on."""

    preferences: dict[str, bool] = Field(default_factory=dict)


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

    # Summary metrics (14 days) - all
    total_page_views_14d: int
    unique_visitors_14d: int
    new_signups_14d: int
    new_posts_14d: int
    total_api_calls_14d: int
    total_errors_14d: int

    # Summary metrics (14 days) - authenticated only
    total_page_views_14d_authenticated: int
    unique_visitors_14d_authenticated: int

    # Trends (14 days) - all
    daily_views: list[DailyCount]
    daily_signups: list[DailyCount]
    daily_posts: list[DailyCount]

    # Trends (14 days) - authenticated only
    daily_views_authenticated: list[DailyCount]

    # Daily unique visitors (14 days)
    daily_unique_visitors: list[DailyCount] = []
    daily_unique_visitors_authenticated: list[DailyCount] = []

    # Granular data (last 24h from events) - all
    hourly_views: list[HourlyCount]

    # Granular data (last 24h from events) - authenticated only
    hourly_views_authenticated: list[HourlyCount]

    # Hourly unique visitors (24h)
    hourly_unique_visitors: list[HourlyCount] = []
    hourly_unique_visitors_authenticated: list[HourlyCount] = []

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
    total_player_artwork_views_14d: int = 0
    active_players_14d: int = 0
    daily_player_views: list[DailyCount] = []
    views_by_player: dict[str, int] = {}  # player_name -> view count

    computed_at: datetime


# ============================================================================
# DOWNLOAD STATS SCHEMAS
# ============================================================================


class DownloadStatsSummary(BaseModel):
    """Headline KPIs for the download-stats tab."""

    total_downloads: int
    unique_artworks: int
    avg_per_artwork: float


class TopArtworkRow(BaseModel):
    """One row of the 'top downloaded artworks' table."""

    post_id: int
    public_sqid: str | None
    title: str
    art_url: str | None
    owner_handle: str
    downloads: int


class DownloadStatsResponse(BaseModel):
    """Artwork download statistics (moderator only).

    Data is rolled up daily by ``app.tasks.rollup_download_stats`` from the
    Caddy vault access log. Counts are split into human vs bot via the UA
    classifier; the ``downloads`` field on each row uses the requested view.
    """

    window_days: int
    include_bots: bool
    summary: DownloadStatsSummary
    daily_downloads: list[DailyCount]
    top_artworks: list[TopArtworkRow]
    computed_at: datetime


class VaultShardingDailyRow(BaseModel):
    """One day of vault downloads split by sharding level (classes summed).

    ``has_data=False`` means the rollup did not run for that day (no
    aggregate rows) — the dashboard must show it as a data gap, never as a
    quiet day, because gaps block the retirement streak.
    """

    date: str  # ISO format date (YYYY-MM-DD)
    has_data: bool
    level2_human: int = 0
    level2_bot: int = 0
    level3_human: int = 0
    level3_bot: int = 0
    level2_misses: int = 0
    level3_misses: int = 0


class VaultShardingClassRow(BaseModel):
    """Window totals for one (asset class, sharding level) pair."""

    asset_class: str  # artwork | avatar | blog_image
    shard_level: int  # 2 | 3
    downloads_human: int
    downloads_bot: int
    misses: int


class LegacyStragglerRow(BaseModel):
    """An artwork still being fetched via legacy 3-level URLs."""

    post_id: int
    public_sqid: str | None
    title: str | None
    art_url: str | None
    owner_handle: str | None
    downloads_human: int
    downloads_bot: int
    last_seen: str  # ISO format date of the most recent legacy fetch


class VaultShardingStatsResponse(BaseModel):
    """Vault resharding migration statistics (moderator only).

    Instrumentation for docs/vault-resharding/: retirement of the legacy
    3-level paths is gated on ``streak_days`` reaching
    ``streak_criterion_days`` — consecutive liveness-valid days with zero
    non-bot legacy downloads (services.download_stats.compute_legacy_streak).
    """

    window_days: int
    streak_days: int
    streak_criterion_days: int
    streak_as_of: str  # ISO date the streak was computed against (yesterday)
    daily: list[VaultShardingDailyRow]
    class_totals: list[VaultShardingClassRow]
    stragglers: list[LegacyStragglerRow]
    straggler_window_days: int
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
    actor_public_sqid: str | None = None  # For /u/{sqid} profile links
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
    files: list[PostFile] = []
    art_url: str
    hidden_by_user: bool
    reaction_count: int
    comment_count: int
    view_count: int
    license_identifier: str | None = None

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


class BatchLicenseChangeRequest(BaseModel):
    """Request for batch license change."""

    post_ids: list[int] = Field(..., min_length=1, max_length=128)
    license_id: int | None = None


class BatchLicenseChangeResponse(BaseModel):
    """Response for batch license change."""

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
    # Whether the viewer has blocked this user (docs/ugc-safety/ D14);
    # always present, false when logged out
    is_blocked_by_viewer: bool = False
    highlights: list[UserHighlightItem] = []  # Featured posts

    model_config = ConfigDict(from_attributes=True)


class BlockedUserEntry(BaseModel):
    """One entry in the caller's blocked-users list (GET /v1/me/blocks)."""

    public_sqid: str
    handle: str
    avatar_url: str | None = None
    blocked_at: datetime


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
    owner_id: int
    owner_handle: str
    owner: UserPublic | None = None
    reacted_at: datetime
    emoji: str  # The emoji used in the reaction
    created_at: datetime
    frame_count: int = 1
    files: list[PostFile] = []
    reaction_count: int = 0
    comment_count: int = 0
    user_has_liked: bool = False  # Whether the current user has liked (👍) this post


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

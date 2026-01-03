"""MQTT notification and player request/response payload schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal, Union
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator


# ============================================================================
# AMP Criteria Filtering Enums and Constants
# ============================================================================


class CriteriaOperator(str, Enum):
    """Supported operators for AMP field criteria."""

    EQ = "eq"  # =
    NEQ = "neq"  # !=
    LT = "lt"  # <
    GT = "gt"  # >
    LTE = "lte"  # <=
    GTE = "gte"  # >=
    IN = "in"  # IN (array)
    NOT_IN = "not_in"  # NOT IN (array)
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"


class CriteriaField(str, Enum):
    """Queryable AMP field names (map to Post model columns)."""

    WIDTH = "width"
    HEIGHT = "height"
    FILE_BYTES = "file_bytes"
    FRAME_COUNT = "frame_count"
    MIN_FRAME_DURATION_MS = "min_frame_duration_ms"
    MAX_FRAME_DURATION_MS = "max_frame_duration_ms"
    UNIQUE_COLORS = "unique_colors"
    TRANSPARENCY_META = "transparency_meta"
    ALPHA_META = "alpha_meta"
    TRANSPARENCY_ACTUAL = "transparency_actual"
    ALPHA_ACTUAL = "alpha_actual"
    FILE_FORMAT = "file_format"
    KIND = "kind"


class FileFormatValue(str, Enum):
    """Valid file format values for file_format field."""

    PNG = "png"
    GIF = "gif"
    WEBP = "webp"
    BMP = "bmp"


class KindValue(str, Enum):
    """Valid kind values for kind field."""

    ARTWORK = "artwork"
    PLAYLIST = "playlist"


# Field type categorizations
NUMERIC_FIELDS = {
    "width",
    "height",
    "file_bytes",
    "frame_count",
    "min_frame_duration_ms",
    "max_frame_duration_ms",
    "unique_colors",
}

BOOLEAN_FIELDS = {
    "transparency_meta",
    "alpha_meta",
    "transparency_actual",
    "alpha_actual",
}

STRING_ENUM_FIELDS = {
    "file_format",
    "kind",
}

NULLABLE_FIELDS = {
    "min_frame_duration_ms",
    "max_frame_duration_ms",
    "unique_colors",
    "file_format",
}

# Valid operators per field type
NUMERIC_OPERATORS = {"eq", "neq", "lt", "gt", "lte", "gte", "in", "not_in", "is_null", "is_not_null"}
BOOLEAN_OPERATORS = {"eq", "neq"}
STRING_ENUM_OPERATORS = {"eq", "neq", "in", "not_in", "is_null", "is_not_null"}


class FilterCriterion(BaseModel):
    """Single filter criterion for AMP field queries."""

    field: CriteriaField = Field(..., description="AMP field to filter on")
    op: CriteriaOperator = Field(..., description="Comparison operator")
    value: Union[int, float, bool, str, list[int], list[str], None] = Field(
        None,
        description="Value(s) to compare. Required for most operators. "
        "Array for IN/NOT IN. Not required for IS NULL/IS NOT NULL.",
    )

    @model_validator(mode="after")
    def validate_field_operator_value_combination(self) -> "FilterCriterion":
        """Validate that operator is valid for field type and value matches."""
        field_name = self.field.value
        op_name = self.op.value

        # Check operator validity for field type
        if field_name in NUMERIC_FIELDS:
            if op_name not in NUMERIC_OPERATORS:
                raise ValueError(f"Operator '{op_name}' not valid for numeric field '{field_name}'")
            # Only allow null checks on nullable numeric fields
            if op_name in ("is_null", "is_not_null") and field_name not in NULLABLE_FIELDS:
                raise ValueError(f"Field '{field_name}' is not nullable")
        elif field_name in BOOLEAN_FIELDS:
            if op_name not in BOOLEAN_OPERATORS:
                raise ValueError(f"Operator '{op_name}' not valid for boolean field '{field_name}'")
        elif field_name in STRING_ENUM_FIELDS:
            if op_name not in STRING_ENUM_OPERATORS:
                raise ValueError(f"Operator '{op_name}' not valid for string field '{field_name}'")
            # Only allow null checks on nullable string fields
            if op_name in ("is_null", "is_not_null") and field_name not in NULLABLE_FIELDS:
                raise ValueError(f"Field '{field_name}' is not nullable")

        # Validate value presence/type
        if op_name in ("is_null", "is_not_null"):
            if self.value is not None:
                raise ValueError(f"Operator '{op_name}' does not accept a value")
        elif op_name in ("in", "not_in"):
            if not isinstance(self.value, list):
                raise ValueError(f"Operator '{op_name}' requires an array value")
            if len(self.value) == 0:
                raise ValueError(f"Operator '{op_name}' requires at least one value")
            if len(self.value) > 128:
                raise ValueError(f"Operator '{op_name}' accepts at most 128 values")
        else:
            if self.value is None:
                raise ValueError(f"Operator '{op_name}' requires a value")

        # Validate value type matches field type
        if self.value is not None:
            if field_name in NUMERIC_FIELDS:
                if op_name in ("in", "not_in"):
                    if not all(isinstance(v, (int, float)) for v in self.value):
                        raise ValueError(f"All values must be numeric for field '{field_name}'")
                else:
                    if not isinstance(self.value, (int, float)):
                        raise ValueError(f"Value must be numeric for field '{field_name}'")
            elif field_name in BOOLEAN_FIELDS:
                if not isinstance(self.value, bool):
                    raise ValueError(f"Value must be boolean for field '{field_name}'")
            elif field_name == "file_format":
                # Validate file_format enum values
                valid_formats = {e.value for e in FileFormatValue}
                if op_name in ("in", "not_in"):
                    invalid = [v for v in self.value if v not in valid_formats]
                    if invalid:
                        raise ValueError(
                            f"Invalid file_format values: {invalid}. Valid: {sorted(valid_formats)}"
                        )
                else:
                    if self.value not in valid_formats:
                        raise ValueError(
                            f"Invalid file_format: {self.value}. Valid: {sorted(valid_formats)}"
                        )
            elif field_name == "kind":
                # Validate kind enum values
                valid_kinds = {e.value for e in KindValue}
                if op_name in ("in", "not_in"):
                    invalid = [v for v in self.value if v not in valid_kinds]
                    if invalid:
                        raise ValueError(
                            f"Invalid kind values: {invalid}. Valid: {sorted(valid_kinds)}"
                        )
                else:
                    if self.value not in valid_kinds:
                        raise ValueError(
                            f"Invalid kind: {self.value}. Valid: {sorted(valid_kinds)}"
                        )

        return self


class PostNotificationPayload(BaseModel):
    """MQTT notification payload for new posts."""

    post_id: int  # Changed from UUID to int
    owner_id: UUID
    owner_handle: str
    title: str
    art_url: HttpUrl
    canvas: str
    promoted_category: str | None = None
    created_at: datetime

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


# ============================================================================
# Player Request/Response Schemas
# ============================================================================


class PlayerRequestBase(BaseModel):
    """Base schema for all player requests."""
    
    request_id: str = Field(..., description="Unique request ID for correlation")
    request_type: str = Field(..., description="Type of request")
    player_key: UUID = Field(..., description="Player's unique key for authentication")


class QueryPostsRequest(PlayerRequestBase):
    """Request to query posts with filters and pagination."""
    
    request_type: Literal["query_posts"] = "query_posts"
    channel: Literal["all", "promoted", "user", "by_user", "artwork", "hashtag"] = Field(
        "all",
        description="Channel to query: 'all', 'promoted', 'user', 'by_user', 'artwork', 'hashtag' (device protocol compatibility)"
    )
    user_handle: str | None = Field(
        None,
        description="User handle for 'by_user' channel (e.g., 'artist123'). Required when channel='by_user'."
    )
    user_sqid: str | None = Field(
        None,
        description="User sqid for 'by_user' channel (alternative to user_handle). Required when channel='by_user' and user_handle is not provided."
    )
    hashtag: str | None = Field(
        None,
        description="Hashtag (without #) for 'hashtag' channel. Required when channel='hashtag'."
    )
    sort: Literal["server_order", "created_at", "random"] = Field(
        "server_order",
        description="Sorting order: 'server_order' (original order), 'created_at' (chronological), 'random' (with seed)"
    )
    random_seed: int | None = Field(
        None,
        description="Random seed for reproducible random ordering (only used when sort='random')"
    )
    cursor: str | None = Field(
        None,
        description="Cursor for pagination (from previous response)"
    )
    limit: int = Field(
        50,
        ge=1,
        le=50,
        description="Number of posts to return (1-50)"
    )
    criteria: list[FilterCriterion] = Field(
        default_factory=list,
        description="AMP field criteria for filtering (0-64 items, AND-ed together)",
        max_length=64,
    )


class ArtworkPostPayload(BaseModel):
    """Artwork post payload for players (firmware protocol)."""

    post_id: int
    kind: Literal["artwork"]
    owner_handle: str
    created_at: datetime
    metadata_modified_at: datetime

    storage_key: str
    art_url: str
    width: int
    height: int
    frame_count: int
    transparency_actual: bool
    alpha_actual: bool
    artwork_modified_at: datetime
    dwell_time_ms: int


class PlaylistPostPayload(BaseModel):
    """Playlist post payload for players (firmware protocol)."""

    post_id: int
    kind: Literal["playlist"]
    owner_handle: str
    created_at: datetime
    metadata_modified_at: datetime

    total_artworks: int
    dwell_time_ms: int


PlayerPostPayload = Annotated[
    ArtworkPostPayload | PlaylistPostPayload, Field(discriminator="kind")
]


class QueryPostsResponse(BaseModel):
    """Response with list of posts."""
    
    request_id: str
    success: bool = True
    posts: list[PlayerPostPayload]
    next_cursor: str | None = None
    has_more: bool = False
    error: str | None = None
    error_code: str | None = None


class GetPostRequest(PlayerRequestBase):
    """Request to fetch a single post by ID."""

    request_type: Literal["get_post"] = "get_post"
    post_id: int = Field(..., description="Post ID to fetch")


class GetPostResponse(BaseModel):
    """Response with a single post."""

    request_id: str
    success: bool = True
    post: PlayerPostPayload | None = None
    error: str | None = None
    error_code: str | None = None


class SubmitReactionRequest(PlayerRequestBase):
    """Request to add an emoji reaction."""
    
    request_type: Literal["submit_reaction"] = "submit_reaction"
    post_id: int = Field(..., description="Post ID to react to")
    emoji: str = Field(..., description="Emoji to add", min_length=1, max_length=20)


class SubmitReactionResponse(BaseModel):
    """Response after submitting a reaction."""
    
    request_id: str
    success: bool = True
    error: str | None = None


class RevokeReactionRequest(PlayerRequestBase):
    """Request to revoke an emoji reaction."""
    
    request_type: Literal["revoke_reaction"] = "revoke_reaction"
    post_id: int = Field(..., description="Post ID to revoke reaction from")
    emoji: str = Field(..., description="Emoji to revoke", min_length=1, max_length=20)


class RevokeReactionResponse(BaseModel):
    """Response after revoking a reaction."""
    
    request_id: str
    success: bool = True
    error: str | None = None


class GetCommentsRequest(PlayerRequestBase):
    """Request to retrieve comments for a post."""
    
    request_type: Literal["get_comments"] = "get_comments"
    post_id: int = Field(..., description="Post ID to get comments for")
    cursor: str | None = Field(
        None,
        description="Cursor for pagination (from previous response)"
    )
    limit: int = Field(
        50,
        ge=1,
        le=200,
        description="Number of comments to return (1-200). Higher limit than posts due to typically smaller payload size."
    )


class CommentSummary(BaseModel):
    """Summary of a comment for player display."""
    
    comment_id: UUID
    post_id: int
    author_handle: str | None  # None for anonymous
    body: str
    depth: int
    parent_id: UUID | None
    created_at: datetime
    deleted: bool


class GetCommentsResponse(BaseModel):
    """Response with list of comments."""
    
    request_id: str
    success: bool = True
    comments: list[CommentSummary]
    next_cursor: str | None = None
    has_more: bool = False
    error: str | None = None


class ErrorResponse(BaseModel):
    """Generic error response."""
    
    request_id: str
    success: bool = False
    error: str
    error_code: str | None = None


# ============================================================================
# P3A Fire-and-Forget View Event (Direct MQTT Topic)
# ============================================================================


class P3AViewEvent(BaseModel):
    """
    Fire-and-forget view event from p3a player devices.
    
    Published to: makapix/player/{player_key}/view
    Optional acknowledgment can be requested via request_ack field.
    If requested, ack is sent to: makapix/player/{player_key}/view/ack
    """
    
    post_id: int = Field(..., description="Artwork post ID")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp (e.g., '2025-12-22T16:24:15Z')")
    timezone: str = Field(..., description="Reserved for future use. Currently empty string.")
    intent: Literal["artwork", "channel"] = Field(
        ...,
        description="View origin: 'artwork' (explicit request) or 'channel' (automated playback)"
    )
    play_order: int = Field(..., ge=0, le=2, description="Playback order: 0=server, 1=created, 2=random")
    channel: str = Field(..., description="Active channel (e.g., 'all', 'promoted', 'hashtag', etc.)")
    player_key: str = Field(..., description="UUID identifying the p3a device")
    
    # Optional fields for future compatibility (not currently sent by p3a)
    channel_user_sqid: str | None = Field(None, description="User sqid for 'by_user' channel")
    channel_hashtag: str | None = Field(None, description="Hashtag for 'hashtag' channel")
    request_ack: bool = Field(False, description="Whether to send acknowledgment to view/ack topic")


"""MQTT notification and player request/response payload schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


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
    channel: Literal["all", "promoted", "user"] = Field(
        "all",
        description="Channel to query: 'all' for recent posts, 'promoted' for promoted posts, 'user' for user's own posts"
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


class PostSummary(BaseModel):
    """Summary of a post for player display."""
    
    post_id: int
    storage_key: UUID
    title: str
    art_url: str
    canvas: str
    width: int
    height: int
    frame_count: int
    has_transparency: bool
    owner_handle: str
    created_at: datetime


class QueryPostsResponse(BaseModel):
    """Response with list of posts."""
    
    request_id: str
    success: bool = True
    posts: list[PostSummary]
    next_cursor: str | None = None
    has_more: bool = False
    error: str | None = None


class SubmitViewRequest(PlayerRequestBase):
    """Request to submit a view event."""
    
    request_type: Literal["submit_view"] = "submit_view"
    post_id: int = Field(..., description="Post ID to record view for")
    view_intent: Literal["automated", "intentional"] = Field(
        "automated",
        description="'automated' for playlist/auto-swap views, 'intentional' for direct user selection"
    )


class SubmitViewResponse(BaseModel):
    """Response after submitting a view."""
    
    request_id: str
    success: bool = True
    error: str | None = None


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


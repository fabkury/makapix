"""Transport-agnostic player RPC handlers.

These functions contain the business logic behind the player request protocol
(`query_posts`, `get_post`, `submit_reaction`, `revoke_reaction`,
`get_comments`, `get_playset`, `echo`). Each takes an authenticated
``models.Player`` plus a typed request and **returns** the corresponding
response model. Known error conditions are signalled by raising
``PlayerRpcError`` (carrying a machine-readable ``error_code``); the calling
transport adapter decides how to surface it — an MQTT ``ErrorResponse`` or an
HTTP status + envelope. Nothing here touches MQTT, HTTP, or any wire format.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, exists, func, or_, text
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..pagination import decode_cursor, encode_cursor
from ..player_protocol.schemas import (
    ArtworkPostPayload,
    CommentSummary,
    EchoRequest,
    EchoResponse,
    FilterCriterion,
    GetCommentsRequest,
    GetCommentsResponse,
    GetPlaysetRequest,
    GetPlaysetResponse,
    GetPostRequest,
    GetPostResponse,
    PlayerPostPayload,
    PlaylistPostPayload,
    PlaysetChannelPayload,
    QueryPostsRequest,
    QueryPostsResponse,
    RevokeReactionRequest,
    RevokeReactionResponse,
    SubmitReactionRequest,
    SubmitReactionResponse,
)
from ..utils.monitored_hashtags import (
    apply_monitored_hashtag_filter,
    post_has_unapproved_monitored_hashtags,
)
from .playset import PlaysetService
from .rate_limit import check_rate_limit

logger = logging.getLogger(__name__)

DEFAULT_DWELL_MS = 30000

# Valid optional field names for artwork payloads
OPTIONAL_ARTWORK_FIELDS = frozenset(
    {
        "owner_handle",
        "metadata_modified_at",
        "artwork_modified_at",
        "width",
        "height",
        "frame_count",
        "dwell_time_ms",
        "transparency_actual",
        "alpha_actual",
    }
)


class PlayerRpcError(Exception):
    """A handled, business-rule error in a player RPC handler.

    Carries a machine-readable ``error_code`` and a human-readable message.
    Transport adapters translate this into their own error representation.
    """

    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message


# ============================================================================
# Payload builders
# ============================================================================


def _build_artwork_payload(
    post: models.Post,
    include_fields: set[str] | None = None,
) -> ArtworkPostPayload:
    """Build artwork payload with optional field inclusion."""
    include = include_fields or set()

    return ArtworkPostPayload(
        # Mandatory fields (always included)
        post_id=post.id,
        kind="artwork",
        created_at=post.created_at,
        storage_key=str(post.storage_key),
        art_url=post.art_url or "",
        storage_shard=post.storage_shard or "",
        native_format=next((f.format for f in post.files if f.is_native), None),
        # Optional fields (None if not requested)
        owner_handle=post.owner.handle if "owner_handle" in include else None,
        metadata_modified_at=(
            post.metadata_modified_at if "metadata_modified_at" in include else None
        ),
        artwork_modified_at=(
            post.artwork_modified_at if "artwork_modified_at" in include else None
        ),
        width=int(post.width or 0) if "width" in include else None,
        height=int(post.height or 0) if "height" in include else None,
        frame_count=int(post.frame_count or 1) if "frame_count" in include else None,
        dwell_time_ms=(
            int(getattr(post, "dwell_time_ms", DEFAULT_DWELL_MS) or DEFAULT_DWELL_MS)
            if "dwell_time_ms" in include
            else None
        ),
        transparency_actual=(
            bool(getattr(post, "transparency_actual", False))
            if "transparency_actual" in include
            else None
        ),
        alpha_actual=(
            bool(getattr(post, "alpha_actual", False))
            if "alpha_actual" in include
            else None
        ),
    )


def _build_playlist_payload(
    playlist_post: models.Post,
    db: Session,
) -> PlaylistPostPayload:
    # Total artworks is the full playlist size.
    total_artworks = (
        db.query(func.count(models.PlaylistItem.id))
        .filter(models.PlaylistItem.playlist_post_id == playlist_post.id)
        .scalar()
        or 0
    )

    return PlaylistPostPayload(
        post_id=playlist_post.id,
        kind="playlist",
        owner_handle=playlist_post.owner.handle,
        created_at=playlist_post.created_at,
        metadata_modified_at=playlist_post.metadata_modified_at,
        total_artworks=int(total_artworks),
        dwell_time_ms=int(
            getattr(playlist_post, "dwell_time_ms", DEFAULT_DWELL_MS)
            or DEFAULT_DWELL_MS
        ),
    )


def _apply_criteria_filters(
    query,
    criteria: list[FilterCriterion],
) -> tuple[Any, str | None]:
    """
    Apply AMP field criteria to a SQLAlchemy query.

    Args:
        query: SQLAlchemy query object
        criteria: List of FilterCriterion objects

    Returns:
        tuple: (modified_query, error_message or None)
    """
    if not criteria:
        return query, None

    # Map field names to Post model columns (direct Post fields)
    field_to_column = {
        "width": models.Post.width,
        "height": models.Post.height,
        "frame_count": models.Post.frame_count,
        "min_frame_duration_ms": models.Post.min_frame_duration_ms,
        "max_frame_duration_ms": models.Post.max_frame_duration_ms,
        "unique_colors": models.Post.unique_colors,
        "transparency_meta": models.Post.transparency_meta,
        "alpha_meta": models.Post.alpha_meta,
        "transparency_actual": models.Post.transparency_actual,
        "alpha_actual": models.Post.alpha_actual,
        "kind": models.Post.kind,
    }

    # Fields that live on PostFile (queried via EXISTS subquery)
    postfile_field_to_column = {
        "file_bytes": models.PostFile.file_bytes,
        "file_format": models.PostFile.format,
    }

    filters = []
    # Conditions for any PostFile row (file_format, file_bytes)
    pf_conditions = [models.PostFile.post_id == models.Post.id]
    has_pf_criteria = False
    # Separate conditions for native PostFile row (native_file_format)
    native_pf_conditions = [
        models.PostFile.post_id == models.Post.id,
        models.PostFile.is_native == True,  # noqa: E712
    ]
    has_native_pf_criteria = False

    def _build_condition(column, op, value, idx):
        if op == "eq":
            return column == value
        elif op == "neq":
            return column != value
        elif op == "lt":
            return column < value
        elif op == "gt":
            return column > value
        elif op == "lte":
            return column <= value
        elif op == "gte":
            return column >= value
        elif op == "in":
            return column.in_(value)
        elif op == "not_in":
            return ~column.in_(value)
        elif op == "is_null":
            return column.is_(None)
        elif op == "is_not_null":
            return column.isnot(None)
        else:
            raise ValueError(f"Unknown operator in criterion {idx}: {op}")

    for i, criterion in enumerate(criteria):
        field_name = criterion.field.value
        op = criterion.op.value
        value = criterion.value

        try:
            if field_name == "native_file_format":
                # Native format — separate EXISTS with is_native=True
                native_pf_conditions.append(
                    _build_condition(models.PostFile.format, op, value, i)
                )
                has_native_pf_criteria = True
            elif field_name in postfile_field_to_column:
                # PostFile criteria — collected into EXISTS subquery
                pf_col = postfile_field_to_column[field_name]
                pf_conditions.append(_build_condition(pf_col, op, value, i))
                has_pf_criteria = True
            elif field_name in field_to_column:
                column = field_to_column[field_name]
                filters.append(_build_condition(column, op, value, i))
            else:
                return None, f"Unknown field in criterion {i}: {field_name}"
        except Exception as e:
            logger.error(f"Error applying criterion {i}: {e}")
            return None, f"Invalid criterion {i}: {str(e)}"

    if has_pf_criteria:
        filters.append(exists().where(*pf_conditions))

    if has_native_pf_criteria:
        filters.append(exists().where(*native_pf_conditions))

    if filters:
        query = query.filter(and_(*filters))

    return query, None


def _resolve_target_user(
    user_handle: str | None,
    user_sqid: str | None,
    channel_label: str,
    db: Session,
) -> models.User:
    """
    Resolve a target user from user_handle or user_sqid.

    Raises PlayerRpcError when the identifier is missing or the user is not
    found.
    """
    target_user: models.User | None = None
    if user_handle:
        target_user = (
            db.query(models.User).filter(models.User.handle == user_handle).first()
        )
    elif user_sqid:
        target_user = (
            db.query(models.User).filter(models.User.public_sqid == user_sqid).first()
        )
    else:
        raise PlayerRpcError(
            "missing_user_identifier",
            f"user_handle or user_sqid is required when channel='{channel_label}'",
        )

    if not target_user:
        identifier = user_handle or user_sqid
        raise PlayerRpcError("user_not_found", f"User '{identifier}' not found")

    return target_user


# ============================================================================
# Request handlers
# ============================================================================


def query_posts(
    player: models.Player,
    request: QueryPostsRequest,
    db: Session,
) -> QueryPostsResponse:
    """Handle a query_posts request."""
    is_reactions_channel = request.channel == "reactions"

    # Build base query (include both artwork and playlist posts)
    query = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner))
        .filter(
            models.Post.kind.in_(["artwork", "playlist"]),
            models.Post.public_sqid.isnot(None),
            models.Post.public_sqid != "",
        )
    )

    # Apply channel filter
    if request.channel == "promoted":
        query = query.filter(models.Post.promoted.is_(True))
    elif request.channel == "user":
        # Only query player owner's posts
        query = query.filter(models.Post.owner_id == player.owner_id)
    elif request.channel == "by_user":
        # Query arbitrary user's posts by handle or sqid
        target_user = _resolve_target_user(
            request.user_handle, request.user_sqid, "by_user", db
        )
        query = query.filter(models.Post.owner_id == target_user.id)
    elif request.channel == "reactions":
        # Query posts the target user has reacted to (latest reaction per post).
        target_user = _resolve_target_user(
            request.user_handle, request.user_sqid, "reactions", db
        )

        # Dedupe: latest reaction row per post for this user
        latest_reaction_ids = (
            db.query(func.max(models.Reaction.id))
            .filter(
                models.Reaction.user_id == target_user.id,
                models.Reaction.user_id.isnot(None),
            )
            .group_by(models.Reaction.post_id)
        )

        query = (
            query.join(models.Reaction, models.Reaction.post_id == models.Post.id)
            .filter(
                models.Reaction.user_id == target_user.id,
                models.Reaction.id.in_(latest_reaction_ids),
            )
            .add_columns(
                models.Reaction.created_at.label("reacted_at"),
                models.Reaction.id.label("reaction_id"),
            )
        )
    elif request.channel == "hashtag":
        # Query posts by hashtag
        if not request.hashtag:
            raise PlayerRpcError(
                "missing_hashtag", "hashtag is required when channel='hashtag'"
            )

        # Normalize hashtag (lowercase, strip) to match how they're stored
        hashtag_normalized = request.hashtag.strip().lower()
        if not hashtag_normalized:
            raise PlayerRpcError("invalid_hashtag", "hashtag cannot be empty")

        query = query.filter(models.Post.hashtags.contains([hashtag_normalized]))
    elif request.channel == "artwork":
        # Protocol compatibility: do not exclude playlists (per server policy).
        pass
    # "all" requires no additional filter

    # Apply visibility filters (aligned with /api/post endpoint behavior)
    # Determine if viewing own posts (for public_visibility exemption)
    is_viewing_own_posts = request.channel == "user"

    # Always exclude user-deleted posts
    query = query.filter(~models.Post.deleted_by_user)

    # Apply standard visibility filters (no moderator exceptions here;
    # moderator-only views are handled in the Moderator Dashboard)
    query = query.filter(
        models.Post.visible,
        ~models.Post.hidden_by_user,
        ~models.Post.hidden_by_mod,
        ~models.Post.non_conformant,
    )

    # Apply public_visibility filter unless viewing own posts
    # Posts pending approval are visible only to their owner.
    # For the reactions channel, also exempt posts owned by the player's
    # own owner — matches the /reacted-posts HTTP endpoint behaviour where
    # a viewer sees their own private posts that others have reacted to.
    if not is_viewing_own_posts:
        if is_reactions_channel:
            query = query.filter(
                or_(
                    models.Post.public_visibility.is_(True),
                    models.Post.owner_id == player.owner_id,
                )
            )
        else:
            query = query.filter(models.Post.public_visibility.is_(True))

    # Apply monitored hashtag filtering based on player owner's preferences
    query = apply_monitored_hashtag_filter(query, models.Post, player.owner)

    # Apply AMP criteria filters
    if request.criteria:
        query, error = _apply_criteria_filters(query, request.criteria)
        if error:
            raise PlayerRpcError("invalid_criteria", f"Invalid criteria: {error}")

    # Apply sorting
    if is_reactions_channel and request.sort in ("server_order", "reacted_at"):
        # Latest-reaction-first, stable on ties via Reaction.id
        query = query.order_by(
            models.Reaction.created_at.desc(), models.Reaction.id.desc()
        )
    elif request.sort == "reacted_at":
        # Non-reactions channel asking for reacted_at — fall back silently
        query = query.order_by(models.Post.id.desc())
    elif request.sort == "created_at":
        query = query.order_by(models.Post.created_at.desc())
    elif request.sort == "random":
        # Use random seed if provided for reproducible ordering
        if request.random_seed is not None:
            # PostgreSQL-specific random ordering with seed
            # Use parameterized query to prevent SQL injection
            seed_value = (request.random_seed % 1000000) / 1000000.0
            db.execute(text("SELECT setseed(:seed)"), {"seed": seed_value})
        query = query.order_by(func.random())
    else:
        # "server_order" - use id order (insertion order)
        query = query.order_by(models.Post.id.desc())

    # Apply cursor pagination
    offset = 0
    if is_reactions_channel:
        # Keyset pagination on Reaction.created_at (see pagination.py)
        if request.cursor:
            cursor_data = decode_cursor(request.cursor)
            if cursor_data:
                _, sort_value = cursor_data
                if sort_value:
                    try:
                        cursor_dt = datetime.fromisoformat(
                            str(sort_value).replace("Z", "+00:00")
                        )
                        query = query.filter(models.Reaction.created_at < cursor_dt)
                    except (ValueError, AttributeError):
                        logger.warning(f"Invalid cursor: {request.cursor}")
        query = query.limit(request.limit + 1)
    else:
        # Offset-based pagination for every other channel
        if request.cursor:
            try:
                offset = int(request.cursor)
            except ValueError:
                logger.warning(f"Invalid cursor: {request.cursor}")
        query = query.offset(offset).limit(request.limit + 1)

    # Execute query
    posts = query.all()

    # Check if there are more results
    has_more = len(posts) > request.limit
    if has_more:
        posts = posts[: request.limit]

    # Calculate next cursor
    next_cursor = None
    if has_more:
        if is_reactions_channel:
            last_row = posts[-1]
            next_cursor = encode_cursor(
                str(last_row.reaction_id),
                last_row.reacted_at.isoformat(),
            )
        else:
            next_cursor = str(offset + request.limit)

    # Compute valid include_fields set
    include_fields: set[str] | None = None
    if request.include_fields:
        include_fields = set(request.include_fields) & OPTIONAL_ARTWORK_FIELDS

    # Build response payload posts
    payload_posts: list[PlayerPostPayload] = []
    for row in posts:
        post = row.Post if is_reactions_channel else row
        if post.kind == "artwork":
            payload_posts.append(_build_artwork_payload(post, include_fields))
        elif post.kind == "playlist":
            payload_posts.append(_build_playlist_payload(post, db))

    logger.info(
        f"query_posts for player {player.player_key}: {len(payload_posts)} posts"
    )

    return QueryPostsResponse(
        request_id=request.request_id,
        posts=payload_posts,
        next_cursor=next_cursor,
        has_more=has_more,
    )


def get_post(
    player: models.Player,
    request: GetPostRequest,
    db: Session,
) -> GetPostResponse:
    """Handle a get_post request."""
    post = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner))
        .filter(models.Post.id == request.post_id)
        .first()
    )
    if not post:
        raise PlayerRpcError("not_found", f"Post {request.post_id} not found")

    # Check if post was deleted by user
    if post.deleted_by_user:
        raise PlayerRpcError("deleted", "Post has been deleted")

    # Visibility (same logic as query_posts)
    is_moderator = "moderator" in player.owner.roles or "owner" in player.owner.roles
    if not post.visible:
        raise PlayerRpcError("not_visible", "Post is not visible")
    if post.hidden_by_user:
        raise PlayerRpcError("not_available", "Post is not available")
    if not is_moderator and (post.hidden_by_mod or post.non_conformant):
        raise PlayerRpcError("not_available", "Post is not available")

    # Check if post has monitored hashtags that owner hasn't approved
    if post_has_unapproved_monitored_hashtags(post, player.owner):
        raise PlayerRpcError(
            "content_not_approved", "Post contains content not approved by user"
        )

    # Compute valid include_fields set
    include_fields: set[str] | None = None
    if request.include_fields:
        include_fields = set(request.include_fields) & OPTIONAL_ARTWORK_FIELDS

    if post.kind == "artwork":
        payload_post: PlayerPostPayload = _build_artwork_payload(post, include_fields)
    elif post.kind == "playlist":
        payload_post = _build_playlist_payload(post, db)
    else:
        raise PlayerRpcError("unsupported_kind", f"Unsupported post kind: {post.kind}")

    return GetPostResponse(
        request_id=request.request_id,
        success=True,
        post=payload_post,
    )


def submit_reaction(
    player: models.Player,
    request: SubmitReactionRequest,
    db: Session,
) -> SubmitReactionResponse:
    """Handle a submit_reaction request."""
    # Validate emoji (basic validation)
    emoji = request.emoji.strip()
    if not emoji or len(emoji) > 20:
        raise PlayerRpcError("invalid_emoji", "Invalid emoji format")

    # Check if post exists
    post = db.query(models.Post).filter(models.Post.id == request.post_id).first()
    if not post:
        raise PlayerRpcError("not_found", f"Post {request.post_id} not found")

    # Check if post was deleted by user
    if post.deleted_by_user:
        raise PlayerRpcError("deleted", "Post has been deleted")

    # Check if reaction already exists (idempotent)
    existing = (
        db.query(models.Reaction)
        .filter(
            models.Reaction.post_id == request.post_id,
            models.Reaction.user_id == player.owner_id,
            models.Reaction.emoji == emoji,
        )
        .first()
    )
    if existing:
        # Already exists, return success
        logger.debug(f"Reaction already exists for post {request.post_id}")
        return SubmitReactionResponse(request_id=request.request_id)

    # Check reaction limit (max 5 per user per post)
    reaction_count = (
        db.query(func.count(models.Reaction.id))
        .filter(
            models.Reaction.post_id == request.post_id,
            models.Reaction.user_id == player.owner_id,
        )
        .scalar()
    )
    if reaction_count >= 5:
        raise PlayerRpcError(
            "reaction_limit_exceeded", "Maximum 5 reactions per post exceeded"
        )

    # Create reaction
    reaction = models.Reaction(
        post_id=request.post_id,
        user_id=player.owner_id,
        emoji=emoji,
    )
    db.add(reaction)
    db.commit()

    logger.info(
        f"Added reaction '{emoji}' to post {request.post_id} from player {player.player_key}"
    )

    return SubmitReactionResponse(request_id=request.request_id)


def revoke_reaction(
    player: models.Player,
    request: RevokeReactionRequest,
    db: Session,
) -> RevokeReactionResponse:
    """Handle a revoke_reaction request."""
    # Find and delete reaction
    reaction = (
        db.query(models.Reaction)
        .filter(
            models.Reaction.post_id == request.post_id,
            models.Reaction.user_id == player.owner_id,
            models.Reaction.emoji == request.emoji.strip(),
        )
        .first()
    )

    if reaction:
        db.delete(reaction)
        db.commit()
        logger.info(
            f"Revoked reaction '{request.emoji}' from post {request.post_id} "
            f"for player {player.player_key}"
        )
    else:
        # Idempotent - return success even if reaction didn't exist
        logger.debug(f"No reaction to revoke for post {request.post_id}")

    return RevokeReactionResponse(request_id=request.request_id)


def get_comments(
    player: models.Player,
    request: GetCommentsRequest,
    db: Session,
) -> GetCommentsResponse:
    """Handle a get_comments request."""
    # Build query
    query = (
        db.query(models.Comment)
        .options(joinedload(models.Comment.author))
        .filter(models.Comment.post_id == request.post_id)
    )

    # Filter by moderation status
    is_moderator = "moderator" in player.owner.roles or "owner" in player.owner.roles
    if not is_moderator:
        query = query.filter(~models.Comment.hidden_by_mod)

    # Filter by depth (max 2)
    query = query.filter(models.Comment.depth <= 2)

    # Order by creation time
    query = query.order_by(models.Comment.created_at.asc())

    # Apply cursor pagination
    offset = 0
    if request.cursor:
        try:
            offset = int(request.cursor)
        except ValueError:
            logger.warning(f"Invalid cursor: {request.cursor}")

    query = query.offset(offset).limit(request.limit + 1)  # +1 to check if more

    # Execute query
    comments = query.all()

    # Check if there are more results
    has_more = len(comments) > request.limit
    if has_more:
        comments = comments[: request.limit]

    # Calculate next cursor
    next_cursor = None
    if has_more:
        next_cursor = str(offset + request.limit)

    # Build comment summaries
    # Note: Deleted comments are filtered in a simplified way here.
    # A full implementation would require checking if deleted comments have children
    # and preserving them in the tree structure with modified content.
    comment_summaries = []
    for comment in comments:
        # Skip deleted comments (simplified filtering)
        if comment.deleted_by_owner:
            continue

        comment_summaries.append(
            CommentSummary(
                comment_id=comment.id,
                post_id=comment.post_id,
                author_handle=comment.author.handle if comment.author else None,
                body=comment.body,
                depth=comment.depth,
                parent_id=comment.parent_id,
                created_at=comment.created_at,
                deleted=comment.deleted_by_owner,
            )
        )

    logger.info(
        f"get_comments for player {player.player_key}: "
        f"{len(comment_summaries)} comments"
    )

    return GetCommentsResponse(
        request_id=request.request_id,
        comments=comment_summaries,
        next_cursor=next_cursor,
        has_more=has_more,
    )


def get_playset(
    player: models.Player,
    request: GetPlaysetRequest,
    db: Session,
) -> GetPlaysetResponse:
    """Handle a get_playset request.

    Unknown playset names are returned as a normal response with
    ``success=False`` and ``error_code='playset_not_found'`` (not raised), to
    preserve the established wire shape.
    """
    playset = PlaysetService.get_playset(db, player.owner, request.playset_name)

    if playset is None:
        # Unknown playset name
        return GetPlaysetResponse(
            request_id=request.request_id,
            success=False,
            error=f"Playset '{request.playset_name}' not found",
            error_code="playset_not_found",
        )

    # Convert playset channels to response format
    channels = [
        PlaysetChannelPayload(
            type=ch.type,
            name=ch.name,
            identifier=ch.identifier,
            display_name=ch.display_name,
            weight=ch.weight,
        )
        for ch in playset.channels
    ]

    logger.info(
        f"get_playset for player {player.player_key}: "
        f"playset={request.playset_name}, channels={len(channels)}"
    )

    return GetPlaysetResponse(
        request_id=request.request_id,
        success=True,
        playset_name=playset.name,
        channels=channels,
        exposure_mode=playset.exposure_mode,
        pick_mode=playset.pick_mode,
    )


def echo(
    player: models.Player,
    request: EchoRequest,
    db: Session,
) -> EchoResponse:
    """Handle an echo request for connectivity diagnostics."""
    allowed, _ = check_rate_limit(
        f"ratelimit:player:{player.id}:echo", limit=10, window_seconds=60
    )
    if not allowed:
        raise PlayerRpcError(
            "rate_limit_exceeded", "Rate limit exceeded for echo requests"
        )

    logger.info(f"echo for player {player.player_key}")

    return EchoResponse(
        request_id=request.request_id,
        echo_data=request.echo_data,
        received_at=datetime.now(timezone.utc),
    )

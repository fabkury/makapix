"""Post management endpoints."""

from __future__ import annotations

import io
import json
import logging
import os
import subprocess
import sys
import tempfile
import uuid
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse
from PIL import Image
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import (
    check_ownership,
    get_current_user,
    get_current_user_optional,
    require_moderator,
    require_ownership,
)
from ..cache import cache_get, cache_set, cache_invalidate
from ..deps import get_db
from ..pagination import (
    apply_cursor_filter,
    create_page_response,
    decode_cursor,
    encode_cursor,
)
from ..mqtt.notifications import (
    publish_new_post_notification,
    publish_category_promotion_notification,
)
from ..constants import MAX_HASHTAG_LENGTH, MAX_MOD_HASHTAGS_PER_POST
from ..utils.audit import log_moderation_action
from ..utils.hashtags import normalize_hashtags
from ..utils.monitored_hashtags import (
    apply_monitored_hashtag_filter,
    filter_posts_by_monitored_hashtags,
)
from ..utils.view_tracking import record_view, ViewType, ViewSource
from ..utils.site_tracking import record_site_event
from ..services.post_stats import annotate_posts_with_counts, get_user_liked_post_ids
from ..services.storage_quota import check_storage_quota, format_quota_error
from ..services.rate_limit import check_rate_limit
from ..services.social_notifications import SocialNotificationService
from ..errors import AppError, ErrorCode
from ..vault import (
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE_BYTES,
    MKPX_SIZE_LIMIT_BYTES,
    VaultFullError,
    compute_storage_shard,
    delete_mkpx_from_vault,
    get_artwork_url,
    save_artwork_to_vault,
    save_mkpx_to_vault,
    validate_file_size,
    validate_image_dimensions,
    validate_mkpx_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/post", tags=["Posts"])


def get_upload_rate_limit(user: models.User) -> tuple[int, int]:
    """
    Get upload rate limit based on user reputation.

    Tiers:
    - Reputation < 100: 4 uploads per hour
    - Reputation 100-499: 16 uploads per hour
    - Reputation 500+: 64 uploads per hour

    Returns:
        Tuple of (limit, window_seconds)
    """
    if user.reputation >= 500:
        return 64, 3600
    elif user.reputation >= 100:
        return 16, 3600
    else:
        return 4, 3600


def validate_mkpx_upload(mkpx: UploadFile) -> int:
    """
    Validate an uploaded .mkpx layers file: size cap + 8-byte profile
    signature, nothing deeper (docs/mkpx-upload/ D2 — opaque blob). Works on
    the multipart spool without buffering the payload; leaves the file
    positioned at 0. Returns the size in bytes.

    Raises:
        AppError: 413 mkpx_too_large / 422 mkpx_invalid
    """
    f = mkpx.file
    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(0)
    if size > MKPX_SIZE_LIMIT_BYTES:
        raise AppError(
            ErrorCode.mkpx_too_large,
            f"Layers file exceeds {MKPX_SIZE_LIMIT_BYTES} bytes.",
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )
    head = f.read(8)
    f.seek(0)
    if not validate_mkpx_signature(head):
        raise AppError(
            ErrorCode.mkpx_invalid,
            "Not a valid .mkpx layers file (unrecognized signature).",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return size


@router.get("", response_model=schemas.Page[schemas.Post])
def list_posts(
    request: Request,
    owner_id: UUID | None = None,
    hashtag: str | None = None,
    promoted: bool | None = None,
    reacted_by: UUID | None = None,
    visible_only: bool = True,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    sort: str | None = "created_at",
    order: str = Query("desc", regex="^(asc|desc)$"),
    # Filter parameters for FilterButton component
    width_min: int | None = Query(None, ge=1, le=256),
    width_max: int | None = Query(None, ge=1, le=256),
    height_min: int | None = Query(None, ge=1, le=256),
    height_max: int | None = Query(None, ge=1, le=256),
    file_bytes_min: int | None = Query(None, ge=0),
    file_bytes_max: int | None = Query(None, ge=0),
    frame_count_min: int | None = Query(None, ge=1),
    frame_count_max: int | None = Query(None, ge=1),
    unique_colors_min: int | None = Query(None, ge=1),
    unique_colors_max: int | None = Query(None, ge=1),
    reactions_min: int | None = Query(None, ge=0),
    reactions_max: int | None = Query(None, ge=0),
    comments_min: int | None = Query(None, ge=0),
    comments_max: int | None = Query(None, ge=0),
    created_after: str | None = Query(None),  # ISO date string
    created_before: str | None = Query(None),  # ISO date string
    has_transparency: bool | None = None,
    has_semitransparency: bool | None = None,
    file_format: list[str] | None = Query(None),  # PNG, GIF, WEBP, BMP
    kind: list[str] | None = Query(None),  # static, animated
    # Base/Size badge filters (new simplified dimension filtering)
    base: list[int] | None = Query(None),  # Exact base values (min dimension)
    base_gte: int | None = Query(None, ge=1),  # For 128+ case
    size: list[int] | None = Query(
        None
    ),  # Exact size values (max dimension) with OR logic
    size_gte: int | None = Query(None, ge=1),  # For 128+ case
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.Page[schemas.Post]:
    """
    List posts with filters.

    `reacted_by` restricts results to posts the given user (user_key) has
    reacted to — the "reactions channel" (docs/mqtt-api has the physical-player
    counterpart). Only authenticated reactions count, one row per post. With
    `sort=reacted_at` (valid only alongside `reacted_by`) results are ordered
    by when the user reacted.
    """
    # The web/UI post endpoints currently serve artwork posts only.
    # Playlist posts are used primarily for players (MQTT) and have a different shape.
    query = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner), joinedload(models.Post.license))
        .filter(
            models.Post.kind == "artwork",
            models.Post.deleted_by_user == False,  # Exclude user-deleted posts
            models.Post.public_sqid.isnot(None),  # Exclude posts without public_sqid
            models.Post.public_sqid != "",  # Exclude posts with empty public_sqid
        )
    )

    # Convert owner_id (UUID user_key) to integer user id if provided
    owner_user_id = None
    if owner_id:
        owner_user = (
            db.query(models.User).filter(models.User.user_key == owner_id).first()
        )
        if owner_user:
            owner_user_id = owner_user.id
            is_viewing_own_posts = (
                current_user is not None and owner_user_id == current_user.id
            )
        else:
            # User not found, return empty results
            owner_user_id = -1  # Will result in no matches
    else:
        is_viewing_own_posts = False

    if owner_user_id is not None:
        query = query.filter(models.Post.owner_id == owner_user_id)

    # Reactions channel: restrict to posts the target user has reacted to,
    # joining the latest reaction time per post (dedup — a user can react to
    # a post with several emoji). Anonymous (IP-only) reactions are excluded,
    # matching /user/u/{sqid}/reacted-posts and the player RPC channel.
    reacted_at_col = None
    if reacted_by is not None:
        from sqlalchemy import func as sa_func

        reacting_user = (
            db.query(models.User).filter(models.User.user_key == reacted_by).first()
        )
        if reacting_user is None:
            # User not found, return empty results
            query = query.filter(models.Post.id == -1)
        else:
            latest_reactions = (
                db.query(
                    models.Reaction.post_id.label("post_id"),
                    sa_func.max(models.Reaction.created_at).label("reacted_at"),
                )
                .filter(
                    models.Reaction.user_id == reacting_user.id,
                    models.Reaction.user_id.isnot(None),
                )
                .group_by(models.Reaction.post_id)
                .subquery()
            )
            query = query.join(
                latest_reactions, latest_reactions.c.post_id == models.Post.id
            )
            reacted_at_col = latest_reactions.c.reacted_at
    if sort == "reacted_at" and reacted_at_col is None:
        sort = "created_at"

    # Whitelist sort fields. Anything else used to reach getattr(Post, sort) in
    # the keyset filter and 500 (an unauthenticated vector for arbitrary input).
    if sort is None:
        sort = "created_at"
    ALLOWED_SORTS = {
        "created_at",
        "creation_date",
        "width",
        "height",
        "frame_count",
        "unique_colors",
        "file_bytes",
        "reactions",
        "reacted_at",
        "random",
    }
    if sort not in ALLOWED_SORTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid sort field: {sort}",
        )

    # Apply visibility filters
    # Note: Moderator-only visibility exceptions are handled in the Moderator Dashboard
    # endpoints (admin.py), not here. This endpoint shows the same content to all users.
    if visible_only:
        query = query.filter(models.Post.visible == True)

        # Hide posts hidden by moderators (visible only in Moderator Dashboard)
        query = query.filter(models.Post.hidden_by_mod == False)

        # Hide posts hidden by users
        query = query.filter(models.Post.hidden_by_user == False)

        # Hide non-conformant posts (visible only in Moderator Dashboard)
        query = query.filter(models.Post.non_conformant == False)

        # Apply public_visibility filter unless viewing own posts
        # Posts pending approval are visible only to their owner and in Moderator Dashboard
        if not is_viewing_own_posts:
            if reacted_by is not None and current_user is not None:
                # Reactions channel: a viewer's own posts stay visible to them
                # even when not publicly visible (mirrors
                # /user/u/{sqid}/reacted-posts).
                from sqlalchemy import or_

                query = query.filter(
                    or_(
                        models.Post.public_visibility == True,
                        models.Post.owner_id == current_user.id,
                    )
                )
            else:
                query = query.filter(models.Post.public_visibility == True)

    # Apply monitored hashtag filtering (unless viewing own posts)
    if not is_viewing_own_posts:
        query = apply_monitored_hashtag_filter(query, models.Post, current_user)

    # Hide posts by users the viewer has blocked (docs/ugc-safety/ D10)
    from ..utils.blocks import apply_block_filter

    query = apply_block_filter(
        query, models.Post.owner_id, current_user.id if current_user else None
    )

    if promoted is not None:
        query = query.filter(models.Post.promoted == promoted)

    # Implement hashtag filter using PostgreSQL array contains
    if hashtag:
        query = query.filter(models.Post.hashtags.contains([hashtag]))

    # Dimension filters
    if width_min is not None:
        query = query.filter(models.Post.width >= width_min)
    if width_max is not None:
        query = query.filter(models.Post.width <= width_max)
    if height_min is not None:
        query = query.filter(models.Post.height >= height_min)
    if height_max is not None:
        query = query.filter(models.Post.height <= height_max)

    # Frame count filter
    if frame_count_min is not None:
        query = query.filter(models.Post.frame_count >= frame_count_min)
    if frame_count_max is not None:
        query = query.filter(models.Post.frame_count <= frame_count_max)

    # Unique colors filter
    if unique_colors_min is not None:
        query = query.filter(models.Post.unique_colors >= unique_colors_min)
    if unique_colors_max is not None:
        query = query.filter(models.Post.unique_colors <= unique_colors_max)

    # Date filters
    if created_after is not None:
        from datetime import datetime

        try:
            after_date = datetime.fromisoformat(created_after.replace("Z", "+00:00"))
            query = query.filter(models.Post.created_at >= after_date)
        except ValueError:
            pass  # Invalid date format, skip filter
    if created_before is not None:
        from datetime import datetime

        try:
            before_date = datetime.fromisoformat(created_before.replace("Z", "+00:00"))
            query = query.filter(models.Post.created_at <= before_date)
        except ValueError:
            pass  # Invalid date format, skip filter

    # Boolean filters for transparency
    if has_transparency is not None:
        query = query.filter(models.Post.transparency_actual == has_transparency)
    if has_semitransparency is not None:
        query = query.filter(models.Post.alpha_actual == has_semitransparency)

    # File format + file size filters (applied to PostFile rows via EXISTS)
    if (
        (file_format and len(file_format) > 0)
        or file_bytes_min is not None
        or file_bytes_max is not None
    ):
        from sqlalchemy import exists

        pf_conditions = [models.PostFile.post_id == models.Post.id]
        if file_format and len(file_format) > 0:
            normalized_formats = [f.lower() for f in file_format]
            pf_conditions.append(models.PostFile.format.in_(normalized_formats))
        if file_bytes_min is not None:
            pf_conditions.append(models.PostFile.file_bytes >= file_bytes_min)
        if file_bytes_max is not None:
            pf_conditions.append(models.PostFile.file_bytes <= file_bytes_max)
        query = query.filter(exists().where(*pf_conditions))

    # Kind filter (static vs animated based on frame_count)
    if kind is not None and len(kind) > 0:
        from sqlalchemy import or_

        kind_conditions = []
        if "static" in kind:
            kind_conditions.append(models.Post.frame_count == 1)
        if "animated" in kind:
            kind_conditions.append(models.Post.frame_count > 1)
        if kind_conditions:
            query = query.filter(or_(*kind_conditions))

    # Base filter (exact match for values, >= for 128+)
    if base is not None and len(base) > 0:
        from sqlalchemy import or_

        if base_gte is not None:
            # Combine with OR: base in list OR base >= threshold
            query = query.filter(
                or_(models.Post.base.in_(base), models.Post.base >= base_gte)
            )
        else:
            query = query.filter(models.Post.base.in_(base))
    elif base_gte is not None:
        query = query.filter(models.Post.base >= base_gte)

    # Size filter (OR logic for multiple selections)
    if size is not None and len(size) > 0:
        from sqlalchemy import or_

        if size_gte is not None:
            # Combine size list with size >= threshold
            query = query.filter(
                or_(models.Post.size.in_(size), models.Post.size >= size_gte)
            )
        else:
            query = query.filter(models.Post.size.in_(size))
    elif size_gte is not None:
        query = query.filter(models.Post.size >= size_gte)

    # Reactions/Comments filters require subqueries
    if reactions_min is not None or reactions_max is not None:
        from sqlalchemy import func

        reaction_count_subq = (
            db.query(func.count(models.Reaction.id))
            .filter(models.Reaction.post_id == models.Post.id)
            .correlate(models.Post)
            .scalar_subquery()
        )
        if reactions_min is not None:
            query = query.filter(reaction_count_subq >= reactions_min)
        if reactions_max is not None:
            query = query.filter(reaction_count_subq <= reactions_max)

    if comments_min is not None or comments_max is not None:
        from sqlalchemy import func

        comment_count_subq = (
            db.query(func.count(models.Comment.id))
            .filter(models.Comment.post_id == models.Post.id)
            .correlate(models.Post)
            .scalar_subquery()
        )
        if comments_min is not None:
            query = query.filter(comment_count_subq >= comments_min)
        if comments_max is not None:
            query = query.filter(comment_count_subq <= comments_max)

    # ------------------------------------------------------------------
    # Keyset pagination + ordering, unified across every sort field.
    #
    # Each sort resolves to ONE `keyset_expr` (a Post column or a correlated
    # subquery). The cursor encodes that expression's value for the last row of
    # the page plus the post id as a tiebreaker, and the next page filters on the
    # SAME expression. Previously the cursor always encoded created_at regardless
    # of the active sort, so page 2 of width/height/file_bytes/reactions/... hit
    # a type mismatch or getattr(Post, sort) AttributeError — a 500.
    # ------------------------------------------------------------------
    from sqlalchemy import and_, func as sa_func, or_, select as sa_select

    sort_desc = order == "desc"

    native_bytes_subq = (
        sa_select(models.PostFile.file_bytes)
        .where(
            models.PostFile.post_id == models.Post.id,
            models.PostFile.is_native == True,
        )
        .correlate(models.Post)
        .scalar_subquery()
    )
    reaction_count_expr = sa_func.coalesce(
        db.query(sa_func.count(models.Reaction.id))
        .filter(models.Reaction.post_id == models.Post.id)
        .correlate(models.Post)
        .scalar_subquery(),
        0,
    )

    # (keyset expression, is-datetime) per sort. `reacted_at` is only present
    # when reacted_at_col was set (guaranteed by the fallback above).
    keyset_map = {
        "created_at": (models.Post.created_at, True),
        "creation_date": (models.Post.created_at, True),
        "width": (models.Post.width, False),
        "height": (models.Post.height, False),
        "frame_count": (models.Post.frame_count, False),
        "unique_colors": (models.Post.unique_colors, False),
        "file_bytes": (native_bytes_subq, False),
        "reactions": (reaction_count_expr, False),
    }
    if reacted_at_col is not None:
        keyset_map["reacted_at"] = (reacted_at_col, True)

    if sort == "random":
        # Stateless ordering — no keyset cursor.
        query = query.order_by(sa_func.random())
        posts = query.limit(limit + 1).all()[:limit]
        page_data = {"items": posts, "next_cursor": None}
    else:
        keyset_expr, keyset_is_datetime = keyset_map[sort]

        if cursor:
            cursor_data = decode_cursor(cursor)
            if cursor_data:
                last_id, sort_value = cursor_data
                try:
                    last_id = int(last_id)
                except (TypeError, ValueError):
                    last_id = None
                if keyset_is_datetime and isinstance(sort_value, str):
                    from datetime import datetime as _datetime

                    try:
                        sort_value = _datetime.fromisoformat(
                            sort_value.replace("Z", "+00:00")
                        )
                    except ValueError:
                        sort_value = None
                if last_id is not None and sort_value is not None:
                    if sort_desc:
                        query = query.filter(
                            or_(
                                keyset_expr < sort_value,
                                and_(
                                    keyset_expr == sort_value,
                                    models.Post.id < last_id,
                                ),
                            )
                        )
                    else:
                        query = query.filter(
                            or_(
                                keyset_expr > sort_value,
                                and_(
                                    keyset_expr == sort_value,
                                    models.Post.id > last_id,
                                ),
                            )
                        )

        # Order by the keyset expression, then post id as the stable tiebreaker.
        if sort_desc:
            query = query.order_by(keyset_expr.desc(), models.Post.id.desc())
        else:
            query = query.order_by(keyset_expr.asc(), models.Post.id.asc())

        # Fetch limit+1 alongside the keyset value so the next cursor can encode
        # the right field whether it is a column or a subquery.
        rows = query.add_columns(keyset_expr).limit(limit + 1).all()
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            last_post, last_key = rows[-1]
            key_encoded = (
                last_key.isoformat() if hasattr(last_key, "isoformat") else last_key
            )
            next_cursor = encode_cursor(str(last_post.id), key_encoded)
        posts = [row[0] for row in rows]
        page_data = {"items": posts, "next_cursor": next_cursor}

    # Add reaction and comment counts, and user liked status
    annotate_posts_with_counts(db, posts, current_user.id if current_user else None)

    # Record site event for page view
    record_site_event(request, "page_view", user=current_user if current_user else None)

    return schemas.Page(
        items=[schemas.Post.model_validate(p) for p in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )


@router.post(
    "/upload",
    response_model=schemas.ArtworkUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_artwork(
    request: Request,
    image: UploadFile = File(...),
    mkpx: UploadFile | None = File(None),  # Optional .mkpx layers file
    title: str = Form(..., min_length=1, max_length=128),
    description: str | None = Form(None, max_length=5000),
    hashtags: str = Form(""),  # Comma-separated hashtags
    hidden_by_user: str = Form("false"),  # User can choose to hide their artwork
    license_id: int | None = Form(None),  # Creative Commons license ID
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ArtworkUploadResponse:
    """
    Upload a single artwork image directly to the vault.

    The image must be:
    - Under 128x128: Only specific sizes allowed (8x8, 8x16, 16x16, 16x32, 32x32, 32x64, 64x64, 64x128)
    - From 128x128 to 256x256 (inclusive): Any size allowed (square or rectangular)
    - Above 256x256: Not allowed
    - Max 5 MB file size
    - PNG, GIF, WebP, or BMP format

    Public visibility is automatically set based on the user's auto_public_approval privilege.
    If the user does not have this privilege, the artwork will not appear in Recent Artworks
    until a moderator approves it.
    """
    # Rate limiting: varies by reputation (4/16/64 per hour)
    limit, window = get_upload_rate_limit(current_user)
    rate_limit_key = f"ratelimit:upload:{current_user.id}"
    allowed, _ = check_rate_limit(rate_limit_key, limit=limit, window_seconds=window)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Upload rate limit exceeded. Please try again later.",
        )

    # Read the file content
    file_content = await image.read()
    file_size = len(file_content)

    # Optional .mkpx layers file: validate before any write so a bad
    # attachment fails the whole upload atomically (docs/mkpx-upload/).
    mkpx_size = validate_mkpx_upload(mkpx) if mkpx is not None else 0

    # Check storage quota (artwork + layers file together)
    quota_allowed, used, quota = check_storage_quota(
        db, current_user, file_size + mkpx_size
    )
    if not quota_allowed:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=format_quota_error(used, quota),
        )

    # Save to temporary file for AMP inspection
    # Preserve original extension if available
    filename = image.filename or ""
    ext = ""
    if "." in filename:
        ext = "." + filename.lower().split(".")[-1]

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
        tmp_file.write(file_content)
        tmp_path = tmp_file.name

    try:
        # Call AMP inspector to validate and extract metadata
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.amp.amp_inspector",
                "--backend",
                tmp_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        # Parse JSON output
        try:
            amp_result = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse AMP inspector output: {e}\nOutput: {result.stdout}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process image. Please try again.",
            )

        # Check if AMP inspection succeeded
        if not amp_result.get("success"):
            error_info = amp_result.get("error", {})
            error_message = error_info.get(
                "message", "Unknown error during image inspection"
            )
            logger.warning(f"AMP inspection failed: {error_message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message,
            )

        # Extract metadata from AMP result
        metadata = amp_result["metadata"]
        width = metadata["width"]
        height = metadata["height"]
        file_size = metadata["file_bytes"]
        file_format = metadata["file_format"]
        frame_count = metadata["frame_count"]
        min_frame_duration_ms = metadata.get("shortest_duration_ms")
        max_frame_duration_ms = metadata.get("longest_duration_ms")
        total_duration_ms = metadata.get("total_duration_ms")
        unique_colors = metadata.get("unique_colors")
        transparency_meta = metadata.get("transparency_meta", False)
        alpha_meta = metadata.get("alpha_meta", False)
        transparency_actual = metadata.get("transparency_actual", False)
        alpha_actual = metadata.get("alpha_actual", False)

    finally:
        # Clean up temporary file
        try:
            os.unlink(tmp_path)
        except Exception as e:
            logger.warning(f"Failed to delete temp file {tmp_path}: {e}")

    # AMP now provides sha256 after Phase B (after Pillow is done with the file).
    file_hash = metadata.get("sha256")
    if not file_hash:
        logger.error("AMP result missing sha256")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process image. Please try again.",
        )

    # Parse hashtags (comma-separated)
    parsed_hashtags = normalize_hashtags(hashtags.split(","), cap=64)

    # Determine public visibility based on user's auto_public_approval privilege
    public_visibility = getattr(current_user, "auto_public_approval", False)

    # Parse hidden_by_user from form (string "true"/"false" to bool)
    user_hidden = hidden_by_user.lower() in ("true", "1", "yes")

    # Validate license_id if provided; null means "All rights reserved".
    if license_id is not None:
        license_obj = (
            db.query(models.License).filter(models.License.id == license_id).first()
        )
        if not license_obj:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid license_id",
            )

    # Generate UUID for storage_key and pre-compute storage shard
    storage_key = uuid.uuid4()
    storage_shard = compute_storage_shard(storage_key)

    # Create the post record first to get the ID
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    post = models.Post(
        storage_key=storage_key,
        storage_shard=storage_shard,
        owner_id=current_user.id,
        kind="artwork",
        title=title,
        description=description,
        hashtags=parsed_hashtags,
        art_url="",  # Will be updated after saving to vault
        width=width,
        height=height,
        frame_count=frame_count,
        min_frame_duration_ms=min_frame_duration_ms,
        max_frame_duration_ms=max_frame_duration_ms,
        total_duration_ms=total_duration_ms,
        unique_colors=unique_colors,
        transparency_meta=transparency_meta,
        alpha_meta=alpha_meta,
        transparency_actual=transparency_actual,
        alpha_actual=alpha_actual,
        hash=file_hash,
        public_visibility=public_visibility,
        hidden_by_user=user_hidden,
        metadata_modified_at=now,
        artwork_modified_at=now,
        dwell_time_ms=30000,
        license_id=license_id,
    )
    # Fast-path duplicate check (user-friendly error); partial unique index is the
    # authoritative protection against races.
    existing = (
        db.query(models.Post)
        .filter(
            models.Post.kind == "artwork",
            models.Post.hash == file_hash,
            models.Post.deleted_by_user == False,  # Only check non-deleted posts
        )
        .first()
    )
    if existing:
        raise AppError(
            ErrorCode.artwork_duplicate,
            "This artwork already exists.",
            status.HTTP_409_CONFLICT,
            details={"post_id": existing.id, "sqid": existing.public_sqid},
        )

    # Insert first (flush) so the UNIQUE constraint prevents races *before* we
    # write to the vault (avoids orphan vault files on duplicate uploads).
    try:
        db.add(post)
        db.flush()  # Get the post ID without committing
    except IntegrityError:
        db.rollback()
        dup = (
            db.query(models.Post)
            .filter(
                models.Post.kind == "artwork",
                models.Post.hash == file_hash,
                models.Post.deleted_by_user == False,
            )
            .first()
        )
        raise AppError(
            ErrorCode.artwork_duplicate,
            "This artwork already exists.",
            status.HTTP_409_CONFLICT,
            details=({"post_id": dup.id, "sqid": dup.public_sqid} if dup else None),
        )

    # Create native PostFile row
    native_file = models.PostFile(
        post_id=post.id,
        format=file_format,
        file_bytes=file_size,
        is_native=True,
    )
    db.add(native_file)

    # Generate public_sqid from the assigned id
    from ..sqids_config import encode_id

    post.public_sqid = encode_id(post.id)

    # Save to vault using the storage_key
    artwork_path = None
    mkpx_saved = False
    try:
        from ..vault import FORMAT_TO_EXT

        extension = FORMAT_TO_EXT[file_format]
        artwork_path = save_artwork_to_vault(
            post.storage_key,
            file_content,
            file_format,
            storage_shard=post.storage_shard,
        )

        # Update the art_url to point to the vault
        art_url = get_artwork_url(
            post.storage_key, extension, storage_shard=post.storage_shard
        )
        post.art_url = art_url

        # Optional .mkpx layers file (already validated above)
        if mkpx is not None:
            save_mkpx_to_vault(
                post.storage_key,
                mkpx.file,
                mkpx_size,
                storage_shard=post.storage_shard,
            )
            mkpx_saved = True
            post.mkpx_file_bytes = mkpx_size
            post.mkpx_attached_at = now

        db.commit()
        db.refresh(post)
    except Exception as e:
        db.rollback()
        # Don't strand just-written files (the likely failure — a full
        # disk — is exactly when orphans hurt most).
        if artwork_path is not None:
            try:
                artwork_path.unlink(missing_ok=True)
            except OSError:
                pass
        if mkpx is not None and mkpx_saved:
            delete_mkpx_from_vault(post.storage_key, post.storage_shard)
        if isinstance(e, VaultFullError):
            logger.error(f"Vault below free-space floor during upload: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage temporarily unavailable. Please try again later.",
            )
        logger.error(f"Failed to save artwork to vault: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save artwork. Please try again.",
        )

    # Queue SSAFPP task for format conversion and upscaling
    try:
        from ..tasks import process_ssafpp

        process_ssafpp.delay(post.id)
    except Exception as e:
        logger.error(f"Failed to queue SSAFPP task for post {post.id}: {e}")

    # Invalidate feed caches since a new post was created
    if public_visibility:
        cache_invalidate("feed:recent:*")
    cache_invalidate("hashtags:*")

    # Publish MQTT notification to followers
    try:
        publish_new_post_notification(post.id, db)
    except Exception as e:
        logger.error(f"Failed to publish MQTT notification for post {post.id}: {e}")

    message = "Artwork uploaded successfully"
    if not public_visibility:
        message += ". Awaiting moderator approval for public visibility."

    # Record site event for upload
    record_site_event(request, "upload", user=current_user)

    return schemas.ArtworkUploadResponse(
        post=schemas.Post.model_validate(post),
        message=message,
    )


@router.get("/recent", response_model=schemas.Page[schemas.Post])
def list_recent_posts(
    request: Request,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.Page[schemas.Post]:
    """
    List recent posts (visible only) with infinite scroll support.

    Returns recent posts ordered by creation date (newest first).
    Uses cursor-based pagination for efficient infinite scroll.
    Cached for 2 minutes due to high churn rate.
    """
    # Create cache key based on cursor and limit
    # All users see the same results (moderator-only views are in Moderator Dashboard)
    cache_key = f"feed:recent:{cursor or 'first'}:{limit}"

    # Try to get from cache
    cached_result = cache_get(cache_key)
    if cached_result:
        response = schemas.Page(**cached_result)
        # Apply monitored hashtag filtering (user-specific)
        response.items = filter_posts_by_monitored_hashtags(
            response.items, current_user
        )
        # Apply block filtering (user-specific, post-cache; docs/ugc-safety/ D10)
        from ..utils.blocks import filter_items_by_blocks

        response.items = filter_items_by_blocks(
            response.items, db, current_user.id if current_user else None
        )
        # Add user-specific like status if authenticated
        if current_user and response.items:
            post_ids = [item.id for item in response.items]
            liked_ids = get_user_liked_post_ids(db, post_ids, current_user.id)
            for item in response.items:
                item.user_has_liked = item.id in liked_ids
        # Record site event for page view (even on cache hit)
        record_site_event(request, "page_view", user=current_user)
        return response

    query = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner), joinedload(models.Post.license))
        .filter(
            models.Post.kind == "artwork",
            models.Post.visible == True,
            models.Post.hidden_by_mod == False,
            models.Post.hidden_by_user == False,
            models.Post.non_conformant == False,
            models.Post.public_visibility == True,  # Only show publicly visible posts
            models.Post.deleted_by_user == False,  # Exclude user-deleted posts
        )
    )

    # Note: Monitored hashtag filtering is applied in-memory after fetching
    # because this endpoint uses a shared cache across all users.

    # Apply cursor pagination
    query = apply_cursor_filter(
        query, models.Post, cursor, "created_at", sort_desc=True
    )

    # Order and limit
    query = query.order_by(models.Post.created_at.desc())

    # Fetch limit + 1 to check if there are more results
    posts = query.limit(limit + 1).all()

    # Add reaction and comment counts, and user liked status
    annotate_posts_with_counts(db, posts, current_user.id if current_user else None)

    # Create paginated response
    page_data = create_page_response(posts, limit, cursor, "created_at")

    response = schemas.Page(
        items=[schemas.Post.model_validate(p) for p in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )

    # Cache for 2 minutes (120 seconds) - shorter due to high churn
    # Note: Cache stores base data; monitored hashtag filtering and user_has_liked
    # are applied when retrieving from cache
    cache_set(cache_key, response.model_dump(), ttl=120)

    # Apply monitored hashtag filtering (user-specific, after caching)
    response.items = filter_posts_by_monitored_hashtags(response.items, current_user)

    # Apply block filtering (user-specific, after caching; docs/ugc-safety/ D10)
    from ..utils.blocks import filter_items_by_blocks

    response.items = filter_items_by_blocks(
        response.items, db, current_user.id if current_user else None
    )

    # Record site event for page view
    record_site_event(request, "page_view", user=current_user)

    return response


@router.get("/{storage_key}", response_model=schemas.Post)
def get_post_by_storage_key(
    storage_key: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.Post:
    """
    Legacy route: Get post by storage key (UUID).

    Returns the full post data. The canonical URL is /p/{public_sqid}.
    """
    from ..utils.visibility import can_access_post
    from ..services.post_stats import annotate_posts_with_counts

    # Query post with owner and license relationships
    post = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner), joinedload(models.Post.license))
        .filter(models.Post.storage_key == storage_key, models.Post.kind == "artwork")
        .first()
    )

    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    # Check visibility
    if not can_access_post(post, current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    # Add reaction and comment counts
    annotate_posts_with_counts(db, [post], current_user.id if current_user else None)

    # Record site event for page view (sitewide stats)
    record_site_event(request, "page_view", user=current_user)

    # Record view event for post stats (excludes author views)
    record_view(
        db=db,
        post_id=post.id,
        request=request,
        user=current_user,
        view_type=ViewType.INTENTIONAL,
        view_source=ViewSource.WEB,
        post_owner_id=post.owner_id,
    )

    return schemas.Post.model_validate(post)


@router.post("/{id}/view", status_code=status.HTTP_204_NO_CONTENT)
async def register_view(
    id: int,
    request: Request,
    payload: schemas.ViewRegisterPayload | None = None,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> None:
    """
    Register a view on a post.

    Body-less requests come from the Selected Post Overlay and are recorded
    as INTENTIONAL views. Requests with a body come from the Web Player and
    are recorded as LISTING views with channel/play_order metadata.
    """
    from ..services.rate_limit import check_web_view_rate_limit
    from ..utils.view_tracking import hash_ip

    # Rate limit: 1 view per 3 seconds per user
    ip = request.client.host if request.client else "unknown"
    ip_hash = hash_ip(ip)
    user_id = current_user.id if current_user else None

    allowed, retry_after = check_web_view_rate_limit(user_id, ip_hash)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many view requests",
            headers={"Retry-After": str(int(retry_after or 3))},
        )

    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if payload is None:
        record_view(
            db=db,
            post_id=post.id,
            request=request,
            user=current_user,
            view_type=ViewType.INTENTIONAL,
            view_source=ViewSource.WEB,
            post_owner_id=post.owner_id,
        )
    else:
        record_view(
            db=db,
            post_id=post.id,
            request=request,
            user=current_user,
            view_type=ViewType.LISTING,
            view_source=ViewSource.WEB,
            post_owner_id=post.owner_id,
            channel=payload.channel,
            channel_context=payload.channel_context,
            play_order=payload.play_order,
        )


@router.patch("/{id}", response_model=schemas.Post)
def update_post(
    id: int,
    payload: schemas.PostUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Post:
    """
    Update post fields.

    TODO: Re-extract hashtags if title/description changed
    """
    # FOR UPDATE: hashtag writes are read-modify-write against mod_hashtags;
    # without the lock a concurrent mod-hashtags PUT can be silently undone
    # (docs/mod-hashtags/DECISIONS.md D17).
    post = db.query(models.Post).filter(models.Post.id == id).with_for_update().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    require_ownership(post.owner_id, current_user)

    hashtags_changed = False
    if payload.title is not None:
        post.title = payload.title
    if payload.description is not None:
        post.description = payload.description
    if payload.hashtags is not None:
        # The submitted list is the artist-controlled tags; mod-owned tags are
        # re-merged so artists can't remove them (docs/mod-hashtags/ D10).
        artist_tags = normalize_hashtags(payload.hashtags, cap=64)
        mod_tags = post.mod_hashtags or []
        new_hashtags = artist_tags + [t for t in mod_tags if t not in artist_tags]
        hashtags_changed = new_hashtags != post.hashtags
        post.hashtags = new_hashtags
    if payload.hidden_by_user is not None:
        post.hidden_by_user = payload.hidden_by_user
    if payload.hidden_by_mod is not None:
        # Only moderators may change moderation-hide state (D21).
        roles = current_user.roles or []
        if "moderator" in roles or "owner" in roles:
            post.hidden_by_mod = payload.hidden_by_mod

    from datetime import datetime, timezone

    post.metadata_modified_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(post)

    if hashtags_changed:
        cache_invalidate("feed:recent:*")
        cache_invalidate("feed:promoted:*")
        cache_invalidate("hashtags:*")

    return schemas.Post.model_validate(post)


@router.put(
    "/{id}/mod-hashtags",
    response_model=schemas.Post,
    tags=["Admin"],
)
def update_mod_hashtags(
    id: int,
    payload: schemas.ModHashtagsUpdate,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> schemas.Post:
    """
    Replace a post's moderator-owned hashtags (moderator only).

    Full replace of the mod set: tags added to the mod set are also added to
    the effective `hashtags` (claiming them if the artist already had them);
    tags removed from the mod set are removed from `hashtags` entirely.
    See docs/mod-hashtags/API-CONTRACT.md.
    """
    # FOR UPDATE: see update_post (D17).
    post = db.query(models.Post).filter(models.Post.id == id).with_for_update().first()
    # Playlist rows can't serialize as schemas.Post, and a soft-deleted post
    # would notify the artist with a dead link (D18).
    if not post or post.kind != "artwork" or post.deleted_by_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    new_mod = normalize_hashtags(payload.hashtags, cap=None)
    if len(new_mod) > MAX_MOD_HASHTAGS_PER_POST:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"At most {MAX_MOD_HASHTAGS_PER_POST} moderator hashtags per "
                f"post ({len(new_mod)} after normalization)."
            ),
        )
    too_long = [t for t in new_mod if len(t) > MAX_HASHTAG_LENGTH]
    if too_long:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Hashtags longer than {MAX_HASHTAG_LENGTH} characters: "
                f"{', '.join(too_long)}"
            ),
        )

    old_mod = post.mod_hashtags or []
    added = [t for t in new_mod if t not in old_mod]
    removed = [t for t in old_mod if t not in new_mod]

    # Build fresh lists (ARRAY columns aren't mutation-tracked). The append
    # line runs even on a no-op replace so re-submitting the same set repairs
    # a corrupted mod_hashtags ⊆ hashtags invariant (D17).
    effective = [t for t in (post.hashtags or []) if t not in removed]
    effective += [t for t in new_mod if t not in effective]
    post.hashtags = effective
    post.mod_hashtags = new_mod

    from datetime import datetime, timezone

    post.metadata_modified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(post)

    cache_invalidate("feed:recent:*")
    cache_invalidate("feed:promoted:*")
    cache_invalidate("hashtags:*")

    if added or removed:
        diff = " ".join([f"+#{t}" for t in added] + [f"−#{t}" for t in removed])
        log_moderation_action(
            db=db,
            actor_id=moderator.id,
            action="update_mod_hashtags",
            target_type="post",
            target_id=id,
            reason_code=payload.reason_code,
            note=f"{diff} — {payload.note}" if payload.note else diff,
        )
        # Delivered to clients in `comment_preview` (D13); the service
        # self-skips when the moderator edits their own post.
        SocialNotificationService.create_notification(
            db=db,
            user_id=post.owner_id,
            notification_type="mod_hashtags_updated",
            post=post,
            actor=moderator,
            extra_preview=diff,
        )

    return schemas.Post.model_validate(post)


def _get_mkpx_target_post(db: Session, id: int) -> models.Post:
    """Fetch a post for mkpx attach/detach: artwork kind, not soft-deleted.

    Soft-deleted posts are 404 even for the author; playlist posts can never
    carry a layers file (docs/mkpx-upload/API-CONTRACT.md §7).
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post or post.kind != "artwork" or post.deleted_by_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )
    return post


@router.post("/{id}/mkpx", response_model=schemas.Post)
async def attach_mkpx(
    id: int,
    mkpx: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Post:
    """
    Attach an .mkpx layers file to an existing post, or silently replace the
    one already attached (author only; docs/mkpx-upload/). Consumes an
    upload rate-limit token; the file counts toward the owner's storage
    quota (replacement counts only the delta).
    """
    post = _get_mkpx_target_post(db, id)
    require_ownership(post.owner_id, current_user)

    # Attach/replace shares the upload rate-limit bucket (D9)
    limit, window = get_upload_rate_limit(current_user)
    rate_limit_key = f"ratelimit:upload:{current_user.id}"
    allowed, _ = check_rate_limit(rate_limit_key, limit=limit, window_seconds=window)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Upload rate limit exceeded. Please try again later.",
        )

    mkpx_size = validate_mkpx_upload(mkpx)

    # Quota counts against the post owner (== current_user unless a
    # moderator is acting); replacement counts only the delta.
    delta = mkpx_size - (post.mkpx_file_bytes or 0)
    if delta > 0:
        owner = post.owner or current_user
        quota_allowed, used, quota = check_storage_quota(db, owner, delta)
        if not quota_allowed:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=format_quota_error(used, quota),
            )

    from datetime import datetime, timezone

    try:
        save_mkpx_to_vault(
            post.storage_key,
            mkpx.file,
            mkpx_size,
            storage_shard=post.storage_shard,
        )
    except VaultFullError as e:
        logger.error(f"Vault below free-space floor during mkpx attach: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage temporarily unavailable. Please try again later.",
        )
    except (OSError, ValueError) as e:
        logger.error(f"Failed to save mkpx for post {id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save layers file. Please try again.",
        )

    now = datetime.now(timezone.utc)
    post.mkpx_file_bytes = mkpx_size
    post.mkpx_attached_at = now
    post.metadata_modified_at = now
    db.commit()
    db.refresh(post)

    return schemas.Post.model_validate(post)


@router.delete("/{id}/mkpx", response_model=schemas.Post)
def detach_mkpx(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Post:
    """
    Remove the attached .mkpx layers file (author only). 404 if the post has
    none. Consumes no rate-limit token (docs/mkpx-upload/ D9).
    """
    post = _get_mkpx_target_post(db, id)
    require_ownership(post.owner_id, current_user)

    if post.mkpx_file_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post has no layers file attached",
        )

    # Best-effort file removal; the DB columns are the source of truth and
    # a stray file (guarded from public serving) beats a failed request.
    delete_mkpx_from_vault(post.storage_key, post.storage_shard)

    from datetime import datetime, timezone

    post.mkpx_file_bytes = None
    post.mkpx_attached_at = None
    post.metadata_modified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(post)

    return schemas.Post.model_validate(post)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Delete post (soft delete).

    Sets deleted_by_user=True and schedules for permanent deletion after 7 days.
    The artwork hash is immediately freed for re-upload.
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    require_ownership(post.owner_id, current_user)

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    # Mark as deleted by user (frees hash for re-upload)
    post.deleted_by_user = True
    post.deleted_by_user_date = now

    # Keep existing visibility flags for backward compatibility
    post.visible = False
    post.hidden_by_user = True
    db.commit()

    # Invalidate feed caches
    cache_invalidate("feed:recent:*")
    cache_invalidate("feed:promoted:*")
    cache_invalidate("hashtags:*")


@router.delete(
    "/{id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Posts", "Admin"],
)
def permanent_delete_post(
    id: int,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Permanently delete a post (moderator only).

    This action cannot be undone. This also removes the artwork image from the vault.
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    # Delete all artwork format variants + upscaled version
    if post.storage_key:
        from app import vault

        try:
            formats_to_delete = [pf.format for pf in post.files] or []
            vault.delete_all_artwork_formats(
                post.storage_key, formats_to_delete, storage_shard=post.storage_shard
            )
        except Exception as e:
            logger.warning(f"Failed to delete artwork files for post {id}: {e}")

        # Attached .mkpx layers file, if any (best-effort, like the above)
        if post.mkpx_file_bytes is not None:
            delete_mkpx_from_vault(post.storage_key, post.storage_shard)

    # Log to audit before deletion
    # Wrap in try-except to prevent audit logging failures from blocking deletion
    try:
        post_title = post.title or "Untitled"
        log_moderation_action(
            db=db,
            actor_id=moderator.id,
            action="permanent_delete_post",
            target_type="post",
            target_id=id,
            note=f"Permanently deleted post: {post_title}",
        )
    except Exception as e:
        logger.error(
            f"Failed to log moderation action for permanent delete of post {id}: {e}",
            exc_info=True,
        )
        # Continue with deletion even if audit logging fails

    # Delete the post from database
    try:
        db.delete(post)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to delete post {id} from database: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete post: {str(e)}",
        )

    # Invalidate caches
    try:
        cache_invalidate("feed:recent:*")
        cache_invalidate("feed:promoted:*")
        cache_invalidate("hashtags:*")
    except Exception as e:
        logger.warning(f"Failed to invalidate caches after deleting post {id}: {e}")


@router.post("/{id}/hide", status_code=status.HTTP_201_CREATED)
def hide_post(
    id: int,
    payload: schemas.HideRequest | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Hide post.

    TODO: Validate that user is owner or moderator
    TODO: If by=mod, log in audit log
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    by = payload.by if payload else "user"

    if by == "mod":
        # Check moderator role
        if "moderator" not in current_user.roles and "owner" not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Moderator role required to hide posts as moderator",
            )
        post.hidden_by_mod = True
        # Log to audit
        log_moderation_action(
            db=db,
            actor_id=current_user.id,
            action="hide_post",
            target_type="post",
            target_id=id,
            reason_code=payload.reason_code if payload else None,
            note=payload.note or (payload.reason if payload else None),
        )
    else:
        require_ownership(post.owner_id, current_user)
        post.hidden_by_user = True

    db.commit()

    # Invalidate feed caches since post visibility changed
    cache_invalidate("feed:recent:*")
    cache_invalidate("feed:promoted:*")
    cache_invalidate("hashtags:*")


@router.delete("/{id}/hide", status_code=status.HTTP_204_NO_CONTENT)
def unhide_post(
    id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Unhide post.

    Note: Posts that have been deleted by the user cannot be restored.
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    # Prevent restoring deleted posts
    if post.deleted_by_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deleted posts cannot be restored",
        )

    # Check if user is owner or moderator
    is_moderator = "moderator" in current_user.roles or "owner" in current_user.roles
    if not is_moderator:
        require_ownership(post.owner_id, current_user)

    post.hidden_by_user = False
    # Moderators can unhide mod-hidden posts
    if is_moderator and post.hidden_by_mod:
        post.hidden_by_mod = False
        # Log to audit
        log_moderation_action(
            db=db,
            actor_id=current_user.id,
            action="unhide_post",
            target_type="post",
            target_id=id,
        )
    db.commit()

    # Invalidate feed caches since post visibility changed
    cache_invalidate("feed:recent:*")
    cache_invalidate("feed:promoted:*")
    cache_invalidate("hashtags:*")


@router.post(
    "/{id}/promote",
    response_model=schemas.PromotePostResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Admin"],
)
def promote_post(
    id: int,
    payload: schemas.PromotePostRequest,
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.PromotePostResponse:
    """
    Promote post (moderator only).

    TODO: Log in audit log
    TODO: Publish MQTT notification
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    post.promoted = True
    post.promoted_category = payload.category
    db.commit()

    # Invalidate promoted feed cache
    cache_invalidate("feed:promoted:*")

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=_moderator.id,
        action="promote_post",
        target_type="post",
        target_id=id,
        reason_code=payload.reason_code,
        note=payload.note,
    )

    # Notify the artwork owner about the promotion
    _CATEGORY_DISPLAY = {
        "frontpage": "Recommended",
        "editor-pick": "Editor's Pick",
        "weekly-pack": "Weekly Pack",
        "daily's-best": "Daily's Best",
    }
    SocialNotificationService.create_notification(
        db=db,
        user_id=post.owner_id,
        notification_type="post_promoted",
        post=post,
        actor=_moderator,
        extra_preview=_CATEGORY_DISPLAY.get(payload.category, payload.category),
    )

    # Publish MQTT notification if promoted to "daily's-best"
    if payload.category == "daily's-best":
        try:
            publish_category_promotion_notification(post.id, payload.category, db)
        except Exception as e:
            # Log error but don't fail the request
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Failed to publish MQTT notification for category promotion: {e}"
            )

    return schemas.PromotePostResponse(promoted=True, category=payload.category)


@router.delete(
    "/{id}/promote",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Admin"],
)
def demote_post(
    id: int,
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Demote post (moderator only).

    TODO: Log in audit log
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    post.promoted = False
    post.promoted_category = None
    db.commit()

    # Invalidate promoted feed cache
    cache_invalidate("feed:promoted:*")

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=_moderator.id,
        action="demote_post",
        target_type="post",
        target_id=id,
    )


@router.post(
    "/{id}/approve-public",
    response_model=schemas.PublicVisibilityResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Admin"],
)
def approve_public_visibility(
    id: int,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> schemas.PublicVisibilityResponse:
    """
    Approve public visibility for an artwork (moderator only).

    This allows the artwork to appear in Recent Artworks, search results,
    and other public browsing pages.
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    post.public_visibility = True
    db.commit()

    # Invalidate feed caches since public visibility changed
    cache_invalidate("feed:recent:*")
    cache_invalidate("hashtags:*")

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="approve_public_visibility",
        target_type="post",
        target_id=id,
    )

    return schemas.PublicVisibilityResponse(post_id=id, public_visibility=True)


@router.delete(
    "/{id}/approve-public",
    response_model=schemas.PublicVisibilityResponse,
    tags=["Admin"],
)
def revoke_public_visibility(
    id: int,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> schemas.PublicVisibilityResponse:
    """
    Revoke public visibility for an artwork (moderator only).

    This hides the artwork from Recent Artworks, search results,
    and other public browsing pages. The artwork will still be
    visible on the owner's profile page.
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    post.public_visibility = False
    db.commit()

    # Invalidate feed caches since public visibility changed
    cache_invalidate("feed:recent:*")
    cache_invalidate("hashtags:*")

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="revoke_public_visibility",
        target_type="post",
        target_id=id,
    )

    return schemas.PublicVisibilityResponse(post_id=id, public_visibility=False)


@router.post("/{id}/replace-artwork")
async def replace_artwork(
    id: int,
    image: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Replace the artwork of an existing post (Piskel edit feature)"""
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post or post.kind != "artwork":
        raise HTTPException(status_code=404, detail="Post not found")

    if post.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to modify this post",
        )

    # Rate-limit replacements on the shared upload bucket. Without this, replace
    # is an unbounded disk/CPU amplification loop: each call writes up to 5 MB,
    # parks the previous key's files for 7 days outside quota, and queues a
    # Pillow conversion on the single worker.
    limit, window = get_upload_rate_limit(current_user)
    allowed, _ = check_rate_limit(
        f"ratelimit:upload:{current_user.id}", limit=limit, window_seconds=window
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Upload rate limit exceeded. Please try again later.",
        )

    file_content = await image.read()
    file_size = len(file_content)
    # NOTE: previously the return value was ignored, so oversize replacements
    # slipped through. Enforce it with a typed error.
    size_ok, size_err = validate_file_size(file_size)
    if not size_ok:
        raise AppError(
            ErrorCode.file_too_large,
            size_err or "File too large.",
            413,
        )

    # Charge the storage delta (new native bytes vs the current native file), so
    # a user at quota can't grow their footprint by replacing small files with
    # large ones.
    old_native_bytes = next((pf.file_bytes for pf in post.files if pf.is_native), 0)
    delta = file_size - (old_native_bytes or 0)
    if delta > 0:
        owner = post.owner or current_user
        quota_allowed, used, quota = check_storage_quota(db, owner, delta)
        if not quota_allowed:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=format_quota_error(used, quota),
            )

    # Save to temporary file for AMP inspection (preserve extension if possible)
    filename = image.filename or ""
    ext = ""
    if "." in filename:
        ext = "." + filename.lower().split(".")[-1]

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
        tmp_file.write(file_content)
        tmp_path = tmp_file.name

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.amp.amp_inspector",
                "--backend",
                tmp_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        try:
            amp_result = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse AMP inspector output: {e}\nOutput: {result.stdout}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process image. Please try again.",
            )

        if not amp_result.get("success"):
            error_info = amp_result.get("error", {})
            error_message = error_info.get(
                "message", "Unknown error during image inspection"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message,
            )

        metadata = amp_result["metadata"]
        width = metadata["width"]
        height = metadata["height"]
        file_bytes = metadata["file_bytes"]
        file_format = metadata["file_format"]
        frame_count = metadata["frame_count"]
        min_frame_duration_ms = metadata.get("shortest_duration_ms")
        max_frame_duration_ms = metadata.get("longest_duration_ms")
        total_duration_ms = metadata.get("total_duration_ms")
        unique_colors = metadata.get("unique_colors")
        transparency_meta = metadata.get("transparency_meta", False)
        alpha_meta = metadata.get("alpha_meta", False)
        transparency_actual = metadata.get("transparency_actual", False)
        alpha_actual = metadata.get("alpha_actual", False)
        file_hash = metadata.get("sha256")
        if not file_hash:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process image. Please try again.",
            )

        # Disallow redundant replacement (same hash as current artwork)
        if post.hash and file_hash == post.hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Artwork is identical to current artwork",
            )

        # Also disallow replacing with an artwork that already exists elsewhere
        existing = (
            db.query(models.Post)
            .filter(
                models.Post.kind == "artwork",
                models.Post.hash == file_hash,
                models.Post.id != post.id,
                models.Post.deleted_by_user == False,  # Only check non-deleted posts
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Artwork already exists",
            )

    finally:
        try:
            os.unlink(tmp_path)
        except Exception as e:
            logger.warning(f"Failed to delete temp file {tmp_path}: {e}")

    from ..vault import FORMAT_TO_EXT

    # Snapshot the old identity before any mutation. The old files stay on
    # disk (servable at the old URL) for a 7-day grace period — laggard
    # player devices and cached URLs — tracked by a RetiredArtwork row and
    # swept by cleanup_retired_artwork.
    old_storage_key = post.storage_key
    old_storage_shard = post.storage_shard
    old_formats = [pf.format for pf in post.files]
    had_mkpx = post.mkpx_file_bytes is not None

    # Rotate the storage key: the vault serves with `immutable` caching, so
    # replaced bytes must live at a new URL or every HTTP-correct cache keeps
    # showing the old artwork (message/0002).
    new_storage_key = uuid.uuid4()
    new_storage_shard = compute_storage_shard(new_storage_key)
    new_extension = FORMAT_TO_EXT[file_format]
    new_art_url = get_artwork_url(
        new_storage_key, new_extension, storage_shard=new_storage_shard
    )

    # Update post first (flush) so UNIQUE constraint blocks races before vault write
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    post.storage_key = new_storage_key
    post.storage_shard = new_storage_shard
    post.art_url = new_art_url
    post.width = width
    post.height = height
    post.frame_count = frame_count
    post.min_frame_duration_ms = min_frame_duration_ms
    post.max_frame_duration_ms = max_frame_duration_ms
    post.total_duration_ms = total_duration_ms
    post.unique_colors = unique_colors
    post.transparency_meta = transparency_meta
    post.alpha_meta = alpha_meta
    post.transparency_actual = transparency_actual
    post.alpha_actual = alpha_actual
    post.hash = file_hash
    post.metadata_modified_at = now
    post.artwork_modified_at = now

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Artwork already exists",
        )

    # Delete all existing PostFile rows and create new native row
    for pf in list(post.files):
        db.delete(pf)
    db.flush()
    native_file = models.PostFile(
        post_id=post.id,
        format=file_format,
        file_bytes=file_bytes,
        is_native=True,
    )
    db.add(native_file)

    # Replacing the artwork drops any attached .mkpx layers file — it would
    # no longer match the rendered artwork (docs/mkpx-upload/ D4). Columns
    # ride the commit (has_mkpx flips false and downloads 404 immediately,
    # per the frozen contract §10.1); the physical file belongs to the old
    # artwork version and is unlinked with it by the retirement sweep.
    if had_mkpx:
        post.mkpx_file_bytes = None
        post.mkpx_attached_at = None

    # Record the old identity for the 7-day deferred sweep. Rides the same
    # transaction as the key rotation, so a rollback leaves no stray row.
    # No shard means no vault files at the old key (e.g. an imported post
    # whose art_url was external) — nothing to retire.
    if old_storage_shard:
        db.add(
            models.RetiredArtwork(
                post_id=post.id,
                storage_key=old_storage_key,
                storage_shard=old_storage_shard,
                formats=old_formats,
                had_mkpx=had_mkpx,
                delete_after=now + timedelta(days=7),
            )
        )

    # Re-point persisted notification thumbnails at the new URL — the old
    # one 404s once the grace period ends.
    db.query(models.SocialNotification).filter(
        models.SocialNotification.post_id == post.id,
        models.SocialNotification.content_art_url.isnot(None),
    ).update({"content_art_url": new_art_url}, synchronize_session=False)

    # Write the new vault file, then commit. The old file is never touched
    # here, so any failure leaves the post fully consistent on the old key;
    # the only stranding risk is the just-written new file, unlinked below.
    artwork_path = None
    try:
        artwork_path = save_artwork_to_vault(
            new_storage_key,
            file_content,
            file_format,
            storage_shard=new_storage_shard,
        )
        db.commit()
        db.refresh(post)
    except Exception as e:
        db.rollback()
        if artwork_path is not None:
            try:
                artwork_path.unlink(missing_ok=True)
            except OSError:
                pass
        if isinstance(e, VaultFullError):
            logger.error(f"Vault below free-space floor during replace: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage temporarily unavailable. Please try again later.",
            )
        logger.error(f"Failed to replace artwork in vault: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save artwork. Please try again.",
        )

    # Queue SSAFPP for format conversion and upscaling — mandatory after
    # rotation (the new key has no derived files yet).
    try:
        from ..tasks import process_ssafpp

        process_ssafpp.delay(post.id)
    except Exception as e:
        logger.error(f"Failed to queue SSAFPP task for post {post.id}: {e}")

    # Cached feed payloads embed art_url, which just changed
    cache_invalidate("feed:recent:*")
    cache_invalidate("feed:promoted:*")

    logger.info(
        "Artwork replaced for post %s by user %s",
        post.public_sqid,
        current_user.public_sqid,
    )

    return {
        "message": "Artwork replaced successfully",
        "post": {
            "id": post.id,
            "public_sqid": post.public_sqid,
            "art_url": post.art_url,
            "width": post.width,
            "height": post.height,
            "frame_count": post.frame_count,
        },
    }


@router.get(
    "/{id}/admin-notes",
    response_model=schemas.AdminNoteList,
    tags=["Admin"],
)
def list_post_admin_notes(
    id: int,
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.AdminNoteList:
    """
    List admin notes for a post (moderator only).
    """
    notes = (
        db.query(models.AdminNote)
        .filter(models.AdminNote.post_id == id)
        .order_by(models.AdminNote.created_at.desc())
        .all()
    )

    return schemas.AdminNoteList(
        items=[schemas.AdminNoteItem.model_validate(n) for n in notes]
    )


@router.post(
    "/{id}/admin-notes",
    status_code=status.HTTP_201_CREATED,
    tags=["Admin"],
)
def add_post_admin_note(
    id: int,
    payload: schemas.AdminNoteCreate,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Add admin note to a post (moderator only).

    TODO: Validate that post exists
    """
    note = models.AdminNote(
        post_id=id,
        created_by=moderator.id,
        note=payload.note,
    )
    db.add(note)
    db.commit()


@router.delete(
    "/admin-notes/{noteId}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Admin"],
)
def delete_admin_note(
    noteId: UUID,
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Delete admin note (moderator only).
    """
    db.query(models.AdminNote).filter(models.AdminNote.id == noteId).delete()
    db.commit()

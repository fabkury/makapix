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
from ..pagination import apply_cursor_filter, create_page_response
from ..mqtt.notifications import (
    publish_new_post_notification,
    publish_category_promotion_notification,
)
from ..utils.audit import log_moderation_action
from ..utils.monitored_hashtags import (
    apply_monitored_hashtag_filter,
    filter_posts_by_monitored_hashtags,
)
from ..utils.view_tracking import record_view, ViewType, ViewSource
from ..utils.site_tracking import record_site_event
from ..services.post_stats import annotate_posts_with_counts, get_user_liked_post_ids
from ..services.storage_quota import check_storage_quota, format_quota_error
from ..services.rate_limit import check_rate_limit
from ..vault import (
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE_BYTES,
    delete_artwork_from_vault,
    get_artwork_url,
    save_artwork_to_vault,
    validate_file_size,
    validate_image_dimensions,
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


@router.get("", response_model=schemas.Page[schemas.Post])
def list_posts(
    request: Request,
    owner_id: UUID | None = None,
    hashtag: str | None = None,
    promoted: bool | None = None,
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
    size: list[int] | None = Query(None),  # Exact size values (max dimension) with OR logic
    size_gte: int | None = Query(None, ge=1),  # For 128+ case
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Page[schemas.Post]:
    """
    List posts with filters.
    """
    # The web/UI post endpoints currently serve artwork posts only.
    # Playlist posts are used primarily for players (MQTT) and have a different shape.
    query = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner))
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
            is_viewing_own_posts = owner_user_id == current_user.id
        else:
            # User not found, return empty results
            owner_user_id = -1  # Will result in no matches
    else:
        is_viewing_own_posts = False

    if owner_user_id is not None:
        query = query.filter(models.Post.owner_id == owner_user_id)

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
            query = query.filter(models.Post.public_visibility == True)

    # Apply monitored hashtag filtering (unless viewing own posts)
    if not is_viewing_own_posts:
        query = apply_monitored_hashtag_filter(query, models.Post, current_user)

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

    # File size filter
    if file_bytes_min is not None:
        query = query.filter(models.Post.file_bytes >= file_bytes_min)
    if file_bytes_max is not None:
        query = query.filter(models.Post.file_bytes <= file_bytes_max)

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

    # File format filter (multi-select)
    if file_format is not None and len(file_format) > 0:
        # Normalize to lowercase for comparison
        normalized_formats = [f.lower() for f in file_format]
        query = query.filter(models.Post.file_format.in_(normalized_formats))

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

    # Apply cursor pagination
    sort_desc = order == "desc"
    query = apply_cursor_filter(
        query, models.Post, cursor, sort or "created_at", sort_desc=sort_desc
    )

    # Map sort field to model attribute and apply ordering
    sort_field_map = {
        "created_at": models.Post.created_at,
        "creation_date": models.Post.created_at,  # Alias
        "width": models.Post.width,
        "height": models.Post.height,
        "file_bytes": models.Post.file_bytes,
        "frame_count": models.Post.frame_count,
        "unique_colors": models.Post.unique_colors,
    }

    # Handle reactions sorting as a special case (requires subquery)
    if sort == "reactions":
        from sqlalchemy import func

        reaction_count_sort_subq = (
            db.query(func.count(models.Reaction.id))
            .filter(models.Reaction.post_id == models.Post.id)
            .correlate(models.Post)
            .scalar_subquery()
        )
        sort_expr = func.coalesce(reaction_count_sort_subq, 0)
        if order == "desc":
            query = query.order_by(sort_expr.desc())
        else:
            query = query.order_by(sort_expr.asc())
    else:
        sort_column = sort_field_map.get(sort or "created_at", models.Post.created_at)
        if order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

    # Fetch limit + 1 to check if there are more results
    posts = query.limit(limit + 1).all()

    # Add reaction and comment counts, and user liked status
    annotate_posts_with_counts(db, posts, current_user.id)

    # Create paginated response
    page_data = create_page_response(posts, limit, cursor)

    # Record site event for page view
    record_site_event(request, "page_view", user=current_user)

    return schemas.Page(
        items=[schemas.Post.model_validate(p) for p in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )


@router.post(
    "",
    response_model=schemas.Post,
    status_code=status.HTTP_201_CREATED,
)
def create_post(
    payload: schemas.PostCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Post:
    """
    Create a new post.
    """
    # Parse canvas dimensions from "WxH" format
    try:
        width_str, height_str = payload.canvas.split("x")
        width = int(width_str)
        height = int(height_str)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid canvas format '{payload.canvas}'. Expected format: WIDTHxHEIGHT (e.g., '64x64')",
        )

    # Validate canvas dimensions using the same validation logic as image uploads
    is_valid, error = validate_image_dimensions(width, height)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    # Validate file size (basic check)
    if payload.file_bytes > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size {payload.file_bytes} bytes exceeds limit of {MAX_FILE_SIZE_BYTES} bytes",
        )

    # Normalize hashtags (lowercase, strip whitespace)
    normalized_hashtags = []
    for tag in payload.hashtags:
        normalized_tag = tag.strip().lower()
        if normalized_tag and normalized_tag not in normalized_hashtags:
            normalized_hashtags.append(normalized_tag)

    # Limit hashtags to 64
    normalized_hashtags = normalized_hashtags[:64]

    # Generate UUID for storage_key
    storage_key = uuid.uuid4()

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    post = models.Post(
        storage_key=storage_key,
        owner_id=current_user.id,
        kind=payload.kind,
        title=payload.title,
        description=payload.description,
        hashtags=normalized_hashtags,
        art_url=str(payload.art_url),
        canvas=payload.canvas,
        width=width,
        height=height,
        file_bytes=payload.file_bytes,
        frame_count=1,
        min_frame_duration_ms=None,
        max_frame_duration_ms=None,
        unique_colors=None,
        transparency_meta=False,
        alpha_meta=False,
        transparency_actual=False,
        alpha_actual=False,
        hash=payload.hash,
        metadata_modified_at=now,
        artwork_modified_at=now,
        dwell_time_ms=30000,
    )
    db.add(post)
    db.flush()  # Get the post ID without committing

    # Generate public_sqid from the assigned id
    from ..sqids_config import encode_id

    post.public_sqid = encode_id(post.id)
    db.commit()
    db.refresh(post)

    # Invalidate feed caches since a new post was created
    cache_invalidate("feed:recent:*")
    cache_invalidate("hashtags:*")

    # TODO: Queue conformance check job

    # Publish MQTT notification to followers
    try:
        publish_new_post_notification(post.id, db)
    except Exception as e:
        # Log error but don't fail the request
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to publish MQTT notification for post {post.id}: {e}")

    return schemas.Post.model_validate(post)


@router.post(
    "/upload",
    response_model=schemas.ArtworkUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_artwork(
    request: Request,
    image: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=200),
    description: str | None = Form(None, max_length=5000),
    hashtags: str = Form(""),  # Comma-separated hashtags
    hidden_by_user: str = Form("false"),  # User can choose to hide their artwork
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

    # Check storage quota
    quota_allowed, used, quota = check_storage_quota(db, current_user, file_size)
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

    # Parse hashtags (comma-separated, normalize to lowercase)
    parsed_hashtags = []
    if hashtags.strip():
        for tag in hashtags.split(","):
            normalized_tag = tag.strip().lower()
            # Remove # prefix if present
            if normalized_tag.startswith("#"):
                normalized_tag = normalized_tag[1:]
            if normalized_tag and normalized_tag not in parsed_hashtags:
                parsed_hashtags.append(normalized_tag)

    # Limit hashtags to 64
    parsed_hashtags = parsed_hashtags[:64]

    # Determine public visibility based on user's auto_public_approval privilege
    public_visibility = getattr(current_user, "auto_public_approval", False)

    # Parse hidden_by_user from form (string "true"/"false" to bool)
    user_hidden = hidden_by_user.lower() in ("true", "1", "yes")

    # Generate UUID for storage_key
    storage_key = uuid.uuid4()

    # Create the post record first to get the ID
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    post = models.Post(
        storage_key=storage_key,
        owner_id=current_user.id,
        kind="artwork",
        title=title,
        description=description,
        hashtags=parsed_hashtags,
        art_url="",  # Will be updated after saving to vault
        canvas=f"{width}x{height}",
        width=width,
        height=height,
        file_bytes=file_size,
        frame_count=frame_count,
        min_frame_duration_ms=min_frame_duration_ms,
        max_frame_duration_ms=max_frame_duration_ms,
        unique_colors=unique_colors,
        transparency_meta=transparency_meta,
        alpha_meta=alpha_meta,
        transparency_actual=transparency_actual,
        alpha_actual=alpha_actual,
        hash=file_hash,
        file_format=file_format,
        formats_available=[file_format],  # Initialize with native format
        public_visibility=public_visibility,
        hidden_by_user=user_hidden,
        metadata_modified_at=now,
        artwork_modified_at=now,
        dwell_time_ms=30000,
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
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Artwork already exists",
        )

    # Insert first (flush) so the UNIQUE constraint prevents races *before* we
    # write to the vault (avoids orphan vault files on duplicate uploads).
    try:
        db.add(post)
        db.flush()  # Get the post ID without committing
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Artwork already exists",
        )

    # Generate public_sqid from the assigned id
    from ..sqids_config import encode_id

    post.public_sqid = encode_id(post.id)

    # Save to vault using the storage_key
    try:
        from ..vault import FORMAT_TO_EXT

        extension = FORMAT_TO_EXT[file_format]
        save_artwork_to_vault(post.storage_key, file_content, file_format)

        # Update the art_url to point to the vault
        art_url = get_artwork_url(post.storage_key, extension)
        post.art_url = art_url

        db.commit()
        db.refresh(post)
    except Exception as e:
        db.rollback()
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
        response.items = filter_posts_by_monitored_hashtags(response.items, current_user)
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
        .options(joinedload(models.Post.owner))
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

    # Query post with owner relationship
    post = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner))
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


@router.patch("/{id}", response_model=schemas.Post)
def update_post(
    id: int,
    payload: schemas.PostUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Post:
    """
    Update post fields.

    TODO: Validate ownership before allowing update
    TODO: Only moderators can update hidden_by_mod
    TODO: Re-extract hashtags if title/description changed
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    require_ownership(post.owner_id, current_user)

    if payload.title is not None:
        post.title = payload.title
    if payload.description is not None:
        post.description = payload.description
    if payload.hashtags is not None:
        post.hashtags = payload.hashtags
    if payload.hidden_by_user is not None:
        post.hidden_by_user = payload.hidden_by_user
    if payload.hidden_by_mod is not None:
        # TODO: Only allow moderators to set this
        post.hidden_by_mod = payload.hidden_by_mod

    from datetime import datetime, timezone

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


@router.post(
    "/{id}/undelete",
    status_code=status.HTTP_201_CREATED,
    tags=["Posts", "Admin"],
)
def undelete_post_by_moderator(
    id: int,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Undelete post (moderator only).

    Note: Posts that have been deleted by the user cannot be restored.
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    # Prevent restoring user-deleted posts
    if post.deleted_by_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User-deleted posts cannot be restored",
        )

    post.visible = True
    post.hidden_by_user = False
    post.hidden_by_mod = False
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="undelete_post",
        target_type="post",
        target_id=id,
    )


@router.post(
    "/{id}/delete",
    status_code=status.HTTP_201_CREATED,
    tags=["Posts", "Admin"],
)
def delete_post_by_moderator(
    id: int,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Soft delete post (moderator only).
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    post.visible = False
    post.hidden_by_mod = True
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="delete_post",
        target_type="post",
        target_id=id,
    )


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
            formats_to_delete = post.formats_available or (
                [post.file_format] if post.file_format else []
            )
            vault.delete_all_artwork_formats(post.storage_key, formats_to_delete)
        except Exception as e:
            logger.warning(f"Failed to delete artwork files for post {id}: {e}")

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

    file_content = await image.read()
    file_size = len(file_content)
    validate_file_size(file_size)

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

    # Compute new art_url (may change extension if format changes)
    from ..vault import FORMAT_TO_EXT

    new_extension = FORMAT_TO_EXT[file_format]
    new_art_url = get_artwork_url(post.storage_key, new_extension)

    # Update post first (flush) so UNIQUE constraint blocks races before vault write
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    old_art_url = post.art_url
    post.art_url = new_art_url
    post.width = width
    post.height = height
    post.canvas = f"{width}x{height}"
    post.file_bytes = file_bytes
    post.frame_count = frame_count
    post.min_frame_duration_ms = min_frame_duration_ms
    post.max_frame_duration_ms = max_frame_duration_ms
    post.unique_colors = unique_colors
    post.transparency_meta = transparency_meta
    post.alpha_meta = alpha_meta
    post.transparency_actual = transparency_actual
    post.alpha_actual = alpha_actual
    post.hash = file_hash
    post.file_format = file_format
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

    # If extension changed, delete the old file (best-effort) after flush but before overwrite
    try:
        old_ext = None
        if old_art_url:
            old_ext = "." + old_art_url.rsplit(".", 1)[-1].lower()
        if old_ext and old_ext != new_extension and old_ext in FORMAT_TO_EXT.values():
            delete_artwork_from_vault(post.storage_key, old_ext)
    except Exception as e:
        logger.warning(f"Failed to delete old artwork file for post {post.id}: {e}")

    # Overwrite vault file at storage_key
    try:
        save_artwork_to_vault(post.storage_key, file_content, file_format)
        db.commit()
        db.refresh(post)
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to replace artwork in vault: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save artwork. Please try again.",
        )

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

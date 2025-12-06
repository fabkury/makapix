"""Post management endpoints."""

from __future__ import annotations

import hashlib
import io
import logging
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
from ..utils.view_tracking import record_view, ViewType, ViewSource
from ..utils.site_tracking import record_site_event
from ..services.post_stats import annotate_posts_with_counts, get_user_liked_post_ids
from ..vault import (
    ALLOWED_MIME_TYPES,
    MAX_CANVAS_SIZE,
    MAX_FILE_SIZE_BYTES,
    get_artwork_url,
    save_artwork_to_vault,
    validate_file_size,
    validate_image_dimensions,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/post", tags=["Posts"])


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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Page[schemas.Post]:
    """
    List posts with filters.
    """
    query = db.query(models.Post).options(joinedload(models.Post.owner))

    is_moderator = "moderator" in current_user.roles or "owner" in current_user.roles

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
    if visible_only:
        query = query.filter(models.Post.visible == True)

        # Hide posts hidden by moderators unless current user is moderator/owner
        if not is_moderator:
            query = query.filter(models.Post.hidden_by_mod == False)

        # Hide posts hidden by users (should always be hidden from public view)
        query = query.filter(models.Post.hidden_by_user == False)

        # Hide non-conformant posts unless current user is moderator/owner
        if not is_moderator:
            query = query.filter(models.Post.non_conformant == False)

        # Apply public_visibility filter unless viewing own posts or is moderator
        if not is_viewing_own_posts and not is_moderator:
            query = query.filter(models.Post.public_visibility == True)

    if promoted is not None:
        query = query.filter(models.Post.promoted == promoted)

    # Implement hashtag filter using PostgreSQL array contains
    if hashtag:
        query = query.filter(models.Post.hashtags.contains([hashtag]))

    # Apply cursor pagination
    sort_desc = order == "desc"
    query = apply_cursor_filter(
        query, models.Post, cursor, sort or "created_at", sort_desc=sort_desc
    )

    # Order and limit
    if sort == "created_at":
        if order == "desc":
            query = query.order_by(models.Post.created_at.desc())
        else:
            query = query.order_by(models.Post.created_at.asc())

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
        width_str, height_str = payload.canvas.split('x')
        width = int(width_str)
        height = int(height_str)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid canvas format '{payload.canvas}'. Expected format: WIDTHxHEIGHT (e.g., '64x64')"
        )
    
    # Validate canvas dimensions against allowed list
    allowed_canvases = [
        "16x16",
        "32x32",
        "64x64",
        "96x64",
        "128x64",
        "128x128",
        "160x128",
        "240x135",
        "240x240",
        "256x256",
    ]
    if payload.canvas not in allowed_canvases:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Canvas size '{payload.canvas}' not allowed. Allowed sizes: {', '.join(allowed_canvases)}",
        )

    # Validate file size (basic check)
    max_file_kb = 5 * 1024  # 15 MB limit
    if payload.file_kb > max_file_kb:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size {payload.file_kb}KB exceeds limit of {max_file_kb}KB",
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
        file_kb=payload.file_kb,
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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ArtworkUploadResponse:
    """
    Upload a single artwork image directly to the vault.

    The image must be:
    - A perfect square (width == height)
    - Max 256x256 pixels
    - Max 5 MB file size
    - PNG, GIF, or WebP format

    Public visibility is automatically set based on the user's auto_public_approval privilege.
    If the user does not have this privilege, the artwork will not appear in Recent Artworks
    until a moderator approves it.
    """
    # Read the file content
    file_content = await image.read()
    file_size = len(file_content)

    # Validate file size
    is_valid, error = validate_file_size(file_size)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    # Determine MIME type from content-type header or file extension
    mime_type = image.content_type
    if mime_type not in ALLOWED_MIME_TYPES:
        # Try to detect from file extension
        filename = image.filename or ""
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        ext_to_mime = {"png": "image/png", "gif": "image/gif", "webp": "image/webp"}
        mime_type = ext_to_mime.get(ext)

        if mime_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid image format. Allowed formats: PNG, GIF, WebP",
            )

    # Validate image dimensions using PIL
    try:
        img = Image.open(io.BytesIO(file_content))
        width, height = img.size
    except Exception as e:
        logger.error(f"Failed to open image: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read image file. Please ensure it's a valid image.",
        )

    # Extract metadata for new fields
    # 1. Frame count - use img.n_frames for animated images
    frame_count = 1
    try:
        frame_count = img.n_frames
    except (AttributeError, Exception) as e:
        logger.warning(f"Failed to get frame count: {e}")

    # 2. Minimum non-zero frame duration (for animated images)
    min_frame_duration_ms = None
    if frame_count > 1:
        try:
            durations = []
            for frame_idx in range(frame_count):
                img.seek(frame_idx)
                duration = img.info.get("duration")
                if duration is not None and duration > 0:
                    durations.append(duration)
            if durations:
                min_frame_duration_ms = min(durations)
            # Reset to first frame
            img.seek(0)
        except Exception as e:
            logger.warning(f"Failed to extract frame durations: {e}")

    # 3. Detect transparency
    has_transparency = False
    try:
        # Check if image mode has alpha channel
        if img.mode in ("RGBA", "LA", "PA"):
            has_transparency = True
        # For palette images (including GIFs), check for transparency info
        elif img.mode == "P" and "transparency" in img.info:
            has_transparency = True
    except Exception as e:
        logger.warning(f"Failed to detect transparency: {e}")

    # Validate dimensions (must be square, max 256x256)
    is_valid, error = validate_image_dimensions(width, height)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error,
        )

    # Calculate SHA256 hash of the file content
    file_hash = hashlib.sha256(file_content).hexdigest()

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

    # Generate UUID for storage_key
    storage_key = uuid.uuid4()

    # Create the post record first to get the ID
    post = models.Post(
        storage_key=storage_key,
        owner_id=current_user.id,
        kind="art",
        title=title,
        description=description,
        hashtags=parsed_hashtags,
        art_url="",  # Will be updated after saving to vault
        canvas=f"{width}x{height}",
        width=width,
        height=height,
        file_kb=file_size // 1024,
        file_bytes=file_size,
        frame_count=frame_count,
        min_frame_duration_ms=min_frame_duration_ms,
        has_transparency=has_transparency,
        expected_hash=file_hash,
        mime_type=mime_type,
        public_visibility=public_visibility,
    )
    db.add(post)
    db.flush()  # Get the post ID without committing

    # Generate public_sqid from the assigned id
    from ..sqids_config import encode_id

    post.public_sqid = encode_id(post.id)

    # Save to vault using the storage_key
    try:
        extension = ALLOWED_MIME_TYPES[mime_type]
        save_artwork_to_vault(post.storage_key, file_content, mime_type)

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
    # Include moderator flag in cache key since they see different results
    is_moderator = current_user and (
        "moderator" in current_user.roles or "owner" in current_user.roles
    )
    cache_key = (
        f"feed:recent:{'mod' if is_moderator else 'user'}:{cursor or 'first'}:{limit}"
    )

    # Try to get from cache
    cached_result = cache_get(cache_key)
    if cached_result:
        response = schemas.Page(**cached_result)
        # Add user-specific like status if authenticated
        if current_user and response.items:
            post_ids = [item.id for item in response.items]
            liked_ids = get_user_liked_post_ids(db, post_ids, current_user.id)
            for item in response.items:
                item.user_has_liked = item.id in liked_ids
        return response

    query = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner))
        .filter(
            models.Post.visible == True,
            models.Post.hidden_by_mod == False,
            models.Post.hidden_by_user == False,
            models.Post.public_visibility == True,  # Only show publicly visible posts
        )
    )

    # Hide non-conformant posts unless current user is moderator/owner
    if not is_moderator:
        query = query.filter(models.Post.non_conformant == False)

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
    # Note: Cache stores base data; user_has_liked is added when retrieving from cache
    cache_set(cache_key, response.model_dump(), ttl=120)

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
        .filter(models.Post.storage_key == storage_key)
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

    TODO: Implement soft delete (set visible=False)
    TODO: Validate ownership before allowing delete
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    require_ownership(post.owner_id, current_user)

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
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
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

    This action cannot be undone. The post must be hidden before it can be permanently deleted.
    This also removes the artwork image from the vault.
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    # Only allow permanent deletion of hidden posts
    if not post.hidden_by_mod and not post.hidden_by_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Post must be hidden before it can be permanently deleted",
        )

    # Delete the artwork from vault if it exists
    if post.art_url:
        # Extract extension from art_url (e.g., "/api/vault/a1/b2/c3/uuid.png" -> ".png")
        from app import vault

        try:
            ext = "." + post.art_url.rsplit(".", 1)[-1].lower()
            if ext in vault.ALLOWED_MIME_TYPES.values():
                vault.delete_artwork_from_vault(post.storage_key, ext)
        except Exception as e:
            logger.warning(f"Failed to delete artwork file for post {id}: {e}")

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

    TODO: Validate that user is owner or moderator
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
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

"""User management endpoints."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import (
    check_ownership,
    get_current_user,
    get_current_user_optional,
    require_moderator,
    require_ownership,
)
from ..constants import MONITORED_HASHTAGS
from ..avatar_vault import ALLOWED_MIME_TYPES as AVATAR_ALLOWED_MIME_TYPES
from ..avatar_vault import get_avatar_url, save_avatar_image
from ..avatar_vault import try_delete_avatar_by_public_url
from ..deps import get_db
from ..utils.handles import validate_handle, is_handle_taken
from ..pagination import (
    apply_cursor_filter,
    create_page_response,
    decode_cursor,
    encode_cursor,
)
from ..services.blog_post_stats import annotate_blog_posts_with_counts
from ..services.artist_dashboard import get_artist_stats, get_posts_stats_list

router = APIRouter(prefix="/user", tags=["Users"])


@router.get("/browse", response_model=schemas.Page[schemas.UserPublic])
def browse_users(
    q: str | None = None,
    sort: str = Query("alphabetical", regex="^(alphabetical|recent|reputation)$"),
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Page[schemas.UserPublic]:
    """
    Browse and search users (requires authentication).
    """
    query = db.query(models.User)

    # Hide unverified users from everyone on public browse
    query = query.filter(models.User.email_verified == True)

    # Always hide owner from browse listings (applies to everyone)
    # Cast JSON to JSONB for containment operator support
    query = query.filter(~models.User.roles.cast(JSONB).contains(["owner"]))

    # Apply additional visibility filters for non-moderators
    is_moderator = current_user and (
        "moderator" in current_user.roles or "owner" in current_user.roles
    )
    if not is_moderator:
        query = query.filter(
            models.User.hidden_by_user == False,
            models.User.hidden_by_mod == False,
            models.User.non_conformant == False,
            models.User.deactivated == False,
            models.User.banned_until.is_(None),
        )

    # Apply search filter
    if q:
        search_term = f"%{q}%"
        query = query.filter(models.User.handle.ilike(search_term))

    # Apply sorting and cursor pagination
    if sort == "alphabetical":
        sort_field = "handle"
        sort_desc = False
        query = apply_cursor_filter(
            query, models.User, cursor, sort_field, sort_desc=sort_desc
        )
        query = query.order_by(models.User.handle.asc())
    elif sort == "recent":
        sort_field = "created_at"
        sort_desc = True
        query = apply_cursor_filter(
            query, models.User, cursor, sort_field, sort_desc=sort_desc
        )
        query = query.order_by(models.User.created_at.desc())
    elif sort == "reputation":
        sort_field = "reputation"
        sort_desc = True
        # For reputation, we need to handle cursor differently since it's an integer
        if cursor:
            cursor_data = decode_cursor(cursor)
            if cursor_data:
                last_id, sort_value = cursor_data
                # Filter: reputation < sort_value OR (reputation == sort_value AND id < last_id)
                if sort_value is not None:
                    try:
                        last_reputation = int(sort_value)
                        last_user_id = int(last_id)  # User.id is Integer, not UUID
                        query = query.filter(
                            (models.User.reputation < last_reputation)
                            | (
                                (models.User.reputation == last_reputation)
                                & (models.User.id < last_user_id)
                            )
                        )
                    except (ValueError, TypeError):
                        pass
        query = query.order_by(models.User.reputation.desc(), models.User.id.desc())

    # Fetch limit + 1 to check if there are more results
    users = query.limit(limit + 1).all()

    # Create paginated response
    if sort == "reputation":
        # Handle reputation cursor encoding manually
        next_cursor = None
        if len(users) > limit:
            users = users[:limit]
            if users:
                last_user = users[-1]
                next_cursor = encode_cursor(str(last_user.id), last_user.reputation)
        page_data = {"items": users, "next_cursor": next_cursor}
    else:
        page_data = create_page_response(users, limit, cursor, sort_field=sort_field)

    return schemas.Page(
        items=[schemas.UserPublic.model_validate(u) for u in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )


@router.get("", response_model=schemas.Page[schemas.UserFull])
def list_users_admin(
    q: str | None = None,
    hidden: bool | None = None,
    banned: bool | None = None,
    non_conformant: bool | None = None,
    recent: bool | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.Page[schemas.UserFull]:
    """
    List users (moderator/owner only).
    """
    query = db.query(models.User)

    # Apply search filter (search by handle only since display_name no longer exists)
    if q:
        search_term = f"%{q}%"
        query = query.filter(models.User.handle.ilike(search_term))

    # Apply filters
    if hidden is not None:
        query = query.filter(models.User.hidden_by_user == hidden)

    if banned is not None:
        if banned:
            query = query.filter(models.User.banned_until.isnot(None))
        else:
            query = query.filter(models.User.banned_until.is_(None))

    if non_conformant is not None:
        query = query.filter(models.User.non_conformant == non_conformant)

    if recent:
        # Show users created in the last 7 days
        from datetime import datetime, timedelta, timezone

        recent_date = datetime.now(timezone.utc) - timedelta(days=7)
        query = query.filter(models.User.created_at >= recent_date)

    # Apply cursor pagination
    query = apply_cursor_filter(
        query, models.User, cursor, "created_at", sort_desc=True
    )

    # Order and limit
    query = query.order_by(models.User.created_at.desc())

    # Fetch limit + 1 to check if there are more results
    users = query.limit(limit + 1).all()

    # Create paginated response
    page_data = create_page_response(users, limit, cursor)

    return schemas.Page(
        items=[schemas.UserFull.model_validate(u) for u in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )


@router.post(
    "",
    response_model=schemas.UserFull,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.UserFull:
    """
    Create user (post-OAuth bootstrap).

    TODO: This should only be called after OAuth, not for new signups
    TODO: Validate that handle is unique
    TODO: Validate handle format (alphanumeric + hyphen/underscore)
    TODO: Validate website URL format
    """
    # Check if handle already exists
    existing = (
        db.query(models.User).filter(models.User.handle == payload.handle).first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Handle already taken"
        )

    # PLACEHOLDER: Create user (in production this would be done during OAuth)
    user = models.User(
        handle=payload.handle,
        bio=payload.bio,
        website=payload.website,
        roles=["user"],
    )
    db.add(user)
    db.flush()  # Get the user ID without committing

    # Generate public_sqid from the assigned id
    from ..sqids_config import encode_user_id

    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)

    return schemas.UserFull.model_validate(user)


@router.get("/u/{public_sqid}", response_model=schemas.UserPublic | schemas.UserFull)
def get_user_by_sqid(
    public_sqid: str,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.UserPublic | schemas.UserFull:
    """
    Get user by public Sqids ID (canonical URL).

    This is the canonical URL for user profiles sitewide.
    """
    # Decode the Sqids ID
    from ..sqids_config import decode_user_sqid

    user_id = decode_user_sqid(public_sqid)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Query user
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Verify public_sqid matches (safety check)
    if user.public_sqid != public_sqid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check if user is hidden and current user doesn't have permission to see it
    if user.hidden_by_user and (
        not current_user or not check_ownership(user.id, current_user)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Hide unverified users from public view (unless moderator or self)
    is_moderator = current_user and (
        "moderator" in current_user.roles or "owner" in current_user.roles
    )
    is_own_profile = current_user and current_user.id == user.id
    if not user.email_verified and not is_moderator and not is_own_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Hide owner from ALL view (only owner can see own profile)
    is_target_owner = "owner" in (user.roles or [])
    if is_target_owner and not is_own_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Return UserFull for moderators/owners, UserPublic for others
    if is_moderator:
        return schemas.UserFull.model_validate(user)
    else:
        return schemas.UserPublic.model_validate(user)


@router.get("/{id}", response_model=schemas.UserPublic | schemas.UserFull)
def get_user(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.UserPublic | schemas.UserFull:
    """
    Get user by user_key (UUID).

    Legacy endpoint - returns user data including public_sqid for redirect purposes.
    The canonical URL is /u/{public_sqid}.
    """
    # Look up by user_key (UUID)
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check if user is hidden and current user doesn't have permission to see it
    if user.hidden_by_user and (
        not current_user or not check_ownership(user.id, current_user)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Hide unverified users from public view (unless moderator or self)
    is_moderator = current_user and (
        "moderator" in current_user.roles or "owner" in current_user.roles
    )
    is_own_profile = current_user and current_user.id == user.id
    if not user.email_verified and not is_moderator and not is_own_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Hide owner from ALL view (only owner can see own profile)
    is_target_owner = "owner" in (user.roles or [])
    if is_target_owner and not is_own_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Return UserFull for moderators/owners, UserPublic for others
    if is_moderator:
        return schemas.UserFull.model_validate(user)
    else:
        return schemas.UserPublic.model_validate(user)


@router.patch("/{id}", response_model=schemas.UserFull)
def update_user(
    id: UUID,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.UserFull:
    """
    Update user fields.
    """
    # Look up by user_key (UUID)
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Authorization:
    # - Users can always edit their own profile
    # - Owners can edit anyone
    # - Moderators can edit anyone EXCEPT other moderators/owners
    is_actor_owner = "owner" in (current_user.roles or [])
    is_actor_moderator = is_actor_owner or ("moderator" in (current_user.roles or []))
    is_target_moderator = "moderator" in (user.roles or [])
    is_target_owner = "owner" in (user.roles or [])

    if user.id != current_user.id:
        if is_actor_owner:
            pass
        elif is_actor_moderator:
            if is_target_owner or is_target_moderator:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Moderators cannot edit other moderators",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this resource",
            )

    # Update handle if provided
    if payload.handle is not None:
        # Prevent owner from changing their handle
        if "owner" in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The site owner's handle cannot be changed",
            )

        # Strip whitespace but preserve original case
        new_handle = payload.handle.strip()

        # Validate handle format
        is_valid, error_msg = validate_handle(new_handle)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid handle: {error_msg}",
            )

        # Check if handle is already taken (case-insensitive, excluding current user)
        if is_handle_taken(db, new_handle, exclude_user_id=user.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Handle already taken",
            )

        # Preserve original case
        user.handle = new_handle

    # Update fields
    if payload.bio is not None:
        user.bio = payload.bio
    if payload.tagline is not None:
        user.tagline = payload.tagline
    if payload.website is not None:
        user.website = payload.website
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url

    # Only allow moderators to update hidden_by_user for other users
    if payload.hidden_by_user is not None:
        if (
            user.id == current_user.id
            or "moderator" in current_user.roles
            or "owner" in current_user.roles
        ):
            user.hidden_by_user = payload.hidden_by_user
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only moderators can change hidden_by_user for other users",
            )

    # Update approved_hashtags (users can only set their own, moderators can set for anyone)
    if payload.approved_hashtags is not None:
        if user.id != current_user.id and not is_actor_moderator:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only update your own approved hashtags",
            )
        # Validate that all hashtags are in the monitored list
        invalid_tags = set(payload.approved_hashtags) - MONITORED_HASHTAGS
        if invalid_tags:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid hashtags: {', '.join(sorted(invalid_tags))}. "
                f"Allowed values: {', '.join(sorted(MONITORED_HASHTAGS))}",
            )
        user.approved_hashtags = list(payload.approved_hashtags)

    db.commit()
    db.refresh(user)

    return schemas.UserFull.model_validate(user)


@router.post(
    "/{id}/avatar", response_model=schemas.UserFull, status_code=status.HTTP_201_CREATED
)
async def upload_user_avatar(
    request: Request,
    id: UUID,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.UserFull:
    """
    Upload a user avatar.

    Stores raw bytes as-uploaded (no re-encoding) so animated GIF/WEBP stay animated.
    """
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Authorization (same policy as profile patch):
    # - Users can edit self
    # - Owners can edit anyone
    # - Moderators can edit anyone except other moderators/owners
    is_actor_owner = "owner" in (current_user.roles or [])
    is_actor_moderator = is_actor_owner or ("moderator" in (current_user.roles or []))
    is_target_moderator = "moderator" in (user.roles or [])
    is_target_owner = "owner" in (user.roles or [])

    if user.id != current_user.id:
        if is_actor_owner:
            pass
        elif is_actor_moderator:
            if is_target_owner or is_target_moderator:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Moderators cannot edit other moderators",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this resource",
            )

    file_content = await image.read()
    if not file_content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file"
        )

    # Determine MIME type
    mime_type = (image.content_type or "").lower()
    if mime_type == "image/jpg":
        mime_type = "image/jpeg"

    if mime_type not in AVATAR_ALLOWED_MIME_TYPES:
        # Try to detect from file extension
        filename = image.filename or ""
        ext = filename.lower().split(".")[-1] if "." in filename else ""
        ext_to_mime = {
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
        }
        mime_type = ext_to_mime.get(ext, "")
        if mime_type not in AVATAR_ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image format. Allowed formats: PNG, JPEG, GIF, WebP",
            )

    from uuid import uuid4

    avatar_id = uuid4()
    try:
        save_avatar_image(avatar_id, file_content, mime_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    extension = AVATAR_ALLOWED_MIME_TYPES[mime_type]
    user.avatar_url = get_avatar_url(avatar_id, extension)
    db.commit()
    db.refresh(user)

    return schemas.UserFull.model_validate(user)


@router.delete("/{id}/avatar", response_model=schemas.UserFull)
def delete_user_avatar(
    request: Request,
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.UserFull:
    """
    Remove (clear) a user's avatar without uploading a new one.

    This sets user.avatar_url to NULL. If the previous avatar URL points to our
    vault avatar path, we also attempt a best-effort file deletion.
    """
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Authorization (same policy as profile patch/upload):
    is_actor_owner = "owner" in (current_user.roles or [])
    is_actor_moderator = is_actor_owner or ("moderator" in (current_user.roles or []))
    is_target_moderator = "moderator" in (user.roles or [])
    is_target_owner = "owner" in (user.roles or [])

    if user.id != current_user.id:
        if is_actor_owner:
            pass
        elif is_actor_moderator:
            if is_target_owner or is_target_moderator:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Moderators cannot edit other moderators",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to access this resource",
            )

    old_avatar_url = user.avatar_url
    user.avatar_url = None
    db.commit()
    db.refresh(user)

    # Best-effort file cleanup (non-fatal)
    try_delete_avatar_by_public_url(old_avatar_url)

    return schemas.UserFull.model_validate(user)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_account(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Delete own profile (irreversible for user, but soft-delete).

    TODO: Implement soft delete (set deactivated=True)
    TODO: Consider anonymizing user data instead of deletion
    TODO: Cascade hide all user's posts and comments
    """
    # Look up by user_key (UUID)
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    require_ownership(user.id, current_user)

    # Soft delete
    user.deactivated = True
    user.hidden_by_user = True
    db.commit()


@router.post("/delete-account", status_code=status.HTTP_202_ACCEPTED)
def request_account_deletion(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict:
    """
    Request permanent deletion of the current user's account.

    This endpoint:
    1. Prevents owner role from deleting their account
    2. Marks user as deactivated immediately (prevents login during deletion)
    3. Queues a background task to delete all user data
    4. Creates an audit log entry

    Returns 202 Accepted - deletion is processed asynchronously.
    """
    from ..tasks import delete_user_account_task
    from ..utils.audit import log_moderation_action

    # Prevent owner from deleting their own account
    if "owner" in (current_user.roles or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The site owner cannot delete their own account",
        )

    # Immediately mark user as deactivated to prevent login during deletion
    current_user.deactivated = True
    db.commit()

    # Log the deletion request
    try:
        log_moderation_action(
            db=db,
            actor_id=current_user.id,
            action="account_deletion_requested",
            target_type="user",
            target_id=current_user.id,
            reason_code="user_request",
            note="User requested permanent account deletion",
        )
    except Exception as e:
        # Don't fail the request if audit logging fails
        import logging

        logging.getLogger(__name__).error(
            f"Failed to log account deletion request: {e}"
        )

    # Queue the background task to perform full deletion
    delete_user_account_task.delay(current_user.id)

    return {"status": "accepted", "message": "Account deletion has been queued"}


@router.get("/{id}/blog-posts/recent", response_model=list[schemas.BlogPost])
def get_user_recent_blog_posts(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> list[schemas.BlogPost]:
    """
    Get the 2 most recent blog posts for a user.

    Used for displaying recent blog posts panel on user profile pages.

    FEATURE POSTPONED: Blog posts are deferred to a later time.
    """
    # FEATURE POSTPONED - Remove this block to reactivate blog posts
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Blog posts are deferred to a later time",
    )
    # Look up user by user_key (UUID)
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    query = (
        db.query(models.BlogPost)
        .options(joinedload(models.BlogPost.owner))
        .filter(models.BlogPost.owner_id == user.id)
    )

    # Only show visible posts for non-owners/non-moderators
    is_viewing_own_posts = (
        isinstance(current_user, models.User) and current_user.id == user.id
    )
    is_moderator = isinstance(current_user, models.User) and (
        "moderator" in current_user.roles or "owner" in current_user.roles
    )

    if not is_viewing_own_posts and not is_moderator:
        query = query.filter(
            models.BlogPost.visible == True,
            models.BlogPost.hidden_by_user == False,
            models.BlogPost.hidden_by_mod == False,
            models.BlogPost.public_visibility == True,
        )

    posts = query.order_by(models.BlogPost.created_at.desc()).limit(2).all()

    return [schemas.BlogPost.model_validate(p) for p in posts]


@router.get("/{id}/blog-posts", response_model=schemas.Page[schemas.BlogPost])
def get_user_blog_posts(
    id: UUID,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.Page[schemas.BlogPost]:
    """
    Get blog posts for a user.

    Used for displaying blog posts on user profile pages.

    FEATURE POSTPONED: Blog posts are deferred to a later time.
    """
    # FEATURE POSTPONED - Remove this block to reactivate blog posts
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Blog posts are deferred to a later time",
    )
    # Look up user by user_key (UUID)
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    query = (
        db.query(models.BlogPost)
        .options(joinedload(models.BlogPost.owner))
        .filter(models.BlogPost.owner_id == user.id)
    )

    # Always show user's own posts on their profile, even if not publicly visible
    is_viewing_own_posts = (
        isinstance(current_user, models.User) and current_user.id == user.id
    )
    is_moderator = isinstance(current_user, models.User) and (
        "moderator" in current_user.roles or "owner" in current_user.roles
    )

    if not is_viewing_own_posts and not is_moderator:
        # For other users, only show visible, non-hidden, publicly visible posts
        query = query.filter(
            models.BlogPost.visible == True,
            models.BlogPost.hidden_by_user == False,
            models.BlogPost.hidden_by_mod == False,
            models.BlogPost.public_visibility == True,
        )

    # Apply cursor pagination
    query = apply_cursor_filter(
        query, models.BlogPost, cursor, "created_at", sort_desc=True
    )
    query = query.order_by(models.BlogPost.created_at.desc())

    # Fetch limit + 1 to check if there are more results
    posts = query.limit(limit + 1).all()

    # Add reaction and comment counts in batch (avoids N+1 queries on frontend)
    annotate_blog_posts_with_counts(db, posts)

    # Create paginated response
    page_data = create_page_response(posts, limit, cursor)

    return schemas.Page(
        items=[schemas.BlogPost.model_validate(p) for p in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )


@router.get(
    "/{user_key}/artist-dashboard", response_model=schemas.ArtistDashboardResponse
)
def get_artist_dashboard(
    user_key: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ArtistDashboardResponse:
    """
    Get artist dashboard with aggregated statistics and post list.

    Returns comprehensive statistics across all posts by the artist,
    plus a paginated list of individual post statistics.

    **Authorization:**
    - Artist can view their own dashboard
    - Moderators and owners can view any artist's dashboard

    **Query Parameters:**
    - `page`: Page number (1-indexed, default: 1)
    - `page_size`: Number of posts per page (1-100, default: 20)
    """
    # Resolve user_key (could be user_key UUID or public_sqid)
    try:
        user_key_uuid = UUID(user_key)
        user = (
            db.query(models.User).filter(models.User.user_key == user_key_uuid).first()
        )
    except ValueError:
        # Not a valid UUID, try as public_sqid
        user = db.query(models.User).filter(models.User.public_sqid == user_key).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Authorization: owner of profile OR moderator/owner role
    is_owner = user.id == current_user.id
    is_moderator = "moderator" in current_user.roles or "owner" in current_user.roles

    if not is_owner and not is_moderator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this artist dashboard",
        )

    # Get aggregated artist stats
    artist_stats = get_artist_stats(db, user.user_key)

    if artist_stats is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute artist statistics",
        )

    # Get paginated post stats list
    offset = (page - 1) * page_size
    posts_stats = get_posts_stats_list(
        db, user.user_key, limit=page_size + 1, offset=offset
    )

    # Check if there are more pages
    has_more = len(posts_stats) > page_size
    if has_more:
        posts_stats = posts_stats[:page_size]

    # Convert artist stats to response schema
    artist_stats_response = schemas.ArtistStatsResponse(
        user_id=artist_stats.user_id,
        user_key=artist_stats.user_key,
        total_posts=artist_stats.total_posts,
        total_views=artist_stats.total_views,
        unique_viewers=artist_stats.unique_viewers,
        views_by_country=artist_stats.views_by_country,
        views_by_device=artist_stats.views_by_device,
        total_reactions=artist_stats.total_reactions,
        reactions_by_emoji=artist_stats.reactions_by_emoji,
        total_comments=artist_stats.total_comments,
        total_views_authenticated=artist_stats.total_views_authenticated,
        unique_viewers_authenticated=artist_stats.unique_viewers_authenticated,
        views_by_country_authenticated=artist_stats.views_by_country_authenticated,
        views_by_device_authenticated=artist_stats.views_by_device_authenticated,
        total_reactions_authenticated=artist_stats.total_reactions_authenticated,
        reactions_by_emoji_authenticated=artist_stats.reactions_by_emoji_authenticated,
        total_comments_authenticated=artist_stats.total_comments_authenticated,
        first_post_at=(
            datetime.fromisoformat(artist_stats.first_post_at)
            if artist_stats.first_post_at
            else None
        ),
        latest_post_at=(
            datetime.fromisoformat(artist_stats.latest_post_at)
            if artist_stats.latest_post_at
            else None
        ),
        computed_at=datetime.fromisoformat(artist_stats.computed_at),
    )

    # Convert post stats to response schema
    posts_response = [
        schemas.PostStatsListItem(
            post_id=ps.post_id,
            public_sqid=ps.public_sqid,
            title=ps.title,
            created_at=datetime.fromisoformat(ps.created_at),
            total_views=ps.total_views,
            unique_viewers=ps.unique_viewers,
            total_reactions=ps.total_reactions,
            total_comments=ps.total_comments,
            total_views_authenticated=ps.total_views_authenticated,
            unique_viewers_authenticated=ps.unique_viewers_authenticated,
            total_reactions_authenticated=ps.total_reactions_authenticated,
            total_comments_authenticated=ps.total_comments_authenticated,
        )
        for ps in posts_stats
    ]

    return schemas.ArtistDashboardResponse(
        artist_stats=artist_stats_response,
        posts=posts_response,
        total_posts=artist_stats.total_posts,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


# ============================================================================
# ENHANCED USER PROFILE ENDPOINTS
# ============================================================================


@router.get("/u/{public_sqid}/profile", response_model=schemas.UserProfileEnhanced)
def get_user_profile_enhanced(
    public_sqid: str,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.UserProfileEnhanced:
    """
    Get enhanced user profile with stats and tag badges.

    This is the main endpoint for loading user profile pages. Returns:
    - Basic user info
    - Tag badges (badges with is_tag_badge=True)
    - Profile statistics (total_posts, total_reactions_received, total_views, follower_count)
    - Whether current user follows this user
    - User's highlights (featured posts)
    """
    from ..sqids_config import decode_user_sqid
    from ..services.user_profile_stats import get_user_profile_stats
    from sqlalchemy import func

    user_id = decode_user_sqid(public_sqid)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Query user with badges
    user = (
        db.query(models.User)
        .options(joinedload(models.User.badges))
        .options(
            joinedload(models.User.highlights).joinedload(models.UserHighlight.post)
        )
        .filter(models.User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user.public_sqid != public_sqid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check if user is hidden
    is_own_profile = current_user and current_user.id == user.id
    is_moderator = current_user and (
        "moderator" in current_user.roles or "owner" in current_user.roles
    )
    if user.hidden_by_user and not is_own_profile and not is_moderator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Hide unverified users from public view (unless moderator or self)
    if not user.email_verified and not is_own_profile and not is_moderator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Hide owner from ALL view (only owner can see own profile)
    is_target_owner = "owner" in (user.roles or [])
    if is_target_owner and not is_own_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Get tag badges
    user_badge_names = [bg.badge for bg in user.badges]
    tag_badges = []
    if user_badge_names:
        badge_defs = (
            db.query(models.BadgeDefinition)
            .filter(
                models.BadgeDefinition.badge.in_(user_badge_names),
                models.BadgeDefinition.is_tag_badge == True,
                models.BadgeDefinition.icon_url_16.isnot(None),
            )
            .all()
        )
        tag_badges = [
            schemas.TagBadgeInfo(
                badge=bd.badge,
                label=bd.label,
                icon_url_16=bd.icon_url_16,
            )
            for bd in badge_defs
        ]

    # Get profile stats
    stats = get_user_profile_stats(db, user.id)
    if stats is None:
        # Create empty stats if computation failed
        stats_schema = schemas.UserProfileStats(
            total_posts=0,
            total_reactions_received=0,
            total_views=0,
            follower_count=0,
        )
    else:
        stats_schema = schemas.UserProfileStats(
            total_posts=stats.total_posts,
            total_reactions_received=stats.total_reactions_received,
            total_views=stats.total_views,
            follower_count=stats.follower_count,
        )

    # Check if current user follows this user
    is_following = False
    if current_user and not is_own_profile:
        follow = (
            db.query(models.Follow)
            .filter(
                models.Follow.follower_id == current_user.id,
                models.Follow.following_id == user.id,
            )
            .first()
        )
        is_following = follow is not None

    # Get highlights
    highlights = []
    for hl in user.highlights:
        if hl.post and not hl.post.deleted_by_user:
            highlights.append(
                schemas.UserHighlightItem(
                    id=hl.id,
                    post_id=hl.post_id,
                    position=hl.position,
                    post_public_sqid=hl.post.public_sqid,
                    post_title=hl.post.title,
                    post_art_url=hl.post.art_url,
                    post_width=hl.post.width,
                    post_height=hl.post.height,
                    created_at=hl.created_at,
                )
            )

    return schemas.UserProfileEnhanced(
        id=user.id,
        user_key=user.user_key,
        public_sqid=user.public_sqid,
        handle=user.handle,
        bio=user.bio,
        tagline=user.tagline,
        website=user.website,
        avatar_url=user.avatar_url,
        badges=[schemas.BadgeGrant.model_validate(b) for b in user.badges],
        reputation=user.reputation,
        hidden_by_user=user.hidden_by_user,
        hidden_by_mod=user.hidden_by_mod,
        non_conformant=user.non_conformant,
        deactivated=user.deactivated,
        created_at=user.created_at,
        tag_badges=tag_badges,
        stats=stats_schema,
        is_following=is_following,
        is_own_profile=is_own_profile or False,
        highlights=highlights,
    )


# ============================================================================
# FOLLOW ENDPOINTS
# ============================================================================


@router.post("/u/{public_sqid}/follow", response_model=schemas.FollowResponse)
def follow_user(
    public_sqid: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.FollowResponse:
    """
    Follow a user.
    """
    from ..sqids_config import decode_user_sqid
    from ..services.user_profile_stats import invalidate_user_profile_stats_cache
    from sqlalchemy import func

    user_id = decode_user_sqid(public_sqid)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Can't follow yourself
    if target_user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot follow yourself",
        )

    # Check if already following
    existing = (
        db.query(models.Follow)
        .filter(
            models.Follow.follower_id == current_user.id,
            models.Follow.following_id == target_user.id,
        )
        .first()
    )

    if existing:
        # Already following, return current state
        follower_count = (
            db.query(func.count(models.Follow.id))
            .filter(models.Follow.following_id == target_user.id)
            .scalar()
            or 0
        )
        return schemas.FollowResponse(following=True, follower_count=follower_count)

    # Create follow relationship
    follow = models.Follow(
        follower_id=current_user.id,
        following_id=target_user.id,
    )
    db.add(follow)
    db.commit()

    # Invalidate stats cache for target user
    invalidate_user_profile_stats_cache(db, target_user.id)

    follower_count = (
        db.query(func.count(models.Follow.id))
        .filter(models.Follow.following_id == target_user.id)
        .scalar()
        or 0
    )

    return schemas.FollowResponse(following=True, follower_count=follower_count)


@router.delete("/u/{public_sqid}/follow", response_model=schemas.FollowResponse)
def unfollow_user(
    public_sqid: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.FollowResponse:
    """
    Unfollow a user.
    """
    from ..sqids_config import decode_user_sqid
    from ..services.user_profile_stats import invalidate_user_profile_stats_cache
    from sqlalchemy import func

    user_id = decode_user_sqid(public_sqid)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Delete follow relationship if it exists
    deleted = (
        db.query(models.Follow)
        .filter(
            models.Follow.follower_id == current_user.id,
            models.Follow.following_id == target_user.id,
        )
        .delete()
    )
    db.commit()

    if deleted:
        # Invalidate stats cache for target user
        invalidate_user_profile_stats_cache(db, target_user.id)

    follower_count = (
        db.query(func.count(models.Follow.id))
        .filter(models.Follow.following_id == target_user.id)
        .scalar()
        or 0
    )

    return schemas.FollowResponse(following=False, follower_count=follower_count)


@router.get("/u/{public_sqid}/followers", response_model=schemas.FollowersResponse)
def get_user_followers(
    public_sqid: str,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.FollowersResponse:
    """
    Get list of users who follow this user.
    """
    from ..sqids_config import decode_user_sqid
    from sqlalchemy import func

    user_id = decode_user_sqid(public_sqid)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Get total count (only verified users)
    total = (
        db.query(func.count(models.Follow.id))
        .join(models.User, models.Follow.follower_id == models.User.id)
        .filter(
            models.Follow.following_id == user.id,
            models.User.email_verified == True,
        )
        .scalar()
        or 0
    )

    # Query followers (only verified users)
    query = (
        db.query(models.User)
        .join(models.Follow, models.Follow.follower_id == models.User.id)
        .filter(
            models.Follow.following_id == user.id,
            models.User.email_verified == True,
        )
    )

    # Apply cursor pagination
    query = apply_cursor_filter(
        query, models.Follow, cursor, "created_at", sort_desc=True
    )
    query = query.order_by(models.Follow.created_at.desc())

    followers = query.limit(limit + 1).all()

    # Create paginated response
    page_data = create_page_response(followers, limit, cursor)

    return schemas.FollowersResponse(
        items=[schemas.UserPublic.model_validate(u) for u in page_data["items"]],
        next_cursor=page_data["next_cursor"],
        total=total,
    )


@router.get("/u/{public_sqid}/following", response_model=schemas.FollowingResponse)
def get_user_following(
    public_sqid: str,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.FollowingResponse:
    """
    Get list of users this user follows.
    """
    from ..sqids_config import decode_user_sqid
    from sqlalchemy import func

    user_id = decode_user_sqid(public_sqid)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Get total count (only verified users)
    total = (
        db.query(func.count(models.Follow.id))
        .join(models.User, models.Follow.following_id == models.User.id)
        .filter(
            models.Follow.follower_id == user.id,
            models.User.email_verified == True,
        )
        .scalar()
        or 0
    )

    # Query following (only verified users)
    query = (
        db.query(models.User)
        .join(models.Follow, models.Follow.following_id == models.User.id)
        .filter(
            models.Follow.follower_id == user.id,
            models.User.email_verified == True,
        )
    )

    # Apply cursor pagination
    query = apply_cursor_filter(
        query, models.Follow, cursor, "created_at", sort_desc=True
    )
    query = query.order_by(models.Follow.created_at.desc())

    following = query.limit(limit + 1).all()

    # Create paginated response
    page_data = create_page_response(following, limit, cursor)

    return schemas.FollowingResponse(
        items=[schemas.UserPublic.model_validate(u) for u in page_data["items"]],
        next_cursor=page_data["next_cursor"],
        total=total,
    )


# ============================================================================
# HIGHLIGHTS ENDPOINTS
# ============================================================================


@router.get(
    "/u/{public_sqid}/highlights", response_model=schemas.UserHighlightsResponse
)
def get_user_highlights(
    public_sqid: str,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.UserHighlightsResponse:
    """
    Get user's highlighted posts.
    """
    from ..sqids_config import decode_user_sqid

    user_id = decode_user_sqid(public_sqid)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    highlights = (
        db.query(models.UserHighlight)
        .options(joinedload(models.UserHighlight.post))
        .filter(models.UserHighlight.user_id == user.id)
        .order_by(models.UserHighlight.position.asc())
        .all()
    )

    items = []
    for hl in highlights:
        if hl.post and not hl.post.deleted_by_user:
            items.append(
                schemas.UserHighlightItem(
                    id=hl.id,
                    post_id=hl.post_id,
                    position=hl.position,
                    post_public_sqid=hl.post.public_sqid,
                    post_title=hl.post.title,
                    post_art_url=hl.post.art_url,
                    post_width=hl.post.width,
                    post_height=hl.post.height,
                    created_at=hl.created_at,
                )
            )

    return schemas.UserHighlightsResponse(items=items, total=len(items))


@router.post(
    "/me/highlights",
    response_model=schemas.AddHighlightResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_highlight(
    payload: schemas.AddHighlightRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.AddHighlightResponse:
    """
    Add a post to the user's highlights.

    Maximum 128 highlights per user. New highlights are added at the end.
    """
    from sqlalchemy import func

    # Check if post exists and belongs to user
    post = db.query(models.Post).filter(models.Post.id == payload.post_id).first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Post not found"
        )

    if post.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only highlight your own posts",
        )

    if post.deleted_by_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot highlight a deleted post",
        )

    # Check if already highlighted
    existing = (
        db.query(models.UserHighlight)
        .filter(
            models.UserHighlight.user_id == current_user.id,
            models.UserHighlight.post_id == payload.post_id,
        )
        .first()
    )
    if existing:
        return schemas.AddHighlightResponse(id=existing.id, position=existing.position)

    # Check highlight count limit
    count = (
        db.query(func.count(models.UserHighlight.id))
        .filter(models.UserHighlight.user_id == current_user.id)
        .scalar()
        or 0
    )
    if count >= 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 128 highlights allowed",
        )

    # Get next position
    max_position = (
        db.query(func.max(models.UserHighlight.position))
        .filter(models.UserHighlight.user_id == current_user.id)
        .scalar()
    )
    next_position = (max_position or -1) + 1

    # Create highlight
    highlight = models.UserHighlight(
        user_id=current_user.id,
        post_id=payload.post_id,
        position=next_position,
    )
    db.add(highlight)
    db.commit()
    db.refresh(highlight)

    return schemas.AddHighlightResponse(id=highlight.id, position=highlight.position)


@router.delete("/me/highlights/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_highlight(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Remove a post from the user's highlights.
    """
    highlight = (
        db.query(models.UserHighlight)
        .filter(
            models.UserHighlight.user_id == current_user.id,
            models.UserHighlight.post_id == post_id,
        )
        .first()
    )
    if not highlight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found"
        )

    removed_position = highlight.position
    db.delete(highlight)

    # Reorder remaining highlights to close the gap
    db.query(models.UserHighlight).filter(
        models.UserHighlight.user_id == current_user.id,
        models.UserHighlight.position > removed_position,
    ).update(
        {models.UserHighlight.position: models.UserHighlight.position - 1},
        synchronize_session=False,
    )

    db.commit()


@router.put("/me/highlights/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_highlights(
    payload: schemas.ReorderHighlightsRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Reorder the user's highlights.

    The post_ids list defines the new order. All existing highlights must be
    included in the list.
    """
    # Get all current highlights
    highlights = (
        db.query(models.UserHighlight)
        .filter(models.UserHighlight.user_id == current_user.id)
        .all()
    )

    current_post_ids = {h.post_id for h in highlights}
    new_post_ids = set(payload.post_ids)

    # Verify all highlights are accounted for
    if current_post_ids != new_post_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All existing highlights must be included in the reorder request",
        )

    # Check for duplicates in the request
    if len(payload.post_ids) != len(new_post_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate post_ids in request",
        )

    # Create lookup for highlights
    highlight_by_post_id = {h.post_id: h for h in highlights}

    # Update positions using a two-pass approach to avoid unique constraint violations
    # First, set all positions to negative values
    for i, post_id in enumerate(payload.post_ids):
        highlight_by_post_id[post_id].position = -(i + 1)
    db.flush()

    # Then, set to final positive values
    for i, post_id in enumerate(payload.post_ids):
        highlight_by_post_id[post_id].position = i

    db.commit()


# ============================================================================
# REACTED POSTS ENDPOINT
# ============================================================================


@router.get(
    "/u/{public_sqid}/reacted-posts", response_model=schemas.ReactedPostsResponse
)
def get_user_reacted_posts(
    public_sqid: str,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ReactedPostsResponse:
    """
    Get posts the user has reacted to.

    Returns up to 8192 most recent reactions. Reactions are ordered by
    reaction time (newest first).

    Requires authentication.
    """
    from sqlalchemy import and_, or_

    from ..sqids_config import decode_user_sqid

    user_id = decode_user_sqid(public_sqid)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Query reactions with posts - base query
    query = (
        db.query(models.Reaction, models.Post)
        .join(models.Post, models.Post.id == models.Reaction.post_id)
        .filter(
            models.Reaction.user_id == user.id,
            models.Post.deleted_by_user == False,
        )
    )

    # Apply visibility filters based on viewer's role
    is_moderator = "moderator" in current_user.roles or "owner" in current_user.roles

    if is_moderator:
        # Moderators see everything (except deleted - already filtered)
        pass
    else:
        # Logged-in user: publicly visible posts + their own posts
        query = query.filter(
            or_(
                and_(
                    models.Post.visible == True,
                    models.Post.hidden_by_mod == False,
                    models.Post.hidden_by_user == False,
                    models.Post.non_conformant == False,
                    or_(
                        models.Post.public_visibility == True,
                        models.Post.promoted == True,
                    ),
                ),
                models.Post.owner_id == current_user.id,
            )
        )

    # Apply cursor pagination on reaction created_at
    if cursor:
        cursor_data = decode_cursor(cursor)
        if cursor_data:
            last_id, sort_value = cursor_data
            if sort_value:
                query = query.filter(models.Reaction.created_at < sort_value)

    query = query.order_by(models.Reaction.created_at.desc())

    # Limit to 8192 total reactions (per spec)
    results = query.limit(min(limit + 1, 8192)).all()

    # Build response items
    items = []
    for i, (reaction, post) in enumerate(results[:limit]):
        owner = db.query(models.User).filter(models.User.id == post.owner_id).first()
        items.append(
            schemas.ReactedPostItem(
                id=post.id,
                public_sqid=post.public_sqid,
                title=post.title,
                art_url=post.art_url,
                width=post.width,
                height=post.height,
                owner_id=post.owner_id,
                owner_handle=owner.handle if owner else "unknown",
                owner=schemas.UserPublic.model_validate(owner) if owner else None,
                reacted_at=reaction.created_at,
                emoji=reaction.emoji,
                created_at=post.created_at,
                file_bytes=post.file_bytes or 0,
                frame_count=post.frame_count or 1,
                file_format=post.file_format,
            )
        )

    # Create next cursor
    next_cursor = None
    if len(results) > limit:
        last_reaction = results[limit - 1][0]
        next_cursor = encode_cursor(
            str(last_reaction.id), last_reaction.created_at.isoformat()
        )

    return schemas.ReactedPostsResponse(items=items, next_cursor=next_cursor)

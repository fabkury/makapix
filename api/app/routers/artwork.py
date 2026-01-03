"""Artwork routes for canonical URLs and downloads."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_user_optional
from ..deps import get_db
from ..utils.visibility import can_access_post
from ..utils.site_tracking import record_site_event
from ..utils.view_tracking import record_view, ViewType, ViewSource
from ..vault import get_artwork_file_path, ALLOWED_MIME_TYPES

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Artwork"])


def get_post_file_path_from_storage_key(storage_key: UUID, file_format: str | None) -> Path:
    """
    Get the file path for a post from its storage_key (UUID).

    Args:
        storage_key: The UUID storage key
        file_format: The file format (e.g., "png", "gif") to determine extension

    Returns:
        Path to the file in the vault
    """
    from ..vault import FORMAT_TO_EXT

    # Determine extension from file_format
    if file_format and file_format in FORMAT_TO_EXT:
        extension = FORMAT_TO_EXT[file_format]
    else:
        # Default to .png if file_format is not available
        extension = ".png"

    return get_artwork_file_path(storage_key, extension)


@router.get("/p/{public_sqid}", response_model=schemas.Post)
def get_post_by_sqid(
    public_sqid: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.Post:
    """
    Get post by public Sqids ID (canonical URL).
    
    This is the canonical URL for posts sitewide.
    """
    # Decode the Sqids ID using the single canonical alphabet (SQIDS_ALPHABET).
    from ..sqids_config import decode_sqid

    post_id = decode_sqid(public_sqid)
    if post_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # Query post with owner relationship
    post = (
        db.query(models.Post)
        .options(joinedload(models.Post.owner))
        .filter(models.Post.id == post_id)
        .first()
    )
    
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    # Verify public_sqid matches (safety check)
    if post.public_sqid != public_sqid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    # Check visibility
    if not can_access_post(post, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    # Add reaction and comment counts
    from ..services.post_stats import annotate_posts_with_counts
    
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


@router.get("/d/{public_sqid}")
def download_by_sqid(
    public_sqid: str,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> FileResponse:
    """
    Download artwork file by public Sqids ID.
    """
    # Decode the Sqids ID using the single canonical alphabet (SQIDS_ALPHABET).
    from ..sqids_config import decode_sqid

    post_id = decode_sqid(public_sqid)
    if post_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # Query post
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    # Verify public_sqid matches
    if post.public_sqid != public_sqid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    # Check visibility
    if not can_access_post(post, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    # Get file path
    file_path = get_post_file_path_from_storage_key(post.storage_key, post.file_format)

    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Determine filename for download
    filename = f"{post.title or 'artwork'}{file_path.suffix}"

    # Get MIME type from file_format
    from ..vault import FORMAT_TO_MIME
    media_type = FORMAT_TO_MIME.get(post.file_format, "image/png") if post.file_format else "image/png"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/download/{storage_key}")
def download_by_storage_key(
    storage_key: UUID,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> FileResponse:
    """
    Download artwork file by storage key (UUID).
    """
    # Query post
    post = db.query(models.Post).filter(models.Post.storage_key == storage_key).first()
    
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    # Check visibility
    if not can_access_post(post, current_user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # Get file path
    file_path = get_post_file_path_from_storage_key(post.storage_key, post.file_format)

    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Determine filename for download
    filename = f"{post.title or 'artwork'}{file_path.suffix}"

    # Get MIME type from file_format
    from ..vault import FORMAT_TO_MIME
    media_type = FORMAT_TO_MIME.get(post.file_format, "image/png") if post.file_format else "image/png"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/u/{public_sqid}", response_model=schemas.UserPublic | schemas.UserFull)
def get_user_by_sqid_canonical(
    public_sqid: str,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.UserPublic | schemas.UserFull:
    """
    Get user by public Sqids ID (canonical URL).
    
    This is the canonical URL for user profiles sitewide.
    Returns UserFull if viewing own profile, UserPublic otherwise.
    """
    from ..sqids_config import decode_user_sqid
    
    user_id = decode_user_sqid(public_sqid)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Query user with badges
    user = (
        db.query(models.User)
        .options(joinedload(models.User.badges))
        .filter(models.User.id == user_id)
        .first()
    )
    
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Check visibility - use same logic as users router
    is_moderator = current_user and ("moderator" in current_user.roles or "owner" in current_user.roles)
    is_own_profile = current_user and current_user.id == user.id
    
    if not is_moderator and not is_own_profile:
        if user.hidden_by_user or user.hidden_by_mod or user.non_conformant or user.deactivated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if user.banned_until:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Return full profile if viewing own profile, public otherwise
    if is_own_profile or is_moderator:
        return schemas.UserFull.model_validate(user)
    return schemas.UserPublic.model_validate(user)

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
from ..vault import get_artwork_file_path, ALLOWED_MIME_TYPES

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Artwork"])


def get_post_file_path_from_storage_key(storage_key: UUID, mime_type: str | None) -> Path:
    """
    Get the file path for a post from its storage_key (UUID).
    
    Args:
        storage_key: The UUID storage key
        mime_type: The MIME type (e.g., "image/png") to determine extension
        
    Returns:
        Path to the file in the vault
    """
    # Determine extension from mime_type
    if mime_type and mime_type in ALLOWED_MIME_TYPES:
        extension = ALLOWED_MIME_TYPES[mime_type]
    else:
        # Default to .png if mime_type is not available
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
    # Decode the Sqids ID
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
    
    # Record site event for page view
    record_site_event(request, "page_view", user=current_user)
    
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
    # Decode the Sqids ID
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
    file_path = get_post_file_path_from_storage_key(post.storage_key, post.mime_type)
    
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    
    # Determine filename for download
    filename = f"{post.title or 'artwork'}{file_path.suffix}"
    
    return FileResponse(
        path=str(file_path),
        media_type=post.mime_type or "image/png",
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
    file_path = get_post_file_path_from_storage_key(post.storage_key, post.mime_type)
    
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    
    # Determine filename for download
    filename = f"{post.title or 'artwork'}{file_path.suffix}"
    
    return FileResponse(
        path=str(file_path),
        media_type=post.mime_type or "image/png",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


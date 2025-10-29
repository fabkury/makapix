"""Playlist management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_moderator, require_ownership
from ..deps import get_db

router = APIRouter(prefix="/playlists", tags=["Playlists"])


def validate_post_visibility(post_ids: list[UUID], db: Session) -> list[UUID]:
    """
    Validate that posts exist and are visible.
    
    Returns list of valid (visible) post IDs.
    Raises HTTPException if any post doesn't exist.
    """
    if not post_ids:
        return []
    
    valid_post_ids = []
    
    for post_id in post_ids:
        post = db.query(models.Post).filter(models.Post.id == post_id).first()
        
        if not post:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Post {post_id} not found"
            )
        
        # Only include visible, non-hidden posts
        if post.visible and not post.hidden_by_mod and not post.non_conformant:
            valid_post_ids.append(post_id)
    
    return valid_post_ids


@router.get("", response_model=schemas.Page[schemas.Playlist])
def list_playlists(
    owner_id: UUID | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    sort: str | None = "created_at",
    order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
) -> schemas.Page[schemas.Playlist]:
    """
    List playlists.
    
    TODO: Implement search query
    TODO: Implement cursor pagination
    TODO: Apply visibility filters
    """
    query = db.query(models.Playlist).filter(
        models.Playlist.visible == True,
        models.Playlist.hidden_by_mod == False,
    )
    
    if owner_id:
        query = query.filter(models.Playlist.owner_id == owner_id)
    
    query = query.order_by(models.Playlist.created_at.desc()).limit(limit)
    playlists = query.all()
    
    return schemas.Page(
        items=[schemas.Playlist.model_validate(p) for p in playlists],
        next_cursor=None,
    )


@router.post(
    "",
    response_model=schemas.Playlist,
    status_code=status.HTTP_201_CREATED,
)
def create_playlist(
    payload: schemas.PlaylistCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Playlist:
    """
    Create playlist.
    
    Validates that all posts exist and are visible.
    """
    # Validate all posts exist and filter to visible ones
    valid_post_ids = validate_post_visibility(payload.post_ids, db)
    
    playlist = models.Playlist(
        owner_id=current_user.id,
        title=payload.title,
        description=payload.description,
        post_ids=valid_post_ids,
    )
    db.add(playlist)
    db.commit()
    db.refresh(playlist)
    
    return schemas.Playlist.model_validate(playlist)


@router.get("/{id}", response_model=schemas.Playlist)
def get_playlist(id: UUID, db: Session = Depends(get_db)) -> schemas.Playlist:
    """Get playlist by ID."""
    playlist = db.query(models.Playlist).filter(models.Playlist.id == id).first()
    if not playlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    
    return schemas.Playlist.model_validate(playlist)


@router.patch("/{id}", response_model=schemas.Playlist)
def update_playlist(
    id: UUID,
    payload: schemas.PlaylistUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Playlist:
    """
    Update playlist.
    
    Validates ownership and post visibility.
    """
    playlist = db.query(models.Playlist).filter(models.Playlist.id == id).first()
    if not playlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    
    require_ownership(playlist.owner_id, current_user)
    
    if payload.title is not None:
        playlist.title = payload.title
    if payload.description is not None:
        playlist.description = payload.description
    if payload.post_ids is not None:
        # Validate all posts exist and filter to visible ones
        valid_post_ids = validate_post_visibility(payload.post_ids, db)
        playlist.post_ids = valid_post_ids
    if payload.hidden_by_user is not None:
        playlist.hidden_by_user = payload.hidden_by_user
    if payload.hidden_by_mod is not None:
        playlist.hidden_by_mod = payload.hidden_by_mod
    
    db.commit()
    db.refresh(playlist)
    
    return schemas.Playlist.model_validate(playlist)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playlist(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Delete playlist (soft delete)."""
    playlist = db.query(models.Playlist).filter(models.Playlist.id == id).first()
    if not playlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    
    require_ownership(playlist.owner_id, current_user)
    
    playlist.visible = False
    playlist.hidden_by_user = True
    db.commit()


@router.post(
    "/{id}/undelete",
    status_code=status.HTTP_201_CREATED,
    tags=["Playlists", "Admin"],
)
def undelete_playlist(
    id: UUID,
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> None:
    """Undelete playlist (moderator only)."""
    playlist = db.query(models.Playlist).filter(models.Playlist.id == id).first()
    if not playlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    
    playlist.visible = True
    playlist.hidden_by_user = False
    playlist.hidden_by_mod = False
    db.commit()


@router.post("/{id}/hide", status_code=status.HTTP_201_CREATED)
def hide_playlist(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Hide playlist."""
    playlist = db.query(models.Playlist).filter(models.Playlist.id == id).first()
    if not playlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    
    require_ownership(playlist.owner_id, current_user)
    playlist.hidden_by_user = True
    db.commit()


@router.delete("/{id}/hide", status_code=status.HTTP_204_NO_CONTENT)
def unhide_playlist(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Unhide playlist."""
    playlist = db.query(models.Playlist).filter(models.Playlist.id == id).first()
    if not playlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found")
    
    require_ownership(playlist.owner_id, current_user)
    playlist.hidden_by_user = False
    db.commit()

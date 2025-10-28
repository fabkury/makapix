"""Playlist management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_moderator, require_ownership
from ..deps import get_db

router = APIRouter(prefix="/playlists", tags=["Playlists"])


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
    
    TODO: Validate that all post_ids exist and are visible
    """
    playlist = models.Playlist(
        owner_id=current_user.id,
        title=payload.title,
        description=payload.description,
        post_ids=payload.post_ids,
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
    
    TODO: Validate ownership
    TODO: Validate that all post_ids exist
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
        playlist.post_ids = payload.post_ids
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

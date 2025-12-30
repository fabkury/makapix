"""Playlist management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_moderator, require_ownership
from ..deps import get_db

router = APIRouter(prefix="/playlist", tags=["Playlists"])


def validate_post_visibility(post_ids: list[int], db: Session) -> list[int]:
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
        if (
            post.kind == "artwork"
            and post.visible
            and not post.hidden_by_mod
            and not post.non_conformant
        ):
            valid_post_ids.append(post_id)
    
    return valid_post_ids


def _get_playlist_post_by_legacy_id(id: UUID, db: Session) -> models.Post:
    """Resolve legacy playlist UUID to the underlying playlist post row."""
    pp = (
        db.query(models.PlaylistPost)
        .filter(models.PlaylistPost.legacy_playlist_id == id)
        .first()
    )
    if not pp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
        )
    post = db.query(models.Post).filter(models.Post.id == pp.post_id).first()
    if not post or post.kind != "playlist":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Playlist not found"
        )
    return post


def _playlist_schema_from_post(post: models.Post, db: Session) -> schemas.Playlist:
    legacy_id = (
        db.query(models.PlaylistPost.legacy_playlist_id)
        .filter(models.PlaylistPost.post_id == post.id)
        .scalar()
    )
    if legacy_id is None:
        # Should not happen, but keep API stable.
        legacy_id = uuid.uuid4()

    item_ids = (
        db.query(models.PlaylistItem.artwork_post_id)
        .filter(models.PlaylistItem.playlist_post_id == post.id)
        .order_by(models.PlaylistItem.position.asc())
        .all()
    )
    post_ids = [pid for (pid,) in item_ids]

    return schemas.Playlist(
        id=legacy_id,
        owner_id=post.owner_id,
        title=post.title,
        description=post.description,
        post_ids=post_ids,
        visible=post.visible,
        hidden_by_user=post.hidden_by_user,
        hidden_by_mod=post.hidden_by_mod,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


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
    # Playlists are represented as posts(kind="playlist") + playlist_items.
    query = db.query(models.Post).filter(
        models.Post.kind == "playlist",
        models.Post.visible == True,
        models.Post.hidden_by_mod == False,
    )
    
    if owner_id:
        # owner_id is a legacy user_key UUID in API; map to integer users.id
        owner = db.query(models.User).filter(models.User.user_key == owner_id).first()
        if not owner:
            return schemas.Page(items=[], next_cursor=None)
        query = query.filter(models.Post.owner_id == owner.id)
    
    # TODO: Implement q/cursor/sort/order for playlists in a future iteration.
    query = query.order_by(models.Post.created_at.desc()).limit(limit)
    playlist_posts = query.all()
    
    return schemas.Page(
        items=[_playlist_schema_from_post(p, db) for p in playlist_posts],
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
    
    now = datetime.now(timezone.utc)

    # Create an underlying post(kind="playlist")
    playlist_post = models.Post(
        storage_key=uuid.uuid4(),
        owner_id=current_user.id,
        kind="playlist",
        title=payload.title,
        description=payload.description,
        hashtags=[],
        art_url=None,
        canvas=None,
        width=None,
        height=None,
        file_bytes=None,
        frame_count=1,
        min_frame_duration_ms=None,
        max_frame_duration_ms=None,
        bit_depth=None,
        unique_colors=None,
        transparency_meta=False,
        alpha_meta=False,
        transparency_actual=False,
        alpha_actual=False,
        hash=None,
        mime_type=None,
        visible=True,
        hidden_by_user=False,
        hidden_by_mod=False,
        non_conformant=False,
        public_visibility=False,
        promoted=False,
        promoted_category=None,
        metadata_modified_at=now,
        artwork_modified_at=now,
        dwell_time_ms=30000,
    )
    db.add(playlist_post)
    db.flush()  # get playlist_post.id

    from ..sqids_config import encode_id

    playlist_post.public_sqid = encode_id(playlist_post.id)

    legacy_id = uuid.uuid4()
    db.add(models.PlaylistPost(post_id=playlist_post.id, legacy_playlist_id=legacy_id))

    for idx, post_id in enumerate(valid_post_ids):
        db.add(
            models.PlaylistItem(
                playlist_post_id=playlist_post.id,
                artwork_post_id=post_id,
                position=idx,
                dwell_time_ms=30000,
            )
        )

    db.commit()
    db.refresh(playlist_post)

    return _playlist_schema_from_post(playlist_post, db)


@router.get("/{id}", response_model=schemas.Playlist)
def get_playlist(id: UUID, db: Session = Depends(get_db)) -> schemas.Playlist:
    """Get playlist by ID."""
    playlist_post = _get_playlist_post_by_legacy_id(id, db)
    return _playlist_schema_from_post(playlist_post, db)


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
    playlist_post = _get_playlist_post_by_legacy_id(id, db)
    require_ownership(playlist_post.owner_id, current_user)
    
    if payload.title is not None:
        playlist_post.title = payload.title
    if payload.description is not None:
        playlist_post.description = payload.description
    if payload.post_ids is not None:
        # Validate all posts exist and filter to visible ones
        valid_post_ids = validate_post_visibility(payload.post_ids, db)
        # Replace items (preserve order)
        db.query(models.PlaylistItem).filter(
            models.PlaylistItem.playlist_post_id == playlist_post.id
        ).delete()
        for idx, post_id in enumerate(valid_post_ids):
            db.add(
                models.PlaylistItem(
                    playlist_post_id=playlist_post.id,
                    artwork_post_id=post_id,
                    position=idx,
                    dwell_time_ms=30000,
                )
            )
    if payload.hidden_by_user is not None:
        playlist_post.hidden_by_user = payload.hidden_by_user
    if payload.hidden_by_mod is not None:
        playlist_post.hidden_by_mod = payload.hidden_by_mod

    playlist_post.metadata_modified_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(playlist_post)
    
    return _playlist_schema_from_post(playlist_post, db)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playlist(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Delete playlist (soft delete)."""
    playlist_post = _get_playlist_post_by_legacy_id(id, db)
    require_ownership(playlist_post.owner_id, current_user)

    playlist_post.visible = False
    playlist_post.hidden_by_user = True
    playlist_post.metadata_modified_at = datetime.now(timezone.utc)
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
    playlist_post = _get_playlist_post_by_legacy_id(id, db)

    playlist_post.visible = True
    playlist_post.hidden_by_user = False
    playlist_post.hidden_by_mod = False
    playlist_post.metadata_modified_at = datetime.now(timezone.utc)
    db.commit()


@router.post("/{id}/hide", status_code=status.HTTP_201_CREATED)
def hide_playlist(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Hide playlist."""
    playlist_post = _get_playlist_post_by_legacy_id(id, db)
    require_ownership(playlist_post.owner_id, current_user)
    playlist_post.hidden_by_user = True
    playlist_post.metadata_modified_at = datetime.now(timezone.utc)
    db.commit()


@router.delete("/{id}/hide", status_code=status.HTTP_204_NO_CONTENT)
def unhide_playlist(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Unhide playlist."""
    playlist_post = _get_playlist_post_by_legacy_id(id, db)
    require_ownership(playlist_post.owner_id, current_user)
    playlist_post.hidden_by_user = False
    playlist_post.metadata_modified_at = datetime.now(timezone.utc)
    db.commit()

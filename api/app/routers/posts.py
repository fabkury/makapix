"""Post management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import check_ownership, get_current_user, get_current_user_optional, require_moderator, require_ownership
from ..deps import get_db
from ..pagination import apply_cursor_filter, create_page_response

router = APIRouter(prefix="/posts", tags=["Posts"])


@router.get("", response_model=schemas.Page[schemas.Post])
def list_posts(
    owner_id: UUID | None = None,
    hashtag: str | None = None,
    promoted: bool | None = None,
    visible_only: bool = True,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    sort: str | None = "created_at",
    order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.Page[schemas.Post]:
    """
    List posts with filters.
    """
    query = db.query(models.Post)
    
    if owner_id:
        query = query.filter(models.Post.owner_id == owner_id)
    
    # Apply visibility filters
    if visible_only:
        query = query.filter(models.Post.visible == True)
        
        # Hide posts hidden by moderators unless current user is moderator/owner
        if not current_user or not ("moderator" in current_user.roles or "owner" in current_user.roles):
            query = query.filter(models.Post.hidden_by_mod == False)
        
        # Hide non-conformant posts unless current user is moderator/owner
        if not current_user or not ("moderator" in current_user.roles or "owner" in current_user.roles):
            query = query.filter(models.Post.non_conformant == False)
    
    if promoted is not None:
        query = query.filter(models.Post.promoted == promoted)
    
    # Implement hashtag filter using PostgreSQL array contains
    if hashtag:
        query = query.filter(models.Post.hashtags.contains([hashtag]))
    
    # Apply cursor pagination
    sort_desc = order == "desc"
    query = apply_cursor_filter(query, models.Post, cursor, sort or "created_at", sort_desc=sort_desc)
    
    # Order and limit
    if sort == "created_at":
        if order == "desc":
            query = query.order_by(models.Post.created_at.desc())
        else:
            query = query.order_by(models.Post.created_at.asc())
    
    # Fetch limit + 1 to check if there are more results
    posts = query.limit(limit + 1).all()
    
    # Create paginated response
    page_data = create_page_response(posts, limit, cursor)
    
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
    # Validate canvas dimensions against allowed list
    allowed_canvases = ["16x16", "32x32", "64x64", "96x64", "128x64", "128x128", "160x128", "240x135", "240x240", "256x256"]
    if payload.canvas not in allowed_canvases:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Canvas size '{payload.canvas}' not allowed. Allowed sizes: {', '.join(allowed_canvases)}"
        )
    
    # Validate file size (basic check)
    max_file_kb = 350  # Default limit
    if payload.file_kb > max_file_kb:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size {payload.file_kb}KB exceeds limit of {max_file_kb}KB"
        )
    
    # Normalize hashtags (lowercase, strip whitespace)
    normalized_hashtags = []
    for tag in payload.hashtags:
        normalized_tag = tag.strip().lower()
        if normalized_tag and normalized_tag not in normalized_hashtags:
            normalized_hashtags.append(normalized_tag)
    
    post = models.Post(
        owner_id=current_user.id,
        kind=payload.kind,
        title=payload.title,
        description=payload.description,
        hashtags=normalized_hashtags,
        art_url=str(payload.art_url),
        canvas=payload.canvas,
        file_kb=payload.file_kb,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    
    # TODO: Queue conformance check job
    # TODO: Publish MQTT notification
    
    return schemas.Post.model_validate(post)


@router.get("/recent", response_model=schemas.Page[schemas.Post])
def list_recent_posts(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> schemas.Page[schemas.Post]:
    """
    List recent posts (visible only).
    
    TODO: Implement cursor pagination
    TODO: Cache this query with short TTL
    """
    query = (
        db.query(models.Post)
        .filter(
            models.Post.visible == True,
            models.Post.hidden_by_mod == False,
        )
        .order_by(models.Post.created_at.desc())
        .limit(limit)
    )
    
    posts = query.all()
    
    return schemas.Page(
        items=[schemas.Post.model_validate(p) for p in posts],
        next_cursor=None,
    )


@router.get("/{id}", response_model=schemas.Post)
def get_post(
    id: UUID, 
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional)
) -> schemas.Post:
    """
    Get post by ID.
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    # Check visibility
    if not post.visible:
        if not current_user or not check_ownership(post.owner_id, current_user):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    if post.hidden_by_mod:
        if not current_user or not ("moderator" in current_user.roles or "owner" in current_user.roles):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    if post.non_conformant:
        if not current_user or not ("moderator" in current_user.roles or "owner" in current_user.roles):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    return schemas.Post.model_validate(post)


@router.patch("/{id}", response_model=schemas.Post)
def update_post(
    id: UUID,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
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
    id: UUID,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    require_ownership(post.owner_id, current_user)
    
    post.visible = False
    post.hidden_by_user = True
    db.commit()


@router.post(
    "/{id}/undelete",
    status_code=status.HTTP_201_CREATED,
    tags=["Posts", "Admin"],
)
def undelete_post_by_moderator(
    id: UUID,
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Undelete post (moderator only).
    
    TODO: Log this action in audit log
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    post.visible = True
    post.hidden_by_user = False
    post.hidden_by_mod = False
    db.commit()


@router.post("/{id}/hide", status_code=status.HTTP_201_CREATED)
def hide_post(
    id: UUID,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    by = payload.by if payload else "user"
    
    if by == "mod":
        # TODO: Check moderator role
        post.hidden_by_mod = True
    else:
        require_ownership(post.owner_id, current_user)
        post.hidden_by_user = True
    
    db.commit()


@router.delete("/{id}/hide", status_code=status.HTTP_204_NO_CONTENT)
def unhide_post(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Unhide post.
    
    TODO: Validate that user is owner or moderator
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    require_ownership(post.owner_id, current_user)
    
    post.hidden_by_user = False
    # Moderators can unhide mod-hidden posts
    # TODO: Check if user is moderator before allowing to unhide hidden_by_mod
    db.commit()


@router.post(
    "/{id}/promote",
    response_model=schemas.PromotePostResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Admin"],
)
def promote_post(
    id: UUID,
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    post.promoted = True
    post.promoted_category = payload.category
    db.commit()
    
    return schemas.PromotePostResponse(promoted=True, category=payload.category)


@router.delete(
    "/{id}/promote",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Admin"],
)
def demote_post(
    id: UUID,
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Demote post (moderator only).
    
    TODO: Log in audit log
    """
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    post.promoted = False
    post.promoted_category = None
    db.commit()


@router.get(
    "/{id}/admin-notes",
    response_model=schemas.AdminNoteList,
    tags=["Admin"],
)
def list_post_admin_notes(
    id: UUID,
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
    id: UUID,
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

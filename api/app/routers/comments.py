"""Comment management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_moderator, require_ownership
from ..deps import get_db

router = APIRouter(prefix="/posts", tags=["Comments"])


@router.get("/{id}/comments", response_model=schemas.Page[schemas.Comment])
def list_comments(
    id: UUID,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    view: str = Query("flat", regex="^(flat|tree)$"),
    db: Session = Depends(get_db),
) -> schemas.Page[schemas.Comment]:
    """
    List comments for a post.
    
    TODO: Implement tree view (nested structure)
    TODO: Implement cursor pagination
    TODO: Hide hidden_by_mod comments for non-moderators
    """
    query = (
        db.query(models.Comment)
        .filter(models.Comment.post_id == id)
        .order_by(models.Comment.created_at.asc())
        .limit(limit)
    )
    
    comments = query.all()
    
    return schemas.Page(
        items=[schemas.Comment.model_validate(c) for c in comments],
        next_cursor=None,
    )


@router.post(
    "/{id}/comments",
    response_model=schemas.Comment,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    id: UUID,
    payload: schemas.CommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Comment:
    """
    Create comment on a post.
    
    TODO: Validate max_comment_depth (currently 2)
    TODO: Validate max_comments_per_post
    TODO: Check if parent comment exists and belongs to this post
    TODO: Calculate depth based on parent
    TODO: Publish MQTT notification
    """
    depth = 0
    if payload.parent_id:
        parent = db.query(models.Comment).filter(models.Comment.id == payload.parent_id).first()
        if not parent or parent.post_id != id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid parent comment"
            )
        depth = parent.depth + 1
        if depth > 2:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Maximum comment depth exceeded"
            )
    
    comment = models.Comment(
        post_id=id,
        author_id=current_user.id,
        parent_id=payload.parent_id,
        depth=depth,
        body=payload.body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    
    return schemas.Comment.model_validate(comment)


@router.patch("/comments/{commentId}", response_model=schemas.Comment)
def update_comment(
    commentId: UUID,
    payload: schemas.CommentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Comment:
    """
    Update comment.
    
    TODO: Validate ownership
    TODO: Set updated_at timestamp
    """
    comment = db.query(models.Comment).filter(models.Comment.id == commentId).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    
    require_ownership(comment.author_id, current_user)
    
    comment.body = payload.body
    db.commit()
    db.refresh(comment)
    
    return schemas.Comment.model_validate(comment)


@router.delete("/comments/{commentId}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    commentId: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """
    Delete comment (soft delete).
    
    TODO: Set deleted_by_owner=True instead of hard delete
    """
    comment = db.query(models.Comment).filter(models.Comment.id == commentId).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    
    require_ownership(comment.author_id, current_user)
    
    comment.deleted_by_owner = True
    comment.body = "[deleted]"
    db.commit()


@router.post(
    "/comments/{commentId}/undelete",
    status_code=status.HTTP_201_CREATED,
    tags=["Comments", "Admin"],
)
def undelete_comment(
    commentId: UUID,
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> None:
    """Undelete comment (moderator only)."""
    comment = db.query(models.Comment).filter(models.Comment.id == commentId).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    
    comment.deleted_by_owner = False
    db.commit()


@router.post(
    "/comments/{commentId}/hide",
    status_code=status.HTTP_201_CREATED,
    tags=["Comments", "Admin"],
)
def hide_comment(
    commentId: UUID,
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> None:
    """Hide comment (moderator only)."""
    comment = db.query(models.Comment).filter(models.Comment.id == commentId).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    
    comment.hidden_by_mod = True
    db.commit()


@router.delete(
    "/comments/{commentId}/hide",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Comments", "Admin"],
)
def unhide_comment(
    commentId: UUID,
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> None:
    """Unhide comment (moderator only)."""
    comment = db.query(models.Comment).filter(models.Comment.id == commentId).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    
    comment.hidden_by_mod = False
    db.commit()

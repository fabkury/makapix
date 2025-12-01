"""Comment management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import AnonymousUser, get_current_user, get_current_user_or_anonymous, require_moderator, require_ownership
from ..deps import get_db
from ..utils.audit import log_moderation_action

router = APIRouter(prefix="/post", tags=["Comments"])


@router.get("/{id}/comments", response_model=schemas.Page[schemas.Comment])
def list_comments(
    id: int,  # Post ID (integer)
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    view: str = Query("flat", regex="^(flat|tree)$"),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_or_anonymous),
) -> schemas.Page[schemas.Comment]:
    """
    List comments for a post.
    
    Returns comments with guest names for anonymous users.
    Moderators can see hidden comments; regular users cannot.
    Filters out comments with invalid depth (> 2) to prevent widget errors.
    Deleted comments are filtered out unless they have child comments (to maintain thread structure).
    """
    query = db.query(models.Comment).options(joinedload(models.Comment.author)).filter(models.Comment.post_id == id)
    
    # Hide comments hidden by moderators unless current user is a moderator
    is_moderator = (
        isinstance(current_user, models.User) 
        and ("moderator" in current_user.roles or "owner" in current_user.roles)
    )
    if not is_moderator:
        query = query.filter(models.Comment.hidden_by_mod == False)
    
    # Filter out comments with invalid depth (> 2) to prevent widget errors
    query = query.filter(models.Comment.depth <= 2)
    
    # Order by creation time and apply limit
    query = query.order_by(models.Comment.created_at.asc()).limit(limit)
    
    comments = query.all()
    
    # Filter out deleted comments recursively using bottom-up approach
    # Build a map of comment ID -> list of children comment IDs
    comment_dict = {c.id: c for c in comments}
    children_map: dict[UUID, list[UUID]] = {}
    for comment in comments:
        if comment.parent_id is not None:
            if comment.parent_id not in children_map:
                children_map[comment.parent_id] = []
            children_map[comment.parent_id].append(comment.id)
    
    # Iteratively remove deleted comments that have no children (bottom-up)
    # Continue until no more deletions occur
    removed_ids: set[UUID] = set()
    changed = True
    while changed:
        changed = False
        # Find deleted leaf comments (comments with no children in the current result set)
        for comment_id, comment in list(comment_dict.items()):
            if comment.deleted_by_owner and comment_id not in removed_ids:
                # Check if this comment has any children that are still in the result set
                has_children = False
                if comment_id in children_map:
                    for child_id in children_map[comment_id]:
                        if child_id not in removed_ids:
                            has_children = True
                            break
                
                # If no children, remove this deleted comment
                if not has_children:
                    removed_ids.add(comment_id)
                    changed = True
    
    # Filter out removed comments
    comments = [c for c in comments if c.id not in removed_ids]
    
    # Additional validation: filter out comments that reference invalid parents
    valid_comments = []
    comment_ids = {c.id for c in comments}
    
    for comment in comments:
        # Skip comments with parent_id that doesn't exist in the result set
        # (orphaned comments or invalid parent references)
        if comment.parent_id is None:
            valid_comments.append(comment)
        elif comment.parent_id in comment_ids:
            valid_comments.append(comment)
        # else: skip orphaned comment
    
    return schemas.Page(
        items=[schemas.Comment.model_validate(c) for c in valid_comments],
        next_cursor=None,
    )


@router.post(
    "/{id}/comments",
    response_model=schemas.Comment,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    id: int,  # Post ID (integer)
    payload: schemas.CommentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | AnonymousUser = Depends(get_current_user_or_anonymous),
) -> schemas.Comment:
    """
    Create comment on a post.
    
    Supports both authenticated and anonymous users.
    Enforces max depth of 2 and max 1000 comments per post.
    """
    # Check comment count limit (1000 per post)
    comment_count = db.query(func.count(models.Comment.id)).filter(
        models.Comment.post_id == id
    ).scalar()
    
    if comment_count >= 1000:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Maximum comments per post (1000) exceeded"
        )
    
    # Validate parent comment and calculate depth
    depth = 0
    if payload.parent_id:
        parent = db.query(models.Comment).filter(models.Comment.id == payload.parent_id).first()
        if not parent or parent.post_id != id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid parent comment"
            )
        
        # Validate parent depth is valid (< 2)
        if parent.depth >= 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reply to comment at maximum depth"
            )
        
        depth = parent.depth + 1
        if depth > 2:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Maximum comment depth (2) exceeded"
            )
    
    # Create comment with appropriate author identification
    comment = models.Comment(
        post_id=id,
        author_id=current_user.id if isinstance(current_user, models.User) else None,
        author_ip=current_user.ip if isinstance(current_user, AnonymousUser) else None,
        parent_id=payload.parent_id,
        depth=depth,
        body=payload.body,
    )
    db.add(comment)
    db.commit()
    
    # Reload comment with author relationship to ensure display name is available
    comment = db.query(models.Comment).options(
        joinedload(models.Comment.author)
    ).filter(models.Comment.id == comment.id).first()
    
    return schemas.Comment.model_validate(comment)


@router.patch("/comments/{commentId}", response_model=schemas.Comment)
def update_comment(
    commentId: UUID,
    payload: schemas.CommentUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Comment:
    """
    Update comment (authenticated users only).
    
    Anonymous users cannot edit their comments.
    """
    comment = db.query(models.Comment).filter(models.Comment.id == commentId).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    
    # Anonymous comments cannot be edited
    if comment.author_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Anonymous comments cannot be edited"
        )
    
    require_ownership(comment.author_id, current_user)
    
    comment.body = payload.body
    db.commit()
    
    # Reload comment with author relationship to ensure display name is available
    comment = db.query(models.Comment).options(
        joinedload(models.Comment.author)
    ).filter(models.Comment.id == comment.id).first()
    
    return schemas.Comment.model_validate(comment)


@router.delete("/comments/{commentId}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    commentId: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | AnonymousUser = Depends(get_current_user_or_anonymous),
) -> None:
    """
    Delete comment (soft delete).
    
    Supports both authenticated and anonymous users.
    For anonymous users, ownership is verified by IP address.
    """
    comment = db.query(models.Comment).filter(models.Comment.id == commentId).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    
    # Check ownership
    if isinstance(current_user, models.User):
        # Authenticated user: check by user_id
        if comment.author_id != current_user.id:
            # Check if user is moderator/owner
            if "moderator" not in current_user.roles and "owner" not in current_user.roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to delete this comment"
                )
    else:
        # Anonymous user: check by IP
        if comment.author_id is not None:
            # Comment was created by authenticated user, anonymous can't delete it
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this comment"
            )
        if comment.author_ip != current_user.ip:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this comment"
            )
    
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
    
    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=_moderator.id,
        action="undelete_comment",
        target_type="comment",
        target_id=commentId,
    )


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
    
    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=_moderator.id,
        action="hide_comment",
        target_type="comment",
        target_id=commentId,
    )


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
    
    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=_moderator.id,
        action="unhide_comment",
        target_type="comment",
        target_id=commentId,
    )

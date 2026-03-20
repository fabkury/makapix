"""Comment like endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, get_current_user_or_anonymous, AnonymousUser
from ..deps import get_db
from ..services.social_notifications import SocialNotificationService
from ..services.rate_limit import check_rate_limit

router = APIRouter(prefix="/post", tags=["Comment Likes"])


def annotate_comments_with_likes(
    db: Session,
    comments: list[models.Comment],
    current_user_id: int | None,
) -> None:
    """Annotate Comment ORM objects with _like_count and _liked_by_me."""
    if not comments:
        return

    comment_ids = [c.id for c in comments]

    # Bulk query: like counts per comment
    count_rows = (
        db.query(
            models.CommentLike.comment_id,
            func.count(models.CommentLike.id).label("cnt"),
        )
        .filter(models.CommentLike.comment_id.in_(comment_ids))
        .group_by(models.CommentLike.comment_id)
        .all()
    )
    count_map = {row.comment_id: row.cnt for row in count_rows}

    # Bulk query: which comments the current user liked
    liked_set: set[UUID] = set()
    if current_user_id:
        liked_rows = (
            db.query(models.CommentLike.comment_id)
            .filter(
                models.CommentLike.comment_id.in_(comment_ids),
                models.CommentLike.user_id == current_user_id,
            )
            .all()
        )
        liked_set = {row.comment_id for row in liked_rows}

    for comment in comments:
        comment._like_count = count_map.get(comment.id, 0)
        comment._liked_by_me = comment.id in liked_set


@router.put(
    "/comments/{commentId}/like",
    status_code=status.HTTP_204_NO_CONTENT,
)
def like_comment(
    commentId: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Toggle like ON for a comment (idempotent)."""
    # Rate limit: 120 likes per 5 minutes
    allowed, _ = check_rate_limit(f"ratelimit:comment_like:{current_user.id}", 120, 300)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many likes. Please slow down.",
        )

    comment = (
        db.query(models.Comment)
        .filter(
            models.Comment.id == commentId,
            models.Comment.deleted_by_owner == False,
            models.Comment.hidden_by_mod == False,
        )
        .first()
    )
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found.",
        )

    # Create like if not exists (idempotent)
    existing = (
        db.query(models.CommentLike)
        .filter(
            models.CommentLike.comment_id == commentId,
            models.CommentLike.user_id == current_user.id,
        )
        .first()
    )
    if not existing:
        like = models.CommentLike(comment_id=commentId, user_id=current_user.id)
        db.add(like)
        db.commit()

        # Send notification to comment author
        if comment.author_id:
            post = (
                db.query(models.Post).filter(models.Post.id == comment.post_id).first()
            )
            if post:
                SocialNotificationService.create_notification(
                    db,
                    user_id=comment.author_id,
                    notification_type="comment_like",
                    post=post,
                    actor=current_user,
                    comment=comment,
                )

    return None


@router.delete(
    "/comments/{commentId}/like",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unlike_comment(
    commentId: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Toggle like OFF for a comment (idempotent)."""
    existing = (
        db.query(models.CommentLike)
        .filter(
            models.CommentLike.comment_id == commentId,
            models.CommentLike.user_id == current_user.id,
        )
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()

    return None


@router.get(
    "/comments/{commentId}/like-users",
    response_model=schemas.CommentLikeUsersResponse,
)
def get_comment_like_users(
    commentId: UUID,
    db: Session = Depends(get_db),
):
    """List users who liked a comment."""
    likes = (
        db.query(models.CommentLike)
        .filter(models.CommentLike.comment_id == commentId)
        .order_by(models.CommentLike.created_at.desc())
        .limit(200)
        .all()
    )

    items = []
    for like in likes:
        user = like.user
        if user:
            items.append(
                schemas.CommentLikeUserItem(
                    created_at=like.created_at,
                    user_handle=user.handle,
                    user_avatar_url=user.avatar_url,
                    user_public_sqid=user.public_sqid,
                )
            )

    return schemas.CommentLikeUsersResponse(items=items, total=len(items))

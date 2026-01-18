"""User Management Dashboard (UMD) endpoints.

Provides moderator-only endpoints for managing individual users.
Accessible via /u/{sqid}/manage in the frontend.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import require_moderator, require_owner
from ..deps import get_db
from ..sqids_config import decode_user_sqid
from ..utils.audit import log_moderation_action
from ..pagination import apply_cursor_filter, create_page_response

router = APIRouter(prefix="/admin", tags=["UMD"])


def get_user_by_sqid_or_404(db: Session, sqid: str) -> models.User:
    """Look up user by public_sqid, raise 404 if not found."""
    user_id = decode_user_sqid(sqid)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.public_sqid != sqid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return user


def protect_owner(target: models.User, actor: models.User) -> None:
    """Raise 403 if target is owner and actor is not the owner themselves."""
    if "owner" in target.roles and target.id != actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage the site owner",
        )


# ============================================================================
# USER DATA
# ============================================================================


@router.get("/user/{sqid}/manage", response_model=schemas.UMDUserData)
def get_umd_user_data(
    sqid: str,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> schemas.UMDUserData:
    """
    Get user data for UMD page (moderator only).

    Returns user profile, badges, and moderation status.
    Cannot be used on the site owner.
    """
    user = get_user_by_sqid_or_404(db, sqid)
    protect_owner(user, moderator)

    # Load badges
    badges = db.query(models.BadgeGrant).filter(models.BadgeGrant.user_id == user.id).all()

    return schemas.UMDUserData(
        id=user.id,
        user_key=user.user_key,
        public_sqid=user.public_sqid,
        handle=user.handle,
        avatar_url=user.avatar_url,
        reputation=user.reputation,
        badges=[schemas.BadgeGrant.model_validate(b) for b in badges],
        auto_public_approval=user.auto_public_approval,
        hidden_by_mod=user.hidden_by_mod,
        banned_until=user.banned_until,
        roles=user.roles,
        created_at=user.created_at,
    )


# ============================================================================
# REPUTATION
# ============================================================================


@router.post("/user/{sqid}/reputation", response_model=schemas.ReputationAdjustResponse)
def adjust_reputation(
    sqid: str,
    payload: schemas.UMDReputationAdjustRequest,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> schemas.ReputationAdjustResponse:
    """
    Adjust user reputation (moderator only).

    Delta must be between -1000 and +1000.
    Reason must be at least 8 characters.
    """
    user = get_user_by_sqid_or_404(db, sqid)
    protect_owner(user, moderator)

    # Apply reputation change
    user.reputation = user.reputation + payload.delta

    # Create history record
    history = models.ReputationHistory(
        user_id=user.id,
        delta=payload.delta,
        reason=payload.reason,
    )
    db.add(history)

    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="adjust_reputation",
        target_type="user",
        target_id=user.id,
        note=f"Delta: {payload.delta:+d}, Reason: {payload.reason}",
    )

    return schemas.ReputationAdjustResponse(new_total=user.reputation)


# ============================================================================
# BADGES
# ============================================================================


@router.get("/badges", response_model=schemas.UMDBadgeListResponse)
def list_badges(
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.UMDBadgeListResponse:
    """List all available badges (moderator only)."""
    badges = db.query(models.BadgeDefinition).order_by(models.BadgeDefinition.label).all()
    return schemas.UMDBadgeListResponse(
        badges=[schemas.BadgeDefinition.model_validate(b) for b in badges]
    )


@router.post("/user/{sqid}/badge/{badge}", status_code=status.HTTP_201_CREATED)
def grant_badge(
    sqid: str,
    badge: str,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> dict:
    """Grant badge to user (moderator only)."""
    user = get_user_by_sqid_or_404(db, sqid)
    protect_owner(user, moderator)

    # Check badge exists
    badge_def = db.query(models.BadgeDefinition).filter(models.BadgeDefinition.badge == badge).first()
    if not badge_def:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Badge not found")

    # Check if user already has badge
    existing = db.query(models.BadgeGrant).filter(
        models.BadgeGrant.user_id == user.id,
        models.BadgeGrant.badge == badge,
    ).first()

    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already has this badge")

    # Grant badge
    grant = models.BadgeGrant(user_id=user.id, badge=badge)
    db.add(grant)
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="grant_badge",
        target_type="user",
        target_id=user.id,
        note=f"Badge: {badge}",
    )

    return {"status": "granted", "badge": badge}


@router.delete("/user/{sqid}/badge/{badge}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_badge(
    sqid: str,
    badge: str,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """Revoke badge from user (moderator only)."""
    user = get_user_by_sqid_or_404(db, sqid)
    protect_owner(user, moderator)

    # Find existing badge grant
    grant = db.query(models.BadgeGrant).filter(
        models.BadgeGrant.user_id == user.id,
        models.BadgeGrant.badge == badge,
    ).first()

    if not grant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User does not have this badge")

    db.delete(grant)
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="revoke_badge",
        target_type="user",
        target_id=user.id,
        note=f"Badge: {badge}",
    )


# ============================================================================
# COMMENTS
# ============================================================================


@router.get("/user/{sqid}/comments", response_model=schemas.UMDCommentsResponse)
def get_user_comments(
    sqid: str,
    cursor: str | None = None,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> schemas.UMDCommentsResponse:
    """Get user's comments for moderation (moderator only)."""
    user = get_user_by_sqid_or_404(db, sqid)
    protect_owner(user, moderator)

    # Count total
    total = db.query(models.Comment).filter(models.Comment.author_id == user.id).count()

    # Query comments with post data
    query = db.query(models.Comment).filter(models.Comment.author_id == user.id)

    # Apply cursor pagination
    query = apply_cursor_filter(query, models.Comment, cursor, "created_at", sort_desc=True)
    query = query.order_by(models.Comment.created_at.desc()).limit(limit + 1)
    comments = query.all()

    page_data = create_page_response(comments, limit, cursor)

    # Build response items with post data
    items = []
    for comment in page_data["items"]:
        post = db.query(models.Post).filter(models.Post.id == comment.post_id).first()
        items.append(schemas.UMDCommentItem(
            id=comment.id,
            post_id=comment.post_id,
            post_public_sqid=post.public_sqid if post else "",
            post_title=post.title if post else "[Deleted]",
            post_art_url=post.art_url if post else None,
            body=comment.body,
            hidden_by_mod=comment.hidden_by_mod,
            created_at=comment.created_at,
        ))

    return schemas.UMDCommentsResponse(
        items=items,
        total=total,
        next_cursor=page_data["next_cursor"],
    )


@router.post("/comment/{comment_id}/hide", status_code=status.HTTP_201_CREATED)
def hide_comment(
    comment_id: UUID,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> dict:
    """Hide comment (moderator only)."""
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    comment.hidden_by_mod = True
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="hide_comment",
        target_type="comment",
        target_id=comment_id,
    )

    return {"status": "hidden"}


@router.delete("/comment/{comment_id}/hide", status_code=status.HTTP_204_NO_CONTENT)
def unhide_comment(
    comment_id: UUID,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """Unhide comment (moderator only)."""
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    comment.hidden_by_mod = False
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="unhide_comment",
        target_type="comment",
        target_id=comment_id,
    )


@router.delete("/comment/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: UUID,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """Delete comment permanently (moderator only)."""
    comment = db.query(models.Comment).filter(models.Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    # Store info for audit before deletion
    post_id = comment.post_id
    author_id = comment.author_id

    db.delete(comment)
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="delete_comment",
        target_type="comment",
        target_id=comment_id,
        note=f"Post ID: {post_id}, Author ID: {author_id}",
    )


# ============================================================================
# VIOLATIONS
# ============================================================================


@router.get("/user/{sqid}/violations", response_model=schemas.ViolationsResponse)
def get_user_violations(
    sqid: str,
    cursor: str | None = None,
    limit: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> schemas.ViolationsResponse:
    """Get user's violations (moderator only)."""
    user = get_user_by_sqid_or_404(db, sqid)
    protect_owner(user, moderator)

    # Count total
    total = db.query(models.Violation).filter(models.Violation.user_id == user.id).count()

    # Query violations
    query = db.query(models.Violation).filter(models.Violation.user_id == user.id)

    # Apply cursor pagination
    query = apply_cursor_filter(query, models.Violation, cursor, "created_at", sort_desc=True)
    query = query.order_by(models.Violation.created_at.desc()).limit(limit + 1)
    violations = query.all()

    page_data = create_page_response(violations, limit, cursor)

    # Build response items with moderator handles
    items = []
    for violation in page_data["items"]:
        moderator = db.query(models.User).filter(models.User.id == violation.moderator_id).first()
        items.append(schemas.ViolationItem(
            id=violation.id,
            reason=violation.reason,
            moderator_id=violation.moderator_id,
            moderator_handle=moderator.handle if moderator else "[Unknown]",
            created_at=violation.created_at,
        ))

    return schemas.ViolationsResponse(
        items=items,
        total=total,
        next_cursor=page_data["next_cursor"],
    )


@router.post("/user/{sqid}/violation", status_code=status.HTTP_201_CREATED)
def issue_violation(
    sqid: str,
    payload: schemas.IssueViolationRequest,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> dict:
    """Issue violation to user (moderator only)."""
    user = get_user_by_sqid_or_404(db, sqid)
    protect_owner(user, moderator)

    # Create violation
    violation = models.Violation(
        user_id=user.id,
        moderator_id=moderator.id,
        reason=payload.reason,
    )
    db.add(violation)
    db.commit()
    db.refresh(violation)

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="issue_violation",
        target_type="user",
        target_id=user.id,
        note=payload.reason,
    )

    return {"status": "issued", "id": violation.id}


@router.delete("/violation/{violation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_violation(
    violation_id: int,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """Delete/revoke violation (moderator only)."""
    violation = db.query(models.Violation).filter(models.Violation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Violation not found")

    user_id = violation.user_id
    reason = violation.reason

    db.delete(violation)
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="delete_violation",
        target_type="user",
        target_id=user_id,
        note=f"Revoked: {reason[:100]}",
    )


# ============================================================================
# MODERATOR ACTIONS
# ============================================================================


@router.post("/user/{sqid}/trust", status_code=status.HTTP_201_CREATED)
def trust_user(
    sqid: str,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> dict:
    """Trust user - grant auto_public_approval (moderator only)."""
    user = get_user_by_sqid_or_404(db, sqid)
    protect_owner(user, moderator)

    user.auto_public_approval = True
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="trust_user",
        target_type="user",
        target_id=user.id,
    )

    return {"status": "trusted", "auto_public_approval": True}


@router.delete("/user/{sqid}/trust", status_code=status.HTTP_204_NO_CONTENT)
def distrust_user(
    sqid: str,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """Distrust user - revoke auto_public_approval (moderator only)."""
    user = get_user_by_sqid_or_404(db, sqid)
    protect_owner(user, moderator)

    user.auto_public_approval = False
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="distrust_user",
        target_type="user",
        target_id=user.id,
    )


@router.post("/user/{sqid}/hide", status_code=status.HTTP_201_CREATED)
def hide_user(
    sqid: str,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> dict:
    """Hide user profile (moderator only)."""
    user = get_user_by_sqid_or_404(db, sqid)
    protect_owner(user, moderator)

    user.hidden_by_mod = True
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="hide_user",
        target_type="user",
        target_id=user.id,
    )

    return {"status": "hidden"}


@router.delete("/user/{sqid}/hide", status_code=status.HTTP_204_NO_CONTENT)
def unhide_user(
    sqid: str,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """Unhide user profile (moderator only)."""
    user = get_user_by_sqid_or_404(db, sqid)
    protect_owner(user, moderator)

    user.hidden_by_mod = False
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="unhide_user",
        target_type="user",
        target_id=user.id,
    )


@router.post("/user/{sqid}/ban", status_code=status.HTTP_201_CREATED)
def ban_user(
    sqid: str,
    duration_days: int | None = Query(None, ge=1, le=365, description="Ban duration in days (null = permanent)"),
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> dict:
    """Ban user (moderator only). No duration = permanent ban."""
    user = get_user_by_sqid_or_404(db, sqid)
    protect_owner(user, moderator)

    until = None
    if duration_days:
        until = datetime.now(timezone.utc) + timedelta(days=duration_days)

    user.banned_until = until
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="ban_user",
        target_type="user",
        target_id=user.id,
        note=f"Duration: {'permanent' if until is None else f'{duration_days} days'}",
    )

    return {"status": "banned", "until": until}


@router.delete("/user/{sqid}/ban", status_code=status.HTTP_204_NO_CONTENT)
def unban_user(
    sqid: str,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """Unban user (moderator only)."""
    user = get_user_by_sqid_or_404(db, sqid)
    protect_owner(user, moderator)

    user.banned_until = None
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="unban_user",
        target_type="user",
        target_id=user.id,
    )


@router.get("/user/{sqid}/email", response_model=schemas.EmailRevealResponse)
def reveal_email(
    sqid: str,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> schemas.EmailRevealResponse:
    """
    Reveal user's email (moderator only).

    This action is logged to the audit log.
    """
    user = get_user_by_sqid_or_404(db, sqid)
    protect_owner(user, moderator)

    # Log to audit before revealing
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="reveal_email",
        target_type="user",
        target_id=user.id,
    )

    return schemas.EmailRevealResponse(email=user.email)


# Note: Owner-only moderator management endpoints (/user/{id}/moderator)
# are defined in admin.py and use user_key (UUID) instead of sqid.

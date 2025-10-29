"""Admin and moderation endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import require_moderator, require_owner, ensure_not_owner_self, ensure_not_owner, ensure_authenticated_user
from ..deps import get_db
from ..utils.audit import log_moderation_action
from ..pagination import apply_cursor_filter, create_page_response

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post(
    "/users/{id}/ban",
    response_model=schemas.BanResponse,
    status_code=status.HTTP_201_CREATED,
)
def ban_user(
    id: UUID,
    payload: schemas.BanUserRequest,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> schemas.BanResponse:
    """
    Ban user (moderator only).
    
    TODO: Log in audit log
    TODO: Send notification to user
    TODO: Hide all user's content
    """
    from datetime import datetime, timedelta, timezone
    
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    until = None
    if payload.duration_days:
        until = datetime.now(timezone.utc) + timedelta(days=payload.duration_days)
    
    user.banned_until = until
    db.commit()
    
    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="ban_user",
        target_type="user",
        target_id=id,
    )
    
    return schemas.BanResponse(status="banned", until=until)


@router.delete("/users/{id}/ban", status_code=status.HTTP_204_NO_CONTENT)
def unban_user(
    id: UUID,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Unban user (moderator only).
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    user.banned_until = None
    db.commit()
    
    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="unban_user",
        target_type="user",
        target_id=id,
    )


@router.post(
    "/users/{id}/moderator",
    response_model=schemas.PromoteModeratorResponse,
    status_code=status.HTTP_201_CREATED,
)
def promote_moderator(
    id: UUID,
    db: Session = Depends(get_db),
    _owner: models.User = Depends(require_owner),
) -> schemas.PromoteModeratorResponse:
    """
    Promote user to moderator (owner only).
    
    Only authenticated users (with github_user_id) can be promoted.
    Owner cannot be demoted from moderator role.
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Ensure user is authenticated
    ensure_authenticated_user(user)
    
    # Ensure not trying to modify owner's own moderator status
    ensure_not_owner_self(user, _owner)
    
    # Owner always has moderator role - ensure it's present
    if "owner" in user.roles and "moderator" not in user.roles:
        user.roles = user.roles + ["moderator"]
        db.commit()
        return schemas.PromoteModeratorResponse(user_id=id, role="moderator")
    
    if "moderator" not in user.roles:
        user.roles = user.roles + ["moderator"]
        db.commit()
        
        # Log to audit
        log_moderation_action(
            db=db,
            actor_id=_owner.id,
            action="promote_moderator",
            target_type="user",
            target_id=id,
        )
    
    return schemas.PromoteModeratorResponse(user_id=id, role="moderator")


@router.delete(
    "/users/{id}/moderator",
    status_code=status.HTTP_204_NO_CONTENT,
)
def demote_moderator(
    id: UUID,
    db: Session = Depends(get_db),
    _owner: models.User = Depends(require_owner),
) -> None:
    """
    Demote moderator to user (owner only).
    
    Owner cannot be demoted from moderator role.
    Owner role cannot be removed.
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Prevent demoting owner from moderator
    if "owner" in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner cannot be demoted from moderator role"
        )
    
    # Prevent modifying own roles
    ensure_not_owner_self(user, _owner)
    
    if "moderator" in user.roles:
        user.roles = [r for r in user.roles if r != "moderator"]
        db.commit()
        
        # Log to audit
        log_moderation_action(
            db=db,
            actor_id=_owner.id,
            action="demote_moderator",
            target_type="user",
            target_id=id,
        )


@router.post("/users/{id}/hide", status_code=status.HTTP_201_CREATED)
def hide_user(
    id: UUID,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Hide user profile (moderator only).
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    user.hidden_by_mod = True
    db.commit()
    
    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="hide_user",
        target_type="user",
        target_id=id,
    )


@router.delete("/users/{id}/hide", status_code=status.HTTP_204_NO_CONTENT)
def unhide_user(
    id: UUID,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Unhide user profile (moderator only).
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    user.hidden_by_mod = False
    db.commit()
    
    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="unhide_user",
        target_type="user",
        target_id=id,
    )


@router.get("/recent-profiles", response_model=schemas.Page[schemas.UserFull])
def recent_profiles(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.Page[schemas.UserFull]:
    """
    Recent user profiles (moderator only).
    """
    query = db.query(models.User)
    
    # Apply cursor pagination
    query = apply_cursor_filter(query, models.User, cursor, "created_at", sort_desc=True)
    
    # Order and limit
    query = query.order_by(models.User.created_at.desc()).limit(limit + 1)
    users = query.all()
    
    page_data = create_page_response(users, limit, cursor)
    
    return schemas.Page(
        items=[schemas.UserFull.model_validate(u) for u in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )


@router.get("/recent-posts", response_model=schemas.Page[schemas.Post])
def recent_posts(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.Page[schemas.Post]:
    """
    Recent posts (moderator only).
    """
    query = db.query(models.Post)
    
    # Apply cursor pagination
    query = apply_cursor_filter(query, models.Post, cursor, "created_at", sort_desc=True)
    
    # Order and limit
    query = query.order_by(models.Post.created_at.desc()).limit(limit + 1)
    posts = query.all()
    
    page_data = create_page_response(posts, limit, cursor)
    
    return schemas.Page(
        items=[schemas.Post.model_validate(p) for p in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )


@router.get("/audit-log", response_model=schemas.Page[schemas.AuditLogEntry])
def get_audit_log(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    actor_id: UUID | None = Query(None),
    action: str | None = Query(None),
    target_type: str | None = Query(None),
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.Page[schemas.AuditLogEntry]:
    """
    Get audit log (moderator only).
    
    Supports filtering by actor_id, action, and target_type.
    """
    query = db.query(models.AuditLog)
    
    # Apply filters
    if actor_id:
        query = query.filter(models.AuditLog.actor_id == actor_id)
    if action:
        query = query.filter(models.AuditLog.action == action)
    if target_type:
        query = query.filter(models.AuditLog.target_type == target_type)
    
    # Apply cursor pagination
    query = apply_cursor_filter(query, models.AuditLog, cursor, "created_at", sort_desc=True)
    
    # Order and limit
    query = query.order_by(models.AuditLog.created_at.desc()).limit(limit + 1)
    logs = query.all()
    
    page_data = create_page_response(logs, limit, cursor)
    
    return schemas.Page(
        items=[schemas.AuditLogEntry.model_validate(log) for log in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )


@router.get("/owner/users", response_model=schemas.Page[schemas.UserFull])
def list_authenticated_users(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _owner: models.User = Depends(require_owner),
) -> schemas.Page[schemas.UserFull]:
    """
    List authenticated users (owner only).
    
    Returns users with github_user_id set, ordered alphabetically by handle.
    """
    query = db.query(models.User).filter(models.User.github_user_id.isnot(None))
    
    # Apply cursor pagination (handle-based, alphabetical)
    # Note: Using handle as sort field for alphabetical ordering
    query = apply_cursor_filter(query, models.User, cursor, "handle", sort_desc=False)
    
    # Order alphabetically by handle
    query = query.order_by(models.User.handle.asc()).limit(limit + 1)
    users = query.all()
    
    page_data = create_page_response(users, limit, cursor, sort_field="handle")
    
    return schemas.Page(
        items=[schemas.UserFull.model_validate(u) for u in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )


@router.get("/owner/users/anonymous", response_model=schemas.Page[schemas.UserPublic])
def list_anonymous_users(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _owner: models.User = Depends(require_owner),
) -> schemas.Page[schemas.UserPublic]:
    """
    List non-authenticated users (owner only).
    
    Returns users without github_user_id, ordered alphabetically by handle.
    """
    query = db.query(models.User).filter(models.User.github_user_id.is_(None))
    
    # Apply cursor pagination (handle-based, alphabetical)
    query = apply_cursor_filter(query, models.User, cursor, "handle", sort_desc=False)
    
    # Order alphabetically by handle
    query = query.order_by(models.User.handle.asc()).limit(limit + 1)
    users = query.all()
    
    page_data = create_page_response(users, limit, cursor, sort_field="handle")
    
    return schemas.Page(
        items=[schemas.UserPublic.model_validate(u, from_attributes=True) for u in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )

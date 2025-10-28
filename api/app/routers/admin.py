"""Admin and moderation endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import require_moderator, require_owner
from ..deps import get_db

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
    
    return schemas.BanResponse(status="banned", until=until)


@router.delete("/users/{id}/ban", status_code=status.HTTP_204_NO_CONTENT)
def unban_user(
    id: UUID,
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Unban user (moderator only).
    
    TODO: Log in audit log
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    user.banned_until = None
    db.commit()


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
    
    TODO: Log in audit log
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if "moderator" not in user.roles:
        user.roles = user.roles + ["moderator"]
        db.commit()
    
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
    
    TODO: Log in audit log
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if "moderator" in user.roles:
        user.roles = [r for r in user.roles if r != "moderator"]
        db.commit()


@router.get("/recent-profiles", response_model=schemas.Page[schemas.UserFull])
def recent_profiles(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.Page[schemas.UserFull]:
    """
    Recent user profiles (moderator only).
    
    TODO: Implement cursor pagination
    """
    users = (
        db.query(models.User)
        .order_by(models.User.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return schemas.Page(
        items=[schemas.UserFull.model_validate(u) for u in users],
        next_cursor=None,
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
    
    TODO: Implement cursor pagination
    """
    posts = (
        db.query(models.Post)
        .order_by(models.Post.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return schemas.Page(
        items=[schemas.Post.model_validate(p) for p in posts],
        next_cursor=None,
    )


@router.get("/audit-log", response_model=schemas.Page[schemas.AuditLogEntry])
def get_audit_log(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.Page[schemas.AuditLogEntry]:
    """
    Get audit log (moderator only).
    
    TODO: Implement cursor pagination
    TODO: Implement automatic audit logging for admin actions
    """
    logs = (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return schemas.Page(
        items=[schemas.AuditLogEntry.model_validate(log) for log in logs],
        next_cursor=None,
    )

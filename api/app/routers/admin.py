"""Admin and moderation endpoints."""

from __future__ import annotations

from datetime import datetime
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
        reason_code=payload.reason_code,
        note=payload.note or payload.reason,
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
    ensure_authenticated_user(user, db)
    
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


@router.post(
    "/users/{id}/auto-approval",
    response_model=schemas.AutoApprovalResponse,
    status_code=status.HTTP_201_CREATED,
)
def grant_auto_approval(
    id: UUID,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> schemas.AutoApprovalResponse:
    """
    Grant auto-approval privilege to a user (moderator only).
    
    Users with this privilege have their uploaded artworks automatically
    approved for public visibility, appearing immediately in Recent Artworks
    and search results without requiring moderator review.
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    user.auto_public_approval = True
    db.commit()
    
    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="grant_auto_approval",
        target_type="user",
        target_id=id,
    )
    
    return schemas.AutoApprovalResponse(user_id=id, auto_public_approval=True)


@router.delete(
    "/users/{id}/auto-approval",
    response_model=schemas.AutoApprovalResponse,
)
def revoke_auto_approval(
    id: UUID,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> schemas.AutoApprovalResponse:
    """
    Revoke auto-approval privilege from a user (moderator only).
    
    After revocation, the user's newly uploaded artworks will require
    moderator approval before appearing in Recent Artworks and search results.
    """
    user = db.query(models.User).filter(models.User.id == id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    user.auto_public_approval = False
    db.commit()
    
    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="revoke_auto_approval",
        target_type="user",
        target_id=id,
    )
    
    return schemas.AutoApprovalResponse(user_id=id, auto_public_approval=False)


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


@router.get("/pending-approval", response_model=schemas.Page[schemas.Post])
def pending_approval(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.Page[schemas.Post]:
    """
    List posts pending public visibility approval (moderator only).
    
    Returns posts where public_visibility is False, ordered by creation date (newest first).
    These are artworks uploaded by users without auto_public_approval privilege
    that need moderator review before appearing in Recent Artworks and search results.
    """
    query = db.query(models.Post).filter(
        models.Post.public_visibility == False,
        models.Post.hidden_by_user == False,
        models.Post.hidden_by_mod == False,
    )
    
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
    
    Returns users with at least one auth identity, ordered alphabetically by handle.
    """
    from ..models import AuthIdentity
    # Get user IDs that have at least one auth identity
    authenticated_user_ids = db.query(AuthIdentity.user_id).distinct().subquery()
    query = db.query(models.User).filter(models.User.id.in_(db.query(authenticated_user_ids.c.user_id)))
    
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
    
    Returns users without any auth identity, ordered alphabetically by handle.
    """
    from ..models import AuthIdentity
    # Get user IDs that have at least one auth identity
    authenticated_user_ids = db.query(AuthIdentity.user_id).distinct().subquery()
    query = db.query(models.User).filter(~models.User.id.in_(db.query(authenticated_user_ids.c.user_id)))
    
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


@router.get("/sitewide-stats", response_model=schemas.SitewideStatsResponse)
def get_sitewide_stats(
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.SitewideStatsResponse:
    """
    Get comprehensive sitewide statistics (moderator only).
    
    Returns event-level granularity for the past 7 days, then daily aggregates
    until the past 30 days. Includes hourly breakdown for the last 24 hours.
    
    Statistics are cached in Redis for 5 minutes.
    """
    from ..services.site_stats import get_sitewide_stats
    
    stats = get_sitewide_stats(db)
    
    if stats is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute sitewide statistics"
        )
    
    # Convert to response schema
    return schemas.SitewideStatsResponse(
        total_page_views_30d=stats.total_page_views_30d,
        unique_visitors_30d=stats.unique_visitors_30d,
        new_signups_30d=stats.new_signups_30d,
        new_posts_30d=stats.new_posts_30d,
        total_api_calls_30d=stats.total_api_calls_30d,
        total_errors_30d=stats.total_errors_30d,
        total_page_views_30d_authenticated=stats.total_page_views_30d_authenticated,
        unique_visitors_30d_authenticated=stats.unique_visitors_30d_authenticated,
        daily_views=[
            schemas.DailyCount(date=dv.date, count=dv.count)
            for dv in stats.daily_views
        ],
        daily_signups=[
            schemas.DailyCount(date=ds.date, count=ds.count)
            for ds in stats.daily_signups
        ],
        daily_posts=[
            schemas.DailyCount(date=dp.date, count=dp.count)
            for dp in stats.daily_posts
        ],
        daily_views_authenticated=[
            schemas.DailyCount(date=dv.date, count=dv.count)
            for dv in stats.daily_views_authenticated
        ],
        hourly_views=[
            schemas.HourlyCount(hour=hv.hour, count=hv.count)
            for hv in stats.hourly_views
        ],
        hourly_views_authenticated=[
            schemas.HourlyCount(hour=hv.hour, count=hv.count)
            for hv in stats.hourly_views_authenticated
        ],
        views_by_page=stats.views_by_page,
        views_by_country=stats.views_by_country,
        views_by_device=stats.views_by_device,
        top_referrers=stats.top_referrers,
        views_by_page_authenticated=stats.views_by_page_authenticated,
        views_by_country_authenticated=stats.views_by_country_authenticated,
        views_by_device_authenticated=stats.views_by_device_authenticated,
        top_referrers_authenticated=stats.top_referrers_authenticated,
        errors_by_type=stats.errors_by_type,
        computed_at=datetime.fromisoformat(stats.computed_at),
    )

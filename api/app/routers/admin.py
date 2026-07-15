"""Admin and moderation endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import (
    require_moderator,
    require_owner,
    ensure_not_owner_self,
    ensure_not_owner,
    ensure_authenticated_user,
)
from ..deps import get_db
from ..utils.audit import log_moderation_action
from ..utils.view_tracking import truncate_ip
from ..pagination import (
    apply_cursor_filter,
    create_page_response,
    decode_cursor,
    encode_cursor,
)
from ..services.social_notifications import SocialNotificationService

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post(
    "/user/{id}/ban",
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

    Banning a user prevents them from authenticating but does NOT delete their account.
    The user profile and all associated data remain in the database indefinitely.

    - No duration (None/0) = permanent ban (banned_until = PERMANENT_BAN_UNTIL)
    - With duration = temporary ban (banned_until = current_time + duration_days)

    Note: There is no automatic cleanup of banned user profiles. To completely remove
    a user's data, a separate deletion process would need to be implemented.

    TODO: Send notification to user (currently not implemented)
    TODO: Hide all user's content (currently content visibility depends on other flags)
    """
    from datetime import datetime, timedelta, timezone

    # Look up by user_key (UUID)
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Block if target is owner AND actor is not the target
    if "owner" in user.roles and user.id != moderator.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage the site owner",
        )

    # Permanent ban uses the sentinel (NOT NULL, which would read as "not banned").
    if payload.duration_days:
        until = datetime.now(timezone.utc) + timedelta(days=payload.duration_days)
    else:
        until = models.PERMANENT_BAN_UNTIL

    user.banned_until = until
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="ban_user",
        target_type="user",
        target_id=user.id,
        reason_code=payload.reason_code,
        note=payload.note or payload.reason,
    )

    return schemas.BanResponse(status="banned", until=until)


@router.delete("/user/{id}/ban", status_code=status.HTTP_204_NO_CONTENT)
def unban_user(
    id: UUID,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Unban user (moderator only).

    Removes the ban by setting banned_until to NULL, allowing the user to
    authenticate again immediately. Does not delete the user's profile or data.
    """
    # Look up by user_key (UUID)
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Block if target is owner AND actor is not the target
    if "owner" in user.roles and user.id != moderator.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage the site owner",
        )

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


@router.post(
    "/user/{id}/moderator",
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
    # Look up by user_key (UUID)
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Ensure user is authenticated
    ensure_authenticated_user(user, db)

    # Ensure not trying to modify owner's own moderator status
    ensure_not_owner_self(user, _owner)

    # Owner always has moderator role - ensure it's present
    if "owner" in user.roles and "moderator" not in user.roles:
        user.roles = user.roles + ["moderator"]
        db.commit()
        return schemas.PromoteModeratorResponse(user_id=user.id, role="moderator")

    if "moderator" not in user.roles:
        user.roles = user.roles + ["moderator"]
        db.commit()

        # Log to audit
        log_moderation_action(
            db=db,
            actor_id=_owner.id,
            action="promote_moderator",
            target_type="user",
            target_id=user.id,
        )

        # Send notification to the new moderator
        SocialNotificationService.create_system_notification(
            db=db,
            user_id=user.id,
            notification_type="moderator_granted",
            actor=_owner,
        )

    return schemas.PromoteModeratorResponse(user_id=user.id, role="moderator")


@router.delete(
    "/user/{id}/moderator",
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
    # Look up by user_key (UUID)
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Prevent demoting owner from moderator
    if "owner" in user.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner cannot be demoted from moderator role",
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
            target_id=user.id,
        )

        # Send notification to the demoted user
        SocialNotificationService.create_system_notification(
            db=db,
            user_id=user.id,
            notification_type="moderator_revoked",
            actor=_owner,
        )


@router.post("/user/{id}/hide", status_code=status.HTTP_201_CREATED)
def hide_user(
    id: UUID,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Hide user profile (moderator only).
    """
    # Look up by user_key (UUID)
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Block if target is owner AND actor is not the target
    if "owner" in user.roles and user.id != moderator.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage the site owner",
        )

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


@router.delete("/user/{id}/hide", status_code=status.HTTP_204_NO_CONTENT)
def unhide_user(
    id: UUID,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> None:
    """
    Unhide user profile (moderator only).
    """
    # Look up by user_key (UUID)
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Block if target is owner AND actor is not the target
    if "owner" in user.roles and user.id != moderator.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage the site owner",
        )

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


@router.post(
    "/user/{id}/auto-approval",
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
    # Look up by user_key (UUID)
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Block if target is owner AND actor is not the target
    if "owner" in user.roles and user.id != moderator.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage the site owner",
        )

    user.auto_public_approval = True
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="grant_auto_approval",
        target_type="user",
        target_id=user.id,
    )

    return schemas.AutoApprovalResponse(user_id=user.id, auto_public_approval=True)


@router.delete(
    "/user/{id}/auto-approval",
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
    # Look up by user_key (UUID)
    user = db.query(models.User).filter(models.User.user_key == id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Block if target is owner AND actor is not the target
    if "owner" in user.roles and user.id != moderator.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot manage the site owner",
        )

    user.auto_public_approval = False
    db.commit()

    # Log to audit
    log_moderation_action(
        db=db,
        actor_id=moderator.id,
        action="revoke_auto_approval",
        target_type="user",
        target_id=user.id,
    )

    return schemas.AutoApprovalResponse(user_id=user.id, auto_public_approval=False)


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
    query = apply_cursor_filter(
        query, models.User, cursor, "created_at", sort_desc=True
    )

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
        models.Post.deleted_by_user == False,  # Exclude user-deleted posts
    )

    # Apply cursor pagination
    query = apply_cursor_filter(
        query, models.Post, cursor, "created_at", sort_desc=True
    )

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
    query = apply_cursor_filter(
        query, models.Post, cursor, "created_at", sort_desc=True
    )

    # Order and limit
    query = query.order_by(models.Post.created_at.desc()).limit(limit + 1)
    posts = query.all()

    page_data = create_page_response(posts, limit, cursor)

    return schemas.Page(
        items=[schemas.Post.model_validate(p) for p in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )


PULSE_TYPES = ("post", "comment", "post_reaction", "comment_like", "player", "profile")

_PULSE_PREVIEW_LEN = 140


def _pulse_preview(body: str | None) -> str | None:
    if body is None:
        return None
    if len(body) <= _PULSE_PREVIEW_LEN:
        return body
    return body[: _PULSE_PREVIEW_LEN - 1] + "…"


def _pulse_actor(user: models.User | None, ip: str | None) -> dict:
    if user is not None:
        return {
            "actor_handle": user.handle,
            "actor_public_sqid": user.public_sqid,
            "actor_avatar_url": user.avatar_url,
        }
    return {"anonymous_id": truncate_ip(ip) if ip else None}


def _pulse_post_context(post: models.Post | None) -> dict:
    if post is None:
        return {}
    return {
        "post_id": post.id,
        "post_public_sqid": post.public_sqid,
        "post_title": post.title,
        "post_art_url": post.art_url,
    }


def _pulse_post_flags(post: models.Post) -> list[str]:
    flags = []
    if post.hidden_by_mod:
        flags.append("hidden_by_mod")
    if post.hidden_by_user:
        flags.append("hidden_by_user")
    if post.deleted_by_user:
        flags.append("deleted_by_user")
    if post.non_conformant:
        flags.append("non_conformant")
    return flags


@router.get("/pulse", response_model=schemas.Page[schemas.PulseItem])
def pulse(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    include_anonymous: bool = Query(True),
    types: str | None = Query(
        None,
        description=(
            "Comma-separated subset of post, comment, post_reaction, "
            "comment_like, player, profile (default: all)"
        ),
    ),
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.Page[schemas.PulseItem]:
    """
    Chronological firehose of recent community activity (moderator only).

    Merges new posts, comments (including replies), post reactions, comment
    likes, player registrations and new user profiles into a single feed,
    newest first. Hidden
    and deleted content is included, marked via `flags`. Anonymous actors are
    identified by a truncated IP so moderators can differentiate visitors
    without seeing full addresses.
    """
    if types:
        requested = [t.strip() for t in types.split(",") if t.strip()]
        unknown = sorted(set(requested) - set(PULSE_TYPES))
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown pulse types: {', '.join(unknown)}",
            )
        active = set(requested)
    else:
        active = set(PULSE_TYPES)

    # The cursor carries only a timestamp: each source is filtered with a
    # strict `event_time < cursor` and the merged page is cut at `limit`.
    # Events sharing an identical microsecond timestamp across a page
    # boundary can be skipped; acceptable for a moderation firehose.
    cursor_ts: datetime | None = None
    decoded = decode_cursor(cursor)
    if decoded:
        _, sort_value = decoded
        if isinstance(sort_value, str):
            try:
                if sort_value.endswith("Z"):
                    sort_value = sort_value[:-1] + "+00:00"
                cursor_ts = datetime.fromisoformat(sort_value)
            except ValueError:
                cursor_ts = None

    fetch = limit + 1

    def page_of(query, ts_col):
        if cursor_ts is not None:
            query = query.filter(ts_col < cursor_ts)
        return query.order_by(ts_col.desc()).limit(fetch).all()

    merged: list[schemas.PulseItem] = []

    if "post" in active:
        query = db.query(models.Post).options(joinedload(models.Post.owner))
        for p in page_of(query, models.Post.created_at):
            merged.append(
                schemas.PulseItem(
                    type="post",
                    id=str(p.id),
                    created_at=p.created_at,
                    **_pulse_actor(p.owner, None),
                    **_pulse_post_context(p),
                    flags=_pulse_post_flags(p),
                )
            )

    if "comment" in active:
        query = db.query(models.Comment).options(
            joinedload(models.Comment.author),
            joinedload(models.Comment.post),
        )
        if not include_anonymous:
            query = query.filter(models.Comment.author_id.isnot(None))
        for c in page_of(query, models.Comment.created_at):
            flags = []
            if c.hidden_by_mod:
                flags.append("hidden_by_mod")
            if c.deleted_by_owner:
                flags.append("deleted_by_owner")
            if c.deleted_by_mod:
                flags.append("deleted_by_mod")
            merged.append(
                schemas.PulseItem(
                    type="comment",
                    id=str(c.id),
                    created_at=c.created_at,
                    **_pulse_actor(c.author, c.author_ip),
                    **_pulse_post_context(c.post),
                    # Mods see the preserved pre-deletion body until purged
                    comment_preview=_pulse_preview(c.original_body or c.body),
                    is_reply=c.parent_id is not None,
                    flags=flags,
                    has_original_body=c.original_body is not None,
                )
            )

    if "post_reaction" in active:
        query = db.query(models.Reaction).options(
            joinedload(models.Reaction.user),
            joinedload(models.Reaction.post),
        )
        if not include_anonymous:
            query = query.filter(models.Reaction.user_id.isnot(None))
        for r in page_of(query, models.Reaction.created_at):
            merged.append(
                schemas.PulseItem(
                    type="post_reaction",
                    id=str(r.id),
                    created_at=r.created_at,
                    **_pulse_actor(r.user, r.user_ip),
                    **_pulse_post_context(r.post),
                    emoji=r.emoji,
                )
            )

    if "comment_like" in active:
        query = db.query(models.CommentLike).options(
            joinedload(models.CommentLike.user),
            joinedload(models.CommentLike.comment).joinedload(models.Comment.post),
        )
        for cl in page_of(query, models.CommentLike.created_at):
            comment = cl.comment
            merged.append(
                schemas.PulseItem(
                    type="comment_like",
                    id=str(cl.id),
                    created_at=cl.created_at,
                    **_pulse_actor(cl.user, None),
                    **_pulse_post_context(comment.post if comment else None),
                    comment_preview=_pulse_preview(comment.body if comment else None),
                )
            )

    if "player" in active:
        query = (
            db.query(models.Player)
            .options(joinedload(models.Player.owner))
            .filter(
                models.Player.registration_status == "registered",
                models.Player.registered_at.isnot(None),
            )
        )
        for pl in page_of(query, models.Player.registered_at):
            merged.append(
                schemas.PulseItem(
                    type="player",
                    id=str(pl.id),
                    created_at=pl.registered_at,
                    **_pulse_actor(pl.owner, None),
                    player_name=pl.name,
                    player_model=pl.device_model,
                )
            )

    if "profile" in active:
        now = datetime.now(timezone.utc)
        query = db.query(models.User)
        for u in page_of(query, models.User.created_at):
            flags = []
            if u.hidden_by_mod:
                flags.append("hidden_by_mod")
            if u.deactivated:
                flags.append("deactivated")
            if u.banned_until is not None and u.banned_until > now:
                flags.append("banned")
            merged.append(
                schemas.PulseItem(
                    type="profile",
                    id=str(u.id),
                    created_at=u.created_at,
                    **_pulse_actor(u, None),
                    flags=flags,
                )
            )

    merged.sort(key=lambda item: (item.created_at, item.type, item.id), reverse=True)

    # Each source fetched at most limit+1 rows, so a merged total <= limit
    # means every active source was exhausted below the cursor.
    has_more = len(merged) > limit
    items = merged[:limit]
    next_cursor = (
        encode_cursor("pulse", items[-1].created_at.isoformat())
        if has_more and items
        else None
    )

    return schemas.Page(items=items, next_cursor=next_cursor)


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
    query = apply_cursor_filter(
        query, models.AuditLog, cursor, "created_at", sort_desc=True
    )

    # Order and limit
    query = query.order_by(models.AuditLog.created_at.desc()).limit(limit + 1)
    logs = query.all()

    page_data = create_page_response(logs, limit, cursor)

    return schemas.Page(
        items=[schemas.AuditLogEntry.model_validate(log) for log in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )


@router.get("/owner/user", response_model=schemas.Page[schemas.UserFull])
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
    query = db.query(models.User).filter(
        models.User.id.in_(db.query(authenticated_user_ids.c.user_id))
    )

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


@router.get("/owner/user/anonymous", response_model=schemas.Page[schemas.UserPublic])
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
    query = db.query(models.User).filter(
        ~models.User.id.in_(db.query(authenticated_user_ids.c.user_id))
    )

    # Apply cursor pagination (handle-based, alphabetical)
    query = apply_cursor_filter(query, models.User, cursor, "handle", sort_desc=False)

    # Order alphabetically by handle
    query = query.order_by(models.User.handle.asc()).limit(limit + 1)
    users = query.all()

    page_data = create_page_response(users, limit, cursor, sort_field="handle")

    return schemas.Page(
        items=[
            schemas.UserPublic.model_validate(u, from_attributes=True)
            for u in page_data["items"]
        ],
        next_cursor=page_data["next_cursor"],
    )


@router.get("/sitewide-stats", response_model=schemas.SitewideStatsResponse)
def get_sitewide_stats(
    refresh: bool = Query(False, description="Force cache refresh"),
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.SitewideStatsResponse:
    """
    Get comprehensive sitewide statistics (moderator only).

    Returns event-level granularity for the past 7 days, then daily aggregates
    until the past 14 days. Includes hourly breakdown for the last 24 hours.

    Statistics are cached in Redis for 5 minutes.
    """
    from ..services.site_stats import get_sitewide_stats, SiteStatsService

    if refresh:
        service = SiteStatsService(db)
        service.invalidate_cache()

    stats = get_sitewide_stats(db)

    if stats is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compute sitewide statistics",
        )

    # Convert to response schema
    return schemas.SitewideStatsResponse(
        total_page_views_14d=stats.total_page_views_14d,
        unique_visitors_14d=stats.unique_visitors_14d,
        new_signups_14d=stats.new_signups_14d,
        new_posts_14d=stats.new_posts_14d,
        total_api_calls_14d=stats.total_api_calls_14d,
        total_errors_14d=stats.total_errors_14d,
        total_page_views_14d_authenticated=stats.total_page_views_14d_authenticated,
        unique_visitors_14d_authenticated=stats.unique_visitors_14d_authenticated,
        daily_views=[
            schemas.DailyCount(date=dv.date, count=dv.count) for dv in stats.daily_views
        ],
        daily_signups=[
            schemas.DailyCount(date=ds.date, count=ds.count)
            for ds in stats.daily_signups
        ],
        daily_posts=[
            schemas.DailyCount(date=dp.date, count=dp.count) for dp in stats.daily_posts
        ],
        daily_views_authenticated=[
            schemas.DailyCount(date=dv.date, count=dv.count)
            for dv in stats.daily_views_authenticated
        ],
        daily_unique_visitors=[
            schemas.DailyCount(date=dv.date, count=dv.count)
            for dv in stats.daily_unique_visitors
        ],
        daily_unique_visitors_authenticated=[
            schemas.DailyCount(date=dv.date, count=dv.count)
            for dv in stats.daily_unique_visitors_authenticated
        ],
        hourly_views=[
            schemas.HourlyCount(hour=hv.hour, count=hv.count)
            for hv in stats.hourly_views
        ],
        hourly_views_authenticated=[
            schemas.HourlyCount(hour=hv.hour, count=hv.count)
            for hv in stats.hourly_views_authenticated
        ],
        hourly_unique_visitors=[
            schemas.HourlyCount(hour=hv.hour, count=hv.count)
            for hv in stats.hourly_unique_visitors
        ],
        hourly_unique_visitors_authenticated=[
            schemas.HourlyCount(hour=hv.hour, count=hv.count)
            for hv in stats.hourly_unique_visitors_authenticated
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
        total_player_artwork_views_14d=stats.total_player_artwork_views_14d,
        active_players_14d=stats.active_players_14d,
        daily_player_views=[
            schemas.DailyCount(date=dv.date, count=dv.count)
            for dv in stats.daily_player_views
        ],
        views_by_player=stats.views_by_player,
        computed_at=datetime.fromisoformat(stats.computed_at),
    )


@router.get("/download-stats", response_model=schemas.DownloadStatsResponse)
def get_download_stats(
    days: int = Query(14, ge=1, le=90, description="Window size in days"),
    top_n: int = Query(
        50, ge=1, le=200, description="Number of top artworks to return"
    ),
    include_bots: bool = Query(
        False,
        description="If true, count bot/crawler downloads in the totals alongside humans",
    ),
    refresh: bool = Query(False, description="Force cache refresh"),
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.DownloadStatsResponse:
    """
    Get per-artwork download statistics from the vault access log (moderator only).

    Aggregates the ``download_stats_daily`` rollup table populated by
    ``app.tasks.rollup_download_stats``. Results are cached in Redis for 5
    minutes. The bot-filter toggle simply selects which of the
    ``downloads_human``/``downloads_bot`` columns to sum (or both when
    ``include_bots=True``).
    """
    from datetime import date, datetime, timedelta, timezone

    from .. import cache
    from ..services.site_stats import STATS_CACHE_TTL

    cache_key = f"download_stats:{days}:{top_n}:{1 if include_bots else 0}"
    if refresh:
        cache.cache_delete(cache_key)
    else:
        cached = cache.cache_get(cache_key)
        if cached is not None:
            return schemas.DownloadStatsResponse.model_validate(cached)

    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days - 1)

    DS = models.DownloadStatsDaily
    # The column we treat as "downloads" for this view.
    if include_bots:
        downloads_col = (DS.downloads_human + DS.downloads_bot).label("downloads")
    else:
        downloads_col = DS.downloads_human.label("downloads")

    # Daily totals for the trend chart (one row per date in the window, even zeros).
    daily_rows = dict(
        db.query(DS.date, sa.func.sum(downloads_col))
        .filter(DS.date >= start_date, DS.date <= today)
        .group_by(DS.date)
        .all()
    )
    daily_downloads = []
    for offset in range(days):
        d = start_date + timedelta(days=offset)
        daily_downloads.append(
            schemas.DailyCount(date=d.isoformat(), count=int(daily_rows.get(d, 0) or 0))
        )

    # Top-N artwork rows for the window.
    top_subq = (
        db.query(DS.post_id, sa.func.sum(downloads_col).label("downloads"))
        .filter(DS.date >= start_date, DS.date <= today)
        .group_by(DS.post_id)
        .having(sa.func.sum(downloads_col) > 0)
        .subquery()
    )
    top_rows = (
        db.query(
            models.Post.id,
            models.Post.public_sqid,
            models.Post.title,
            models.Post.art_url,
            models.User.handle,
            top_subq.c.downloads,
        )
        .join(top_subq, top_subq.c.post_id == models.Post.id)
        .join(models.User, models.User.id == models.Post.owner_id)
        .order_by(top_subq.c.downloads.desc(), models.Post.id.asc())
        .limit(top_n)
        .all()
    )

    top_artworks = [
        schemas.TopArtworkRow(
            post_id=r.id,
            public_sqid=r.public_sqid,
            title=r.title,
            art_url=r.art_url,
            owner_handle=r.handle,
            downloads=int(r.downloads or 0),
        )
        for r in top_rows
    ]

    total_downloads = sum(dc.count for dc in daily_downloads)
    unique_artworks_row = (
        db.query(sa.func.count(sa.func.distinct(DS.post_id)))
        .filter(DS.date >= start_date, DS.date <= today)
        .filter(downloads_col > 0)
        .scalar()
    )
    unique_artworks = int(unique_artworks_row or 0)
    avg_per_artwork = (
        round(total_downloads / unique_artworks, 2) if unique_artworks else 0.0
    )

    response = schemas.DownloadStatsResponse(
        window_days=days,
        include_bots=include_bots,
        summary=schemas.DownloadStatsSummary(
            total_downloads=total_downloads,
            unique_artworks=unique_artworks,
            avg_per_artwork=avg_per_artwork,
        ),
        daily_downloads=daily_downloads,
        top_artworks=top_artworks,
        computed_at=datetime.now(timezone.utc),
    )

    cache.cache_set(cache_key, response.model_dump(mode="json"), ttl=STATS_CACHE_TTL)
    return response


STREAK_CRITERION_DAYS = 14
STRAGGLER_WINDOW_DAYS = 14


@router.get("/vault-sharding-stats", response_model=schemas.VaultShardingStatsResponse)
def get_vault_sharding_stats(
    days: int = Query(30, ge=1, le=90, description="Window size in days"),
    refresh: bool = Query(False, description="Force cache refresh"),
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.VaultShardingStatsResponse:
    """
    Vault resharding migration statistics (moderator only).

    Aggregates ``vault_sharding_stats_daily`` (populated nightly by
    ``app.tasks.rollup_download_stats``): daily downloads split by sharding
    level, the retirement streak counter, and the legacy-straggler list.
    See docs/vault-resharding/ for the migration this instruments.
    Results are cached in Redis for 5 minutes.
    """
    from datetime import datetime, timedelta, timezone

    from .. import cache
    from ..services.download_stats import compute_legacy_streak
    from ..services.site_stats import STATS_CACHE_TTL

    cache_key = f"vault_sharding_stats:{days}"
    if refresh:
        cache.cache_delete(cache_key)
    else:
        cached = cache.cache_get(cache_key)
        if cached is not None:
            return schemas.VaultShardingStatsResponse.model_validate(cached)

    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    start_date = today - timedelta(days=days - 1)

    VS = models.VaultShardingStatsDaily

    # Aggregate rows (post_id IS NULL) for the window.
    agg_rows = (
        db.query(
            VS.date,
            VS.asset_class,
            VS.shard_level,
            VS.downloads_human,
            VS.downloads_bot,
            VS.misses,
        )
        .filter(VS.post_id.is_(None), VS.date >= start_date, VS.date <= today)
        .all()
    )

    # Daily trend rows: every date in the window, gaps marked explicitly.
    by_day: dict = {}
    class_totals: dict[tuple[str, int], list[int]] = {}
    for r in agg_rows:
        day_bucket = by_day.setdefault(r.date, {2: [0, 0, 0], 3: [0, 0, 0]})
        day_bucket[r.shard_level][0] += r.downloads_human
        day_bucket[r.shard_level][1] += r.downloads_bot
        day_bucket[r.shard_level][2] += r.misses
        ct = class_totals.setdefault((r.asset_class, r.shard_level), [0, 0, 0])
        ct[0] += r.downloads_human
        ct[1] += r.downloads_bot
        ct[2] += r.misses

    daily = []
    for offset in range(days):
        d = start_date + timedelta(days=offset)
        bucket = by_day.get(d)
        if bucket is None:
            daily.append(
                schemas.VaultShardingDailyRow(date=d.isoformat(), has_data=False)
            )
        else:
            daily.append(
                schemas.VaultShardingDailyRow(
                    date=d.isoformat(),
                    has_data=True,
                    level2_human=bucket[2][0],
                    level2_bot=bucket[2][1],
                    level2_misses=bucket[2][2],
                    level3_human=bucket[3][0],
                    level3_bot=bucket[3][1],
                    level3_misses=bucket[3][2],
                )
            )

    class_total_rows = [
        schemas.VaultShardingClassRow(
            asset_class=cls,
            shard_level=lvl,
            downloads_human=counts[0],
            downloads_bot=counts[1],
            misses=counts[2],
        )
        for (cls, lvl), counts in sorted(class_totals.items())
    ]

    # Legacy stragglers: per-post level-3 rows from the last 14 days.
    straggler_start = today - timedelta(days=STRAGGLER_WINDOW_DAYS - 1)
    straggler_subq = (
        db.query(
            VS.post_id,
            sa.func.sum(VS.downloads_human).label("human"),
            sa.func.sum(VS.downloads_bot).label("bot"),
            sa.func.max(VS.date).label("last_seen"),
        )
        .filter(VS.post_id.isnot(None), VS.date >= straggler_start)
        .group_by(VS.post_id)
        .having(sa.func.sum(VS.downloads_human + VS.downloads_bot) > 0)
        .subquery()
    )
    straggler_rows = (
        db.query(
            models.Post.id,
            models.Post.public_sqid,
            models.Post.title,
            models.Post.art_url,
            models.User.handle,
            straggler_subq.c.human,
            straggler_subq.c.bot,
            straggler_subq.c.last_seen,
        )
        .join(straggler_subq, straggler_subq.c.post_id == models.Post.id)
        .join(models.User, models.User.id == models.Post.owner_id)
        .order_by(
            (straggler_subq.c.human + straggler_subq.c.bot).desc(),
            models.Post.id.asc(),
        )
        .limit(200)
        .all()
    )
    stragglers = [
        schemas.LegacyStragglerRow(
            post_id=r.id,
            public_sqid=r.public_sqid,
            title=r.title,
            art_url=r.art_url,
            owner_handle=r.handle,
            downloads_human=int(r.human or 0),
            downloads_bot=int(r.bot or 0),
            last_seen=r.last_seen.isoformat(),
        )
        for r in straggler_rows
    ]

    # Streak is computed against yesterday — today's rollup hasn't run yet.
    streak = compute_legacy_streak(db, as_of=yesterday)

    response = schemas.VaultShardingStatsResponse(
        window_days=days,
        streak_days=streak,
        streak_criterion_days=STREAK_CRITERION_DAYS,
        streak_as_of=yesterday.isoformat(),
        daily=daily,
        class_totals=class_total_rows,
        stragglers=stragglers,
        straggler_window_days=STRAGGLER_WINDOW_DAYS,
        computed_at=datetime.now(timezone.utc),
    )

    cache.cache_set(cache_key, response.model_dump(mode="json"), ttl=STATS_CACHE_TTL)
    return response


@router.get("/online-players", response_model=schemas.OnlinePlayersResponse)
def get_online_players(
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.OnlinePlayersResponse:
    """
    Get list of currently online players (moderator only).

    Returns players with connection_status='online'.
    """
    # Query online players
    online_players = (
        db.query(models.Player)
        .filter(models.Player.connection_status == "online")
        .order_by(models.Player.last_seen_at.desc())
        .all()
    )

    # Get owner handles
    owner_ids = [p.owner_id for p in online_players if p.owner_id]
    owners = {}
    if owner_ids:
        users = db.query(models.User).filter(models.User.id.in_(owner_ids)).all()
        owners = {u.id: u.handle for u in users}

    # Build response
    player_infos = []
    for player in online_players:
        player_infos.append(
            schemas.OnlinePlayerInfo(
                id=player.id,
                name=player.name,
                device_model=player.device_model,
                firmware_version=player.firmware_version,
                last_seen_at=player.last_seen_at,
                owner_handle=owners.get(player.owner_id) if player.owner_id else None,
            )
        )

    return schemas.OnlinePlayersResponse(
        online_players=player_infos,
        total_online=len(player_infos),
    )

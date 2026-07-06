"""Report management endpoints (docs/ugc-safety/).

- POST /report: auth OPTIONAL (anonymous reports allowed, D2) with per-user /
  per-IP rate limits (D23), target validation (D9), and moderator alerting
  (email + system notification, throttled per target, D4/D18).
- Moderator triage (GET/PATCH) with auto-applied actions; user targets are
  addressed by public_sqid (D9).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user_optional, get_trusted_client_ip, require_moderator
from ..deps import get_db
from ..errors import AppError, ErrorCode
from ..pagination import apply_cursor_filter, create_page_response
from ..services import email as email_service
from ..services.rate_limit import check_rate_limit
from ..services.social_notifications import SocialNotificationService
from ..utils.audit import ensure_system_user, log_moderation_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/report", tags=["Reports"])

# Rate limits (D23) — operational values, not contract.
REPORTS_PER_USER_PER_HOUR = 10
REPORTS_PER_IP_PER_HOUR = 5
REPORTS_PER_IP_PER_DAY = 20
# One moderator alert (email + notification) per target per window (D18).
ALERT_THROTTLE_SECONDS = 6 * 3600


def _resolve_target(
    db: Session, target_type: str, target_id: str
) -> models.Post | models.Comment | models.User | None:
    """Resolve a report target per the D9 id-type table.

    post -> integer id, comment -> UUID, user -> public_sqid.
    Raises 422 on a malformed id; returns None when the target doesn't exist.
    """
    if target_type == "post":
        try:
            post_id = int(target_id)
        except ValueError:
            raise AppError(
                ErrorCode.validation_error,
                "Post target_id must be an integer id.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return db.query(models.Post).filter(models.Post.id == post_id).first()

    if target_type == "comment":
        try:
            comment_id = UUID(target_id)
        except ValueError:
            raise AppError(
                ErrorCode.validation_error,
                "Comment target_id must be a UUID.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return db.query(models.Comment).filter(models.Comment.id == comment_id).first()

    # target_type == "user" (schema-constrained)
    return db.query(models.User).filter(models.User.public_sqid == target_id).first()


def _fire_moderator_alerts(
    db: Session, report: models.Report, reporter: models.User | None
) -> None:
    """Email acme@ + system-notify moderators about a new report (D4).

    Throttled to one alert per target per 6 h (D18). Best-effort: failures are
    logged and never fail the request.
    """
    allowed, _ = check_rate_limit(
        f"ratelimit:report_alert:{report.target_type}:{report.target_id}",
        limit=1,
        window_seconds=ALERT_THROTTLE_SECONDS,
    )
    if not allowed:
        return

    email_service.send_report_alert_email(
        target_type=report.target_type,
        target_id=report.target_id,
        reason_code=report.reason_code,
        notes=report.notes,
        reporter_handle=reporter.handle if reporter else None,
    )

    try:
        # Notifications use the system actor: anonymous reports have no
        # reporter to attribute, and mods shouldn't learn reporter identity
        # from the notification anyway (D18).
        system_user = ensure_system_user(db)
        moderators = (
            db.query(models.User)
            .filter(
                or_(
                    models.User.roles.cast(JSONB).contains(["moderator"]),
                    models.User.roles.cast(JSONB).contains(["owner"]),
                )
            )
            .all()
        )
        for mod in moderators:
            SocialNotificationService.create_system_notification(
                db,
                user_id=mod.id,
                notification_type="new_report",
                actor=system_user,
                content_title=f"New {report.target_type} report: {report.reason_code}",
            )
    except Exception:
        logger.exception("Failed to send new_report notifications")


@router.post(
    "",
    response_model=schemas.Report,
    status_code=status.HTTP_201_CREATED,
)
def create_report(
    payload: schemas.ReportCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> schemas.Report:
    """
    Create a content report. Auth optional: logged-out reports are accepted
    subject to stricter per-IP limits (docs/ugc-safety/API-CONTRACT.md §3).
    """
    client_ip = get_trusted_client_ip(request)

    if current_user:
        allowed, _ = check_rate_limit(
            f"ratelimit:report:user:{current_user.id}",
            limit=REPORTS_PER_USER_PER_HOUR,
            window_seconds=3600,
        )
        if not allowed:
            raise AppError(
                ErrorCode.rate_limited,
                "You're reporting too fast — try again later.",
                status.HTTP_429_TOO_MANY_REQUESTS,
            )
    else:
        allowed_day = True
        allowed_hour, _ = check_rate_limit(
            f"ratelimit:report:ip:{client_ip}",
            limit=REPORTS_PER_IP_PER_HOUR,
            window_seconds=3600,
        )
        if allowed_hour:
            allowed_day, _ = check_rate_limit(
                f"ratelimit:report:ip:day:{client_ip}",
                limit=REPORTS_PER_IP_PER_DAY,
                window_seconds=86400,
            )
        if not allowed_hour or not allowed_day:
            raise AppError(
                ErrorCode.rate_limited,
                "You're reporting too fast — try again later, "
                "or email acme@makapix.club.",
                status.HTTP_429_TOO_MANY_REQUESTS,
            )

    target = _resolve_target(db, payload.target_type, payload.target_id)
    if target is None:
        raise AppError(
            ErrorCode.not_found,
            "Report target not found.",
            status.HTTP_404_NOT_FOUND,
        )

    report = models.Report(
        reporter_id=current_user.id if current_user else None,
        # IP stored only for anonymous reports (D24); swept after 30 days.
        reporter_ip=None if current_user else client_ip,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason_code=payload.reason_code,
        notes=payload.notes,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    _fire_moderator_alerts(db, report, current_user)

    return schemas.Report.model_validate(report)


@router.get("", response_model=schemas.Page[schemas.Report], tags=["Reports", "Admin"])
def list_reports(
    status_filter: str | None = Query(None, alias="status"),
    target_type: str | None = None,
    reporter_id: int | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _moderator: models.User = Depends(require_moderator),
) -> schemas.Page[schemas.Report]:
    """
    List reports (moderator only).
    """
    query = db.query(models.Report)

    # Apply filters
    if status_filter:
        query = query.filter(models.Report.status == status_filter)
    if target_type:
        query = query.filter(models.Report.target_type == target_type)
    if reporter_id:
        query = query.filter(models.Report.reporter_id == reporter_id)

    # Apply cursor pagination
    query = apply_cursor_filter(
        query, models.Report, cursor, "created_at", sort_desc=True
    )

    # Order and limit
    query = query.order_by(models.Report.created_at.desc()).limit(limit + 1)
    reports = query.all()

    page_data = create_page_response(reports, limit, cursor)

    # Enrich with reporter handles (moderator listings only; null = anonymous)
    reporter_ids = {r.reporter_id for r in page_data["items"] if r.reporter_id}
    handles: dict[int, str] = {}
    if reporter_ids:
        rows = (
            db.query(models.User.id, models.User.handle)
            .filter(models.User.id.in_(reporter_ids))
            .all()
        )
        handles = {row[0]: row[1] for row in rows}

    items = []
    for r in page_data["items"]:
        item = schemas.Report.model_validate(r)
        if r.reporter_id:
            item.reporter_handle = handles.get(r.reporter_id)
        items.append(item)

    return schemas.Page(items=items, next_cursor=page_data["next_cursor"])


@router.patch("/{id}", response_model=schemas.Report, tags=["Reports", "Admin"])
def update_report(
    id: UUID,
    payload: schemas.ReportUpdate,
    db: Session = Depends(get_db),
    moderator: models.User = Depends(require_moderator),
) -> schemas.Report:
    """
    Update report status (moderator only).

    If action_taken is set, automatically applies the moderation action.
    Moderator notes land in `mod_notes`; the reporter's text is immutable (D25).
    """
    report = db.query(models.Report).filter(models.Report.id == id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    # Auto-apply action if specified
    action_applied = False
    if payload.action_taken and payload.action_taken != "none":
        if report.target_type == "user":
            # target_id is the user's public_sqid (D9)
            target_user = (
                db.query(models.User)
                .filter(models.User.public_sqid == report.target_id)
                .first()
            )
            if not target_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Target user {report.target_id} not found",
                )

            if payload.action_taken == "ban":
                target_user.banned_until = datetime.now(timezone.utc) + timedelta(
                    days=7
                )  # Default 7 days
                action_applied = True
            elif payload.action_taken == "hide":
                target_user.hidden_by_mod = True
                action_applied = True

        elif report.target_type == "post":
            # target_id is stored as string, convert to int for post lookup
            try:
                target_post_id = int(report.target_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid post ID format: {report.target_id}",
                )
            target_post = (
                db.query(models.Post).filter(models.Post.id == target_post_id).first()
            )
            if not target_post:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Target post {report.target_id} not found",
                )

            if payload.action_taken == "hide":
                target_post.hidden_by_mod = True
                action_applied = True
            elif payload.action_taken == "delete":
                target_post.visible = False
                action_applied = True

        elif report.target_type == "comment":
            # target_id is stored as string, convert to UUID for comment lookup
            try:
                target_comment_id = UUID(report.target_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid comment ID format: {report.target_id}",
                )
            target_comment = (
                db.query(models.Comment)
                .filter(models.Comment.id == target_comment_id)
                .first()
            )
            if not target_comment:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Target comment {report.target_id} not found",
                )

            if payload.action_taken == "hide":
                target_comment.hidden_by_mod = True
                action_applied = True
            elif payload.action_taken == "delete":
                target_comment.deleted_by_owner = True
                target_comment.body = "[deleted by moderator]"
                action_applied = True

    # Update report fields
    if payload.status is not None:
        report.status = payload.status
    if payload.action_taken is not None:
        report.action_taken = payload.action_taken
    if payload.notes is not None:
        report.mod_notes = payload.notes  # D25: never overwrite reporter notes

    db.commit()
    db.refresh(report)

    # Log actions to audit log after commit
    if action_applied and payload.action_taken:
        action_name = {
            "ban": "ban_user",
            "hide": f"hide_{report.target_type}",
            "delete": f"delete_{report.target_type}",
        }.get(payload.action_taken)

        if action_name:
            log_moderation_action(
                db=db,
                actor_id=moderator.id,
                action=action_name,
                target_type=report.target_type,
                target_id=report.target_id,
                reason_code=report.reason_code,
                note=payload.notes
                or report.mod_notes
                or f"Action taken via report {report.id}",
            )

    # Log report resolution to audit log
    if payload.status == "resolved":
        log_moderation_action(
            db=db,
            actor_id=moderator.id,
            action="resolve_report",
            target_type="report",
            target_id=report.id,
            reason_code=report.reason_code,
            note=payload.notes or report.mod_notes or f"Report resolved: {report.id}",
        )

        # Close the loop with the (logged-in) reporter (D5/D22).
        if report.reporter_id:
            try:
                SocialNotificationService.create_system_notification(
                    db,
                    user_id=report.reporter_id,
                    notification_type="report_resolved",
                    actor=ensure_system_user(db),
                    content_title="Thanks — we've reviewed your report.",
                )
            except Exception:
                logger.exception("Failed to send report_resolved notification")

    return schemas.Report.model_validate(report)

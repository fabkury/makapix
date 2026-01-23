"""Report management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_moderator
from ..deps import get_db
from ..utils.audit import log_moderation_action
from ..pagination import apply_cursor_filter, create_page_response

router = APIRouter(prefix="/report", tags=["Reports"])


@router.post(
    "",
    response_model=schemas.Report,
    status_code=status.HTTP_201_CREATED,
)
def create_report(
    payload: schemas.ReportCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Report:
    """
    Create a content report.

    TODO: Validate that target_id exists for target_type
    TODO: Check rate limiting (prevent spam reports)
    TODO: Send notification to moderators
    """
    report = models.Report(
        reporter_id=current_user.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason_code=payload.reason_code,
        notes=payload.notes,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return schemas.Report.model_validate(report)


@router.get("", response_model=schemas.Page[schemas.Report], tags=["Reports", "Admin"])
def list_reports(
    status_filter: str | None = Query(None, alias="status"),
    target_type: str | None = None,
    reporter_id: UUID | None = None,
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

    return schemas.Page(
        items=[schemas.Report.model_validate(r) for r in page_data["items"]],
        next_cursor=page_data["next_cursor"],
    )


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
            # target_id is stored as string, convert to UUID for user lookup
            from uuid import UUID as UUIDType

            try:
                target_user_id = UUIDType(report.target_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid user ID format: {report.target_id}",
                )
            target_user = (
                db.query(models.User).filter(models.User.id == target_user_id).first()
            )
            if not target_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Target user {report.target_id} not found",
                )

            if payload.action_taken == "ban":
                from datetime import datetime, timedelta, timezone

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
            from uuid import UUID as UUIDType

            try:
                target_comment_id = UUIDType(report.target_id)
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
        report.notes = payload.notes

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
                or report.notes
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
            note=payload.notes or report.notes or f"Report resolved: {report.id}",
        )

    return schemas.Report.model_validate(report)

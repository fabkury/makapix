"""Report management endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_moderator
from ..deps import get_db

router = APIRouter(prefix="/reports", tags=["Reports"])


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
    
    TODO: Implement cursor pagination
    TODO: Apply filters
    """
    query = db.query(models.Report)
    
    if status_filter:
        query = query.filter(models.Report.status == status_filter)
    if target_type:
        query = query.filter(models.Report.target_type == target_type)
    if reporter_id:
        query = query.filter(models.Report.reporter_id == reporter_id)
    
    query = query.order_by(models.Report.created_at.desc()).limit(limit)
    reports = query.all()
    
    return schemas.Page(
        items=[schemas.Report.model_validate(r) for r in reports],
        next_cursor=None,
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
    
    TODO: Log in audit log
    TODO: Auto-apply action_taken if specified
    """
    report = db.query(models.Report).filter(models.Report.id == id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    
    if payload.status is not None:
        report.status = payload.status
    if payload.action_taken is not None:
        report.action_taken = payload.action_taken
    if payload.notes is not None:
        report.notes = payload.notes
    
    db.commit()
    db.refresh(report)
    
    return schemas.Report.model_validate(report)

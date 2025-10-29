"""Audit logging utility for moderation actions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from .. import models


def log_moderation_action(
    db: Session,
    actor_id: UUID,
    action: str,
    target_type: str | None = None,
    target_id: UUID | None = None,
) -> models.AuditLog:
    """
    Log a moderation action to the audit log.
    
    Args:
        db: Database session
        actor_id: ID of the user performing the action
        action: Action name (e.g., "ban_user", "hide_post", "promote_post")
        target_type: Type of target (e.g., "user", "post", "comment")
        target_id: ID of the target entity
    
    Returns:
        The created AuditLog entry
    """
    audit_entry = models.AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)
    return audit_entry


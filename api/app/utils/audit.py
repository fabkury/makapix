"""Audit logging utility for moderation actions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from .. import models


# System user UUID for automated actions (hash checks, etc.)
SYSTEM_USER_UUID = UUID("00000000-0000-0000-0000-000000000001")


def ensure_system_user(db: Session) -> models.User:
    """
    Ensure system user exists in the database.
    Creates it if it doesn't exist.
    
    Returns:
        The system user
    """
    system_user = db.query(models.User).filter(models.User.id == SYSTEM_USER_UUID).first()
    if not system_user:
        system_user = models.User(
            id=SYSTEM_USER_UUID,
            handle="system",
            display_name="System",
            bio="Automated system actions",
            roles=["user"],  # System user has minimal roles
            deactivated=False,
        )
        db.add(system_user)
        db.commit()
        db.refresh(system_user)
    return system_user


def log_moderation_action(
    db: Session,
    actor_id: UUID,
    action: str,
    target_type: str | None = None,
    target_id: UUID | None = None,
    reason_code: str | None = None,
    note: str | None = None,
) -> models.AuditLog:
    """
    Log a moderation action to the audit log.
    
    Args:
        db: Database session
        actor_id: ID of the user performing the action
        action: Action name (e.g., "ban_user", "hide_post", "promote_post")
        target_type: Type of target (e.g., "user", "post", "comment")
        target_id: ID of the target entity
        reason_code: Reason code for the action (e.g., "spam", "abuse", "copyright", "other")
        note: Additional context or notes about the action
    
    Returns:
        The created AuditLog entry
    """
    # Ensure system user exists if this is a system action
    if actor_id == SYSTEM_USER_UUID:
        ensure_system_user(db)
    
    audit_entry = models.AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason_code=reason_code,
        note=note,
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)
    return audit_entry



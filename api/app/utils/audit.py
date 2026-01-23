"""Audit logging utility for moderation actions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from .. import models

# System user key (UUID) for automated actions (hash checks, etc.)
SYSTEM_USER_KEY = UUID("00000000-0000-0000-0000-000000000001")

# Cached system user ID (integer) - populated on first access
_system_user_id: int | None = None


def ensure_system_user(db: Session) -> models.User:
    """
    Ensure system user exists in the database.
    Creates it if it doesn't exist.

    Returns:
        The system user
    """
    global _system_user_id

    # First try by cached integer ID
    if _system_user_id is not None:
        system_user = (
            db.query(models.User).filter(models.User.id == _system_user_id).first()
        )
        if system_user:
            return system_user

    # Try by user_key (UUID)
    system_user = (
        db.query(models.User).filter(models.User.user_key == SYSTEM_USER_KEY).first()
    )
    if not system_user:
        # Create the system user
        system_user = models.User(
            user_key=SYSTEM_USER_KEY,
            handle="system",
            email="system@notification.makapix.club",
            email_verified=True,
            bio="Automated system actions",
            roles=["user"],  # System user has minimal roles
            deactivated=False,
        )
        db.add(system_user)
        db.flush()  # Get the ID

        # Generate public_sqid
        from ..sqids_config import encode_user_id

        system_user.public_sqid = encode_user_id(system_user.id)

        db.commit()
        db.refresh(system_user)

    # Cache the ID
    _system_user_id = system_user.id
    return system_user


def get_system_user_id(db: Session) -> int:
    """Get the system user's integer ID, creating system user if needed."""
    system_user = ensure_system_user(db)
    return system_user.id


def log_moderation_action(
    db: Session,
    actor_id: int,
    action: str,
    target_type: str | None = None,
    target_id: str | int | UUID | None = None,
    reason_code: str | None = None,
    note: str | None = None,
) -> models.AuditLog:
    """
    Log a moderation action to the audit log.

    Args:
        db: Database session
        actor_id: ID of the user performing the action (integer)
        action: Action name (e.g., "ban_user", "hide_post", "promote_post")
        target_type: Type of target (e.g., "user", "post", "comment")
        target_id: ID of the target entity
        reason_code: Reason code for the action (e.g., "spam", "abuse", "copyright", "other")
        note: Additional context or notes about the action

    Returns:
        The created AuditLog entry
    """
    # Ensure system user exists if this is a system action
    if _system_user_id is not None and actor_id == _system_user_id:
        ensure_system_user(db)

    # Convert target_id to string for storage (supports both UUID and integer IDs)
    target_id_str = str(target_id) if target_id is not None else None

    audit_entry = models.AuditLog(
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id_str,
        reason_code=reason_code,
        note=note,
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)
    return audit_entry

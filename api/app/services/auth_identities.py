"""Authentication identity service for managing user authentication methods."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import AuthIdentity, User

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_password_identity(
    db: Session,
    user_id: UUID,
    email: str,
    password: str,
) -> AuthIdentity:
    """
    Create a password-based authentication identity.

    Args:
        db: Database session
        user_id: User ID
        email: Email address (used as provider_user_id for login)
        password: Plain text password (will be hashed)

    Returns:
        Created AuthIdentity

    Raises:
        IntegrityError: If identity already exists
    """
    identity = AuthIdentity(
        user_id=user_id,
        provider="password",
        provider_user_id=email.lower(),  # Store lowercase for case-insensitive lookup
        secret_hash=hash_password(password),
        email=email.lower(),
    )
    db.add(identity)
    db.commit()
    db.refresh(identity)
    return identity


def create_oauth_identity(
    db: Session,
    user_id: UUID,
    provider: str,
    provider_user_id: str,
    email: str | None = None,
    provider_metadata: dict[str, Any] | None = None,
) -> AuthIdentity:
    """
    Create an OAuth-based authentication identity.

    Args:
        db: Database session
        user_id: User ID
        provider: Provider name (e.g., "github", "reddit")
        provider_user_id: Provider's user ID
        email: Optional email address
        provider_metadata: Optional provider-specific metadata (e.g., username, avatar_url)

    Returns:
        Created AuthIdentity

    Raises:
        IntegrityError: If identity already exists
    """
    identity = AuthIdentity(
        user_id=user_id,
        provider=provider,
        provider_user_id=provider_user_id,
        secret_hash=None,  # OAuth doesn't use passwords
        email=email,
        provider_metadata=provider_metadata or {},
    )
    db.add(identity)
    db.commit()
    db.refresh(identity)
    return identity


def find_identity_by_password(
    db: Session,
    email: str,
    password: str,
) -> AuthIdentity | None:
    """
    Find and verify a password-based identity by email.

    Args:
        db: Database session
        email: User's email address
        password: Plain text password

    Returns:
        AuthIdentity if found and password matches, None otherwise
    """
    identity = (
        db.query(AuthIdentity)
        .filter(
            AuthIdentity.provider == "password",
            AuthIdentity.provider_user_id == email.lower(),
        )
        .first()
    )

    if not identity:
        return None

    if not identity.secret_hash:
        return None

    if not verify_password(password, identity.secret_hash):
        return None

    return identity


def update_password(
    db: Session,
    user_id: UUID,
    new_password: str,
) -> bool:
    """
    Update a user's password.

    Args:
        db: Database session
        user_id: User ID
        new_password: New plain text password (will be hashed)

    Returns:
        True if password was updated, False if no password identity found
    """
    identity = (
        db.query(AuthIdentity)
        .filter(
            AuthIdentity.user_id == user_id,
            AuthIdentity.provider == "password",
        )
        .first()
    )

    if not identity:
        return False

    identity.secret_hash = hash_password(new_password)
    db.commit()
    return True


def find_identity_by_oauth(
    db: Session,
    provider: str,
    provider_user_id: str,
) -> AuthIdentity | None:
    """
    Find an OAuth-based identity.

    Args:
        db: Database session
        provider: Provider name
        provider_user_id: Provider's user ID

    Returns:
        AuthIdentity if found, None otherwise
    """
    return (
        db.query(AuthIdentity)
        .filter(
            AuthIdentity.provider == provider,
            AuthIdentity.provider_user_id == provider_user_id,
        )
        .first()
    )


def get_user_identities(db: Session, user_id: UUID) -> list[AuthIdentity]:
    """
    Get all authentication identities for a user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        List of AuthIdentity objects
    """
    return (
        db.query(AuthIdentity)
        .filter(
            AuthIdentity.user_id == user_id,
        )
        .all()
    )


def delete_identity(db: Session, identity_id: UUID, user_id: UUID) -> bool:
    """
    Delete an authentication identity.

    Prevents deletion if it's the last identity for the user.

    Args:
        db: Database session
        identity_id: Identity ID to delete
        user_id: User ID (for verification)

    Returns:
        True if deleted, False if prevented (last identity)

    Raises:
        ValueError: If identity doesn't belong to user
    """
    identity = (
        db.query(AuthIdentity)
        .filter(
            AuthIdentity.id == identity_id,
            AuthIdentity.user_id == user_id,
        )
        .first()
    )

    if not identity:
        raise ValueError("Identity not found or doesn't belong to user")

    # Check if this is the last identity
    all_identities = get_user_identities(db, user_id)
    if len(all_identities) <= 1:
        logger.warning(f"Cannot delete last identity for user {user_id}")
        return False

    db.delete(identity)
    db.commit()
    return True


def link_oauth_identity(
    db: Session,
    user_id: UUID,
    provider: str,
    provider_user_id: str,
    email: str | None = None,
    provider_metadata: dict[str, Any] | None = None,
) -> AuthIdentity:
    """
    Link an OAuth identity to an existing user account.

    If the identity already exists for another user, raises IntegrityError.
    If the identity already exists for this user, returns the existing identity.

    Args:
        db: Database session
        user_id: User ID to link to
        provider: Provider name
        provider_user_id: Provider's user ID
        email: Optional email address
        metadata: Optional provider-specific metadata

    Returns:
        AuthIdentity (created or existing)

    Raises:
        IntegrityError: If identity already exists for another user
    """
    # Check if identity already exists for this user
    existing = (
        db.query(AuthIdentity)
        .filter(
            AuthIdentity.user_id == user_id,
            AuthIdentity.provider == provider,
            AuthIdentity.provider_user_id == provider_user_id,
        )
        .first()
    )

    if existing:
        # Update metadata if provided
        if provider_metadata:
            existing.provider_metadata = provider_metadata
            if email:
                existing.email = email
            db.commit()
            db.refresh(existing)
        return existing

    # Check if identity exists for another user (shouldn't happen due to unique constraint)
    other_user_identity = (
        db.query(AuthIdentity)
        .filter(
            AuthIdentity.provider == provider,
            AuthIdentity.provider_user_id == provider_user_id,
        )
        .first()
    )

    if other_user_identity:
        raise IntegrityError("Identity already linked to another user")

    # Create new identity
    return create_oauth_identity(
        db=db,
        user_id=user_id,
        provider=provider,
        provider_user_id=provider_user_id,
        email=email,
        provider_metadata=provider_metadata,
    )

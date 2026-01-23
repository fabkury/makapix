"""Password reset service for handling password reset tokens."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from .. import models
from .email import send_password_reset_email

logger = logging.getLogger(__name__)

# Token expiration: 1 hour
PASSWORD_RESET_TOKEN_EXPIRATION_HOURS = 1

# Rate limiting: max 3 reset requests per hour per user
RESET_RATE_LIMIT_HOURS = 1
RESET_RATE_LIMIT_COUNT = 3


def _hash_token(token: str) -> str:
    """Hash a token using SHA256."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_reset_token(db: Session, user_id: UUID) -> str:
    """
    Create a password reset token for a user.

    Args:
        db: Database session
        user_id: User ID to create token for

    Returns:
        Plain text token (to be sent via email)

    Raises:
        ValueError: If rate limit exceeded
    """
    # Clean up expired tokens
    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == user_id,
        models.PasswordResetToken.used_at.is_(None),
        models.PasswordResetToken.expires_at < datetime.now(timezone.utc),
    ).delete()
    db.commit()

    # Check rate limit
    recent_tokens_count = (
        db.query(models.PasswordResetToken)
        .filter(
            models.PasswordResetToken.user_id == user_id,
            models.PasswordResetToken.created_at
            >= datetime.now(timezone.utc) - timedelta(hours=RESET_RATE_LIMIT_HOURS),
        )
        .count()
    )

    if recent_tokens_count >= RESET_RATE_LIMIT_COUNT:
        raise ValueError(
            f"Rate limit exceeded. Please wait before requesting another password reset."
        )

    # Generate secure token
    plain_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(plain_token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=PASSWORD_RESET_TOKEN_EXPIRATION_HOURS
    )

    # Create token record
    reset_token = models.PasswordResetToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(reset_token)
    db.commit()
    db.refresh(reset_token)

    logger.info(
        f"Created password reset token for user {user_id}, expires at {expires_at}"
    )
    return plain_token


def verify_reset_token(db: Session, token: str) -> models.PasswordResetToken | None:
    """
    Verify a password reset token.

    Args:
        db: Database session
        token: Plain text token from email

    Returns:
        PasswordResetToken record if valid, None otherwise
    """
    token_hash = _hash_token(token)

    reset_token = (
        db.query(models.PasswordResetToken)
        .filter(
            models.PasswordResetToken.token_hash == token_hash,
            models.PasswordResetToken.used_at.is_(None),
            models.PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )

    return reset_token


def mark_token_used(db: Session, token_id: UUID) -> None:
    """
    Mark a password reset token as used.

    Args:
        db: Database session
        token_id: Token ID to mark as used
    """
    token = (
        db.query(models.PasswordResetToken)
        .filter(models.PasswordResetToken.id == token_id)
        .first()
    )

    if token:
        token.used_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"Marked password reset token {token_id} as used")


def send_reset_email_for_user(db: Session, user: models.User) -> bool:
    """
    Create a reset token and send password reset email to a user.

    Args:
        db: Database session
        user: The user to send reset email to

    Returns:
        True if email was sent successfully, False otherwise
    """
    if not user.email:
        logger.error(f"No email address for user {user.id}")
        return False

    try:
        # Create token
        token = create_reset_token(db, user.id)

        # Send email
        result = send_password_reset_email(
            to_email=user.email,
            token=token,
            handle=user.handle,
        )

        return result is not None

    except ValueError as e:
        # Rate limit exceeded
        logger.warning(f"Could not send password reset email: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")
        return False

"""Email verification token service for secure token generation and validation."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from .email import send_verification_email

logger = logging.getLogger(__name__)

# Token configuration
TOKEN_EXPIRY_HOURS = 24
MAX_TOKENS_PER_HOUR = 6  # Rate limit: max verification emails per user per hour


def _hash_token(token: str) -> str:
    """Hash a token using SHA256 for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_verification_token(db: Session, user_id: UUID, email: str) -> str:
    """
    Create a new email verification token.

    Args:
        db: Database session
        user_id: The user's ID
        email: The email address being verified

    Returns:
        The plain token (to be sent via email)

    Raises:
        ValueError: If rate limit exceeded
    """
    # Check rate limit: count tokens created in the last hour
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent_tokens = (
        db.query(models.EmailVerificationToken)
        .filter(
            models.EmailVerificationToken.user_id == user_id,
            models.EmailVerificationToken.created_at >= one_hour_ago,
        )
        .count()
    )

    if recent_tokens >= MAX_TOKENS_PER_HOUR:
        raise ValueError(
            f"Rate limit exceeded. Maximum {MAX_TOKENS_PER_HOUR} verification emails per hour."
        )

    # Generate secure token
    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)

    # Create expiration time
    expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS)

    # Create token record
    verification_token = models.EmailVerificationToken(
        user_id=user_id,
        token_hash=token_hash,
        email=email,
        expires_at=expires_at,
    )

    db.add(verification_token)
    db.commit()

    logger.info(
        f"Created verification token for user {user_id}, expires at {expires_at}"
    )
    return token


def verify_token(db: Session, token: str) -> models.EmailVerificationToken | None:
    """
    Verify a token and return the token record if valid.

    Args:
        db: Database session
        token: The plain token from the verification link

    Returns:
        The token record if valid and not expired/used, None otherwise
    """
    token_hash = _hash_token(token)

    # Find token by hash
    verification_token = (
        db.query(models.EmailVerificationToken)
        .filter(
            models.EmailVerificationToken.token_hash == token_hash,
        )
        .first()
    )

    if not verification_token:
        logger.warning(f"Verification token not found")
        return None

    # Check if already used
    if verification_token.used_at is not None:
        logger.warning(
            f"Verification token already used at {verification_token.used_at}"
        )
        return None

    # Check expiration
    if verification_token.expires_at < datetime.now(timezone.utc):
        logger.warning(f"Verification token expired at {verification_token.expires_at}")
        return None

    return verification_token


def mark_email_verified(db: Session, token: str) -> models.User | None:
    """
    Verify a token and mark the user's email as verified.

    Args:
        db: Database session
        token: The plain token from the verification link

    Returns:
        The user if verification successful, None otherwise
    """
    verification_token = verify_token(db, token)
    if not verification_token:
        return None

    # Mark token as used
    verification_token.used_at = datetime.now(timezone.utc)

    # Get user and mark email as verified
    user = (
        db.query(models.User)
        .filter(models.User.id == verification_token.user_id)
        .first()
    )

    if not user:
        logger.error(
            f"User {verification_token.user_id} not found for verification token"
        )
        return None

    # Update user's email if it changed and mark as verified
    user.email = verification_token.email
    user.email_verified = True

    db.commit()
    db.refresh(user)

    logger.info(f"Email verified for user {user.id} ({user.email})")
    return user


def send_verification_email_for_user(
    db: Session,
    user: models.User,
    email: str | None = None,
    password: str | None = None,
) -> bool:
    """
    Create a verification token and send verification email to a user.

    Args:
        db: Database session
        user: The user to send verification to
        email: Optional email to verify (defaults to user's email)
        password: Optional generated password to include in the email

    Returns:
        True if email was sent successfully, False otherwise
    """
    email_to_verify = email or user.email
    if not email_to_verify:
        logger.error(f"No email address for user {user.id}")
        return False

    try:
        # Create token
        token = create_verification_token(db, user.id, email_to_verify)

        # Send email
        result = send_verification_email(
            to_email=email_to_verify,
            token=token,
            handle=user.handle,
            password=password,
        )

        return result is not None

    except ValueError as e:
        # Rate limit exceeded
        logger.warning(f"Could not send verification email: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to send verification email: {e}")
        return False


def get_pending_verifications(
    db: Session, user_id: UUID
) -> list[models.EmailVerificationToken]:
    """
    Get all pending (unused, unexpired) verification tokens for a user.

    Args:
        db: Database session
        user_id: The user's ID

    Returns:
        List of pending verification tokens
    """
    now = datetime.now(timezone.utc)
    return (
        db.query(models.EmailVerificationToken)
        .filter(
            models.EmailVerificationToken.user_id == user_id,
            models.EmailVerificationToken.used_at.is_(None),
            models.EmailVerificationToken.expires_at > now,
        )
        .all()
    )


def invalidate_pending_verifications(db: Session, user_id: UUID) -> int:
    """
    Invalidate all pending verification tokens for a user.
    Useful when user's email is verified through other means.

    Args:
        db: Database session
        user_id: The user's ID

    Returns:
        Number of tokens invalidated
    """
    now = datetime.now(timezone.utc)
    count = (
        db.query(models.EmailVerificationToken)
        .filter(
            models.EmailVerificationToken.user_id == user_id,
            models.EmailVerificationToken.used_at.is_(None),
            models.EmailVerificationToken.expires_at > now,
        )
        .update({"used_at": now})
    )

    db.commit()
    logger.info(f"Invalidated {count} pending verification tokens for user {user_id}")
    return count

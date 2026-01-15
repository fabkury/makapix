"""Storage quota service for user upload limits."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models


# Storage quota tiers (in bytes)
QUOTA_TIER_NEW = 50 * 1024 * 1024       # 50MB for reputation < 100
QUOTA_TIER_ESTABLISHED = 100 * 1024 * 1024  # 100MB for reputation 100-499
QUOTA_TIER_TRUSTED = 250 * 1024 * 1024  # 250MB for reputation 500-999
QUOTA_TIER_VETERAN = 500 * 1024 * 1024  # 500MB for reputation 1000+


def get_user_storage_quota(user: models.User) -> int:
    """
    Get storage quota in bytes based on user reputation.

    Tiers:
    - Reputation < 100: 50MB
    - Reputation 100-499: 100MB
    - Reputation 500-999: 250MB
    - Reputation 1000+: 500MB

    Args:
        user: The user to get quota for

    Returns:
        Storage quota in bytes
    """
    if user.reputation >= 1000:
        return QUOTA_TIER_VETERAN
    elif user.reputation >= 500:
        return QUOTA_TIER_TRUSTED
    elif user.reputation >= 100:
        return QUOTA_TIER_ESTABLISHED
    else:
        return QUOTA_TIER_NEW


def get_user_storage_used(db: Session, user_id: int) -> int:
    """
    Calculate storage used by non-deleted posts.

    Only counts posts where deleted_by_user is False.
    Storage is freed only after permanent deletion by cleanup job.

    Args:
        db: Database session
        user_id: User ID to check

    Returns:
        Storage used in bytes
    """
    result = db.query(func.coalesce(func.sum(models.Post.file_bytes), 0)).filter(
        models.Post.owner_id == user_id,
        models.Post.deleted_by_user == False,
    ).scalar()
    return int(result)


def check_storage_quota(
    db: Session, user: models.User, file_size: int
) -> tuple[bool, int, int]:
    """
    Check if user has enough quota for upload.

    Args:
        db: Database session
        user: User attempting upload
        file_size: Size of file to upload in bytes

    Returns:
        Tuple of (allowed, used_bytes, quota_bytes)
    """
    quota = get_user_storage_quota(user)
    used = get_user_storage_used(db, user.id)

    return (used + file_size <= quota, used, quota)


def format_quota_error(used: int, quota: int) -> str:
    """Format a human-readable quota error message."""
    used_mb = used / 1024 / 1024
    quota_mb = quota / 1024 / 1024
    return f"Storage quota exceeded. Used: {used_mb:.1f}MB / {quota_mb:.0f}MB"

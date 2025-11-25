"""Handle generation and validation utilities."""

from __future__ import annotations

import re
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import User


def is_url_safe(handle: str) -> bool:
    """
    Check if a handle is URL-safe.
    
    Allows: alphanumeric, hyphens, underscores
    Must start with alphanumeric.
    """
    if not handle:
        return False
    
    # Must start with alphanumeric
    if not handle[0].isalnum():
        return False
    
    # Only allow alphanumeric, hyphens, and underscores
    pattern = re.compile(r'^[a-zA-Z0-9_-]+$')
    return bool(pattern.match(handle))


def validate_handle(handle: str, min_length: int = 2, max_length: int = 50) -> tuple[bool, str | None]:
    """
    Validate a handle format and return (is_valid, error_message).
    
    Returns:
        (True, None) if valid
        (False, error_message) if invalid
    """
    if not handle:
        return False, "Handle cannot be empty"
    
    if len(handle) < min_length:
        return False, f"Handle must be at least {min_length} characters"
    
    if len(handle) > max_length:
        return False, f"Handle must be at most {max_length} characters"
    
    if not is_url_safe(handle):
        return False, "Handle can only contain letters, numbers, hyphens, and underscores, and must start with a letter or number"
    
    return True, None


def is_handle_taken(db: Session, handle: str, exclude_user_id: str | None = None) -> bool:
    """
    Check if a handle is already taken.
    
    Args:
        db: Database session
        handle: Handle to check
        exclude_user_id: Optional user ID to exclude from check (for updates)
    """
    query = db.query(User).filter(User.handle == handle.lower())
    
    if exclude_user_id:
        query = query.filter(User.id != exclude_user_id)
    
    return query.first() is not None


def generate_default_handle(db: Session) -> str:
    """
    Generate a default handle in the format "makapix-user-X" where X is an integer.
    
    Uses a sequence to ensure uniqueness and avoid gaps.
    """
    # Get the next value from the sequence
    result = db.execute(
        text("SELECT nextval('handle_sequence')")
    )
    handle_number = result.scalar()
    
    return f"makapix-user-{handle_number}"




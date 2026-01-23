"""Handle generation and validation utilities."""

from __future__ import annotations

import unicodedata
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from ..models import User


def is_printable_char(char: str) -> bool:
    """
    Check if a character is printable (not a control character).

    Allows:
    - All printable Unicode characters (letters, digits, symbols, punctuation, emoji)

    Rejects:
    - Control characters (Cc category)
    - Format characters (Cf category)
    - Private use characters (Co category)
    - Surrogate characters (Cs category)
    - Unassigned characters (Cn category)
    """
    if not char:
        return False

    category = unicodedata.category(char)
    # Reject control, format, private use, surrogate, and unassigned characters
    if category in ("Cc", "Cf", "Co", "Cs", "Cn"):
        return False

    return True


def is_valid_handle_content(handle: str) -> tuple[bool, str | None]:
    """
    Check if a handle contains only valid characters.

    Allows any UTF-8 printable character including:
    - All letters (Latin, Cyrillic, CJK, Arabic, etc.)
    - All digits
    - Emoji
    - Punctuation and symbols

    Rejects:
    - Control characters
    - Non-printable characters
    - Whitespace-only handles (but whitespace within is allowed)

    Returns:
        (True, None) if valid
        (False, error_message) if invalid
    """
    if not handle:
        return False, "Handle cannot be empty"

    # Check each character is printable
    for i, char in enumerate(handle):
        if not is_printable_char(char):
            char_code = ord(char)
            return (
                False,
                f"Handle contains invalid character at position {i + 1} (code: U+{char_code:04X})",
            )

    return True, None


def validate_handle(
    handle: str, min_length: int = 1, max_length: int = 32
) -> tuple[bool, str | None]:
    """
    Validate a handle format and return (is_valid, error_message).

    Requirements:
    - Must be stripped of leading/trailing whitespace
    - Must be 1-32 characters after stripping
    - Must contain only printable UTF-8 characters (no control characters)

    Returns:
        (True, None) if valid
        (False, error_message) if invalid
    """
    if handle is None:
        return False, "Handle cannot be empty"

    # Strip whitespace - this should already be done by caller, but ensure it here
    stripped = handle.strip()

    if not stripped:
        return False, "Handle cannot be empty or whitespace-only"

    if len(stripped) < min_length:
        return (
            False,
            f"Handle must be at least {min_length} character{'s' if min_length > 1 else ''}",
        )

    if len(stripped) > max_length:
        return False, f"Handle must be at most {max_length} characters"

    # Check content is valid (printable UTF-8, no control characters)
    is_valid, error_msg = is_valid_handle_content(stripped)
    if not is_valid:
        return False, error_msg

    return True, None


def is_handle_taken(
    db: Session, handle: str, exclude_user_id: int | None = None
) -> bool:
    """
    Check if a handle is already taken (case-insensitive).

    Uniqueness is case-insensitive: "User", "user", and "USER" are considered the same.
    However, the original casing is preserved in the database for display.

    Args:
        db: Database session
        handle: Handle to check (will be compared case-insensitively)
        exclude_user_id: Optional user ID to exclude from check (for updates)
    """
    # Use LOWER() for case-insensitive comparison
    query = db.query(User).filter(func.lower(User.handle) == handle.lower())

    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)

    return query.first() is not None


def generate_default_handle(db: Session) -> str:
    """
    Generate a default handle in the format "makapix-user-X" where X is an integer.

    Uses a sequence to ensure uniqueness and avoid gaps.
    """
    # Get the next value from the sequence
    result = db.execute(text("SELECT nextval('handle_sequence')"))
    handle_number = result.scalar()

    return f"makapix-user-{handle_number}"

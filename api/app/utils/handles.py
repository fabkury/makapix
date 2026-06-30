"""Handle generation and uniqueness utilities.

Character/format validation and the confusable skeleton live in the pure,
model-free :mod:`app.utils.handle_normalize`; this module adds the DB-backed
pieces (uniqueness lookup + default-handle generation). ``validate_handle`` is
re-exported here so existing imports (`from ..utils.handles import
validate_handle`) keep working.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import User
from .handle_normalize import (  # noqa: F401 - re-exported for existing imports
    compute_handle_skeleton,
    normalize_handle,
    validate_handle,
)


def is_handle_taken(
    db: Session, handle: str, exclude_user_id: int | None = None
) -> bool:
    """Check whether a handle is already taken.

    Uniqueness is by the confusable skeleton (see
    :func:`app.utils.handle_normalize.compute_handle_skeleton`): case-insensitive
    AND confusable-folded, so visually identical handles across scripts collide.
    The original casing/script is preserved on the row for display.

    Args:
        db: Database session
        handle: Handle to check
        exclude_user_id: Optional user ID to exclude (for self-updates)
    """
    skeleton = compute_handle_skeleton(handle)
    query = db.query(User).filter(User.handle_normalized == skeleton)
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

"""Sqids configuration for encoding/decoding post IDs."""

from __future__ import annotations

import os

from sqids import Sqids

# Get alphabets from environment variables
SQIDS_ALPHABET = os.getenv("SQIDS_ALPHABET", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
NEW_SQIDS_ALPHABET = os.getenv("NEW_SQIDS_ALPHABET", SQIDS_ALPHABET)

# Create singleton Sqids instances
# Note: Salt has been removed from sqids library, so we don't use it
sqids = Sqids(
    alphabet=SQIDS_ALPHABET,
    min_length=0,  # Zero minimum length as specified
)

# New alphabet instance for encoding (after migration)
sqids_new = Sqids(
    alphabet=NEW_SQIDS_ALPHABET,
    min_length=0,
)

# Old alphabet instance for decoding legacy sqids (during transition)
sqids_old = Sqids(
    alphabet=SQIDS_ALPHABET,
    min_length=0,
)


def encode_id(post_id: int) -> str:
    """
    Encode a post ID (integer) to a Sqids string using NEW_SQIDS_ALPHABET.
    
    Args:
        post_id: The integer post ID
        
    Returns:
        The encoded Sqids string (public_sqid)
    """
    return sqids_new.encode([post_id])


def decode_sqid(sqid: str) -> int | None:
    """
    Decode a Sqids string to a post ID (integer).
    
    Tries NEW_SQIDS_ALPHABET first, then falls back to OLD alphabet
    for backward compatibility during transition period.
    
    Args:
        sqid: The Sqids-encoded string (public_sqid)
        
    Returns:
        The decoded post ID, or None if invalid
    """
    # Try new alphabet first
    try:
        decoded = sqids_new.decode(sqid)
        if decoded and len(decoded) == 1:
            return decoded[0]
    except Exception:
        pass
    
    # Fall back to old alphabet for legacy sqids
    try:
        decoded = sqids_old.decode(sqid)
        if decoded and len(decoded) == 1:
            return decoded[0]
    except Exception:
        pass
    
    return None


def encode_user_id(user_id: int) -> str:
    """
    Encode a user ID (integer) to a Sqids string using NEW_SQIDS_ALPHABET.
    
    Args:
        user_id: The integer user ID
        
    Returns:
        The encoded Sqids string (public_sqid)
    """
    return sqids_new.encode([user_id])


def decode_user_sqid(sqid: str) -> int | None:
    """
    Decode a Sqids string to a user ID (integer).
    
    Tries NEW_SQIDS_ALPHABET first, then falls back to OLD alphabet
    for backward compatibility during transition period.
    
    Args:
        sqid: The Sqids-encoded string (public_sqid)
        
    Returns:
        The decoded user ID, or None if invalid
    """
    # Try new alphabet first
    try:
        decoded = sqids_new.decode(sqid)
        if decoded and len(decoded) == 1:
            return decoded[0]
    except Exception:
        pass
    
    # Fall back to old alphabet for legacy sqids (if any exist)
    try:
        decoded = sqids_old.decode(sqid)
        if decoded and len(decoded) == 1:
            return decoded[0]
    except Exception:
        pass
    
    return None


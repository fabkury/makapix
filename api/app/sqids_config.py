"""Sqids configuration for encoding/decoding post IDs."""

from __future__ import annotations

import os

from sqids import Sqids

# Get alphabet from environment variable (already defined in .env)
SQIDS_ALPHABET = os.getenv("SQIDS_ALPHABET", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

# Create singleton Sqids instance
# Note: Salt has been removed from sqids library, so we don't use it
sqids = Sqids(
    alphabet=SQIDS_ALPHABET,
    min_length=0,  # Zero minimum length as specified
)


def encode_id(post_id: int) -> str:
    """
    Encode a post ID (integer) to a Sqids string.
    
    Args:
        post_id: The integer post ID
        
    Returns:
        The encoded Sqids string (public_sqid)
    """
    return sqids.encode([post_id])


def decode_sqid(sqid: str) -> int | None:
    """
    Decode a Sqids string to a post ID (integer).
    
    Args:
        sqid: The Sqids-encoded string (public_sqid)
        
    Returns:
        The decoded post ID, or None if invalid
    """
    try:
        decoded = sqids.decode(sqid)
        if decoded and len(decoded) == 1:
            return decoded[0]
        return None
    except Exception:
        return None


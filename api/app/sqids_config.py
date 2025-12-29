"""Sqids configuration for encoding/decoding public IDs.

This codebase has completed the Sqids alphabet migration. Only the current
alphabet (SQIDS_ALPHABET) is supported; there is no legacy decoding fallback.
"""

from __future__ import annotations

import os

from sqids import Sqids

# Get alphabet from environment variable.
#
# Default is base62, but in production we expect SQIDS_ALPHABET to be explicitly
# set to our canonical alphabet (with ambiguous characters removed).
SQIDS_ALPHABET = os.getenv("SQIDS_ALPHABET", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

# Create singleton Sqids instance
# Note: Salt has been removed from sqids library, so we don't use it.
sqids = Sqids(alphabet=SQIDS_ALPHABET, min_length=0)


def encode_id(post_id: int) -> str:
    """
    Encode a post ID (integer) to a Sqids string using SQIDS_ALPHABET.
    
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
    except Exception:
        pass

    return None


def encode_user_id(user_id: int) -> str:
    """
    Encode a user ID (integer) to a Sqids string using SQIDS_ALPHABET.
    
    Args:
        user_id: The integer user ID
        
    Returns:
        The encoded Sqids string (public_sqid)
    """
    return sqids.encode([user_id])


def decode_user_sqid(sqid: str) -> int | None:
    """
    Decode a Sqids string to a user ID (integer).
    
    Args:
        sqid: The Sqids-encoded string (public_sqid)
        
    Returns:
        The decoded user ID, or None if invalid
    """
    try:
        decoded = sqids.decode(sqid)
        if decoded and len(decoded) == 1:
            return decoded[0]
    except Exception:
        pass

    return None


def encode_blog_post_id(blog_post_id: int) -> str:
    """
    Encode a blog post ID (integer) to a Sqids string using SQIDS_ALPHABET.
    
    Args:
        blog_post_id: The integer blog post ID
        
    Returns:
        The encoded Sqids string (public_sqid)
    """
    return sqids.encode([blog_post_id])


def decode_blog_post_sqid(sqid: str) -> int | None:
    """
    Decode a Sqids string to a blog post ID (integer).
    
    Args:
        sqid: The Sqids-encoded string (public_sqid)
        
    Returns:
        The decoded blog post ID, or None if invalid
    """
    try:
        decoded = sqids.decode(sqid)
        if decoded and len(decoded) == 1:
            return decoded[0]
    except Exception:
        pass

    return None


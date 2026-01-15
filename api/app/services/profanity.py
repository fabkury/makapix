"""Profanity filtering service for comments and other user content."""

from __future__ import annotations

import logging

from better_profanity import profanity

logger = logging.getLogger(__name__)

# Load default censor words on module import
profanity.load_censor_words()


def contains_profanity(text: str) -> bool:
    """
    Check if text contains profanity.

    Uses the better-profanity library with its default word list.

    Args:
        text: The text to check

    Returns:
        True if text contains profanity, False otherwise
    """
    if not text:
        return False
    return profanity.contains_profanity(text)


def censor_profanity(text: str) -> str:
    """
    Censor profanity in text by replacing with asterisks.

    Args:
        text: The text to censor

    Returns:
        Censored text with profanity replaced
    """
    if not text:
        return text
    return profanity.censor(text)

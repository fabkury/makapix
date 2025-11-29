"""Registration code generation utilities."""

from __future__ import annotations

import secrets


def generate_registration_code() -> str:
    """
    Generate 6-character case-insensitive alphanumeric code.
    
    Excludes ambiguous characters: 0, O, I, 1, L
    Uses uppercase letters and digits for clarity.
    
    Returns:
        6-character registration code (e.g., "A3F8X2")
    """
    # Alphabet excluding ambiguous characters: 0, O, I, 1, L
    alphabet = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(6))


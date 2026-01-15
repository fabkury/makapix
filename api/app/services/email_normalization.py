"""Email normalization service to prevent plus-syntax and dot-syntax abuse."""

from __future__ import annotations


def normalize_email(email: str) -> str:
    """
    Normalize email to prevent plus-syntax and dot-syntax abuse.

    Handles provider-specific normalization rules:
    - Gmail/Googlemail: Ignores dots and removes plus-suffix (user+tag@gmail.com -> user@gmail.com)
    - Outlook/Hotmail/Live/MSN: Removes plus-suffix only (dots are significant)
    - Yahoo/Ymail: Removes hyphen-suffix (user-tag@yahoo.com -> user@yahoo.com)
    - Other providers: Removes plus-suffix as common pattern

    Args:
        email: The email address to normalize

    Returns:
        Normalized email address
    """
    if "@" not in email:
        return email.lower()

    local, domain = email.lower().split("@", 1)

    # Gmail/Google: ignore dots and plus-suffix
    if domain in ["gmail.com", "googlemail.com"]:
        local = local.replace(".", "")
        if "+" in local:
            local = local.split("+")[0]

    # Outlook/Hotmail/Live/MSN: only remove plus-suffix (dots are significant)
    elif domain in ["outlook.com", "hotmail.com", "live.com", "msn.com"]:
        if "+" in local:
            local = local.split("+")[0]

    # Yahoo/Ymail: plus-syntax uses hyphen
    elif domain in ["yahoo.com", "ymail.com"]:
        if "-" in local:
            local = local.split("-")[0]

    # Other providers: just remove plus-suffix as common pattern
    else:
        if "+" in local:
            local = local.split("+")[0]

    return f"{local}@{domain}"

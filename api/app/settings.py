"""Centralized environment-driven settings.

Keep this module lightweight: stdlib only, no app imports, to avoid circular deps.
"""

from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# Global maximum size for a single artwork upload / asset (bytes).
# Configured via .env: MAKAPIX_ARTWORK_SIZE_LIMIT=5242880  (5 MiB)
MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES: int = _int_env(
    "MAKAPIX_ARTWORK_SIZE_LIMIT", 5 * 1024 * 1024
)


def vault_public_base_url() -> str:
    """Return the public base URL for vault assets, or "" if unset.

    When set, URL builders (get_artwork_url / get_avatar_url /
    get_blog_image_url) prefix it onto returned URLs so browsers fetch
    images directly from Caddy. When empty, builders return relative
    /api/vault/... paths (legacy behavior). Read at call time so tests
    can monkeypatch the environment.
    """
    return os.environ.get("VAULT_PUBLIC_BASE_URL", "").rstrip("/")

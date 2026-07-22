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

# Maximum size for an attached .mkpx layers file (bytes); advertised to
# clients via /config upload.mkpx (docs/mkpx-upload/). Default 50 MiB.
MAKAPIX_MKPX_SIZE_LIMIT_BYTES: int = _int_env(
    "MAKAPIX_MKPX_SIZE_LIMIT", 50 * 1024 * 1024
)

# Vault free-space floor (bytes): writes are refused when the vault volume
# has less free space than this, so uploads fail cleanly instead of via
# ENOSPC mid-write. Default 500 MiB.
MAKAPIX_VAULT_MIN_FREE_BYTES: int = _int_env(
    "MAKAPIX_VAULT_MIN_FREE_BYTES", 500 * 1024 * 1024
)


def vault_public_base_url() -> str:
    """Return the public base URL for vault assets (required setting).

    URL builders (get_artwork_url / get_avatar_url / get_blog_image_url)
    prefix it onto returned URLs so clients fetch images directly from the
    Caddy vault subdomain. The legacy relative /api/vault/... serving mount
    was removed 2026-07-22 (docs/remove-api-vault/), so there is no fallback:
    an unset value would silently mint dead URLs, hence the hard failure.
    Read at call time so tests can monkeypatch the environment.
    """
    url = os.environ.get("VAULT_PUBLIC_BASE_URL", "").rstrip("/")
    if not url:
        raise RuntimeError(
            "VAULT_PUBLIC_BASE_URL must be set (e.g. https://vault.makapix.club); "
            "vault asset URLs cannot be generated without it"
        )
    return url

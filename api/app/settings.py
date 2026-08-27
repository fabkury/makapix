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


def ip_hash_salt() -> str:
    """Return the secret salt for IP-address hashing (required setting).

    Unsalted SHA-256 over the IPv4 space is brute-forceable, so stored
    visitor_ip_hash values would be reversible by anyone with DB access
    (docs/artwork-views/ D14). The salt is a deployment secret (generate
    with `openssl rand -hex 32`), static so hashes stay comparable across
    days. Read at call time so tests can monkeypatch the environment.
    """
    salt = os.environ.get("MAKAPIX_IP_HASH_SALT", "")
    if not salt:
        raise RuntimeError(
            "MAKAPIX_IP_HASH_SALT must be set (generate with `openssl rand -hex 32`); "
            "visitor IP hashes cannot be computed without it"
        )
    return salt


def webauthn_rp_id() -> str:
    """Return the WebAuthn Relying Party ID (required setting).

    Picks which credentials are valid against this deployment: prod uses the
    apex (`makapix.club`, valid across subdomains), dev uses
    `app-dev.makapix.club` so dev-registered credentials can never be offered
    against prod (docs/zero-tap-signin/PLAN.md). Read at call time so tests can
    monkeypatch the environment.
    """
    rp_id = os.environ.get("WEBAUTHN_RP_ID", "").strip()
    if not rp_id:
        raise RuntimeError(
            "WEBAUTHN_RP_ID must be set (prod: makapix.club, "
            "dev: app-dev.makapix.club); WebAuthn/restore-credential "
            "options cannot be generated without it"
        )
    return rp_id


def webauthn_allow_debug_origin() -> bool:
    """Whether debug-signed Android builds may mint sessions via WebAuthn.

    The expected-origin list gates real session minting (unlike App Links,
    which only route a URL), so prod accepts only the upload and Play
    app-signing certs; dev sets this to accept `flutter run` builds too
    (docs/zero-tap-signin/messages/0003 §2c).
    """
    return os.environ.get("WEBAUTHN_ALLOW_DEBUG_ORIGIN", "").strip().lower() in (
        "1",
        "true",
        "yes",
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

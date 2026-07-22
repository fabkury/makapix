"""Vault-only art_url invariant.

Every stored posts.art_url must point at Makapix's own vault — either the
relative /api/vault/... path served by FastAPI or an absolute URL on the
configured vault subdomain (VAULT_PUBLIC_BASE_URL). External hosting of
artworks was removed 2026-07-22 (docs/remove-external-hosting/); this guard
exists so a future endpoint cannot quietly reintroduce a foreign-URL writer.

Guard failures are server bugs, not client errors: the only callers are the
upload/replace paths, which derive the URL from vault.get_artwork_url —
hence a plain ValueError rather than an AppError.
"""

from ..settings import vault_public_base_url

_RELATIVE_VAULT_PREFIX = "/api/vault/"


def is_vault_art_url(url: str) -> bool:
    """True if ``url`` points at this deployment's own vault."""
    if not url:
        return False
    if url.startswith(_RELATIVE_VAULT_PREFIX):
        return True
    base = vault_public_base_url()
    if base and url.startswith(base.rstrip("/") + "/"):
        return True
    return False


def assert_vault_art_url(url: str) -> str:
    """Return ``url`` unchanged, raising ValueError if it is not vault-hosted."""
    if not is_vault_art_url(url):
        raise ValueError(
            f"art_url must be vault-derived (self-hosted artworks only); got {url!r}"
        )
    return url

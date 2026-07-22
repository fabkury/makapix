"""Vault-only art_url invariant.

Every stored posts.art_url must point at Makapix's own vault — an absolute
URL on the configured vault subdomain (VAULT_PUBLIC_BASE_URL, required).
External hosting of artworks was removed 2026-07-22
(docs/remove-external-hosting/) and the legacy relative /api/vault/... form
went with the FastAPI serving mount the same day (docs/remove-api-vault/);
this guard exists so a future endpoint cannot quietly reintroduce either.

Guard failures are server bugs, not client errors: the only callers are the
upload/replace paths, which derive the URL from vault.get_artwork_url —
hence a plain ValueError rather than an AppError.
"""

from ..settings import vault_public_base_url


def is_vault_art_url(url: str) -> bool:
    """True if ``url`` points at this deployment's own vault."""
    if not url:
        return False
    return url.startswith(vault_public_base_url().rstrip("/") + "/")


def assert_vault_art_url(url: str) -> str:
    """Return ``url`` unchanged, raising ValueError if it is not vault-hosted."""
    if not is_vault_art_url(url):
        raise ValueError(
            f"art_url must be vault-derived (self-hosted artworks only); got {url!r}"
        )
    return url

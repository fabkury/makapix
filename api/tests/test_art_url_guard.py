"""Tests for the vault-only art_url invariant (docs/remove-external-hosting/).

External hosting of artworks was removed 2026-07-22; posts.art_url must
always be vault-derived. These tests pin the guard's accept/reject behavior
and census every art_url writer under app/ so a future endpoint cannot
quietly reintroduce a foreign-URL write path.
"""

import re
from pathlib import Path

import pytest

from app.utils.art_url import assert_vault_art_url, is_vault_art_url


def test_accepts_vault_subdomain_url(monkeypatch):
    from app import settings

    monkeypatch.setattr(
        settings, "vault_public_base_url", lambda: "https://vault.makapix.club"
    )
    # The guard reads the setting through its own import; patch there too.
    from app.utils import art_url as guard

    monkeypatch.setattr(
        guard, "vault_public_base_url", lambda: "https://vault.makapix.club"
    )
    assert is_vault_art_url("https://vault.makapix.club/0a/1b/deadbeef.png")
    # A foreign host that merely embeds the base string does not pass.
    assert not is_vault_art_url("https://vault.makapix.club.evil.example/x.png")


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/art.png",
        "https://someone.github.io/gallery/art.png",
        "http://vault.makapix.club/0a/1b/x.png",  # wrong scheme vs configured base
        "//evil.example/art.png",
        "vault/relative-ish.png",
        # legacy relative form — mount removed 2026-07-22 (docs/remove-api-vault/)
        "/api/vault/0a/1b/deadbeef.png",
        "",
    ],
)
def test_rejects_non_vault_urls(url, monkeypatch):
    from app.utils import art_url as guard

    monkeypatch.setattr(
        guard, "vault_public_base_url", lambda: "https://vault.makapix.club"
    )
    assert not is_vault_art_url(url)
    with pytest.raises(ValueError):
        assert_vault_art_url(url)


def test_writer_census():
    """Every `<something>.art_url = ...` assignment under app/ must be guarded.

    Allowed writers: the upload and replace paths in routers/posts.py (both
    wrap the value in assert_vault_art_url) and the placeholder empty-string
    initializer on the freshly created Post row. api/scripts/reshard_vault.py
    also rewrites art_url (vault URLs only, dormant migration script) but
    lives outside app/ and is deliberately out of census scope.
    """
    app_dir = Path(__file__).resolve().parents[1] / "app"
    writer_re = re.compile(r"\bart_url\s*=(?!=)")
    hits = []
    for py in app_dir.rglob("*.py"):
        for lineno, line in enumerate(py.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if writer_re.search(line):
                hits.append((py.relative_to(app_dir).as_posix(), lineno, stripped))

    def is_allowed(path, line):
        # The SQLAlchemy column definition and no-artwork rows (playlists).
        if "Column(" in line or "art_url=None" in line:
            return True
        if path == "routers/posts.py":
            return (
                "assert_vault_art_url" in line
                # upload placeholder before the vault write assigns the real URL
                or 'art_url=""' in line
                # local vars later routed through assert_vault_art_url
                or "art_url = get_artwork_url(" in line
                or "post.art_url = new_art_url" in line
            )
        # Response/schema/keyword usages (art_url=<read>) elsewhere are reads
        # of post.art_url being copied into payloads, not DB writes.
        return (
            "post.art_url" in line
            or "p.art_url" in line
            or "r.art_url" in line
            or "artwork.art_url" in line
            or "art_url=art_url" in line
        )

    offenders = [h for h in hits if not is_allowed(h[0], h[2])]
    assert not offenders, f"unguarded art_url writers found: {offenders}"

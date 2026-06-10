"""Tests for the avatar sub-vault's dual-location behavior
(docs/vault-resharding/)."""

from uuid import UUID

import pytest

from app.avatar_vault import (
    get_avatar_url,
    save_avatar_image,
    try_delete_avatar_by_public_url,
)
from app.vault import compute_storage_shard_v1, compute_storage_shard_v2

AVATAR_ID = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
V1 = "a4/47/ee"  # compute_storage_shard_v1(AVATAR_ID)
V2 = "24/07"  # compute_storage_shard_v2(AVATAR_ID)


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    monkeypatch.setenv("VAULT_PUBLIC_BASE_URL", "")
    return tmp_path


def test_shard_constants_match_derivation():
    assert compute_storage_shard_v1(AVATAR_ID) == V1
    assert compute_storage_shard_v2(AVATAR_ID) == V2


def test_new_avatar_is_v2_single_copy(vault):
    """New avatars (fresh UUID, no legacy presence) land at the v2 canonical
    path only — no v1 twin is created (D10)."""
    save_avatar_image(AVATAR_ID, b"png bytes", "image/png")
    assert (vault / "avatar" / V2 / f"{AVATAR_ID}.png").read_bytes() == b"png bytes"
    assert not (vault / "avatar" / V1).exists()


def test_avatar_with_legacy_presence_mirrors_to_v1(vault):
    """An avatar that already has files at the legacy path (pre-cutover
    upload) keeps its v1 copy in sync on re-save."""
    legacy = vault / "avatar" / V1 / f"{AVATAR_ID}.png"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"old")
    save_avatar_image(AVATAR_ID, b"new bytes", "image/png")
    assert (vault / "avatar" / V2 / f"{AVATAR_ID}.png").read_bytes() == b"new bytes"
    assert legacy.read_bytes() == b"new bytes"


def test_save_rejects_bad_mime(vault):
    with pytest.raises(ValueError):
        save_avatar_image(AVATAR_ID, b"x", "image/tiff")


def test_delete_by_v1_url_removes_both_copies(vault):
    save_avatar_image(AVATAR_ID, b"x", "image/png")
    assert try_delete_avatar_by_public_url(f"/api/vault/avatar/{V1}/{AVATAR_ID}.png")
    assert not (vault / "avatar" / V1 / f"{AVATAR_ID}.png").exists()
    assert not (vault / "avatar" / V2 / f"{AVATAR_ID}.png").exists()


def test_delete_by_v2_url_removes_both_copies(vault):
    save_avatar_image(AVATAR_ID, b"x", "image/png")
    url = f"https://vault.makapix.club/avatar/{V2}/{AVATAR_ID}.png"
    assert try_delete_avatar_by_public_url(url)
    assert not (vault / "avatar" / V1 / f"{AVATAR_ID}.png").exists()
    assert not (vault / "avatar" / V2 / f"{AVATAR_ID}.png").exists()


def test_delete_ignores_non_vault_urls(vault):
    assert not try_delete_avatar_by_public_url(
        "https://avatars.githubusercontent.com/u/12345?v=4"
    )
    assert not try_delete_avatar_by_public_url(None)
    assert not try_delete_avatar_by_public_url("")


def test_url_builder_matches_canonical_save_location(vault):
    save_avatar_image(AVATAR_ID, b"x", "image/png")
    url = get_avatar_url(AVATAR_ID, ".png")
    # The URL must point at a file that exists (the canonical copy).
    rel = url.removeprefix("/api/vault/")
    assert (vault / rel).exists()

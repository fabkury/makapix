"""Test vault storage utilities, including the resharding dual-location
primitives (docs/vault-resharding/)."""

import hashlib
from uuid import UUID

import pytest

from app.vault import (
    TMP_SUFFIX,
    compute_storage_shard,
    compute_storage_shard_v1,
    compute_storage_shard_v2,
    delete_all_artwork_formats,
    delete_artwork_from_vault,
    derive_twin_shard,
    get_artwork_file_path,
    get_artwork_url,
    get_upscaled_file_path,
    hash_artwork_id,
    save_artwork_to_vault,
    save_upscaled_artwork,
    write_file_atomic,
)

# Worked example from docs/vault-resharding/PLAN.md §2:
# sha256("a1b2c3d4-e5f6-7890-abcd-ef1234567890") starts a447ee...
WORKED_KEY = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    """Point VAULT_LOCATION at a temp dir."""
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


class TestShardDerivation:
    def test_v1_worked_example(self):
        assert compute_storage_shard_v1(WORKED_KEY) == "a4/47/ee"

    def test_v2_worked_example(self):
        # digest bytes 0xa4, 0x47 -> masked 0x24, 0x07
        assert compute_storage_shard_v2(WORKED_KEY) == "24/07"

    def test_v1_matches_hash_artwork_id(self):
        key = UUID("12345678-1234-5678-1234-567812345678")
        h = hash_artwork_id(key)
        assert compute_storage_shard_v1(key) == f"{h[0:2]}/{h[2:4]}/{h[4:6]}"

    def test_v2_matches_digest_masking(self):
        key = UUID("12345678-1234-5678-1234-567812345678")
        d = hashlib.sha256(str(key).encode()).digest()
        assert compute_storage_shard_v2(key) == f"{d[0] & 0x3F:02x}/{d[1] & 0x3F:02x}"

    def test_v2_components_in_range(self):
        """All v2 components must be in 00..3f."""
        for i in range(50):
            key = UUID(int=i)
            shard = compute_storage_shard_v2(key)
            a, b = shard.split("/")
            assert 0 <= int(a, 16) <= 0x3F
            assert 0 <= int(b, 16) <= 0x3F

    def test_canonical_is_v1_until_cutover(self):
        """PR-A: compute_storage_shard is still v1; PR-B flips it to v2."""
        assert compute_storage_shard(WORKED_KEY) == compute_storage_shard_v1(WORKED_KEY)

    def test_deterministic(self):
        key = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        assert compute_storage_shard_v1(key) == compute_storage_shard_v1(key)
        assert compute_storage_shard_v2(key) == compute_storage_shard_v2(key)


class TestDeriveTwinShard:
    def test_from_v1_gives_v2(self):
        assert derive_twin_shard(WORKED_KEY, "a4/47/ee") == "24/07"

    def test_from_v2_gives_v1(self):
        assert derive_twin_shard(WORKED_KEY, "24/07") == "a4/47/ee"

    def test_unrecognized_shard_raises(self):
        with pytest.raises(ValueError):
            derive_twin_shard(WORKED_KEY, "a447ee")  # slash-less 6 chars
        with pytest.raises(ValueError):
            derive_twin_shard(WORKED_KEY, "")


class TestRequiredShard:
    """Paths must never be silently derived from the key (I2): the stored
    shard is the source of truth and a derived path can point at the wrong
    scheme for the row."""

    def test_file_path_requires_shard(self, vault):
        with pytest.raises(ValueError):
            get_artwork_file_path(WORKED_KEY, ".png", None)
        with pytest.raises(ValueError):
            get_artwork_file_path(WORKED_KEY, ".png", "")

    def test_url_requires_shard(self, vault):
        with pytest.raises(ValueError):
            get_artwork_url(WORKED_KEY, ".png", None)

    def test_upscaled_path_requires_shard(self, vault):
        with pytest.raises(ValueError):
            get_upscaled_file_path(WORKED_KEY, None)


class TestPathAndUrlBuilders:
    def test_v1_shard_path(self, vault):
        p = get_artwork_file_path(WORKED_KEY, ".png", "a4/47/ee")
        assert p == vault / "a4/47/ee" / f"{WORKED_KEY}.png"

    def test_v2_shard_path(self, vault):
        p = get_artwork_file_path(WORKED_KEY, "png", "24/07")
        assert p == vault / "24/07" / f"{WORKED_KEY}.png"

    def test_url_uses_shard_opaquely(self, vault, monkeypatch):
        monkeypatch.setenv("VAULT_PUBLIC_BASE_URL", "")
        assert (
            get_artwork_url(WORKED_KEY, ".gif", "24/07")
            == f"/api/vault/24/07/{WORKED_KEY}.gif"
        )
        assert (
            get_artwork_url(WORKED_KEY, ".gif", "a4/47/ee")
            == f"/api/vault/a4/47/ee/{WORKED_KEY}.gif"
        )


class TestAtomicWrite:
    def test_writes_content_and_leaves_no_tmp(self, vault):
        target = vault / "x" / "file.bin"
        write_file_atomic(target, b"hello")
        assert target.read_bytes() == b"hello"
        assert not list(vault.rglob(f"*{TMP_SUFFIX}"))

    def test_overwrites_existing(self, vault):
        target = vault / "file.bin"
        write_file_atomic(target, b"one")
        write_file_atomic(target, b"two")
        assert target.read_bytes() == b"two"


class TestDualWrite:
    def test_save_writes_canonical_and_twin(self, vault):
        content = b"fake png bytes"
        canonical = save_artwork_to_vault(WORKED_KEY, content, "png", "a4/47/ee")
        assert canonical == vault / "a4/47/ee" / f"{WORKED_KEY}.png"
        assert canonical.read_bytes() == content
        twin = vault / "24/07" / f"{WORKED_KEY}.png"
        assert twin.read_bytes() == content

    def test_save_with_v2_canonical_mirrors_to_v1(self, vault):
        """Post-cutover: canonical v2, twin at the derived v1 path."""
        content = b"bytes"
        canonical = save_artwork_to_vault(WORKED_KEY, content, "gif", "24/07")
        assert canonical == vault / "24/07" / f"{WORKED_KEY}.gif"
        assert (vault / "a4/47/ee" / f"{WORKED_KEY}.gif").read_bytes() == content

    def test_save_requires_shard(self, vault):
        with pytest.raises(ValueError):
            save_artwork_to_vault(WORKED_KEY, b"x", "png", None)

    def test_save_rejects_unknown_format(self, vault):
        with pytest.raises(ValueError):
            save_artwork_to_vault(WORKED_KEY, b"x", "tiff", "a4/47/ee")

    def test_save_upscaled_writes_both(self, vault):
        content = b"upscaled webp"
        canonical = save_upscaled_artwork(WORKED_KEY, content, "a4/47/ee")
        assert canonical == vault / "a4/47/ee" / f"{WORKED_KEY}_upscaled.webp"
        twin = vault / "24/07" / f"{WORKED_KEY}_upscaled.webp"
        assert twin.read_bytes() == content


class TestDualDelete:
    def test_delete_removes_both_copies(self, vault):
        save_artwork_to_vault(WORKED_KEY, b"x", "png", "a4/47/ee")
        assert delete_artwork_from_vault(WORKED_KEY, ".png", "a4/47/ee") is True
        assert not (vault / "a4/47/ee" / f"{WORKED_KEY}.png").exists()
        assert not (vault / "24/07" / f"{WORKED_KEY}.png").exists()

    def test_delete_removes_twin_even_if_canonical_missing(self, vault):
        """A delete during the dual window must not leave the other copy
        fetchable."""
        twin = vault / "24/07" / f"{WORKED_KEY}.png"
        twin.parent.mkdir(parents=True)
        twin.write_bytes(b"x")
        assert delete_artwork_from_vault(WORKED_KEY, ".png", "a4/47/ee") is True
        assert not twin.exists()

    def test_delete_missing_returns_false(self, vault):
        assert delete_artwork_from_vault(WORKED_KEY, ".png", "a4/47/ee") is False

    def test_delete_all_formats_clears_both_trees(self, vault):
        save_artwork_to_vault(WORKED_KEY, b"p", "png", "a4/47/ee")
        save_artwork_to_vault(WORKED_KEY, b"g", "gif", "a4/47/ee")
        save_upscaled_artwork(WORKED_KEY, b"u", "a4/47/ee")

        results = delete_all_artwork_formats(WORKED_KEY, ["png", "gif"], "a4/47/ee")
        assert results == {"png": True, "gif": True, "upscaled": True}
        leftovers = [p for p in vault.rglob("*") if p.is_file()]
        assert leftovers == []

"""Tests for the legacy 3-level URL serving fallback (D16).

Covers the pure path transform (cross-checked against the canonical shard
functions) and the miss-only StaticFiles fallback behavior.
"""

from uuid import UUID, uuid4

from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from app.vault import compute_storage_shard_v1, compute_storage_shard_v2
from app.vault_serving import (
    LegacyShardFallbackStaticFiles,
    legacy_vault_path_to_v2,
)

# Worked example from docs/vault-resharding/PLAN.md §2:
# sha256("a1b2c3d4-e5f6-7890-abcd-ef1234567890") starts a447ee...
WORKED_KEY = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


class TestLegacyPathTransform:
    def test_worked_example(self):
        assert (
            legacy_vault_path_to_v2(f"a4/47/ee/{WORKED_KEY}.png")
            == f"24/07/{WORKED_KEY}.png"
        )

    def test_matches_canonical_shard_functions(self):
        for _ in range(200):
            key = uuid4()
            v1 = compute_storage_shard_v1(key)
            v2 = compute_storage_shard_v2(key)
            assert legacy_vault_path_to_v2(f"{v1}/{key}.gif") == f"{v2}/{key}.gif"

    def test_avatar_prefix(self):
        key = uuid4()
        v1 = compute_storage_shard_v1(key)
        v2 = compute_storage_shard_v2(key)
        assert (
            legacy_vault_path_to_v2(f"avatar/{v1}/{key}.webp")
            == f"avatar/{v2}/{key}.webp"
        )

    def test_non_legacy_shapes_return_none(self):
        assert legacy_vault_path_to_v2("24/07/file.png") is None  # already v2
        assert legacy_vault_path_to_v2("robots.txt") is None
        assert legacy_vault_path_to_v2("a4/47/ee/sub/file.png") is None
        assert legacy_vault_path_to_v2("A4/47/EE/file.png") is None  # uppercase
        assert legacy_vault_path_to_v2("a4/47/ze/file.png") is None  # non-hex
        assert legacy_vault_path_to_v2("a4/47/ee/") is None  # no filename
        assert legacy_vault_path_to_v2("blog_image/a4/47/ee/f.png") is None


class TestLegacyShardFallbackServing:
    def _client(self, tmp_path):
        # Mounted like production (api/app/main.py) so HTTPException -> 404.
        static = LegacyShardFallbackStaticFiles(directory=str(tmp_path))
        return TestClient(Starlette(routes=[Mount("/", app=static)]))

    def test_legacy_url_served_from_v2_location(self, tmp_path):
        v2_dir = tmp_path / "24" / "07"
        v2_dir.mkdir(parents=True)
        (v2_dir / f"{WORKED_KEY}.png").write_bytes(b"v2-bytes")

        resp = self._client(tmp_path).get(f"/a4/47/ee/{WORKED_KEY}.png")
        assert resp.status_code == 200
        assert resp.content == b"v2-bytes"

    def test_existing_legacy_twin_served_as_is(self, tmp_path):
        # Dual window: a file at the requested legacy path wins; no remap.
        legacy_dir = tmp_path / "a4" / "47" / "ee"
        legacy_dir.mkdir(parents=True)
        (legacy_dir / f"{WORKED_KEY}.png").write_bytes(b"legacy-bytes")
        v2_dir = tmp_path / "24" / "07"
        v2_dir.mkdir(parents=True)
        (v2_dir / f"{WORKED_KEY}.png").write_bytes(b"v2-bytes")

        resp = self._client(tmp_path).get(f"/a4/47/ee/{WORKED_KEY}.png")
        assert resp.status_code == 200
        assert resp.content == b"legacy-bytes"

    def test_avatar_legacy_url_served_from_v2_location(self, tmp_path):
        v2_dir = tmp_path / "avatar" / "24" / "07"
        v2_dir.mkdir(parents=True)
        (v2_dir / f"{WORKED_KEY}.webp").write_bytes(b"avatar-bytes")

        resp = self._client(tmp_path).get(f"/avatar/a4/47/ee/{WORKED_KEY}.webp")
        assert resp.status_code == 200
        assert resp.content == b"avatar-bytes"

    def test_missing_everywhere_is_404(self, tmp_path):
        resp = self._client(tmp_path).get(f"/a4/47/ee/{WORKED_KEY}.png")
        assert resp.status_code == 404

    def test_v2_url_unaffected(self, tmp_path):
        v2_dir = tmp_path / "24" / "07"
        v2_dir.mkdir(parents=True)
        (v2_dir / f"{WORKED_KEY}.png").write_bytes(b"v2-bytes")

        resp = self._client(tmp_path).get(f"/24/07/{WORKED_KEY}.png")
        assert resp.status_code == 200
        assert resp.content == b"v2-bytes"

"""Tests for the reshard_vault migration tool (docs/vault-resharding/PLAN.md §6).

Covers the destructive-risk-bearing logic: copy idempotency, stale-twin
re-copy, corruption detection in verify, the URL parser used to build the
copy candidate set, and the subtree allowlist that protects live non-asset
data (bdr/, lost+found)."""

import sys

import pytest

sys.path.insert(0, "/workspace/api/scripts")

import reshard_vault as rv  # noqa: E402

KEY = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
V1 = "a4/47/ee"
V2 = "24/07"


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


def _ref(ext=".png", cls="artwork", upscaled=False, optional=False):
    return rv.Ref(cls, KEY, ext, upscaled=upscaled, optional=optional)


def _plant_v1(vault, ref, content=b"image bytes"):
    p = vault / ("" if ref.asset_class == "artwork" else ref.asset_class)
    p = p / V1 / rv.ref_file_name(ref)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


class TestParseVaultUrl:
    def test_v1_absolute(self):
        parsed = rv.parse_vault_url(f"https://vault.makapix.club/{V1}/{KEY}.png")
        assert parsed["cls"] == "artwork"
        assert parsed["level"] == 3
        assert parsed["uuid"] == KEY
        assert parsed["components"] == ("a4", "47", "ee")

    def test_v2_relative_api_prefix(self):
        parsed = rv.parse_vault_url(f"/api/vault/{V2}/{KEY}.gif")
        assert parsed["level"] == 2
        assert parsed["ext"] == ".gif"

    def test_avatar_class(self):
        parsed = rv.parse_vault_url(
            f"https://vault-dev.makapix.club/avatar/{V1}/{KEY}.jpg"
        )
        assert parsed["cls"] == "avatar"

    def test_external_urls_rejected(self):
        assert (
            rv.parse_vault_url("https://avatars.githubusercontent.com/u/1?v=4") is None
        )
        assert rv.parse_vault_url("") is None
        assert rv.parse_vault_url("/some/random/path.png") is None


class TestRefPaths:
    def test_artwork_paths(self, vault):
        v1, v2 = rv.ref_paths(_ref())
        assert v1 == vault / V1 / f"{KEY}.png"
        assert v2 == vault / V2 / f"{KEY}.png"

    def test_subvault_paths(self, vault):
        v1, v2 = rv.ref_paths(_ref(cls="avatar", ext=".jpg"))
        assert v1 == vault / "avatar" / V1 / f"{KEY}.jpg"
        assert v2 == vault / "avatar" / V2 / f"{KEY}.jpg"

    def test_upscaled_name(self, vault):
        v1, _ = rv.ref_paths(_ref(ext=".webp", upscaled=True))
        assert v1.name == f"{KEY}_upscaled.webp"


class TestCopyRefs:
    def test_copy_creates_identical_twin(self, vault):
        ref = _ref()
        _plant_v1(vault, ref, b"content")
        summary = rv.copy_refs([ref])
        assert summary.get("copied") == 1
        _, v2 = rv.ref_paths(ref)
        assert v2.read_bytes() == b"content"

    def test_copy_is_idempotent(self, vault):
        ref = _ref()
        _plant_v1(vault, ref)
        rv.copy_refs([ref])
        summary = rv.copy_refs([ref])
        assert summary.get("already_twinned") == 1
        assert "copied" not in summary

    def test_stale_twin_recopied(self, vault):
        ref = _ref()
        _plant_v1(vault, ref, b"fresh content")
        _, v2 = rv.ref_paths(ref)
        v2.parent.mkdir(parents=True, exist_ok=True)
        v2.write_bytes(b"stale content")
        summary = rv.copy_refs([ref])
        assert summary.get("copied") == 1
        assert v2.read_bytes() == b"fresh content"

    def test_missing_source_reported(self, vault):
        summary = rv.copy_refs([_ref()])
        assert summary.get("missing_source") == 1
        assert summary["missing_source_total"] == 1

    def test_optional_missing_not_an_error(self, vault):
        summary = rv.copy_refs([_ref(ext=".webp", upscaled=True, optional=True)])
        assert summary.get("optional_absent") == 1
        assert summary["missing_source_total"] == 0

    def test_dry_run_writes_nothing(self, vault):
        ref = _ref()
        _plant_v1(vault, ref)
        summary = rv.copy_refs([ref], dry_run=True)
        assert summary.get("would_copy") == 1
        _, v2 = rv.ref_paths(ref)
        assert not v2.exists()

    def test_never_touches_v1(self, vault):
        ref = _ref()
        v1 = _plant_v1(vault, ref, b"original")
        rv.copy_refs([ref])
        assert v1.read_bytes() == b"original"


class TestVerifyRefs:
    def test_verified_pair(self, vault):
        ref = _ref()
        _plant_v1(vault, ref)
        rv.copy_refs([ref])
        results = rv.verify_refs([ref])
        assert results["verified"] == 1
        assert results["failures"] == []

    def test_detects_single_corrupted_byte(self, vault):
        ref = _ref()
        _plant_v1(vault, ref, b"AAAA")
        rv.copy_refs([ref])
        _, v2 = rv.ref_paths(ref)
        v2.write_bytes(b"AAAB")  # same size, different content
        results = rv.verify_refs([ref])
        assert results["verified"] == 0
        assert results["failures"][0]["reason"] == "sha256 mismatch"

    def test_detects_missing_twin(self, vault):
        ref = _ref()
        _plant_v1(vault, ref)
        results = rv.verify_refs([ref])
        assert results["failures"][0]["reason"] == "v2 twin missing"

    def test_v2_only_is_not_a_failure(self, vault):
        """v2-born assets (created after the cutover) have no v1 source."""
        ref = _ref()
        _, v2 = rv.ref_paths(ref)
        v2.parent.mkdir(parents=True, exist_ok=True)
        v2.write_bytes(b"x")
        results = rv.verify_refs([ref])
        assert results["v2_only"] == 1
        assert results["failures"] == []

    def test_missing_both_is_a_failure_unless_optional(self, vault):
        assert rv.verify_refs([_ref()])["failures"]
        assert not rv.verify_refs([_ref(optional=True)])["failures"]


class TestWalkDiskAllowlist:
    def test_out_of_scope_paths_never_classified_as_files(self, vault):
        # Live non-asset data at the vault root (I6).
        (vault / "bdr").mkdir()
        (vault / "bdr" / "batch-123.zip").write_bytes(b"zip")
        (vault / "lost+found").mkdir()
        (vault / "random-file.txt").write_text("hi")
        # A legitimate v1 file.
        ref = _ref()
        _plant_v1(vault, ref)

        result = rv.walk_disk(["artwork"])
        out_of_scope = set(result["out_of_scope_paths"])
        assert str(vault / "bdr") in out_of_scope
        assert str(vault / "lost+found") in out_of_scope
        assert str(vault / "random-file.txt") in out_of_scope
        # The zip inside bdr/ must not appear anywhere — never descended into.
        all_seen = (
            [f.path for f in result["files"]]
            + result["unknown_files"]
            + result["tmp_files"]
        )
        assert not any("batch-123.zip" in str(p) for p in all_seen)

    def test_classifies_both_depths(self, vault):
        ref = _ref()
        _plant_v1(vault, ref)
        rv.copy_refs([ref])
        result = rv.walk_disk(["artwork"])
        levels = sorted(f.level for f in result["files"])
        assert levels == [2, 3]

    def test_avatar_subtree(self, vault):
        ref = _ref(cls="avatar", ext=".jpg")
        _plant_v1(vault, ref)
        result = rv.walk_disk(["avatar"])
        assert len(result["files"]) == 1
        assert result["files"][0].asset_class == "avatar"

    def test_tmp_files_reported(self, vault):
        ref = _ref()
        p = _plant_v1(vault, ref)
        (p.parent / f"junk.{rv.TMP_SUFFIX.lstrip('.')}").write_bytes(b"")
        stray = p.parent / f"{KEY}.png.1234{rv.TMP_SUFFIX}"
        stray.write_bytes(b"partial")
        result = rv.walk_disk(["artwork"])
        assert any(str(stray) == t for t in result["tmp_files"])


class TestShardDerivationGuard:
    def test_copy_refused_on_mismatch(self, vault, monkeypatch):
        """copy must refuse to run when any stored shard disagrees with the
        sha256 derivation (R11) — exercised via the mode entry point with a
        stubbed DB report."""

        def fake_collect(db, classes):
            return set(), {
                "posts_artwork": 1,
                "null_shard_rows": 0,
                "shard_derivation_mismatches": [
                    {"post_id": 1, "stored": "aa/bb/cc", "derived": "a4/47/ee"}
                ],
                "v1_url_refs": {},
                "anomalous_url_refs": [],
            }

        monkeypatch.setattr(rv, "collect_refs", fake_collect)

        class Args:
            classes = ["artwork"]
            key = None
            dry_run = False
            json = False
            limit = 0

        assert rv.mode_copy(None, Args()) == 1

"""Tests for the cleanup_retired_artwork beat task.

replace-artwork rotates the post's storage_key and records the old identity
in retired_artworks with delete_after = now + 7 days; this sweep deletes the
old key's files (all formats + upscaled, from both canonical and legacy-twin
trees, plus any .mkpx) once the grace period has passed.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models import RetiredArtwork
from app.tasks import cleanup_retired_artwork
from app.vault import (
    compute_storage_shard,
    derive_twin_shard,
    get_artwork_file_path,
    get_mkpx_file_path,
    get_upscaled_file_path,
    save_artwork_to_vault,
    save_mkpx_to_vault,
    save_upscaled_artwork,
)

# --- helpers -----------------------------------------------------------------


def make_png_bytes(color=(200, 30, 90, 255)) -> bytes:
    from PIL import Image

    img = Image.new("RGBA", (8, 8), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _retire(db, storage_key, storage_shard, *, formats, had_mkpx=False, days_ago=8):
    """Insert a retirement row whose grace period ended `days_ago - 7` ago."""
    row = RetiredArtwork(
        post_id=None,
        storage_key=storage_key,
        storage_shard=storage_shard,
        formats=formats,
        had_mkpx=had_mkpx,
        delete_after=datetime.now(timezone.utc) + timedelta(days=7 - days_ago),
    )
    db.add(row)
    db.commit()
    return row


def _run_sweep() -> dict:
    result = cleanup_retired_artwork.apply()
    return result.result


@pytest.fixture()
def vault_tmp(tmp_path, monkeypatch):
    """Point the vault at a throwaway directory for the test."""
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


# --- tests ---------------------------------------------------------------------


def test_sweep_respects_delete_after(db, vault_tmp):
    key = uuid.uuid4()
    shard = compute_storage_shard(key)
    save_artwork_to_vault(key, make_png_bytes(), "png", storage_shard=shard)
    _retire(db, key, shard, formats=["png"], days_ago=3)  # 4 days of grace left

    result = _run_sweep()
    assert result["status"] == "success"
    assert result["swept"] == 0

    assert get_artwork_file_path(key, ".png", storage_shard=shard).exists()
    assert db.query(RetiredArtwork).count() == 1


def test_sweep_deletes_files_and_row(db, vault_tmp):
    key = uuid.uuid4()
    shard = compute_storage_shard(key)
    png = make_png_bytes()
    save_artwork_to_vault(key, png, "png", storage_shard=shard)
    save_artwork_to_vault(key, png, "webp", storage_shard=shard)
    save_upscaled_artwork(key, png, storage_shard=shard)
    mkpx_bytes = b"MKPX" + b"\x00" * 64
    save_mkpx_to_vault(
        key, io.BytesIO(mkpx_bytes), len(mkpx_bytes), storage_shard=shard
    )

    # Plant a legacy-twin copy by hand (a v2-born key gets no twin on save):
    # the sweep must clear BOTH trees during the resharding dual window (D10).
    twin_shard = derive_twin_shard(key, shard)
    twin_path = get_artwork_file_path(key, ".png", storage_shard=twin_shard)
    twin_path.parent.mkdir(parents=True, exist_ok=True)
    twin_path.write_bytes(png)

    _retire(db, key, shard, formats=["png", "webp"], had_mkpx=True)

    result = _run_sweep()
    assert result["status"] == "success"
    assert result["swept"] == 1
    assert result["errors"] is None

    assert not get_artwork_file_path(key, ".png", storage_shard=shard).exists()
    assert not get_artwork_file_path(key, ".webp", storage_shard=shard).exists()
    assert not get_upscaled_file_path(key, storage_shard=shard).exists()
    assert not get_mkpx_file_path(key, shard).exists()
    assert not twin_path.exists()
    assert db.query(RetiredArtwork).count() == 0


def test_sweep_survives_missing_files(db, vault_tmp):
    key = uuid.uuid4()
    shard = compute_storage_shard(key)
    _retire(db, key, shard, formats=["png", "gif"], had_mkpx=True)  # nothing on disk

    result = _run_sweep()
    assert result["status"] == "success"
    assert result["swept"] == 1
    assert db.query(RetiredArtwork).count() == 0


def test_sweep_skips_mkpx_when_not_flagged(db, vault_tmp):
    key = uuid.uuid4()
    shard = compute_storage_shard(key)
    save_artwork_to_vault(key, make_png_bytes(), "png", storage_shard=shard)
    mkpx_bytes = b"MKPX" + b"\x00" * 64
    save_mkpx_to_vault(
        key, io.BytesIO(mkpx_bytes), len(mkpx_bytes), storage_shard=shard
    )

    _retire(db, key, shard, formats=["png"], had_mkpx=False)

    result = _run_sweep()
    assert result["swept"] == 1
    assert not get_artwork_file_path(key, ".png", storage_shard=shard).exists()
    # had_mkpx=False means the flag is honored — the file is not touched
    assert get_mkpx_file_path(key, shard).exists()


def test_sweep_works_with_null_post_id(db, vault_tmp):
    """A post hard-deleted during the grace period nulls post_id via FK;
    the sweep works purely off the stored key/shard/formats."""
    key = uuid.uuid4()
    shard = compute_storage_shard(key)
    save_artwork_to_vault(key, make_png_bytes(), "png", storage_shard=shard)
    row = _retire(db, key, shard, formats=["png"])
    assert row.post_id is None

    result = _run_sweep()
    assert result["swept"] == 1
    assert not get_artwork_file_path(key, ".png", storage_shard=shard).exists()
    assert db.query(RetiredArtwork).count() == 0

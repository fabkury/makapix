"""Tests for SSAFPP's self-healing "exists" path.

The file write and the PostFile row commit in process_ssafpp are not atomic:
a run that dies in between (worker restart, DB error at commit) leaves the
converted file on disk with no post_files row. The "skip if already exists"
branch must recreate the missing row on retry, or the gap is permanent —
re-running the task would otherwise skip row creation forever.
"""

from __future__ import annotations

import io
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models import Post, PostFile, User
from app.tasks import process_ssafpp
from app.vault import (
    compute_storage_shard,
    get_artwork_file_path,
    save_artwork_to_vault,
)

# --- helpers -----------------------------------------------------------------


def make_png_bytes(color=(200, 30, 90, 255)) -> bytes:
    from PIL import Image

    img = Image.new("RGBA", (8, 8), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_webp_bytes(color=(10, 120, 60, 255)) -> bytes:
    from PIL import Image

    img = Image.new("RGBA", (8, 8), color)
    buf = io.BytesIO()
    img.save(buf, format="WEBP", lossless=True)
    return buf.getvalue()


def _make_user(db: Session) -> User:
    uid = str(uuid.uuid4())[:8]
    u = User(handle=f"sh_{uid}", email=f"sh_{uid}@example.com", roles=["user"])
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_post(db: Session, owner: User) -> Post:
    """Static PNG-native artwork post with its native file in the vault."""
    key = uuid.uuid4()
    shard = compute_storage_shard(key)
    png = make_png_bytes()
    save_artwork_to_vault(key, png, "png", storage_shard=shard)

    post = Post(
        storage_key=key,
        storage_shard=shard,
        owner_id=owner.id,
        kind="artwork",
        title="self-heal test",
        width=8,
        height=8,
        frame_count=1,
        hash="0" * 64,
    )
    db.add(post)
    db.flush()
    db.add(PostFile(post_id=post.id, format="png", file_bytes=len(png), is_native=True))
    db.commit()
    db.refresh(post)
    return post


@pytest.fixture()
def vault_tmp(tmp_path, monkeypatch):
    """Point the vault at a throwaway directory for the test."""
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


# --- tests ---------------------------------------------------------------------


def test_exists_path_heals_missing_row(db, vault_tmp):
    owner = _make_user(db)
    post = _make_post(db, owner)

    # Simulate a prior run that wrote the webp file but died before
    # committing its PostFile row.
    webp = make_webp_bytes()
    save_artwork_to_vault(
        post.storage_key, webp, "webp", storage_shard=post.storage_shard
    )
    assert db.query(PostFile).filter_by(post_id=post.id, format="webp").first() is None

    result = process_ssafpp.apply(args=(post.id,)).result
    assert result["status"] == "success"
    assert result["conversions"]["webp"] == "exists (healed row)"

    db.expire_all()
    row = db.query(PostFile).filter_by(post_id=post.id, format="webp").one()
    assert row.is_native is False
    webp_path = get_artwork_file_path(
        post.storage_key, ".webp", storage_shard=post.storage_shard
    )
    assert row.file_bytes == webp_path.stat().st_size

    # The untouched formats went through the normal conversion path.
    for fmt in ("gif", "bmp"):
        assert result["conversions"][fmt] == "created"
        assert (
            db.query(PostFile).filter_by(post_id=post.id, format=fmt).first()
            is not None
        )


def test_exists_path_does_not_duplicate_row(db, vault_tmp):
    owner = _make_user(db)
    post = _make_post(db, owner)

    # Complete prior state: webp file AND its row both exist.
    webp = make_webp_bytes()
    save_artwork_to_vault(
        post.storage_key, webp, "webp", storage_shard=post.storage_shard
    )
    db.add(
        PostFile(post_id=post.id, format="webp", file_bytes=len(webp), is_native=False)
    )
    db.commit()

    result = process_ssafpp.apply(args=(post.id,)).result
    assert result["status"] == "success"
    assert result["conversions"]["webp"] == "exists"

    db.expire_all()
    rows = db.query(PostFile).filter_by(post_id=post.id, format="webp").all()
    assert len(rows) == 1

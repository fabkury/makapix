"""Tests for SSAFPP's post-deleted-mid-task cleanup.

If the post row is deleted (post or account deletion) while SSAFPP is running,
the pre-commit guard must remove the vault files the run wrote — no retirement
sweep ever covers that key, so they would be orphaned forever. The
replace-artwork rotation case must stay untouched: the retired key keeps
serving old URLs through the 7-day grace window and the retirement sweep owns
its cleanup.

The mid-task deletion/rotation is injected by wrapping vault.save_upscaled_artwork,
which SSAFPP calls after the format conversions but before the guard. The posts
are set up with all variant files AND post_files rows already present so the
run takes the no-write "exists" path — pending PostFile inserts would hold a
KEY SHARE lock on the post row and block the second session's DELETE.
"""

from __future__ import annotations

import io
import uuid

import pytest
from sqlalchemy.orm import Session

from app.models import Post, PostFile, User
from app.tasks import process_ssafpp
from app.vault import (
    FORMAT_TO_EXT,
    compute_storage_shard,
    get_artwork_file_path,
    get_upscaled_file_path,
    save_artwork_to_vault,
)

# --- helpers -----------------------------------------------------------------


def make_image_bytes(fmt: str, color=(200, 30, 90, 255)) -> bytes:
    from PIL import Image

    img = Image.new("RGBA", (8, 8), color)
    if fmt in ("gif", "bmp"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format=fmt.upper(), **({"lossless": True} if fmt == "webp" else {}))
    return buf.getvalue()


def _make_user(db: Session) -> User:
    uid = str(uuid.uuid4())[:8]
    u = User(handle=f"dr_{uid}", email=f"dr_{uid}@example.com", roles=["user"])
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_post_with_all_variants(db: Session, owner: User) -> Post:
    """Artwork post with every format variant on disk and in post_files."""
    key = uuid.uuid4()
    shard = compute_storage_shard(key)

    post = Post(
        storage_key=key,
        storage_shard=shard,
        owner_id=owner.id,
        kind="artwork",
        title="deletion race test",
        width=8,
        height=8,
        frame_count=1,
        hash="0" * 64,
    )
    db.add(post)
    db.flush()

    for fmt in ("png", "gif", "webp", "bmp"):
        data = make_image_bytes(fmt)
        save_artwork_to_vault(key, data, fmt, storage_shard=shard)
        db.add(
            PostFile(
                post_id=post.id,
                format=fmt,
                file_bytes=len(data),
                is_native=(fmt == "png"),
            )
        )
    db.commit()
    db.refresh(post)
    return post


@pytest.fixture()
def vault_tmp(tmp_path, monkeypatch):
    """Point the vault at a throwaway directory for the test."""
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


def _hook_upscale(monkeypatch, side_effect):
    """Run side_effect just before the upscaled file is written."""
    from app import vault as vault_module

    original = vault_module.save_upscaled_artwork

    def wrapper(*args, **kwargs):
        side_effect()
        return original(*args, **kwargs)

    monkeypatch.setattr(vault_module, "save_upscaled_artwork", wrapper)


def _all_variant_paths(post: Post) -> list:
    paths = [
        get_artwork_file_path(post.storage_key, ext, storage_shard=post.storage_shard)
        for ext in FORMAT_TO_EXT.values()
    ]
    paths.append(
        get_upscaled_file_path(post.storage_key, storage_shard=post.storage_shard)
    )
    return paths


# --- tests ---------------------------------------------------------------------


def test_post_deleted_mid_task_sweeps_vault_files(db, vault_tmp, monkeypatch):
    owner = _make_user(db)
    post = _make_post_with_all_variants(db, owner)
    storage_key, storage_shard = post.storage_key, post.storage_shard

    def delete_post():
        db.query(PostFile).filter(PostFile.post_id == post.id).delete()
        db.query(Post).filter(Post.id == post.id).delete()
        db.commit()

    _hook_upscale(monkeypatch, delete_post)

    result = process_ssafpp.apply(args=(post.id,)).result
    assert result["status"] == "skipped"
    assert result["message"] == "post deleted mid-task"

    # Every file at the key is gone, including the upscaled variant the run
    # itself just wrote.
    for ext in list(FORMAT_TO_EXT.values()):
        path = get_artwork_file_path(storage_key, ext, storage_shard=storage_shard)
        assert not path.exists(), f"orphaned {ext} survived"
    upscaled = get_upscaled_file_path(storage_key, storage_shard=storage_shard)
    assert not upscaled.exists(), "orphaned upscaled file survived"


def test_key_rotation_mid_task_keeps_old_files(db, vault_tmp, monkeypatch):
    """Replace-artwork rotation: old-key files must keep serving through the
    retirement grace window — the guard must NOT delete them."""
    owner = _make_user(db)
    post = _make_post_with_all_variants(db, owner)
    old_key, storage_shard = post.storage_key, post.storage_shard

    def rotate_key():
        new_key = uuid.uuid4()
        db.query(Post).filter(Post.id == post.id).update(
            {
                Post.storage_key: new_key,
                Post.storage_shard: compute_storage_shard(new_key),
            }
        )
        db.commit()

    _hook_upscale(monkeypatch, rotate_key)

    result = process_ssafpp.apply(args=(post.id,)).result
    assert result["status"] == "skipped"
    assert result["message"] == "storage_key rotated mid-task"

    for ext in list(FORMAT_TO_EXT.values()):
        path = get_artwork_file_path(old_key, ext, storage_shard=storage_shard)
        assert path.exists(), f"{ext} at retired key was wrongly deleted"

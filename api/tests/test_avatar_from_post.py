"""Tests for POST /user/{id}/avatar/from-post ("use as profile photo").

Covers: snapshot copy into the avatar vault, attribution recording/clearing
(users.avatar_source_post_id), BMP-to-PNG transcoding, animated passthrough,
visibility/auth/rate-limit errors, and old-avatar cleanup on replace.
"""

import io
import uuid
from datetime import datetime, timezone

import pytest

from app import models
from app.auth import create_access_token


def _png_bytes(color=(0, 128, 255, 255)):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (16, 16), color).save(buf, format="PNG")
    return buf.getvalue()


def _bmp_bytes():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (16, 16), (200, 10, 10)).save(buf, format="BMP")
    return buf.getvalue()


def _animated_bytes(fmt: str):
    from PIL import Image

    frames = [
        Image.new("RGBA", (16, 16), (255, 0, 0, 255)),
        Image.new("RGBA", (16, 16), (0, 255, 0, 255)),
    ]
    buf = io.BytesIO()
    frames[0].save(
        buf, format=fmt, save_all=True, append_images=frames[1:], duration=100, loop=0
    )
    return buf.getvalue()


@pytest.fixture()
def vault_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


def _make_user(db, roles=None):
    u = models.User(
        handle=f"afp_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@e.com",
        roles=roles or ["user"],
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def user(db):
    return _make_user(db)


@pytest.fixture()
def other_user(db):
    return _make_user(db)


def _auth(u):
    return {"Authorization": f"Bearer {create_access_token(u)}"}


def _make_post(db, owner, fmt_bytes, native, **flags):
    """Create an artwork post with real files in the (monkeypatched) vault."""
    from app.models import Post, PostFile
    from app.sqids_config import encode_id
    from app.vault import FORMAT_TO_EXT, compute_storage_shard, get_artwork_file_path

    storage_key = uuid.uuid4()
    shard = compute_storage_shard(storage_key)
    now = datetime.now(timezone.utc)
    post = Post(
        storage_key=storage_key,
        storage_shard=shard,
        owner_id=owner.id,
        kind="artwork",
        title="Avatar source",
        art_url="https://example.com/a.png",
        width=16,
        height=16,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=uuid.uuid4().hex + uuid.uuid4().hex,
        **flags,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    for fmt, data in fmt_bytes.items():
        db.add(
            PostFile(
                post_id=post.id,
                format=fmt,
                file_bytes=len(data),
                is_native=(fmt == native),
            )
        )
        path = get_artwork_file_path(storage_key, FORMAT_TO_EXT[fmt], shard)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    db.commit()
    db.refresh(post)
    return post


def _from_post(client, target_user, post_sqid, actor):
    return client.post(
        f"/user/{target_user.user_key}/avatar/from-post",
        json={"post_sqid": post_sqid},
        headers=_auth(actor),
    )


def _avatar_files(pattern="*"):
    from app.avatar_vault import get_avatar_vault_location

    return [p for p in get_avatar_vault_location().rglob(pattern) if p.is_file()]


def test_own_post_sets_avatar_and_attribution(client, db, user, vault_tmp):
    src = _png_bytes()
    post = _make_post(db, user, {"png": src}, "png", promoted=True)

    resp = _from_post(client, user, post.public_sqid, user)
    assert resp.status_code == 201, resp.text
    assert resp.json()["avatar_url"]
    assert "avatar_source_post_id" not in resp.json()

    db.refresh(user)
    assert user.avatar_url
    assert user.avatar_source_post_id == post.id
    files = _avatar_files("*.png")
    assert len(files) == 1
    assert files[0].read_bytes() == src


def test_other_users_post_allowed_with_attribution(
    client, db, user, other_user, vault_tmp
):
    src = _png_bytes()
    post = _make_post(db, other_user, {"png": src}, "png", promoted=True)

    resp = _from_post(client, user, post.public_sqid, user)
    assert resp.status_code == 201, resp.text
    db.refresh(user)
    assert user.avatar_source_post_id == post.id
    assert _avatar_files("*.png")[0].read_bytes() == src


@pytest.mark.parametrize("fmt,ext", [("GIF", "gif"), ("WEBP", "webp")])
def test_animated_artwork_copied_byte_identical(client, db, user, vault_tmp, fmt, ext):
    src = _animated_bytes(fmt)
    post = _make_post(db, user, {ext: src}, ext, promoted=True)

    resp = _from_post(client, user, post.public_sqid, user)
    assert resp.status_code == 201, resp.text
    files = _avatar_files(f"*.{ext}")
    assert len(files) == 1
    assert files[0].read_bytes() == src


def test_bmp_native_prefers_existing_png_variant(client, db, user, vault_tmp):
    png_variant = _png_bytes((1, 2, 3, 255))
    post = _make_post(
        db, user, {"bmp": _bmp_bytes(), "png": png_variant}, "bmp", promoted=True
    )

    resp = _from_post(client, user, post.public_sqid, user)
    assert resp.status_code == 201, resp.text
    files = _avatar_files("*.png")
    assert len(files) == 1
    assert files[0].read_bytes() == png_variant


def test_bmp_native_without_png_variant_is_transcoded(client, db, user, vault_tmp):
    from PIL import Image

    post = _make_post(db, user, {"bmp": _bmp_bytes()}, "bmp", promoted=True)

    resp = _from_post(client, user, post.public_sqid, user)
    assert resp.status_code == 201, resp.text
    files = _avatar_files("*.png")
    assert len(files) == 1
    img = Image.open(io.BytesIO(files[0].read_bytes()))
    assert img.format == "PNG"


def test_non_viewable_post_404(client, db, user, other_user, vault_tmp):
    post = _make_post(db, other_user, {"png": _png_bytes()}, "png")  # not visible

    resp = _from_post(client, user, post.public_sqid, user)
    assert resp.status_code == 404, resp.text


def test_soft_deleted_post_404(client, db, user, vault_tmp):
    post = _make_post(
        db, user, {"png": _png_bytes()}, "png", promoted=True, deleted_by_user=True
    )

    resp = _from_post(client, user, post.public_sqid, user)
    assert resp.status_code == 404, resp.text


def test_bad_sqid_404(client, db, user, vault_tmp):
    resp = _from_post(client, user, "nonexistent0", user)
    assert resp.status_code == 404, resp.text


def test_playlist_post_400(client, db, user, vault_tmp):
    from app.models import Post
    from app.sqids_config import encode_id
    from app.vault import compute_storage_shard

    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
    post = Post(
        storage_key=storage_key,
        storage_shard=compute_storage_shard(storage_key),
        owner_id=user.id,
        kind="playlist",
        title="A playlist",
        metadata_modified_at=now,
        promoted=True,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    db.commit()

    resp = _from_post(client, user, post.public_sqid, user)
    assert resp.status_code == 400, resp.text


def test_unauthenticated_401(client, db, user, vault_tmp):
    post = _make_post(db, user, {"png": _png_bytes()}, "png", promoted=True)
    resp = client.post(
        f"/user/{user.user_key}/avatar/from-post",
        json={"post_sqid": post.public_sqid},
    )
    assert resp.status_code == 401, resp.text


def test_regular_user_cannot_set_others_avatar(client, db, user, other_user, vault_tmp):
    post = _make_post(db, user, {"png": _png_bytes()}, "png", promoted=True)
    resp = _from_post(client, other_user, post.public_sqid, user)
    assert resp.status_code == 403, resp.text


def test_rate_limited_429(client, db, user, vault_tmp, monkeypatch):
    from app.services import rate_limit

    post = _make_post(db, user, {"png": _png_bytes()}, "png", promoted=True)
    monkeypatch.setattr(rate_limit, "check_rate_limit", lambda *a, **k: (False, 0))

    resp = _from_post(client, user, post.public_sqid, user)
    assert resp.status_code == 429, resp.text


def test_replace_deletes_old_avatar_file(client, db, user, vault_tmp):
    post1 = _make_post(
        db, user, {"png": _png_bytes((9, 9, 9, 255))}, "png", promoted=True
    )
    post2 = _make_post(db, user, {"gif": _animated_bytes("GIF")}, "gif", promoted=True)

    assert _from_post(client, user, post1.public_sqid, user).status_code == 201
    assert len(_avatar_files()) == 1
    assert _from_post(client, user, post2.public_sqid, user).status_code == 201
    files = _avatar_files()
    assert len(files) == 1, files
    assert files[0].suffix == ".gif"

    db.refresh(user)
    assert user.avatar_source_post_id == post2.id


def test_manual_upload_clears_attribution(client, db, user, vault_tmp):
    post = _make_post(db, user, {"png": _png_bytes()}, "png", promoted=True)
    assert _from_post(client, user, post.public_sqid, user).status_code == 201
    db.refresh(user)
    assert user.avatar_source_post_id == post.id

    resp = client.post(
        f"/user/{user.user_key}/avatar",
        files={"image": ("a.png", _png_bytes(), "image/png")},
        headers=_auth(user),
    )
    assert resp.status_code == 201, resp.text
    db.refresh(user)
    assert user.avatar_source_post_id is None


def test_delete_avatar_clears_attribution(client, db, user, vault_tmp):
    post = _make_post(db, user, {"png": _png_bytes()}, "png", promoted=True)
    assert _from_post(client, user, post.public_sqid, user).status_code == 201

    resp = client.delete(f"/user/{user.user_key}/avatar", headers=_auth(user))
    assert resp.status_code == 200, resp.text
    db.refresh(user)
    assert user.avatar_url is None
    assert user.avatar_source_post_id is None


def test_oversized_artwork_400(client, db, user, vault_tmp, monkeypatch):
    from app import avatar_vault

    post = _make_post(db, user, {"png": _png_bytes()}, "png", promoted=True)
    monkeypatch.setattr(avatar_vault, "MAX_AVATAR_SIZE_BYTES", 10)

    resp = _from_post(client, user, post.public_sqid, user)
    assert resp.status_code == 400, resp.text
    db.refresh(user)
    assert user.avatar_url is None

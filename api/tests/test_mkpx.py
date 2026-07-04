"""Tests for .mkpx layers-file attachments (docs/mkpx-upload/).

Covers: upload-time attach, attach/replace/detach lifecycle, auth-only
download, quota accounting, replace-artwork drop, permanent-delete cleanup,
config advertisement, and the public static-mount guard.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient as StarletteTestClient

from app.auth import create_access_token
from app.models import Post, PostFile, User
from app.sqids_config import encode_id, encode_user_id
from app.vault import (
    MKPX_MAGIC_COMPACT,
    MKPX_MAGIC_PLAIN,
    compute_storage_shard,
    get_mkpx_file_path,
)
from app.vault_serving import LegacyShardFallbackStaticFiles

# --- helpers -----------------------------------------------------------------


def make_mkpx_bytes(profile: str = "compact", payload: bytes = b"\x00" * 64) -> bytes:
    magic = MKPX_MAGIC_COMPACT if profile == "compact" else MKPX_MAGIC_PLAIN
    return magic + payload


def make_png_bytes(color=(200, 30, 90, 255)) -> bytes:
    from PIL import Image

    img = Image.new("RGBA", (8, 8), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_user(db: Session, roles=None) -> User:
    uid = str(uuid.uuid4())[:8]
    u = User(handle=f"mk_{uid}", email=f"mk_{uid}@example.com", roles=roles or ["user"])
    db.add(u)
    db.commit()
    db.refresh(u)
    u.public_sqid = encode_user_id(u.id)
    db.commit()
    db.refresh(u)
    return u


def _headers(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _make_post(db: Session, owner: User, *, kind="artwork", shard=None) -> Post:
    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
    post = Post(
        storage_key=storage_key,
        storage_shard=shard or compute_storage_shard(storage_key),
        owner_id=owner.id,
        kind=kind,
        title="mkpx test post",
        hashtags=[],
        art_url="/vault/x.png",
        width=8,
        height=8,
        frame_count=1,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=str(storage_key).replace("-", "") + "b" * 32,
        promoted=True,
        visible=True,
        public_visibility=True,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    db.add(PostFile(post_id=post.id, format="png", file_bytes=1024, is_native=True))
    db.commit()
    db.refresh(post)
    return post


@pytest.fixture()
def vault_tmp(tmp_path, monkeypatch):
    """Point the vault at a throwaway directory for the test."""
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


# --- config advertisement ----------------------------------------------------


def test_config_advertises_mkpx(client):
    r = client.get("/v1/config")
    assert r.status_code == 200
    mkpx = r.json()["upload"]["mkpx"]
    assert mkpx["enabled"] is True
    assert mkpx["max_file_bytes"] > 0


# --- upload with mkpx --------------------------------------------------------


def test_upload_with_mkpx(client, db, vault_tmp):
    user = _make_user(db)
    mkpx_bytes = make_mkpx_bytes("compact")
    r = client.post(
        "/v1/post/upload",
        files={
            "image": ("art.png", make_png_bytes(), "image/png"),
            "mkpx": ("art.mkpx", mkpx_bytes, "application/x-mkpx"),
        },
        data={"title": "with layers"},
        headers=_headers(user),
    )
    assert r.status_code == 201, r.text
    post = r.json()["post"]
    assert post["has_mkpx"] is True
    assert post["mkpx_file_bytes"] == len(mkpx_bytes)
    assert post["mkpx_attached_at"] is not None

    row = db.query(Post).filter(Post.id == post["id"]).first()
    path = get_mkpx_file_path(row.storage_key, row.storage_shard)
    assert path.read_bytes() == mkpx_bytes


def test_upload_plain_profile_accepted(client, db, vault_tmp):
    user = _make_user(db)
    r = client.post(
        "/v1/post/upload",
        files={
            "image": ("art.png", make_png_bytes((10, 20, 30, 255)), "image/png"),
            "mkpx": ("art.mkpx", make_mkpx_bytes("plain"), "application/x-mkpx"),
        },
        data={"title": "plain profile"},
        headers=_headers(user),
    )
    assert r.status_code == 201, r.text
    assert r.json()["post"]["has_mkpx"] is True


def test_upload_without_mkpx_unaffected(client, db, vault_tmp):
    user = _make_user(db)
    r = client.post(
        "/v1/post/upload",
        files={"image": ("art.png", make_png_bytes((1, 2, 3, 255)), "image/png")},
        data={"title": "no layers"},
        headers=_headers(user),
    )
    assert r.status_code == 201, r.text
    post = r.json()["post"]
    assert post["has_mkpx"] is False
    assert post["mkpx_file_bytes"] is None


def test_upload_bad_mkpx_magic_fails_atomically(client, db, vault_tmp):
    user = _make_user(db)
    before = db.query(Post).count()
    r = client.post(
        "/v1/post/upload",
        files={
            "image": ("art.png", make_png_bytes(), "image/png"),
            "mkpx": ("art.mkpx", b"NOTMKPX!" + b"\x00" * 32, "application/x-mkpx"),
        },
        data={"title": "bad magic"},
        headers=_headers(user),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "mkpx_invalid"
    assert db.query(Post).count() == before  # no post created


def test_upload_oversize_mkpx(client, db, vault_tmp, monkeypatch):
    import app.routers.posts as posts_mod

    monkeypatch.setattr(posts_mod, "MKPX_SIZE_LIMIT_BYTES", 32)
    user = _make_user(db)
    r = client.post(
        "/v1/post/upload",
        files={
            "image": ("art.png", make_png_bytes(), "image/png"),
            "mkpx": ("art.mkpx", make_mkpx_bytes(payload=b"\x00" * 64)),
        },
        data={"title": "too big"},
        headers=_headers(user),
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "mkpx_too_large"


def test_upload_quota_includes_mkpx(client, db, vault_tmp, monkeypatch):
    """Quota check receives artwork + mkpx combined size."""
    import app.routers.posts as posts_mod

    seen = {}

    def fake_check(db_, user_, size):
        seen["size"] = size
        return (False, 0, 100)

    monkeypatch.setattr(posts_mod, "check_storage_quota", fake_check)
    user = _make_user(db)
    png = make_png_bytes()
    mkpx_bytes = make_mkpx_bytes()
    r = client.post(
        "/v1/post/upload",
        files={
            "image": ("art.png", png, "image/png"),
            "mkpx": ("art.mkpx", mkpx_bytes),
        },
        data={"title": "quota"},
        headers=_headers(user),
    )
    assert r.status_code == 413
    assert seen["size"] == len(png) + len(mkpx_bytes)


# --- attach / replace / detach -----------------------------------------------


def test_attach_replace_detach_lifecycle(client, db, vault_tmp):
    owner = _make_user(db)
    post = _make_post(db, owner)
    path = get_mkpx_file_path(post.storage_key, post.storage_shard)

    # attach
    first = make_mkpx_bytes(payload=b"\x01" * 100)
    r = client.post(
        f"/v1/post/{post.id}/mkpx",
        files={"mkpx": ("f.mkpx", first)},
        headers=_headers(owner),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_mkpx"] is True
    assert body["mkpx_file_bytes"] == len(first)
    first_stamp = body["mkpx_attached_at"]
    assert path.read_bytes() == first

    # replace (silently overwrites; stamp changes)
    second = make_mkpx_bytes(payload=b"\x02" * 200)
    r = client.post(
        f"/v1/post/{post.id}/mkpx",
        files={"mkpx": ("f.mkpx", second)},
        headers=_headers(owner),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mkpx_file_bytes"] == len(second)
    assert body["mkpx_attached_at"] != first_stamp
    assert path.read_bytes() == second

    # detach
    r = client.delete(f"/v1/post/{post.id}/mkpx", headers=_headers(owner))
    assert r.status_code == 200
    body = r.json()
    assert body["has_mkpx"] is False
    assert body["mkpx_file_bytes"] is None
    assert not path.exists()

    # detach again -> 404
    r = client.delete(f"/v1/post/{post.id}/mkpx", headers=_headers(owner))
    assert r.status_code == 404


def test_attach_requires_auth_and_ownership(client, db, vault_tmp):
    owner = _make_user(db)
    other = _make_user(db)
    post = _make_post(db, owner)

    r = client.post(
        f"/v1/post/{post.id}/mkpx", files={"mkpx": ("f.mkpx", make_mkpx_bytes())}
    )
    assert r.status_code == 401

    r = client.post(
        f"/v1/post/{post.id}/mkpx",
        files={"mkpx": ("f.mkpx", make_mkpx_bytes())},
        headers=_headers(other),
    )
    assert r.status_code == 403


def test_attach_playlist_post_404(client, db, vault_tmp):
    owner = _make_user(db)
    post = _make_post(db, owner, kind="playlist")
    r = client.post(
        f"/v1/post/{post.id}/mkpx",
        files={"mkpx": ("f.mkpx", make_mkpx_bytes())},
        headers=_headers(owner),
    )
    assert r.status_code == 404


def test_attach_soft_deleted_404_even_for_author(client, db, vault_tmp):
    owner = _make_user(db)
    post = _make_post(db, owner)
    post.deleted_by_user = True
    post.deleted_by_user_date = datetime.now(timezone.utc)
    db.commit()
    r = client.post(
        f"/v1/post/{post.id}/mkpx",
        files={"mkpx": ("f.mkpx", make_mkpx_bytes())},
        headers=_headers(owner),
    )
    assert r.status_code == 404


def test_attach_with_legacy_v1_shard(client, db, vault_tmp):
    """Posts predating the resharding keep 3-level shards — used verbatim."""
    owner = _make_user(db)
    post = _make_post(db, owner, shard="a4/47/ee")
    mkpx_bytes = make_mkpx_bytes()
    r = client.post(
        f"/v1/post/{post.id}/mkpx",
        files={"mkpx": ("f.mkpx", mkpx_bytes)},
        headers=_headers(owner),
    )
    assert r.status_code == 200, r.text
    assert (vault_tmp / "mkpx" / "a4/47/ee" / f"{post.storage_key}.mkpx").exists()


# --- download ----------------------------------------------------------------


def _attach(client, db, owner, post, payload=b"\x07" * 50):
    mkpx_bytes = make_mkpx_bytes(payload=payload)
    r = client.post(
        f"/v1/post/{post.id}/mkpx",
        files={"mkpx": ("f.mkpx", mkpx_bytes)},
        headers=_headers(owner),
    )
    assert r.status_code == 200, r.text
    return mkpx_bytes


def test_download_requires_auth(client, db, vault_tmp):
    owner = _make_user(db)
    post = _make_post(db, owner)
    _attach(client, db, owner, post)

    r = client.get(f"/v1/d/{post.public_sqid}.mkpx")
    assert r.status_code == 401


def test_download_roundtrip_and_headers(client, db, vault_tmp):
    owner = _make_user(db)
    viewer = _make_user(db)
    post = _make_post(db, owner)
    mkpx_bytes = _attach(client, db, owner, post)

    r = client.get(f"/v1/d/{post.public_sqid}.mkpx", headers=_headers(viewer))
    assert r.status_code == 200
    assert r.content == mkpx_bytes
    assert r.headers["content-type"] == "application/x-mkpx"
    assert r.headers["cache-control"] == "no-store"
    assert (
        r.headers["content-disposition"]
        == f'attachment; filename="makapix-{post.public_sqid}.mkpx"'
    )


def test_download_no_mkpx_404(client, db, vault_tmp):
    owner = _make_user(db)
    viewer = _make_user(db)
    post = _make_post(db, owner)
    r = client.get(f"/v1/d/{post.public_sqid}.mkpx", headers=_headers(viewer))
    assert r.status_code == 404


def test_download_hidden_post_owner_only(client, db, vault_tmp):
    owner = _make_user(db)
    viewer = _make_user(db)
    post = _make_post(db, owner)
    _attach(client, db, owner, post)
    post.visible = False
    post.hidden_by_user = True
    post.promoted = False
    post.public_visibility = False
    db.commit()

    r = client.get(f"/v1/d/{post.public_sqid}.mkpx", headers=_headers(viewer))
    assert r.status_code == 404
    r = client.get(f"/v1/d/{post.public_sqid}.mkpx", headers=_headers(owner))
    assert r.status_code == 200


def test_download_soft_deleted_404_for_everyone(client, db, vault_tmp):
    owner = _make_user(db)
    post = _make_post(db, owner)
    _attach(client, db, owner, post)
    post.deleted_by_user = True
    post.deleted_by_user_date = datetime.now(timezone.utc)
    db.commit()

    r = client.get(f"/v1/d/{post.public_sqid}.mkpx", headers=_headers(owner))
    assert r.status_code == 404


def test_generic_format_route_still_rejects_mkpx_like_junk(client, db, vault_tmp):
    """The literal .mkpx route must not swallow other format downloads."""
    owner = _make_user(db)
    post = _make_post(db, owner)
    r = client.get(f"/v1/d/{post.public_sqid}.exe")
    assert r.status_code == 400  # generic route's invalid-extension error


# --- quota accounting ----------------------------------------------------------


def test_storage_used_counts_mkpx_once(db):
    from app.services.storage_quota import get_user_storage_used

    owner = _make_user(db)
    post = _make_post(db, owner)  # has one PostFile of 1024 bytes
    # A second format-variant row — the mkpx sum must NOT be multiplied by it
    db.add(PostFile(post_id=post.id, format="webp", file_bytes=512, is_native=False))
    post.mkpx_file_bytes = 10_000
    post.mkpx_attached_at = datetime.now(timezone.utc)
    db.commit()

    assert get_user_storage_used(db, owner.id) == 1024 + 512 + 10_000

    post.deleted_by_user = True
    db.commit()
    assert get_user_storage_used(db, owner.id) == 0


# --- lifecycle: replace-artwork / permanent delete ---------------------------


def test_replace_artwork_drops_mkpx(client, db, vault_tmp):
    """The attachment is discarded immediately (contract §10.1), but the
    physical file belongs to the retired artwork version and is unlinked by
    the 7-day retirement sweep, not by the endpoint."""
    from app.models import RetiredArtwork

    owner = _make_user(db)
    # Create via the real upload flow so replace-artwork has real vault files
    r = client.post(
        "/v1/post/upload",
        files={
            "image": ("art.png", make_png_bytes((5, 6, 7, 255)), "image/png"),
            "mkpx": ("art.mkpx", make_mkpx_bytes()),
        },
        data={"title": "to be replaced"},
        headers=_headers(owner),
    )
    assert r.status_code == 201, r.text
    post_id = r.json()["post"]["id"]
    row = db.query(Post).filter(Post.id == post_id).first()
    old_storage_key = row.storage_key
    path = get_mkpx_file_path(row.storage_key, row.storage_shard)
    assert path.exists()

    r = client.post(
        f"/v1/post/{post_id}/replace-artwork",
        files={"image": ("new.png", make_png_bytes((99, 88, 77, 255)), "image/png")},
        headers=_headers(owner),
    )
    assert r.status_code == 200, r.text

    db.expire_all()
    row = db.query(Post).filter(Post.id == post_id).first()
    assert row.mkpx_file_bytes is None
    assert row.mkpx_attached_at is None
    # Physical unlink is deferred to the retirement sweep
    assert path.exists()
    retired = (
        db.query(RetiredArtwork)
        .filter(RetiredArtwork.storage_key == old_storage_key)
        .one()
    )
    assert retired.had_mkpx is True


def test_permanent_delete_removes_mkpx_file(client, db, vault_tmp):
    owner = _make_user(db)
    moderator = _make_user(db, roles=["user", "moderator"])
    post = _make_post(db, owner)
    _attach(client, db, owner, post)
    path = get_mkpx_file_path(post.storage_key, post.storage_shard)
    assert path.exists()

    r = client.delete(f"/v1/post/{post.id}/permanent", headers=_headers(moderator))
    assert r.status_code == 204
    assert not path.exists()


# --- payload exposure ----------------------------------------------------------


def test_single_post_payload_has_mkpx_fields(client, db, vault_tmp):
    owner = _make_user(db)
    post = _make_post(db, owner)
    _attach(client, db, owner, post)

    r = client.get(f"/v1/p/{post.public_sqid}")
    assert r.status_code == 200
    body = r.json()
    assert body["has_mkpx"] is True
    assert body["mkpx_file_bytes"] is not None
    assert body["mkpx_attached_at"] is not None


def test_feed_payload_has_mkpx_field(client, db, vault_tmp):
    owner = _make_user(db)
    post = _make_post(db, owner)
    _attach(client, db, owner, post)

    r = client.get("/v1/post/recent")
    assert r.status_code == 200
    items = r.json()["items"]
    match = [p for p in items if p["id"] == post.id]
    assert match and match[0]["has_mkpx"] is True


# --- public static-mount guard -------------------------------------------------


class TestStaticMountGuard:
    def _app_and_files(self, tmp_path):
        # a real artwork file (must keep serving) and a private mkpx file
        (tmp_path / "24" / "07").mkdir(parents=True)
        (tmp_path / "24" / "07" / "art.png").write_bytes(b"png-bytes")
        (tmp_path / "mkpx" / "24" / "07").mkdir(parents=True)
        (tmp_path / "mkpx" / "24" / "07" / "secret.mkpx").write_bytes(b"secret")
        app = Starlette(
            routes=[
                Mount(
                    "/vault",
                    app=LegacyShardFallbackStaticFiles(directory=str(tmp_path)),
                )
            ]
        )
        return StarletteTestClient(app)

    def test_mkpx_prefix_refused_artwork_still_served(self, tmp_path):
        c = self._app_and_files(tmp_path)
        assert c.get("/vault/24/07/art.png").status_code == 200
        assert c.get("/vault/mkpx/24/07/secret.mkpx").status_code == 404

    def test_encoded_and_dot_segment_variants_refused(self, tmp_path):
        c = self._app_and_files(tmp_path)
        assert c.get("/vault/%6dkpx/24/07/secret.mkpx").status_code == 404
        assert c.get("/vault/./mkpx/24/07/secret.mkpx").status_code == 404
        assert c.get("/vault/24/../mkpx/24/07/secret.mkpx").status_code == 404

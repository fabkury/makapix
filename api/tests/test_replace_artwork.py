"""Tests for POST /post/{id}/replace-artwork storage-key rotation.

The vault serves with `Cache-Control: immutable`, so replace-artwork rotates
the post's storage_key (new UUID, new shard, new URL) instead of overwriting
bytes in place (message/0002). The old key's files stay on disk for a 7-day
grace period, tracked by a RetiredArtwork row and swept by
cleanup_retired_artwork (covered in test_cleanup_retired_artwork.py).

The mkpx deferred-unlink interaction is covered in
test_mkpx.py::test_replace_artwork_drops_mkpx.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import Post, RetiredArtwork, SocialNotification, User
from app.sqids_config import encode_user_id
from app.vault import compute_storage_shard, get_artwork_file_path

# --- helpers -----------------------------------------------------------------


def make_png_bytes(color=(200, 30, 90, 255)) -> bytes:
    from PIL import Image

    img = Image.new("RGBA", (8, 8), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_user(db: Session) -> User:
    uid = str(uuid.uuid4())[:8]
    u = User(handle=f"ra_{uid}", email=f"ra_{uid}@example.com", roles=["user"])
    db.add(u)
    db.commit()
    db.refresh(u)
    u.public_sqid = encode_user_id(u.id)
    db.commit()
    db.refresh(u)
    return u


def _headers(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _upload(client, user: User, color, title="original") -> dict:
    r = client.post(
        "/v1/post/upload",
        files={"image": ("art.png", make_png_bytes(color), "image/png")},
        data={"title": title},
        headers=_headers(user),
    )
    assert r.status_code == 201, r.text
    return r.json()["post"]


def _replace(client, user: User, post_id: int, color):
    return client.post(
        f"/v1/post/{post_id}/replace-artwork",
        files={"image": ("new.png", make_png_bytes(color), "image/png")},
        headers=_headers(user),
    )


@pytest.fixture()
def vault_tmp(tmp_path, monkeypatch):
    """Point the vault at a throwaway directory for the test."""
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


# --- rotation ----------------------------------------------------------------


def test_replace_rotates_key_shard_and_url(client, db, vault_tmp):
    owner = _make_user(db)
    uploaded = _upload(client, owner, (5, 6, 7, 255))
    post_id = uploaded["id"]

    row = db.query(Post).filter(Post.id == post_id).first()
    old_key = row.storage_key
    old_shard = row.storage_shard
    old_art_url = row.art_url
    old_path = get_artwork_file_path(old_key, ".png", storage_shard=old_shard)
    assert old_path.exists()

    r = _replace(client, owner, post_id, (99, 88, 77, 255))
    assert r.status_code == 200, r.text

    db.expire_all()
    row = db.query(Post).filter(Post.id == post_id).first()
    assert row.storage_key != old_key
    assert row.storage_shard == compute_storage_shard(row.storage_key)
    assert row.art_url != old_art_url
    assert str(row.storage_key) in row.art_url
    assert r.json()["post"]["art_url"] == row.art_url

    # New file exists at the new path; the old file survives (7-day grace)
    new_path = get_artwork_file_path(
        row.storage_key, ".png", storage_shard=row.storage_shard
    )
    assert new_path.exists()
    assert old_path.exists()


def test_replace_creates_retirement_row(client, db, vault_tmp):
    owner = _make_user(db)
    uploaded = _upload(client, owner, (10, 20, 30, 255))
    post_id = uploaded["id"]

    row = db.query(Post).filter(Post.id == post_id).first()
    old_key = row.storage_key
    old_shard = row.storage_shard

    before = datetime.now(timezone.utc)
    r = _replace(client, owner, post_id, (40, 50, 60, 255))
    assert r.status_code == 200, r.text
    after = datetime.now(timezone.utc)

    retired = (
        db.query(RetiredArtwork).filter(RetiredArtwork.storage_key == old_key).one()
    )
    assert retired.post_id == post_id
    assert retired.storage_shard == old_shard
    assert retired.formats == ["png"]
    assert retired.had_mkpx is False
    assert before + timedelta(days=7) <= retired.delete_after
    assert retired.delete_after <= after + timedelta(days=7)


def test_replace_updates_social_notification_art_url(client, db, vault_tmp):
    owner = _make_user(db)
    recipient = _make_user(db)
    uploaded = _upload(client, owner, (70, 80, 90, 255))
    post_id = uploaded["id"]

    row = db.query(Post).filter(Post.id == post_id).first()
    old_art_url = row.art_url
    notif = SocialNotification(
        user_id=recipient.id,
        notification_type="reaction",
        post_id=post_id,
        actor_id=owner.id,
        content_art_url=old_art_url,
    )
    db.add(notif)
    db.commit()
    notif_id = notif.id

    r = _replace(client, owner, post_id, (1, 2, 3, 255))
    assert r.status_code == 200, r.text

    db.expire_all()
    row = db.query(Post).filter(Post.id == post_id).first()
    notif = db.query(SocialNotification).filter(SocialNotification.id == notif_id).one()
    assert notif.content_art_url == row.art_url
    assert notif.content_art_url != old_art_url


def test_replace_enqueues_ssafpp(client, db, vault_tmp, monkeypatch):
    from app import tasks

    calls = []
    monkeypatch.setattr(tasks.process_ssafpp, "delay", lambda pid: calls.append(pid))

    owner = _make_user(db)
    uploaded = _upload(client, owner, (11, 22, 33, 255))
    post_id = uploaded["id"]
    calls.clear()  # the upload path enqueues too; only count the replace

    r = _replace(client, owner, post_id, (44, 55, 66, 255))
    assert r.status_code == 200, r.text
    assert calls == [post_id]


# --- failure paths leave the post untouched ----------------------------------


def test_replace_identical_hash_400(client, db, vault_tmp):
    owner = _make_user(db)
    color = (123, 45, 67, 255)
    uploaded = _upload(client, owner, color)
    post_id = uploaded["id"]

    row = db.query(Post).filter(Post.id == post_id).first()
    old_key = row.storage_key

    r = _replace(client, owner, post_id, color)  # identical bytes
    assert r.status_code == 400

    db.expire_all()
    row = db.query(Post).filter(Post.id == post_id).first()
    assert row.storage_key == old_key
    assert db.query(RetiredArtwork).count() == 0


def test_replace_duplicate_hash_409(client, db, vault_tmp):
    owner = _make_user(db)
    color_b = (222, 111, 0, 255)
    post_a = _upload(client, owner, (0, 111, 222, 255), title="post a")
    _upload(client, owner, color_b, title="post b")

    row = db.query(Post).filter(Post.id == post_a["id"]).first()
    old_key = row.storage_key

    r = _replace(client, owner, post_a["id"], color_b)  # post b's exact bytes
    assert r.status_code == 409

    db.expire_all()
    row = db.query(Post).filter(Post.id == post_a["id"]).first()
    assert row.storage_key == old_key
    assert db.query(RetiredArtwork).count() == 0


def test_replace_requires_owner_403(client, db, vault_tmp):
    owner = _make_user(db)
    intruder = _make_user(db)
    uploaded = _upload(client, owner, (9, 8, 7, 255))

    r = _replace(client, intruder, uploaded["id"], (6, 5, 4, 255))
    assert r.status_code == 403
    assert db.query(RetiredArtwork).count() == 0

"""Tests for docs/feed-bump/ — Phase 1: re-moderation of replaced artworks.

D7: a replace-artwork by an owner without Trust (auto_public_approval) sends
the post back to the approval queue (public_visibility=False), promoted posts
included. Trusted owners keep visibility. The moderator queue orders by
artwork_modified_at so a re-queued replacement surfaces at the top.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import Post, PostFile, User
from app.sqids_config import encode_id, encode_user_id
from app.vault import compute_storage_shard

BASE = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _png(color) -> bytes:
    from PIL import Image

    img = Image.new("RGBA", (8, 8), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_user(
    db: Session, *, roles: list[str] | None = None, trusted: bool = False
) -> User:
    uid = str(uuid.uuid4())[:8]
    user = User(
        handle=f"fb_{uid}",
        email=f"fb_{uid}@example.com",
        roles=roles or ["user"],
        auto_public_approval=trusted,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    return user


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _make_post(
    db: Session,
    *,
    owner: User,
    created_at: datetime,
    artwork_modified_at: datetime | None = None,
    public: bool = False,
) -> Post:
    storage_key = uuid.uuid4()
    title = f"art_{str(storage_key)[:8]}"
    post = Post(
        storage_key=storage_key,
        storage_shard=compute_storage_shard(storage_key),
        owner_id=owner.id,
        kind="artwork",
        title=title,
        description=title,
        hashtags=[],
        art_url=f"https://example.com/{title}.png",
        width=64,
        height=64,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        created_at=created_at,
        metadata_modified_at=created_at,
        artwork_modified_at=artwork_modified_at or created_at,
        hash=str(storage_key).replace("-", "") + "f" * 32,
        visible=True,
        public_visibility=public,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    db.add(PostFile(post_id=post.id, format="png", file_bytes=32000, is_native=True))
    db.commit()
    db.refresh(post)
    return post


@pytest.fixture()
def vault_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


def _upload(client, user: User, color) -> int:
    r = client.post(
        "/v1/post/upload",
        files={"image": ("art.png", _png(color), "image/png")},
        data={"title": "original"},
        headers=_auth(user),
    )
    assert r.status_code == 201, r.text
    return r.json()["post"]["id"]


def _replace(client, user: User, post_id: int, color):
    r = client.post(
        f"/v1/post/{post_id}/replace-artwork",
        files={"image": ("new.png", _png(color), "image/png")},
        headers=_auth(user),
    )
    assert r.status_code == 200, r.text
    return r.json()


def _queue_ids(client, mod: User, cursor: str | None = None, limit: int = 50):
    url = f"/admin/pending-approval?limit={limit}"
    if cursor:
        url += f"&cursor={cursor}"
    r = client.get(url, headers=_auth(mod))
    assert r.status_code == 200, r.text
    body = r.json()
    return [item["id"] for item in body["items"]], body["next_cursor"]


# ---------------------------------------------------------------------------
# D7 — replace by an untrusted owner re-queues the post
# ---------------------------------------------------------------------------


def test_untrusted_replace_requeues_approved_post(client, db, vault_tmp):
    owner = _make_user(db)
    mod = _make_user(db, roles=["user", "moderator"])
    post_id = _upload(client, owner, (10, 20, 30, 255))

    r = client.post(f"/v1/post/{post_id}/approve-public", headers=_auth(mod))
    assert r.status_code == 201, r.text
    db.expire_all()
    assert db.get(Post, post_id).public_visibility is True

    body = _replace(client, owner, post_id, (40, 50, 60, 255))
    assert body["post"]["public_visibility"] is False
    db.expire_all()
    assert db.get(Post, post_id).public_visibility is False

    # Back in the queue; re-approval releases it again.
    assert post_id in _queue_ids(client, mod)[0]
    r = client.post(f"/v1/post/{post_id}/approve-public", headers=_auth(mod))
    assert r.status_code == 201, r.text
    db.expire_all()
    assert db.get(Post, post_id).public_visibility is True


def test_untrusted_replace_requeues_promoted_post(client, db, vault_tmp):
    owner = _make_user(db)
    post_id = _upload(client, owner, (11, 21, 31, 255))
    post = db.get(Post, post_id)
    post.public_visibility = True
    post.promoted = True
    post.promoted_at = datetime.now(timezone.utc)
    db.commit()

    _replace(client, owner, post_id, (41, 51, 61, 255))
    db.expire_all()
    post = db.get(Post, post_id)
    assert post.public_visibility is False
    assert post.promoted is True  # promotion survives; only visibility resets

    feed = client.get("/feed/promoted?limit=50")
    assert feed.status_code == 200, feed.text
    assert post_id not in [item["id"] for item in feed.json()["items"]]


def test_untrusted_replace_of_pending_post_stays_pending(client, db, vault_tmp):
    owner = _make_user(db)
    post_id = _upload(client, owner, (12, 22, 32, 255))
    db.expire_all()
    assert db.get(Post, post_id).public_visibility is False

    body = _replace(client, owner, post_id, (42, 52, 62, 255))
    assert body["post"]["public_visibility"] is False


def test_trusted_replace_keeps_visibility(client, db, vault_tmp):
    owner = _make_user(db, trusted=True)
    post_id = _upload(client, owner, (13, 23, 33, 255))
    db.expire_all()
    assert db.get(Post, post_id).public_visibility is True

    body = _replace(client, owner, post_id, (43, 53, 63, 255))
    assert body["post"]["public_visibility"] is True
    db.expire_all()
    assert db.get(Post, post_id).public_visibility is True


# ---------------------------------------------------------------------------
# Moderator queue order: artwork_modified_at DESC
# ---------------------------------------------------------------------------


def test_queue_puts_requeued_replacement_first(client, db, vault_tmp):
    owner = _make_user(db)
    mod = _make_user(db, roles=["user", "moderator"])
    # An old approved post and a newer pending upload.
    old_id = _upload(client, owner, (14, 24, 34, 255))
    old = db.get(Post, old_id)
    old.public_visibility = True
    old.created_at = old.artwork_modified_at = BASE - timedelta(days=30)
    db.commit()
    newer = _make_post(db, owner=owner, created_at=datetime.now(timezone.utc))

    _replace(client, owner, old_id, (44, 54, 64, 255))

    ids, _ = _queue_ids(client, mod)
    assert ids.index(old_id) < ids.index(newer.id)


def test_queue_cursor_pages_cover_every_row_once(client: TestClient, db: Session):
    owner = _make_user(db)
    mod = _make_user(db, roles=["user", "moderator"])
    # Upload order != artwork order; one tie on artwork_modified_at.
    far_future = datetime.now(timezone.utc) + timedelta(days=365)
    posts = [
        _make_post(db, owner=owner, created_at=BASE, artwork_modified_at=far_future),
        _make_post(
            db,
            owner=owner,
            created_at=BASE + timedelta(days=1),
            artwork_modified_at=far_future - timedelta(hours=1),
        ),
        _make_post(
            db,
            owner=owner,
            created_at=BASE + timedelta(days=2),
            artwork_modified_at=far_future - timedelta(hours=1),
        ),
        _make_post(
            db,
            owner=owner,
            created_at=BASE + timedelta(days=3),
            artwork_modified_at=far_future - timedelta(hours=2),
        ),
    ]
    expected = [posts[0].id, posts[2].id, posts[1].id, posts[3].id]

    seen: list[int] = []
    cursor = None
    while True:
        ids, cursor = _queue_ids(client, mod, cursor=cursor, limit=2)
        seen.extend(i for i in ids if i in expected)
        if not cursor or len(seen) == len(expected):
            break
    assert seen == expected

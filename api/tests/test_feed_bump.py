"""Tests for docs/feed-bump/.

Phase 1 — D7: a replace-artwork by an owner without Trust (auto_public_approval)
sends the post back to the approval queue (public_visibility=False), promoted
posts included. Trusted owners keep visibility. The moderator queue orders by
artwork_modified_at so a re-queued replacement surfaces at the top.

Phase 2 — D1/D3/D9/D12: posts.listed_at (defaults to created_at) is the one
sort key of every date-sorted feed on web, app and players; pending uploads
carry pending_listing='first'.
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timedelta, timezone

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import Follow, Player, Post, PostFile, User
from app.mqtt.player_requests import _handle_query_posts
from app.mqtt.schemas import QueryPostsRequest
from app.pagination import encode_cursor
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
    listed_at: datetime | None = None,
    public: bool = False,
    hashtags: list[str] | None = None,
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
        hashtags=hashtags or [],
        art_url=f"https://example.com/{title}.png",
        width=64,
        height=64,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        created_at=created_at,
        metadata_modified_at=created_at,
        artwork_modified_at=artwork_modified_at or created_at,
        listed_at=listed_at,
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


@pytest.fixture(autouse=True)
def _no_cache(monkeypatch) -> None:
    """Shared feed caches would mask ordering between requests."""
    for module in ("app.routers.posts", "app.routers.search"):
        monkeypatch.setattr(f"{module}.cache_get", lambda key: None)
        monkeypatch.setattr(f"{module}.cache_set", lambda *a, **k: None)


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


# ---------------------------------------------------------------------------
# Phase 2 — listed_at defaults and the pending_listing marker
# ---------------------------------------------------------------------------


def test_listed_at_follows_explicit_created_at(db):
    owner = _make_user(db)
    post = _make_post(db, owner=owner, created_at=BASE)
    assert post.listed_at == BASE


def test_upload_sets_listed_at_and_marker(client, db, vault_tmp):
    untrusted = _make_user(db)
    trusted = _make_user(db, trusted=True)
    pending = db.get(Post, _upload(client, untrusted, (15, 25, 35, 255)))
    public = db.get(Post, _upload(client, trusted, (16, 26, 36, 255)))

    assert pending.listed_at == pending.created_at
    assert public.listed_at == public.created_at
    assert pending.pending_listing == "first"
    assert public.pending_listing is None


# ---------------------------------------------------------------------------
# Phase 2 — every date-sorted feed orders by listed_at
# ---------------------------------------------------------------------------


@pytest.fixture()
def trio(db):
    """Three public posts sharing a unique hashtag. `bumped` is the oldest by
    created_at but listed last-but-not-least: newest listing of the three."""
    owner = _make_user(db)
    tag = f"fb{uuid.uuid4().hex[:8]}"
    future = datetime.now(timezone.utc) + timedelta(days=30)
    bumped = _make_post(
        db,
        owner=owner,
        created_at=BASE - timedelta(days=3),
        listed_at=future,
        public=True,
        hashtags=[tag],
    )
    older = _make_post(
        db,
        owner=owner,
        created_at=BASE - timedelta(days=2),
        public=True,
        hashtags=[tag],
    )
    newer = _make_post(
        db,
        owner=owner,
        created_at=BASE - timedelta(days=1),
        public=True,
        hashtags=[tag],
    )
    return {
        "owner": owner,
        "tag": tag,
        "ids": {bumped.id, older.id, newer.id},
        "desc": [bumped.id, newer.id, older.id],
        "posts": (bumped, older, newer),
    }


def _ours(resp, ids) -> list[int]:
    assert resp.status_code == 200, resp.text
    return [item["id"] for item in resp.json()["items"] if item["id"] in ids]


def test_post_list_date_sort_uses_listed_at_both_ways(client, trio):
    tag = trio["tag"]
    for sort in ("created_at", "creation_date"):
        desc = client.get(f"/post?hashtag={tag}&sort={sort}&order=desc")
        assert _ours(desc, trio["ids"]) == trio["desc"]
        asc = client.get(f"/post?hashtag={tag}&sort={sort}&order=asc")
        assert _ours(asc, trio["ids"]) == trio["desc"][::-1]


def test_profile_feed_uses_listed_at(client, trio):
    owner = trio["owner"]
    resp = client.get(f"/post?owner_id={owner.user_key}&sort=created_at")
    assert _ours(resp, trio["ids"]) == trio["desc"]


def test_recent_feed_uses_listed_at(client, trio):
    resp = client.get("/post/recent?limit=200")
    assert _ours(resp, trio["ids"]) == trio["desc"]


def test_recent_feed_cursor_pages_cover_every_row_once(client, trio):
    seen: list[int] = []
    cursor = None
    for _ in range(200):
        url = "/post/recent?limit=2" + (f"&cursor={cursor}" if cursor else "")
        resp = client.get(url)
        seen.extend(_ours(resp, trio["ids"]))
        cursor = resp.json()["next_cursor"]
        if not cursor or len(seen) == 3:
            break
    assert seen == trio["desc"]


def test_recent_feed_accepts_pre_deploy_created_at_cursor(client, trio):
    bumped, older, newer = trio["posts"]
    # A cursor minted before the deploy carries created_at; for a non-bumped
    # post that equals listed_at, so it resumes right after that post.
    legacy = encode_cursor(str(newer.id), newer.created_at.isoformat())
    resp = client.get(f"/post/recent?limit=200&cursor={legacy}")
    assert _ours(resp, trio["ids"]) == [older.id]


def test_hashtag_feed_uses_listed_at(client, trio):
    resp = client.get(f"/hashtags/{trio['tag']}/posts?limit=50")
    assert _ours(resp, trio["ids"]) == trio["desc"]


def test_following_feed_uses_listed_at(client, db, trio):
    viewer = _make_user(db)
    db.add(Follow(follower_id=viewer.id, following_id=trio["owner"].id))
    db.commit()
    resp = client.get("/feed/following?limit=50", headers=_auth(viewer))
    assert _ours(resp, trio["ids"]) == trio["desc"]


@pytest.fixture
def player(db: Session) -> Player:
    owner = _make_user(db)
    player = Player(
        player_key=uuid.uuid4(),
        owner_id=owner.id,
        device_model="TestDevice",
        firmware_version="1.0.0",
        registration_status="registered",
        name="Bump Player",
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def _query(player, db, mock_publish, **kwargs) -> list[int]:
    request = QueryPostsRequest(
        request_id=f"rq-{uuid.uuid4().hex[:6]}",
        player_key=player.player_key,
        **kwargs,
    )
    _handle_query_posts(player, request, db)
    payload = mock_publish.call_args[1]["payload"]
    return [p["post_id"] for p in payload["posts"]]


@patch("app.mqtt.player_requests.publish")
def test_player_channels_use_listed_at(mock_publish: MagicMock, player, db, trio):
    owner = trio["owner"]
    channels = [
        {"channel": "hashtag", "hashtag": trio["tag"]},
        {"channel": "by_user", "user_sqid": owner.public_sqid},
    ]
    for channel in channels:
        for sort in ({}, {"sort": "server_order"}, {"sort": "created_at"}):
            got = _query(player, db, mock_publish, **channel, **sort)
            assert [i for i in got if i in trio["ids"]] == trio["desc"], (channel, sort)


@patch("app.mqtt.player_requests.publish")
def test_player_all_channel_uses_listed_at(mock_publish: MagicMock, player, db, trio):
    got = _query(player, db, mock_publish, channel="all", limit=50)
    # bumped is listed 30 days ahead, so it leads the whole channel
    assert got[0] == trio["desc"][0]

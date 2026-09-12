"""Promoted surfaces sort by promotion time (docs/promoted-feed-order/).

Every surface that serves the promoted set orders by ``posts.promoted_at``
(newest promotion first), coalesced to ``created_at`` so a promoted row that
lacks a stamp is never dropped by the keyset:

- ``GET /feed/promoted`` (website Recommended page, permalink prev/next, app)
- ``GET /post?promoted=true&sort=created_at`` (server-side remap)
- the players' ``promoted`` channel with ``server_order`` / ``created_at``

``POST /post/{id}/promote`` stamps the time on every call (demote → promote
bumps the post back to the top); ``DELETE`` clears it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import Player, Post, PostFile, User
from app.mqtt.player_requests import _handle_query_posts
from app.mqtt.schemas import QueryPostsRequest
from app.pagination import encode_cursor
from app.sqids_config import encode_id, encode_user_id
from app.vault import compute_storage_shard

BASE = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _make_user(db: Session, *, roles: list[str] | None = None) -> User:
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        handle=f"promo_{unique_id}",
        email=f"promo_{unique_id}@example.com",
        roles=roles or ["artist"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    return user


def _make_post(
    db: Session,
    *,
    owner: User,
    created_at: datetime,
    promoted: bool = True,
    promoted_at: datetime | None = None,
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
        artwork_modified_at=created_at,
        hash=str(storage_key).replace("-", "") + "e" * 32,
        visible=True,
        public_visibility=True,
        promoted=promoted,
        promoted_at=promoted_at,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    db.add(PostFile(post_id=post.id, format="png", file_bytes=32000, is_native=True))
    db.commit()
    db.refresh(post)
    return post


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _ids(resp) -> list[int]:
    assert resp.status_code == 200, resp.text
    return [item["id"] for item in resp.json()["items"]]


@pytest.fixture(autouse=True)
def _no_cache(monkeypatch) -> None:
    """The feed's shared 5-minute cache would mask ordering between requests."""
    for module in ("app.routers.posts", "app.routers.search"):
        monkeypatch.setattr(f"{module}.cache_get", lambda key: None)
        monkeypatch.setattr(f"{module}.cache_set", lambda *a, **k: None)
        monkeypatch.setattr(
            f"{module}.cache_invalidate", lambda *a, **k: None, raising=False
        )


# ---------------------------------------------------------------------------
# GET /feed/promoted
# ---------------------------------------------------------------------------


def test_feed_orders_by_promoted_at_with_created_at_fallback(
    client: TestClient, db: Session
):
    owner = _make_user(db)
    # Upload order: old < mid < new. Promotion order says otherwise.
    old = _make_post(
        db, owner=owner, created_at=BASE - timedelta(days=30), promoted_at=BASE
    )
    mid = _make_post(
        db, owner=owner, created_at=BASE - timedelta(days=10), promoted_at=None
    )  # unstamped → falls back to created_at, must not be dropped
    new = _make_post(
        db,
        owner=owner,
        created_at=BASE - timedelta(days=1),
        promoted_at=BASE - timedelta(days=20),
    )
    _make_post(db, owner=owner, created_at=BASE, promoted=False)

    assert _ids(client.get("/feed/promoted?limit=10")) == [old.id, mid.id, new.id]


def test_feed_cursor_pages_cover_every_row_once(client: TestClient, db: Session):
    owner = _make_user(db)
    posts = [
        _make_post(
            db,
            owner=owner,
            created_at=BASE - timedelta(days=i),
            promoted_at=None if i == 2 else BASE + timedelta(hours=i),
        )
        for i in range(5)
    ]
    # Expected: stamped rows newest-first (i=4,3,1,0), the unstamped one
    # (key = created_at = BASE - 2d) sorts last.
    expected = [posts[4].id, posts[3].id, posts[1].id, posts[0].id, posts[2].id]

    seen: list[int] = []
    cursor = None
    for _ in range(10):
        url = "/feed/promoted?limit=2" + (f"&cursor={cursor}" if cursor else "")
        resp = client.get(url)
        seen += _ids(resp)
        cursor = resp.json()["next_cursor"]
        if cursor is None:
            break
    assert seen == expected


def test_feed_accepts_legacy_created_at_cursor(client: TestClient, db: Session):
    """Cursors minted before promoted_at existed encode created_at; grandfathered
    rows have promoted_at == created_at, so such a cursor resumes correctly."""
    owner = _make_user(db)
    posts = [
        _make_post(
            db,
            owner=owner,
            created_at=BASE - timedelta(days=i),
            promoted_at=BASE - timedelta(days=i),
        )
        for i in range(4)
    ]
    legacy_cursor = encode_cursor(str(posts[1].id), posts[1].created_at.isoformat())
    assert _ids(client.get(f"/feed/promoted?limit=10&cursor={legacy_cursor}")) == [
        posts[2].id,
        posts[3].id,
    ]


def test_feed_ignores_garbage_cursor(client: TestClient, db: Session):
    owner = _make_user(db)
    post = _make_post(db, owner=owner, created_at=BASE, promoted_at=BASE)
    assert _ids(client.get("/feed/promoted?limit=10&cursor=not-a-cursor")) == [post.id]


# ---------------------------------------------------------------------------
# POST / DELETE /post/{id}/promote
# ---------------------------------------------------------------------------


def test_promote_stamps_demote_clears_repromote_bumps(client: TestClient, db: Session):
    owner = _make_user(db)
    moderator = _make_user(db, roles=["user", "moderator"])
    old = _make_post(
        db, owner=owner, created_at=BASE - timedelta(days=30), promoted=False
    )
    recent = _make_post(
        db, owner=owner, created_at=BASE - timedelta(days=1), promoted_at=BASE
    )

    before = datetime.now(timezone.utc)
    resp = client.post(
        f"/post/{old.id}/promote",
        json={"category": "frontpage"},
        headers=_auth(moderator),
    )
    assert resp.status_code == 201, resp.text
    db.refresh(old)
    assert old.promoted is True
    assert old.promoted_at is not None and old.promoted_at >= before
    # A 30-day-old upload promoted just now leads the feed.
    assert _ids(client.get("/feed/promoted?limit=10")) == [old.id, recent.id]

    resp = client.delete(f"/post/{old.id}/promote", headers=_auth(moderator))
    assert resp.status_code == 204, resp.text
    db.refresh(old)
    assert old.promoted is False
    assert old.promoted_at is None
    assert _ids(client.get("/feed/promoted?limit=10")) == [recent.id]

    # Re-promote: fresh stamp, back on top.
    resp = client.post(
        f"/post/{old.id}/promote",
        json={"category": "frontpage"},
        headers=_auth(moderator),
    )
    assert resp.status_code == 201, resp.text
    db.refresh(old)
    assert old.promoted_at is not None and old.promoted_at >= before
    assert _ids(client.get("/feed/promoted?limit=10")) == [old.id, recent.id]


# ---------------------------------------------------------------------------
# GET /post?promoted=true (server-side remap of the date sort)
# ---------------------------------------------------------------------------


def test_list_posts_promoted_filter_sorts_by_promotion_time(
    client: TestClient, db: Session
):
    owner = _make_user(db)
    old = _make_post(
        db, owner=owner, created_at=BASE - timedelta(days=30), promoted_at=BASE
    )
    new = _make_post(
        db,
        owner=owner,
        created_at=BASE - timedelta(days=1),
        promoted_at=BASE - timedelta(days=20),
    )
    unpromoted = _make_post(db, owner=owner, created_at=BASE, promoted=False)

    assert _ids(client.get("/post?promoted=true&sort=created_at&limit=10")) == [
        old.id,
        new.id,
    ]
    # Cursor continuity on the remapped key.
    page1 = client.get("/post?promoted=true&sort=created_at&limit=1")
    assert _ids(page1) == [old.id]
    cursor = page1.json()["next_cursor"]
    assert cursor
    assert _ids(
        client.get(f"/post?promoted=true&sort=created_at&limit=1&cursor={cursor}")
    ) == [new.id]
    # Without the promoted filter, created_at still means upload time.
    assert _ids(client.get("/post?sort=created_at&limit=10")) == [
        unpromoted.id,
        new.id,
        old.id,
    ]


# ---------------------------------------------------------------------------
# Player protocol: channel="promoted"
# ---------------------------------------------------------------------------


@pytest.fixture
def player(db: Session) -> Player:
    owner = _make_user(db, roles=["user"])
    player = Player(
        player_key=uuid.uuid4(),
        owner_id=owner.id,
        device_model="TestDevice",
        firmware_version="1.0.0",
        registration_status="registered",
        name="Promo Player",
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def _query(player: Player, db: Session, mock_publish: MagicMock, **kwargs) -> list[int]:
    request = QueryPostsRequest(
        request_id=f"rq-{uuid.uuid4().hex[:6]}",
        player_key=player.player_key,
        channel="promoted",
        **kwargs,
    )
    _handle_query_posts(player, request, db)
    payload = mock_publish.call_args[1]["payload"]
    return [p["post_id"] for p in payload["posts"]]


@patch("app.mqtt.player_requests.publish")
def test_player_promoted_channel_plays_newest_promotion_first(
    mock_publish: MagicMock, player: Player, db: Session
):
    owner = _make_user(db)
    old = _make_post(
        db, owner=owner, created_at=BASE - timedelta(days=30), promoted_at=BASE
    )
    mid = _make_post(
        db, owner=owner, created_at=BASE - timedelta(days=10), promoted_at=None
    )
    new = _make_post(
        db,
        owner=owner,
        created_at=BASE - timedelta(days=1),
        promoted_at=BASE - timedelta(days=20),
    )
    _make_post(db, owner=owner, created_at=BASE, promoted=False)
    expected = [old.id, mid.id, new.id]

    assert _query(player, db, mock_publish) == expected  # server_order default
    assert _query(player, db, mock_publish, sort="created_at") == expected
    # random still runs and returns the same set
    assert sorted(_query(player, db, mock_publish, sort="random")) == sorted(expected)

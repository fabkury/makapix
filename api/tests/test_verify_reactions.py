"""Tests for the player verify-reactions endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def clear_verify_cache():
    """Clear channel-verify cache and rate limit keys before each test."""
    from app.cache import cache_invalidate

    cache_invalidate("chan_verify:reactions:*")
    cache_invalidate("chan_verify:hashtag:*")
    cache_invalidate("ratelimit:player_verify:*")
    yield
    cache_invalidate("chan_verify:reactions:*")


def _make_user(
    db: "Session",
    *,
    handle_prefix: str = "user",
    email_verified: bool = True,
    deactivated: bool = False,
    hidden_by_mod: bool = False,
    banned_until=None,
):
    from app.models import User
    from app.sqids_config import encode_user_id

    unique = str(uuid.uuid4())[:8]
    user = User(
        handle=f"{handle_prefix}_{unique}",
        email=f"{handle_prefix}_{unique}@example.com",
        email_verified=email_verified,
        deactivated=deactivated,
        hidden_by_mod=hidden_by_mod,
        banned_until=banned_until,
        roles=["user"],
    )
    db.add(user)
    db.flush()
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    return user


def _make_post(
    db: "Session",
    *,
    owner,
    hashtags: list[str] | None = None,
    visible: bool = True,
    public_visibility: bool = True,
    hidden_by_mod: bool = False,
    hidden_by_user: bool = False,
    non_conformant: bool = False,
    deleted_by_user: bool = False,
    width: int = 64,
    height: int = 64,
):
    from app.models import Post, PostFile
    from app.sqids_config import encode_id
    from app.vault import compute_storage_shard

    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
    post = Post(
        storage_key=storage_key,
        storage_shard=compute_storage_shard(storage_key),
        owner_id=owner.id,
        kind="artwork",
        title=f"post-{str(storage_key)[:8]}",
        description="t",
        hashtags=hashtags or [],
        art_url=f"https://example.com/{storage_key}.png",
        width=width,
        height=height,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=str(storage_key).replace("-", "") + "d" * 32,
        visible=visible,
        public_visibility=public_visibility,
        hidden_by_mod=hidden_by_mod,
        hidden_by_user=hidden_by_user,
        non_conformant=non_conformant,
        deleted_by_user=deleted_by_user,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    db.add(PostFile(post_id=post.id, format="png", file_bytes=1000, is_native=True))
    db.commit()
    db.refresh(post)
    return post


def _react(db: "Session", *, user, post, emoji: str = "❤️", user_id=None, user_ip=None):
    from app.models import Reaction

    r = Reaction(
        post_id=post.id,
        user_id=user_id if user_id is not None else (user.id if user else None),
        user_ip=user_ip,
        emoji=emoji,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def test_verify_reactions_valid(client: "TestClient", db: "Session"):
    """Eligible user with reactions returns 200 + preview of latest-reacted post."""
    reactor = _make_user(db, handle_prefix="reactor")
    artist = _make_user(db, handle_prefix="artist")
    p1 = _make_post(db, owner=artist, width=32, height=32)
    p2 = _make_post(db, owner=artist, width=64, height=64)
    _react(db, user=reactor, post=p1)
    r2 = _react(db, user=reactor, post=p2)

    response = client.get(f"/player/verify-reactions/{reactor.public_sqid}")
    assert response.status_code == 200
    data = response.json()
    assert data["handle"] == reactor.handle
    assert data["artwork_count"] == 2
    assert data["artwork_count_capped"] is False
    # Latest by reaction time — r2 is newer
    assert data["latest_artwork_sqid"] == p2.public_sqid
    assert data["latest_artwork_width"] == 64
    assert data["latest_artwork_height"] == 64
    assert data["latest_artwork_url"] is not None
    assert response.headers.get("access-control-allow-origin") == "*"
    _ = r2  # silence unused


def test_verify_reactions_zero_reactions(client: "TestClient", db: "Session"):
    """Eligible user with no reactions returns 200 with artwork_count=0 and null preview."""
    user = _make_user(db, handle_prefix="reactor")

    response = client.get(f"/player/verify-reactions/{user.public_sqid}")
    assert response.status_code == 200
    data = response.json()
    assert data["handle"] == user.handle
    assert data["artwork_count"] == 0
    assert data["artwork_count_capped"] is False
    assert data["latest_artwork_url"] is None
    assert data["latest_artwork_sqid"] is None


def test_verify_reactions_dedup_same_post(client: "TestClient", db: "Session"):
    """Multiple reactions to the same post count as one."""
    reactor = _make_user(db, handle_prefix="reactor")
    artist = _make_user(db, handle_prefix="artist")
    post = _make_post(db, owner=artist)

    _react(db, user=reactor, post=post, emoji="❤️")
    _react(db, user=reactor, post=post, emoji="🎉")
    _react(db, user=reactor, post=post, emoji="👍")

    response = client.get(f"/player/verify-reactions/{reactor.public_sqid}")
    assert response.status_code == 200
    assert response.json()["artwork_count"] == 1


def test_verify_reactions_excludes_anonymous_reactions(
    client: "TestClient", db: "Session"
):
    """Reactions with user_id=NULL (anonymous) are not counted as this user's."""
    reactor = _make_user(db, handle_prefix="reactor")
    artist = _make_user(db, handle_prefix="artist")
    post = _make_post(db, owner=artist)

    # Anonymous reaction (user_id is NULL, only user_ip set)
    from app.models import Reaction

    db.add(Reaction(post_id=post.id, user_id=None, user_ip="1.2.3.4", emoji="❤️"))
    db.commit()

    response = client.get(f"/player/verify-reactions/{reactor.public_sqid}")
    assert response.status_code == 200
    assert response.json()["artwork_count"] == 0


def test_verify_reactions_excludes_non_public_posts(
    client: "TestClient", db: "Session"
):
    """Reactions to non-public-visible or hidden posts don't count."""
    reactor = _make_user(db, handle_prefix="reactor")
    artist = _make_user(db, handle_prefix="artist")
    private_post = _make_post(db, owner=artist, public_visibility=False)
    hidden_post = _make_post(db, owner=artist, hidden_by_mod=True)
    nc_post = _make_post(db, owner=artist, non_conformant=True)
    deleted_post = _make_post(db, owner=artist, deleted_by_user=True)

    _react(db, user=reactor, post=private_post)
    _react(db, user=reactor, post=hidden_post)
    _react(db, user=reactor, post=nc_post)
    _react(db, user=reactor, post=deleted_post)

    response = client.get(f"/player/verify-reactions/{reactor.public_sqid}")
    assert response.status_code == 200
    assert response.json()["artwork_count"] == 0


def test_verify_reactions_invalid_sqid(client: "TestClient"):
    response = client.get("/player/verify-reactions/ZZZZZZZZ")
    assert response.status_code == 404


def test_verify_reactions_oversized_sqid(client: "TestClient"):
    response = client.get("/player/verify-reactions/" + "a" * 17)
    assert response.status_code == 404


def test_verify_reactions_unknown_sqid(client: "TestClient"):
    from app.sqids_config import encode_user_id

    fake_sqid = encode_user_id(999_999_999)
    response = client.get(f"/player/verify-reactions/{fake_sqid}")
    assert response.status_code == 404


def test_verify_reactions_unverified_email(client: "TestClient", db: "Session"):
    user = _make_user(db, handle_prefix="unv", email_verified=False)
    response = client.get(f"/player/verify-reactions/{user.public_sqid}")
    assert response.status_code == 404


def test_verify_reactions_deactivated(client: "TestClient", db: "Session"):
    user = _make_user(db, handle_prefix="deact", deactivated=True)
    response = client.get(f"/player/verify-reactions/{user.public_sqid}")
    assert response.status_code == 404


def test_verify_reactions_hidden_by_mod(client: "TestClient", db: "Session"):
    user = _make_user(db, handle_prefix="hid", hidden_by_mod=True)
    response = client.get(f"/player/verify-reactions/{user.public_sqid}")
    assert response.status_code == 404


def test_verify_reactions_banned(client: "TestClient", db: "Session"):
    user = _make_user(
        db,
        handle_prefix="ban",
        banned_until=datetime.now(timezone.utc) + timedelta(days=7),
    )
    response = client.get(f"/player/verify-reactions/{user.public_sqid}")
    assert response.status_code == 404


def test_verify_reactions_count_capped(client: "TestClient", db: "Session"):
    """More than 100 reacted posts yields count=100, capped=True."""
    reactor = _make_user(db, handle_prefix="heavy")
    artist = _make_user(db, handle_prefix="artist")
    for _ in range(101):
        post = _make_post(db, owner=artist)
        _react(db, user=reactor, post=post)

    response = client.get(f"/player/verify-reactions/{reactor.public_sqid}")
    assert response.status_code == 200
    data = response.json()
    assert data["artwork_count"] == 100
    assert data["artwork_count_capped"] is True

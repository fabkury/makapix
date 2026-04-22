"""Tests for the player verify-hashtag endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def clear_verify_cache():
    """Clear channel-verify cache and rate limit keys before each test."""
    from app.cache import cache_invalidate

    cache_invalidate("chan_verify:hashtag:*")
    cache_invalidate("chan_verify:reactions:*")
    cache_invalidate("ratelimit:player_verify:*")
    yield
    cache_invalidate("chan_verify:hashtag:*")


def _make_user(db: "Session", *, handle_prefix: str = "artist") -> object:
    from app.models import User
    from app.sqids_config import encode_user_id

    unique = str(uuid.uuid4())[:8]
    user = User(
        handle=f"{handle_prefix}_{unique}",
        email=f"{handle_prefix}_{unique}@example.com",
        email_verified=True,
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
    hashtags: list[str],
    title: str | None = None,
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
        title=title or f"post-{str(storage_key)[:8]}",
        description="t",
        hashtags=hashtags,
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


def test_verify_hashtag_valid(client: "TestClient", db: "Session"):
    """Hashtag with a visible public post returns 200 with preview fields."""
    owner = _make_user(db)
    post = _make_post(db, owner=owner, hashtags=["pixelart"], width=32, height=64)

    response = client.get("/player/verify-hashtag/pixelart")
    assert response.status_code == 200
    data = response.json()
    assert data["tag"] == "pixelart"
    assert data["artwork_count"] == 1
    assert data["artwork_count_capped"] is False
    assert data["latest_artwork_sqid"] == post.public_sqid
    assert data["latest_artwork_width"] == 32
    assert data["latest_artwork_height"] == 64
    assert data["latest_artwork_url"] is not None
    assert data["latest_artwork_url"].startswith("/api/vault/")
    assert data["latest_artwork_url"].endswith(f"{post.storage_key}.png")


def test_verify_hashtag_normalizes_case_and_whitespace(
    client: "TestClient", db: "Session"
):
    """Tag is normalized to lowercase/stripped."""
    owner = _make_user(db)
    _make_post(db, owner=owner, hashtags=["pixelart"])

    response = client.get("/player/verify-hashtag/%20PixelArt%20")
    assert response.status_code == 200
    assert response.json()["tag"] == "pixelart"


def test_verify_hashtag_unknown_tag(client: "TestClient"):
    """Hashtag with no posts returns 404."""
    response = client.get("/player/verify-hashtag/neverused")
    assert response.status_code == 404
    assert response.json()["detail"] == "Hashtag not found"


def test_verify_hashtag_empty_tag(client: "TestClient"):
    """Whitespace-only tag returns 404."""
    response = client.get("/player/verify-hashtag/%20%20")
    assert response.status_code == 404


def test_verify_hashtag_oversized_tag(client: "TestClient"):
    """Overlong tag returns 404 before any DB work."""
    response = client.get("/player/verify-hashtag/" + "a" * 65)
    assert response.status_code == 404


def test_verify_hashtag_excludes_hidden_and_private(
    client: "TestClient", db: "Session"
):
    """Posts that are non-public, hidden, non-conformant, or deleted don't count."""
    owner = _make_user(db)
    _make_post(db, owner=owner, hashtags=["sekret"], public_visibility=False)
    _make_post(db, owner=owner, hashtags=["sekret"], hidden_by_mod=True)
    _make_post(db, owner=owner, hashtags=["sekret"], non_conformant=True)
    _make_post(db, owner=owner, hashtags=["sekret"], deleted_by_user=True)
    _make_post(db, owner=owner, hashtags=["sekret"], hidden_by_user=True)
    _make_post(db, owner=owner, hashtags=["sekret"], visible=False)

    response = client.get("/player/verify-hashtag/sekret")
    assert response.status_code == 404


def test_verify_hashtag_latest_is_by_created_at(
    client: "TestClient", db: "Session"
):
    """Latest preview corresponds to the most recent visible post."""
    owner = _make_user(db)
    _make_post(db, owner=owner, hashtags=["trend"], title="older")
    newest = _make_post(db, owner=owner, hashtags=["trend"], title="newer")

    response = client.get("/player/verify-hashtag/trend")
    assert response.status_code == 200
    data = response.json()
    assert data["artwork_count"] == 2
    assert data["latest_artwork_sqid"] == newest.public_sqid


def test_verify_hashtag_count_is_capped_at_100(
    client: "TestClient", db: "Session"
):
    """More than 100 matching posts yields artwork_count=100, capped=True."""
    owner = _make_user(db)
    for _ in range(101):
        _make_post(db, owner=owner, hashtags=["spam"])

    response = client.get("/player/verify-hashtag/spam")
    assert response.status_code == 200
    data = response.json()
    assert data["artwork_count"] == 100
    assert data["artwork_count_capped"] is True


def test_verify_hashtag_cors_header(client: "TestClient", db: "Session"):
    """Successful response includes CORS allow-origin header."""
    owner = _make_user(db)
    _make_post(db, owner=owner, hashtags=["pixelart"])
    response = client.get("/player/verify-hashtag/pixelart")
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"


def test_verify_hashtag_rate_limit(client: "TestClient", db: "Session"):
    """More than 30 requests/min from one IP yields 429."""
    owner = _make_user(db)
    _make_post(db, owner=owner, hashtags=["pixelart"])

    # First 30 succeed
    for _ in range(30):
        r = client.get("/player/verify-hashtag/pixelart")
        assert r.status_code == 200
    # 31st is throttled
    r = client.get("/player/verify-hashtag/pixelart")
    assert r.status_code == 429

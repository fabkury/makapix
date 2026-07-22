"""
Tests for GET /api/hashtags/top (header rotating-hashtags bar): monitored
hashtags must never appear in the returned list, regardless of popularity.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.constants import MONITORED_HASHTAGS
from app.models import Post, PostFile, User
from app.sqids_config import encode_id, encode_user_id
from app.vault import compute_storage_shard


def _make_user(db: Session) -> User:
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        handle=f"tophash_{unique_id}",
        email=f"tophash_{unique_id}@example.com",
        roles=["artist"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    return user


def _make_post(db: Session, *, owner: User, hashtags: list[str]) -> Post:
    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
    title = f"art_{str(storage_key)[:8]}"
    post = Post(
        storage_key=storage_key,
        storage_shard=compute_storage_shard(storage_key),
        owner_id=owner.id,
        kind="artwork",
        title=title,
        description=title,
        hashtags=hashtags,
        art_url=f"https://example.com/{title}.png",
        width=64,
        height=64,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=str(storage_key).replace("-", "") + "d" * 32,
        visible=True,
        public_visibility=True,
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


@pytest.fixture(autouse=True)
def _no_cache(monkeypatch) -> None:
    """Bypass the shared Redis cache so each test computes fresh results."""
    monkeypatch.setattr("app.routers.search.cache_get", lambda key: None)
    monkeypatch.setattr("app.routers.search.cache_set", lambda *a, **k: None)


def test_monitored_hashtags_never_returned(client: TestClient, db: Session) -> None:
    """Even the most popular hashtag is excluded if it is monitored."""
    user = _make_user(db)
    # Make every monitored hashtag overwhelmingly the most popular.
    for monitored in sorted(MONITORED_HASHTAGS):
        for _ in range(5):
            _make_post(db, owner=user, hashtags=[monitored, "pixelart"])
    _make_post(db, owner=user, hashtags=["landscape"])

    resp = client.get("/hashtags/top", headers=_auth(user))
    assert resp.status_code == 200
    returned = resp.json()["hashtags"]
    assert not set(returned) & MONITORED_HASHTAGS
    assert returned  # non-monitored tags still surface


def test_non_monitored_hashtags_still_appear(client: TestClient, db: Session) -> None:
    user = _make_user(db)
    for _ in range(5):
        _make_post(db, owner=user, hashtags=["nsfw", "sunset"])

    resp = client.get("/hashtags/top", headers=_auth(user))
    assert resp.status_code == 200
    returned = resp.json()["hashtags"]
    assert "nsfw" not in returned
    assert "sunset" in returned


def test_only_monitored_hashtags_yields_empty_list(
    client: TestClient, db: Session
) -> None:
    """If visible posts carry only monitored tags, the bar list is empty."""
    user = _make_user(db)
    for _ in range(3):
        _make_post(db, owner=user, hashtags=["nsfw", "politics"])

    resp = client.get("/hashtags/top", headers=_auth(user))
    assert resp.status_code == 200
    assert resp.json()["hashtags"] == []

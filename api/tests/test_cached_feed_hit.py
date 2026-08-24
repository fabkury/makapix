"""Cache-HIT paths of the shared post feeds must return 200.

Regression: these endpoints rebuilt cached payloads with the untyped
``schemas.Page(**cached)``, which leaves ``items`` as plain dicts; the
user-specific post-processing (monitored-hashtag filter, like status)
then blew up with AttributeError → 500 on every cache hit
(prod, 2026-08-19). The rebuild must use ``schemas.Page[schemas.Post]``
so items come back as real models.

The warm cache is simulated by monkeypatching ``cache_get`` to return
the cold response's JSON body — the same shape ``cache_set`` stores
(``model_dump()`` through CacheJSONEncoder: UUIDs/datetimes as strings).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import Post, PostFile, User
from app.sqids_config import encode_id, encode_user_id
from app.vault import compute_storage_shard


def _make_user(db: Session) -> User:
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        handle=f"cachedfeed_{unique_id}",
        email=f"cachedfeed_{unique_id}@example.com",
        roles=["artist"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    return user


def _make_post(
    db: Session, *, owner: User, hashtags: list[str], promoted: bool = False
) -> Post:
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
        promoted=promoted,
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
    """Cold by default; individual tests re-patch cache_get to go warm."""
    for module in ("app.routers.posts", "app.routers.search"):
        monkeypatch.setattr(f"{module}.cache_get", lambda key: None)
        monkeypatch.setattr(f"{module}.cache_set", lambda *a, **k: None)


@pytest.mark.parametrize(
    "path,cache_module",
    [
        ("/post/recent?limit=20", "app.routers.posts"),
        ("/hashtags/pixelart/posts?limit=20", "app.routers.search"),
        ("/feed/promoted?limit=20", "app.routers.search"),
    ],
)
def test_cache_hit_returns_200(
    client: TestClient,
    db: Session,
    monkeypatch,
    path: str,
    cache_module: str,
) -> None:
    user = _make_user(db)
    post = _make_post(db, owner=user, hashtags=["pixelart"], promoted=True)

    cold = client.get(path, headers=_auth(user))
    assert cold.status_code == 200
    payload = cold.json()
    assert [item["id"] for item in payload["items"]] == [post.id]

    # Warm: serve the cached payload (items are dicts, as stored in Redis)
    monkeypatch.setattr(f"{cache_module}.cache_get", lambda key: payload)
    warm = client.get(path, headers=_auth(user))
    assert warm.status_code == 200
    assert [item["id"] for item in warm.json()["items"]] == [post.id]

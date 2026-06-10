"""Tests for GET /api/admin/vault-sharding-stats (resharding dashboard)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import Post, User, VaultShardingStatsDaily
from app.sqids_config import encode_id, encode_user_id
from app.vault import compute_storage_shard

URL = "/admin/vault-sharding-stats"


def _make_user(db: Session, *, roles: list[str]) -> User:
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        handle=f"u_{unique_id}",
        email=f"u_{unique_id}@example.com",
        roles=roles,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    return user


def _make_post(db: Session, *, owner: User) -> Post:
    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
    post = Post(
        storage_key=storage_key,
        storage_shard=compute_storage_shard(storage_key),
        owner_id=owner.id,
        kind="artwork",
        title="straggler",
        description="",
        hashtags=[],
        art_url=f"https://example.com/{storage_key}.png",
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
    db.commit()
    db.refresh(post)
    return post


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.user_key)}"}


def _full_day(db: Session, day, *, l2_human=5, l3_human=0):
    for cls in ("artwork", "avatar", "blog_image"):
        for level, human in ((2, l2_human if cls == "artwork" else 0),
                             (3, l3_human if cls == "artwork" else 0)):
            db.add(
                VaultShardingStatsDaily(
                    date=day,
                    asset_class=cls,
                    shard_level=level,
                    post_id=None,
                    downloads_human=human,
                    downloads_bot=0,
                    misses=0,
                )
            )


class TestVaultShardingStats:
    def test_requires_moderator(self, client: TestClient, db: Session):
        user = _make_user(db, roles=["user"])
        response = client.get(URL, headers=_auth(user))
        assert response.status_code == 403

    def test_requires_auth(self, client: TestClient):
        assert client.get(URL).status_code == 401

    def test_returns_streak_daily_and_stragglers(
        self, client: TestClient, db: Session
    ):
        moderator = _make_user(db, roles=["user", "moderator"])
        post = _make_post(db, owner=moderator)

        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        _full_day(db, yesterday)
        _full_day(db, yesterday - timedelta(days=1))
        # A straggler row: this post was fetched via a legacy URL.
        db.add(
            VaultShardingStatsDaily(
                date=yesterday - timedelta(days=2),
                asset_class="artwork",
                shard_level=3,
                post_id=post.id,
                downloads_human=4,
                downloads_bot=1,
                misses=0,
            )
        )
        db.commit()

        response = client.get(URL, params={"refresh": True}, headers=_auth(moderator))
        assert response.status_code == 200
        data = response.json()

        assert data["streak_criterion_days"] == 14
        # Two clean liveness-valid days ending yesterday.
        assert data["streak_days"] == 2
        assert data["window_days"] == 30
        assert len(data["daily"]) == 30

        by_date = {d["date"]: d for d in data["daily"]}
        assert by_date[yesterday.isoformat()]["has_data"] is True
        assert by_date[yesterday.isoformat()]["level2_human"] == 5
        # A day with no rows at all is a data gap, not a zero day.
        gap_day = (yesterday - timedelta(days=5)).isoformat()
        assert by_date[gap_day]["has_data"] is False

        stragglers = data["stragglers"]
        assert len(stragglers) == 1
        assert stragglers[0]["post_id"] == post.id
        assert stragglers[0]["downloads_human"] == 4
        assert stragglers[0]["downloads_bot"] == 1

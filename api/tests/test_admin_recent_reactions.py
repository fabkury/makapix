"""
Tests for GET /api/admin/recent-reactions (moderator dashboard global reaction
list) and the truncate_ip display helper.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import Post, PostFile, Reaction, User
from app.sqids_config import encode_id, encode_user_id
from app.utils.view_tracking import truncate_ip
from app.vault import compute_storage_shard


def _make_user(db: Session, *, handle_prefix: str, roles: list[str]) -> User:
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        handle=f"{handle_prefix}_{unique_id}",
        email=f"{handle_prefix}_{unique_id}@example.com",
        roles=roles,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    return user


def _make_post(db: Session, *, owner: User, title: str) -> Post:
    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
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


def _react(
    db: Session,
    *,
    post: Post,
    user: User | None = None,
    user_ip: str | None = None,
    emoji: str = "❤️",
    created_at: datetime | None = None,
) -> Reaction:
    r = Reaction(
        post_id=post.id,
        user_id=user.id if user else None,
        user_ip=user_ip,
        emoji=emoji,
    )
    if created_at is not None:
        r.created_at = created_at
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


@pytest.fixture
def moderator(db: Session) -> User:
    return _make_user(db, handle_prefix="mod", roles=["user", "moderator"])


@pytest.fixture
def reactor(db: Session) -> User:
    return _make_user(db, handle_prefix="reactor", roles=["user"])


class TestTruncateIp:
    def test_ipv4_keeps_last_two_octets(self):
        assert truncate_ip("203.0.113.45") == "…113.45"

    def test_ipv6_keeps_last_two_groups(self):
        assert truncate_ip("2001:db8:85a3::8a2e:370:7334") == "…0370:7334"

    def test_ipv6_loopback(self):
        assert truncate_ip("::1") == "…0000:0001"

    def test_invalid_input(self):
        assert truncate_ip("unknown") == "…"
        assert truncate_ip("") == "…"


class TestRecentReactions:
    URL = "/admin/recent-reactions"

    def test_requires_auth(self, client: TestClient):
        response = client.get(self.URL)
        assert response.status_code == 401

    def test_requires_moderator(self, client: TestClient, db: Session, reactor: User):
        response = client.get(self.URL, headers=_auth(reactor))
        assert response.status_code == 403

    def test_lists_reactions_newest_first(
        self, client: TestClient, db: Session, moderator: User, reactor: User
    ):
        post = _make_post(db, owner=reactor, title="artwork")
        now = datetime.now(timezone.utc)
        _react(db, post=post, user=reactor, created_at=now - timedelta(minutes=2))
        anon = _react(
            db,
            post=post,
            user_ip="203.0.113.45",
            emoji="🔥",
            created_at=now - timedelta(minutes=1),
        )

        response = client.get(self.URL, headers=_auth(moderator))
        assert response.status_code == 200
        data = response.json()
        items = data["items"]
        assert len(items) == 2

        # Newest first: the anonymous reaction
        assert items[0]["id"] == anon.id
        assert items[0]["emoji"] == "🔥"
        assert items[0]["user_handle"] is None
        assert items[0]["user_public_sqid"] is None
        assert items[0]["anonymous_id"] == "…113.45"
        assert items[0]["post_title"] == "artwork"
        assert items[0]["post_public_sqid"] == post.public_sqid

        # Authenticated reaction
        assert items[1]["user_handle"] == reactor.handle
        assert items[1]["user_public_sqid"] == reactor.public_sqid
        assert items[1]["anonymous_id"] is None

        # The full IP must never appear in the response
        assert "203.0.113.45" not in response.text

    def test_include_anonymous_filter(
        self, client: TestClient, db: Session, moderator: User, reactor: User
    ):
        post = _make_post(db, owner=reactor, title="artwork")
        _react(db, post=post, user=reactor)
        _react(db, post=post, user_ip="203.0.113.45", emoji="🔥")

        response = client.get(
            self.URL, params={"include_anonymous": False}, headers=_auth(moderator)
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["user_handle"] == reactor.handle
        assert items[0]["anonymous_id"] is None

    def test_cursor_pagination(
        self, client: TestClient, db: Session, moderator: User, reactor: User
    ):
        post = _make_post(db, owner=reactor, title="artwork")
        now = datetime.now(timezone.utc)
        emojis = ["❤️", "🔥", "😍", "👍", "🎉"]
        created = [
            _react(
                db,
                post=post,
                user_ip=f"203.0.113.{i}",
                emoji=emojis[i],
                created_at=now - timedelta(minutes=5 - i),
            )
            for i in range(5)
        ]

        seen_ids: list[int] = []
        cursor = None
        for _ in range(3):
            params: dict = {"limit": 2}
            if cursor:
                params["cursor"] = cursor
            response = client.get(self.URL, params=params, headers=_auth(moderator))
            assert response.status_code == 200
            data = response.json()
            seen_ids.extend(item["id"] for item in data["items"])
            cursor = data["next_cursor"]
            if cursor is None:
                break

        assert cursor is None
        # All 5 reactions seen exactly once, newest first
        expected = [
            r.id for r in sorted(created, key=lambda r: r.created_at, reverse=True)
        ]
        assert seen_ids == expected

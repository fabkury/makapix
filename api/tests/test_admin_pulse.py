"""
Tests for GET /api/admin/pulse (moderator dashboard activity firehose) and the
truncate_ip display helper.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import Comment, CommentLike, Player, Post, PostFile, Reaction, User
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


def _make_post(
    db: Session, *, owner: User, title: str, created_at: datetime | None = None
) -> Post:
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
    if created_at is not None:
        post.created_at = created_at
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


def _comment(
    db: Session,
    *,
    post: Post,
    author: User | None = None,
    author_ip: str | None = None,
    body: str = "nice work",
    parent: Comment | None = None,
    created_at: datetime | None = None,
) -> Comment:
    c = Comment(
        post_id=post.id,
        author_id=author.id if author else None,
        author_ip=author_ip,
        parent_id=parent.id if parent else None,
        depth=1 if parent else 0,
        body=body,
    )
    if created_at is not None:
        c.created_at = created_at
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _like_comment(
    db: Session,
    *,
    comment: Comment,
    user: User,
    created_at: datetime | None = None,
) -> CommentLike:
    like = CommentLike(comment_id=comment.id, user_id=user.id)
    if created_at is not None:
        like.created_at = created_at
    db.add(like)
    db.commit()
    db.refresh(like)
    return like


def _make_player(
    db: Session,
    *,
    owner: User | None,
    name: str = "Bedroom player",
    status: str = "registered",
    registered_at: datetime | None = None,
) -> Player:
    player = Player(
        owner_id=owner.id if owner else None,
        name=name,
        device_model="MPX-64",
        registration_status=status,
        registered_at=registered_at,
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


@pytest.fixture
def moderator(db: Session) -> User:
    return _make_user(db, handle_prefix="mod", roles=["user", "moderator"])


@pytest.fixture
def member(db: Session) -> User:
    return _make_user(db, handle_prefix="member", roles=["user"])


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


class TestPulse:
    URL = "/admin/pulse"

    def test_requires_auth(self, client: TestClient):
        response = client.get(self.URL)
        assert response.status_code == 401

    def test_requires_moderator(self, client: TestClient, db: Session, member: User):
        response = client.get(self.URL, headers=_auth(member))
        assert response.status_code == 403

    def test_mixed_feed_newest_first(
        self, client: TestClient, db: Session, moderator: User, member: User
    ):
        now = datetime.now(timezone.utc)
        post = _make_post(
            db, owner=member, title="artwork", created_at=now - timedelta(minutes=10)
        )
        comment = _comment(
            db,
            post=post,
            author=member,
            body="lovely palette",
            created_at=now - timedelta(minutes=8),
        )
        reply = _comment(
            db,
            post=post,
            author=member,
            body="thanks!",
            parent=comment,
            created_at=now - timedelta(minutes=6),
        )
        like = _like_comment(
            db, comment=comment, user=member, created_at=now - timedelta(minutes=4)
        )
        reaction = _react(
            db,
            post=post,
            user=member,
            emoji="🔥",
            created_at=now - timedelta(minutes=2),
        )
        player = _make_player(
            db, owner=member, registered_at=now - timedelta(minutes=1)
        )

        response = client.get(self.URL, headers=_auth(moderator))
        assert response.status_code == 200
        items = response.json()["items"]
        # The fixture users' own profile events also land in the feed; their
        # timestamps (row insertion time) interleave unpredictably with the
        # backdated events, so assert them separately.
        profile_ids = {i["id"] for i in items if i["type"] == "profile"}
        assert {str(member.id), str(moderator.id)} <= profile_ids
        assert [(i["type"], i["id"]) for i in items if i["type"] != "profile"] == [
            ("player", str(player.id)),
            ("post_reaction", str(reaction.id)),
            ("comment_like", str(like.id)),
            ("comment", str(reply.id)),
            ("comment", str(comment.id)),
            ("post", str(post.id)),
        ]

        by_type = {}
        for item in items:
            by_type.setdefault(item["type"], item)

        p = by_type["post"]
        assert p["post_public_sqid"] == post.public_sqid
        assert p["post_title"] == "artwork"
        assert p["actor_handle"] == member.handle
        assert p["actor_public_sqid"] == member.public_sqid
        assert p["flags"] == []

        c = by_type["comment"]  # newest comment first: the reply
        assert c["is_reply"] is True
        assert c["comment_preview"] == "thanks!"
        assert c["post_public_sqid"] == post.public_sqid

        top_level = [i for i in items if i["type"] == "comment"][1]
        assert top_level["is_reply"] is False
        assert top_level["comment_preview"] == "lovely palette"

        cl = by_type["comment_like"]
        assert cl["comment_preview"] == "lovely palette"
        assert cl["post_public_sqid"] == post.public_sqid
        assert cl["actor_handle"] == member.handle

        r = by_type["post_reaction"]
        assert r["emoji"] == "🔥"
        assert r["post_public_sqid"] == post.public_sqid

        pl = by_type["player"]
        assert pl["player_name"] == "Bedroom player"
        assert pl["player_model"] == "MPX-64"
        assert pl["actor_handle"] == member.handle
        assert pl["actor_public_sqid"] == member.public_sqid
        assert pl["post_id"] is None

    def test_include_anonymous_filter(
        self, client: TestClient, db: Session, moderator: User, member: User
    ):
        post = _make_post(db, owner=member, title="artwork")
        _react(db, post=post, user=member)
        _react(db, post=post, user_ip="203.0.113.45", emoji="🔥")
        _comment(db, post=post, author=member, body="signed")
        _comment(db, post=post, author_ip="203.0.113.45", body="anon drive-by")

        response = client.get(self.URL, headers=_auth(moderator))
        assert response.status_code == 200
        items = response.json()["items"]
        anon = [i for i in items if i["anonymous_id"]]
        assert len(anon) == 2
        assert all(i["anonymous_id"] == "…113.45" for i in anon)
        # The full IP must never appear in the response
        assert "203.0.113.45" not in response.text

        response = client.get(
            self.URL, params={"include_anonymous": False}, headers=_auth(moderator)
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert all(i["anonymous_id"] is None for i in items)
        assert {i["type"] for i in items} == {
            "post",
            "post_reaction",
            "comment",
            "profile",
        }
        assert len([i for i in items if i["type"] == "post_reaction"]) == 1
        assert len([i for i in items if i["type"] == "comment"]) == 1

    def test_types_filter(
        self, client: TestClient, db: Session, moderator: User, member: User
    ):
        post = _make_post(db, owner=member, title="artwork")
        _react(db, post=post, user=member)
        _comment(db, post=post, author=member)

        response = client.get(
            self.URL, params={"types": "post_reaction"}, headers=_auth(moderator)
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["type"] == "post_reaction"

        response = client.get(
            self.URL, params={"types": "post,comment"}, headers=_auth(moderator)
        )
        assert response.status_code == 200
        assert {i["type"] for i in response.json()["items"]} == {"post", "comment"}

        response = client.get(
            self.URL, params={"types": "bogus"}, headers=_auth(moderator)
        )
        assert response.status_code == 400

    def test_hidden_content_flagged(
        self, client: TestClient, db: Session, moderator: User, member: User
    ):
        post = _make_post(db, owner=member, title="artwork")
        post.hidden_by_mod = True
        comment = _comment(db, post=post, author=member, body="[removed]")
        comment.hidden_by_mod = True
        db.commit()

        response = client.get(self.URL, headers=_auth(moderator))
        assert response.status_code == 200
        items = {i["type"]: i for i in response.json()["items"]}
        assert "hidden_by_mod" in items["post"]["flags"]
        assert "hidden_by_mod" in items["comment"]["flags"]

    def test_players_use_registered_at_and_exclude_pending(
        self, client: TestClient, db: Session, moderator: User, member: User
    ):
        now = datetime.now(timezone.utc)
        registered = _make_player(
            db, owner=member, registered_at=now - timedelta(minutes=1)
        )
        _make_player(db, owner=None, status="pending", registered_at=None)

        response = client.get(
            self.URL, params={"types": "player"}, headers=_auth(moderator)
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert [i["id"] for i in items] == [str(registered.id)]
        assert items[0]["created_at"] == registered.registered_at.isoformat().replace(
            "+00:00", "Z"
        )

    def test_profile_events(
        self, client: TestClient, db: Session, moderator: User, member: User
    ):
        now = datetime.now(timezone.utc)
        moderator.created_at = now - timedelta(minutes=5)
        ex_banned = _make_user(db, handle_prefix="exban", roles=["user"])
        ex_banned.created_at = now - timedelta(minutes=3)
        ex_banned.banned_until = now - timedelta(days=1)  # expired ban: no flag
        member.created_at = now - timedelta(minutes=1)
        member.hidden_by_mod = True
        member.deactivated = True
        member.banned_until = now + timedelta(days=7)
        db.commit()

        response = client.get(
            self.URL, params={"types": "profile"}, headers=_auth(moderator)
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert all(i["type"] == "profile" for i in items)

        # Newest first (other users, e.g. seed data, may also be present)
        ids = [i["id"] for i in items]
        assert (
            ids.index(str(member.id))
            < ids.index(str(ex_banned.id))
            < ids.index(str(moderator.id))
        )

        by_id = {i["id"]: i for i in items}
        m = by_id[str(member.id)]
        assert m["actor_handle"] == member.handle
        assert m["actor_public_sqid"] == member.public_sqid
        assert m["actor_avatar_url"] is None
        assert m["anonymous_id"] is None
        assert m["post_id"] is None
        assert set(m["flags"]) == {"hidden_by_mod", "deactivated", "banned"}

        assert by_id[str(ex_banned.id)]["flags"] == []
        assert by_id[str(moderator.id)]["flags"] == []

    def test_cursor_pagination_across_types(
        self, client: TestClient, db: Session, moderator: User, member: User
    ):
        now = datetime.now(timezone.utc)
        post_a = _make_post(
            db, owner=member, title="alpha", created_at=now - timedelta(minutes=9)
        )
        post_b = _make_post(
            db, owner=member, title="beta", created_at=now - timedelta(minutes=7)
        )
        comment = _comment(
            db, post=post_a, author=member, created_at=now - timedelta(minutes=5)
        )
        reaction = _react(
            db, post=post_b, user=member, created_at=now - timedelta(minutes=3)
        )
        player = _make_player(
            db, owner=member, registered_at=now - timedelta(minutes=1)
        )
        expected = [
            ("player", str(player.id)),
            ("post_reaction", str(reaction.id)),
            ("comment", str(comment.id)),
            ("post", str(post_b.id)),
            ("post", str(post_a.id)),
        ]

        seen: list[tuple[str, str]] = []
        cursor = None
        for _ in range(4):
            # Exclude profiles: the fixture users' registration timestamps
            # would interleave unpredictably with the backdated events.
            params: dict = {
                "limit": 2,
                "types": "post,comment,post_reaction,comment_like,player",
            }
            if cursor:
                params["cursor"] = cursor
            response = client.get(self.URL, params=params, headers=_auth(moderator))
            assert response.status_code == 200
            data = response.json()
            seen.extend((i["type"], i["id"]) for i in data["items"])
            cursor = data["next_cursor"]
            if cursor is None:
                break

        assert cursor is None
        assert seen == expected

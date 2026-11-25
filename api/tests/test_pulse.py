"""
Tests for GET /pulse — the public community-activity timeline (docs/pulse/).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    BadgeDefinition,
    BadgeGrant,
    PostLineage,
    ReputationHistory,
    User,
    UserBlock,
)
from tests.test_admin_pulse import (
    _auth,
    _comment,
    _make_player,
    _make_post,
    _make_user,
    _react,
)

URL = "/v1/pulse"


@pytest.fixture
def viewer(db: Session) -> User:
    return _make_user(db, handle_prefix="viewer", roles=["user"])


@pytest.fixture
def artist(db: Session) -> User:
    return _make_user(db, handle_prefix="artist", roles=["user"])


@pytest.fixture
def fan(db: Session) -> User:
    return _make_user(db, handle_prefix="fan", roles=["user"])


def _ago(**kwargs) -> datetime:
    return datetime.now(timezone.utc) - timedelta(**kwargs)


def _cards(client: TestClient, user: User, **params) -> list[dict]:
    response = client.get(URL, headers=_auth(user), params=params)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _of(cards: list[dict], kind: str) -> list[dict]:
    return [c for c in cards if c["kind"] == kind]


def test_requires_sign_in(client: TestClient):
    response = client.get(URL)
    assert response.status_code == 401
    assert "error" in response.json()


def test_empty(client: TestClient, viewer: User):
    response = client.get(URL, headers=_auth(viewer))
    assert response.json() == {"items": [], "next_cursor": None}


def test_likes_burst_is_one_card(
    client: TestClient, db: Session, viewer: User, artist: User, fan: User
):
    posts = [
        _make_post(db, owner=artist, title=f"art{i}", created_at=_ago(days=40))
        for i in range(8)
    ]
    for i, post in enumerate(posts):
        _react(db, post=post, user=fan, created_at=_ago(minutes=80 - i * 10))
    # A second emoji on an already-liked post is not a new event
    _react(db, post=posts[0], user=fan, emoji="🔥", created_at=_ago(minutes=1))

    (card,) = _cards(client, viewer)
    assert card["kind"] == "likes"
    assert card["actor"] == {
        "public_sqid": fan.public_sqid,
        "handle": fan.handle,
        "avatar_url": None,
    }
    assert card["count"] == 8
    assert [p["title"] for p in card["posts"]] == [f"art{i}" for i in range(7, 1, -1)]
    assert card["posts"][0]["owner"]["handle"] == artist.handle
    assert card["id"].startswith(f"likes:{fan.public_sqid}:")
    assert card["started_at"] < card["updated_at"]
    assert card["comments"] is None and card["player"] is None


def test_gap_starts_a_new_card_and_chain_extends(
    client: TestClient, db: Session, viewer: User, artist: User, fan: User
):
    # Events 5h apart chain into one card (span 10h > 6h); a 7h gap splits.
    hours = [30, 25, 20, 13, 12]
    for i, h in enumerate(hours):
        post = _make_post(db, owner=artist, title=f"p{i}", created_at=_ago(days=40))
        _react(db, post=post, user=fan, created_at=_ago(hours=h))

    cards = _of(_cards(client, viewer), "likes")
    assert [c["count"] for c in cards] == [2, 3]  # newest card first
    assert [p["title"] for p in cards[0]["posts"]] == ["p4", "p3"]


def test_card_id_is_stable_while_the_card_grows(
    client: TestClient, db: Session, viewer: User, artist: User, fan: User
):
    first = _make_post(db, owner=artist, title="first", created_at=_ago(days=40))
    _react(db, post=first, user=fan, created_at=_ago(hours=2))
    (before,) = _cards(client, viewer)

    second = _make_post(db, owner=artist, title="second", created_at=_ago(days=40))
    _react(db, post=second, user=fan, created_at=_ago(minutes=5))
    (after,) = _cards(client, viewer)

    assert after["id"] == before["id"]
    assert after["count"] == 2
    assert after["updated_at"] > before["updated_at"]


def test_posts_remixes_and_promoted(
    client: TestClient, db: Session, viewer: User, artist: User
):
    original = _make_post(db, owner=artist, title="original", created_at=_ago(hours=3))
    remix = _make_post(db, owner=artist, title="remix", created_at=_ago(hours=2))
    db.add(
        PostLineage(
            child_post_id=remix.id,
            parent_post_id=original.id,
            parent_sqid=original.public_sqid,
            position=0,
        )
    )
    original.promoted = True
    original.promoted_at = _ago(hours=1)
    db.commit()

    cards = _cards(client, viewer)
    assert [c["kind"] for c in cards] == ["promoted", "remixes", "posts"]
    assert [p["title"] for p in cards[0]["posts"]] == ["original"]
    assert [p["title"] for p in cards[1]["posts"]] == ["remix"]
    assert cards[1]["posts"][0]["parent_count"] == 1
    assert [p["title"] for p in cards[2]["posts"]] == ["original"]
    assert all(c["actor"]["handle"] == artist.handle for c in cards)


def test_bump_moves_the_post_event(
    client: TestClient, db: Session, viewer: User, artist: User
):
    post = _make_post(db, owner=artist, title="bumped", created_at=_ago(days=60))
    assert _cards(client, viewer) == []  # listed outside the window

    post.listed_at = _ago(minutes=3)
    db.commit()
    (card,) = _cards(client, viewer)
    assert card["kind"] == "posts" and card["count"] == 1


def test_comments_card(
    client: TestClient, db: Session, viewer: User, artist: User, fan: User
):
    post = _make_post(db, owner=artist, title="art", created_at=_ago(days=40))
    top = _comment(db, post=post, author=fan, body="x" * 200, created_at=_ago(hours=2))
    for i in range(3):
        _comment(
            db,
            post=post,
            author=fan,
            body=f"reply {i}",
            parent=top,
            created_at=_ago(minutes=30 - i),
        )
    _comment(db, post=post, author_ip="203.0.113.9", created_at=_ago(minutes=1))
    deleted = _comment(db, post=post, author=fan, created_at=_ago(minutes=2))
    deleted.deleted_by_owner = True
    db.commit()

    (card,) = _cards(client, viewer)
    assert card["kind"] == "comments"
    assert card["count"] == 4
    assert [c["preview"] for c in card["comments"]] == [
        "reply 2",
        "reply 1",
        "reply 0",
    ]
    assert all(c["is_reply"] for c in card["comments"])
    assert card["comments"][0]["post"]["public_sqid"] == post.public_sqid

    older = _cards(client, viewer, kinds="comments")[0]
    assert older["id"] == card["id"]


def test_comment_preview_is_truncated(
    client: TestClient, db: Session, viewer: User, artist: User, fan: User
):
    post = _make_post(db, owner=artist, title="art", created_at=_ago(days=40))
    _comment(db, post=post, author=fan, body="x" * 200, created_at=_ago(hours=1))
    (card,) = _cards(client, viewer)
    preview = card["comments"][0]["preview"]
    assert len(preview) == 140 and preview.endswith("…")
    assert card["comments"][0]["is_reply"] is False


def test_player_card_per_device_without_name(
    client: TestClient, db: Session, viewer: User, fan: User
):
    _make_player(db, owner=fan, name="Secret bedroom", registered_at=_ago(minutes=9))
    _make_player(db, owner=fan, name="Other", registered_at=_ago(minutes=8))
    _make_player(db, owner=None, status="pending", registered_at=None)

    cards = _cards(client, viewer)
    assert [c["kind"] for c in cards] == ["player", "player"]
    assert all(c["count"] == 1 for c in cards)
    assert cards[0]["player"] == {"device_model": "MPX-64"}
    assert "Secret bedroom" not in str(cards)


def test_badge_card(client: TestClient, db: Session, viewer: User, fan: User):
    db.add(
        BadgeDefinition(
            badge="pulse-test",
            label="Pulse Tester",
            icon_url_64="https://example.com/b64.png",
        )
    )
    db.add(BadgeGrant(user_id=fan.id, badge="pulse-test", granted_at=_ago(hours=1)))
    db.add(BadgeGrant(user_id=fan.id, badge="undefined", granted_at=_ago(minutes=5)))
    db.commit()

    (card,) = _cards(client, viewer)
    assert card["kind"] == "badge" and card["count"] == 2
    assert card["badges"] == [
        {"badge": "undefined", "label": "undefined", "icon_url_64": None},
        {
            "badge": "pulse-test",
            "label": "Pulse Tester",
            "icon_url_64": "https://example.com/b64.png",
        },
    ]


def test_reputation_positive_net_only_and_total_as_of_card(
    client: TestClient, db: Session, viewer: User, fan: User, artist: User
):
    # fan: +10 and +5 two days ago (one card), then +20 an hour ago.
    for delta, when in ((10, _ago(days=2)), (5, _ago(days=2, hours=-1))):
        db.add(ReputationHistory(user_id=fan.id, delta=delta, created_at=when))
    db.add(
        ReputationHistory(
            user_id=fan.id, delta=20, reason="private note", created_at=_ago(hours=1)
        )
    )
    fan.reputation = 135
    # artist: nets to zero → no card
    db.add(ReputationHistory(user_id=artist.id, delta=10, created_at=_ago(hours=2)))
    db.add(ReputationHistory(user_id=artist.id, delta=-10, created_at=_ago(hours=1)))
    db.commit()

    response = client.get(URL, headers=_auth(viewer))
    cards = response.json()["items"]
    assert [c["actor"]["handle"] for c in cards] == [fan.handle, fan.handle]
    assert cards[0]["reputation"] == {"delta": 20, "total": 135}
    assert cards[1]["reputation"] == {"delta": 15, "total": 115}
    assert "private note" not in response.text


def test_visibility_rules(
    client: TestClient, db: Session, viewer: User, artist: User, fan: User
):
    def liked(title: str, **flags) -> None:
        post = _make_post(db, owner=artist, title=title, created_at=_ago(days=40))
        for name, value in flags.items():
            setattr(post, name, value)
        db.commit()
        _react(db, post=post, user=fan, created_at=_ago(minutes=30))

    liked("ok")
    liked("pending", public_visibility=False)
    liked("hidden_mod", hidden_by_mod=True)
    liked("hidden_user", hidden_by_user=True)
    liked("deleted", deleted_by_user=True)
    liked("nonconformant", non_conformant=True)
    liked("invisible", visible=False)
    liked("monitored", hashtags=["nsfw"])

    # Not activity: an anonymous like, and a like on one's own artwork
    ok = _make_post(db, owner=artist, title="own", created_at=_ago(days=40))
    _react(db, post=ok, user_ip="203.0.113.7", created_at=_ago(minutes=5))
    _react(db, post=ok, user=artist, created_at=_ago(minutes=5))

    (card,) = _cards(client, viewer)
    assert card["count"] == 1
    assert [p["title"] for p in card["posts"]] == ["ok"]

    viewer.approved_hashtags = ["nsfw"]
    db.commit()
    (card,) = _cards(client, viewer)
    assert {p["title"] for p in card["posts"]} == {"ok", "monitored"}


@pytest.mark.parametrize(
    "flag,value",
    [
        ("deactivated", True),
        ("hidden_by_mod", True),
        ("hidden_by_user", True),
        ("non_conformant", True),
        ("banned_until", datetime(2999, 1, 1, tzinfo=timezone.utc)),
    ],
)
def test_hidden_actors_have_no_cards(
    client: TestClient, db: Session, viewer: User, artist: User, fan: User, flag, value
):
    post = _make_post(db, owner=artist, title="art", created_at=_ago(days=40))
    _react(db, post=post, user=fan, created_at=_ago(minutes=30))
    assert len(_cards(client, viewer)) == 1

    setattr(fan, flag, value)
    db.commit()
    assert _cards(client, viewer) == []


def test_expired_ban_is_visible_again(
    client: TestClient, db: Session, viewer: User, artist: User, fan: User
):
    post = _make_post(db, owner=artist, title="art", created_at=_ago(days=40))
    _react(db, post=post, user=fan, created_at=_ago(minutes=30))
    fan.banned_until = _ago(days=1)
    db.commit()
    assert len(_cards(client, viewer)) == 1


def test_blocks(client: TestClient, db: Session, viewer: User, artist: User, fan: User):
    other = _make_user(db, handle_prefix="other", roles=["user"])
    by_artist = _make_post(db, owner=artist, title="blocked", created_at=_ago(hours=1))
    by_other = _make_post(db, owner=other, title="fine", created_at=_ago(days=40))
    _react(db, post=by_artist, user=fan, created_at=_ago(minutes=30))
    _react(db, post=by_other, user=fan, created_at=_ago(minutes=20))
    _comment(db, post=by_artist, author=fan, created_at=_ago(minutes=10))

    assert {c["kind"] for c in _cards(client, viewer)} == {
        "posts",
        "likes",
        "comments",
    }

    db.add(UserBlock(blocker_id=viewer.id, blocked_id=artist.id))
    db.commit()
    (card,) = _cards(client, viewer)  # artist's card and content are gone
    assert card["kind"] == "likes" and card["count"] == 1
    assert [p["title"] for p in card["posts"]] == ["fine"]

    # One-way: the blocked artist still sees everything
    assert len(_cards(client, artist)) == 3


def test_window_is_30_days(
    client: TestClient, db: Session, viewer: User, artist: User, fan: User
):
    post = _make_post(db, owner=artist, title="old", created_at=_ago(days=31))
    _react(db, post=post, user=fan, created_at=_ago(days=30, hours=1))
    assert _cards(client, viewer) == []


def test_paging_walks_every_card_once(
    client: TestClient, db: Session, viewer: User, artist: User
):
    post = _make_post(db, owner=artist, title="art", created_at=_ago(days=40))
    fans = [_make_user(db, handle_prefix=f"f{i}", roles=["user"]) for i in range(7)]
    same_time = _ago(hours=1)
    for i, fan in enumerate(fans):
        # Three cards share one timestamp, to exercise the id tiebreaker
        when = same_time if i < 3 else _ago(hours=2 + i)
        _react(db, post=post, user=fan, created_at=when)

    seen: list[str] = []
    cursor = None
    for _ in range(10):
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        response = client.get(URL, headers=_auth(viewer), params=params)
        body = response.json()
        assert len(body["items"]) <= 2
        seen += [c["id"] for c in body["items"]]
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == 7 and len(set(seen)) == 7

    everything = [c["id"] for c in _cards(client, viewer, limit=50)]
    assert seen == everything


def test_kinds_filter_and_bad_input(
    client: TestClient, db: Session, viewer: User, artist: User, fan: User
):
    post = _make_post(db, owner=artist, title="art", created_at=_ago(hours=1))
    _react(db, post=post, user=fan, created_at=_ago(minutes=30))

    assert {c["kind"] for c in _cards(client, viewer)} == {"posts", "likes"}
    assert [c["kind"] for c in _cards(client, viewer, kinds="likes,joined")] == [
        "likes"
    ]
    assert _cards(client, viewer, kinds="joined") == []
    assert len(_cards(client, viewer, cursor="not-a-cursor")) == 2
    assert (
        client.get(URL, headers=_auth(viewer), params={"limit": 51}).status_code == 422
    )


def test_own_activity_and_like_state(
    client: TestClient, db: Session, viewer: User, artist: User
):
    post = _make_post(db, owner=artist, title="art", created_at=_ago(days=40))
    _react(db, post=post, user=viewer, emoji="👍", created_at=_ago(minutes=3))

    (card,) = _cards(client, viewer)
    assert card["actor"]["handle"] == viewer.handle
    assert card["posts"][0]["user_has_liked"] is True
    assert card["posts"][0]["reaction_count"] == 1

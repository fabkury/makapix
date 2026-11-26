"""The "Displayed on" list (docs/impression-list/).

Rows are members, not devices; device models only, calendar days only; one
account switch hides a member from everyone; signed-in only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import models
from app.auth import create_access_token
from app.services import impression_list
from app.sqids_config import encode_id

NOW = datetime.now(timezone.utc)


def _user(db, prefix: str, **kw) -> models.User:
    user = models.User(
        handle=f"{prefix}_{uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:8]}@e.com",
        **kw,
    )
    db.add(user)
    db.flush()
    user.public_sqid = encode_id(user.id)
    db.commit()
    return user


@pytest.fixture
def author(db):
    return _user(db, "author")


@pytest.fixture
def viewer(db):
    return _user(db, "viewer")


@pytest.fixture
def member(db):
    return _user(db, "member")


@pytest.fixture
def post(db, author):
    p = models.Post(
        owner_id=author.id, title="t", storage_key=uuid.uuid4(), kind="artwork"
    )
    db.add(p)
    db.flush()
    p.public_sqid = encode_id(p.id)
    db.commit()
    return p


def _player(db, owner, model="p3a", name="Bedroom") -> models.Player:
    p = models.Player(
        player_key=uuid.uuid4(),
        owner_id=owner.id,
        device_model=model,
        firmware_version="1.0.0",
        registration_status="registered",
        name=name,
    )
    db.add(p)
    db.commit()
    return p


def _show(db, post, user, *, player=None, device_type="player", at=NOW):
    impression_list.record_showing(
        db,
        post_id=post.id,
        user_id=user.id,
        shown_at=at,
        device_type=device_type,
        player_id=player.id if player else None,
    )
    db.commit()


def _get(client, post, viewer, **params):
    return client.get(
        f"/post/{post.id}/impression-users",
        params=params,
        headers={"Authorization": f"Bearer {create_access_token(viewer)}"},
    )


def test_signed_out_is_refused(client, post):
    assert client.get(f"/post/{post.id}/impression-users").status_code == 401


def test_one_row_per_member_with_models_count_and_day(client, db, post, viewer, member):
    _show(db, post, member, player=_player(db, member, "p3a", "Bedroom"))
    _show(db, post, member, player=_player(db, member, "Pixel Jukebox", "Shop"))
    _show(db, post, member, player=_player(db, member, "p3a", "Kitchen"))
    _show(db, post, member, device_type="desktop")

    resp = _get(client, post, viewer)
    assert resp.status_code == 200
    body = resp.json()
    assert body["next_cursor"] is None
    assert body["items"] == [
        {
            "user_handle": member.handle,
            "user_avatar_url": None,
            "user_public_sqid": member.public_sqid,
            "device_models": ["p3a", "Pixel Jukebox"],
            "web_player": True,
            "app": False,
            "count": 4,
            "last_shown_on": NOW.date().isoformat(),
        }
    ]
    # No player name, id or key, and no time of day, anywhere in the payload.
    assert "Bedroom" not in resp.text and "Kitchen" not in resp.text
    assert "T" not in body["items"][0]["last_shown_on"]


def test_app_showing_is_tagged_app(client, db, post, viewer, member):
    _show(db, post, member, device_type="app_android")
    item = _get(client, post, viewer).json()["items"][0]
    assert (item["app"], item["web_player"], item["device_models"]) == (True, False, [])


def test_opt_out_hides_from_everyone_and_opt_in_restores(
    client, db, post, viewer, author, member
):
    _show(db, post, member, player=_player(db, member))
    token = {"Authorization": f"Bearer {create_access_token(member)}"}

    resp = client.patch(
        f"/user/{member.user_key}",
        json={"show_in_impression_lists": False},
        headers=token,
    )
    assert resp.status_code == 200
    assert resp.json()["show_in_impression_lists"] is False

    moderator = _user(db, "mod", roles=["user", "moderator"])
    for who in (viewer, author, moderator, member):
        assert _get(client, post, who).json()["items"] == []

    # Recording continues while hidden, so opting back in restores the row.
    _show(db, post, member, device_type="desktop")
    client.patch(
        f"/user/{member.user_key}",
        json={"show_in_impression_lists": True},
        headers=token,
    )
    assert _get(client, post, viewer).json()["items"][0]["count"] == 2


def test_blocked_hidden_banned_and_deactivated_members_are_left_out(
    client, db, post, viewer, member
):
    blocked = _user(db, "blocked")
    db.add(models.UserBlock(blocker_id=viewer.id, blocked_id=blocked.id))
    others = [
        blocked,
        _user(db, "hid", hidden_by_user=True),
        _user(db, "modhid", hidden_by_mod=True),
        _user(db, "gone", deactivated=True),
        _user(db, "ban", banned_until=NOW + timedelta(days=1)),
    ]
    for u in [member, *others]:
        _show(db, post, u, device_type="desktop")

    handles = [i["user_handle"] for i in _get(client, post, viewer).json()["items"]]
    assert handles == [member.handle]


def test_author_is_never_listed(client, db, post, viewer, author):
    _show(db, post, author, device_type="desktop")
    assert _get(client, post, viewer).json()["items"] == []


def test_hidden_artwork_follows_its_own_access_rules(client, db, post, viewer, member):
    _show(db, post, member, device_type="desktop")
    post.hidden_by_user = True
    db.commit()
    assert _get(client, post, viewer).status_code == 404


def test_recent_first_and_paginated(client, db, post, viewer):
    members = [_user(db, f"m{i}") for i in range(5)]
    for i, m in enumerate(members):
        _show(db, post, m, device_type="desktop", at=NOW - timedelta(days=i))

    first = _get(client, post, viewer, limit=2).json()
    assert [i["user_handle"] for i in first["items"]] == [
        members[0].handle,
        members[1].handle,
    ]
    seen = list(first["items"])
    cursor = first["next_cursor"]
    while cursor:
        page = _get(client, post, viewer, limit=2, cursor=cursor).json()
        seen += page["items"]
        cursor = page["next_cursor"]
    assert [i["user_handle"] for i in seen] == [m.handle for m in members]


def test_forgotten_90_days_after_the_last_showing(client, db, post, viewer, member):
    old = _user(db, "old")
    _show(db, post, old, device_type="desktop", at=NOW - timedelta(days=91))
    _show(db, post, member, device_type="desktop", at=NOW - timedelta(days=89))

    # Already out of the list before the nightly cleanup runs.
    handles = [i["user_handle"] for i in _get(client, post, viewer).json()["items"]]
    assert handles == [member.handle]

    assert impression_list.delete_expired(db) == 1
    db.commit()
    assert db.query(models.PostImpressionUser).count() == 1


def test_write_view_event_feeds_the_list(db, post, member, monkeypatch):
    """Impressions with a member behind them upsert the row; Views and
    anonymous Impressions do not."""
    from app import tasks

    monkeypatch.setattr("app.db.SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    player = _player(db, member, "p3a")

    def event(view_type, user, **extra):
        return {
            "post_id": str(post.id),
            "viewer_user_id": str(user.id) if user else None,
            "viewer_ip_hash": "h",
            "device_type": "desktop",
            "view_source": "web",
            "view_type": view_type,
            "created_at": NOW.isoformat(),
            **extra,
        }

    tasks.write_view_event.run(event("impression", member))
    tasks.write_view_event.run(
        event(
            "impression",
            member,
            device_type="player",
            view_source="player",
            player_id=str(player.id),
            also_view=True,
        )
    )
    tasks.write_view_event.run(event("view", member))
    tasks.write_view_event.run(event("impression", None))

    rows = db.query(models.PostImpressionUser).all()
    assert len(rows) == 1
    row = rows[0]
    assert (row.user_id, row.shown_count) == (member.id, 2)
    assert (row.device_models, row.web_player, row.app) == (["p3a"], True, False)

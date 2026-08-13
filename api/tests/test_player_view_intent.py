"""p3a view-intent mapping tests (docs/artwork-views/ D6).

intent="artwork" -> Artwork View (owner is the Visitor, once per artwork per
UTC day); intent="channel" -> Impression (undeduped volume). Server-side
mapping only — no firmware change.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app import models
from app.player_protocol.schemas import P3AViewEvent
from app.services import player_views


@pytest.fixture
def owner(db):
    user = models.User(
        handle=f"po_{uuid.uuid4().hex[:6]}", email=f"{uuid.uuid4().hex[:6]}@e.com"
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def other(db):
    user = models.User(
        handle=f"px_{uuid.uuid4().hex[:6]}", email=f"{uuid.uuid4().hex[:6]}@e.com"
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture
def player(db, owner):
    p = models.Player(
        player_key=uuid.uuid4(),
        owner_id=owner.id,
        device_model="TestDevice",
        firmware_version="1.1.0",
        registration_status="registered",
        name="Shelf",
    )
    db.add(p)
    db.commit()
    return p


@pytest.fixture
def post(db, other):
    p = models.Post(
        owner_id=other.id, title="t", storage_key=uuid.uuid4(), kind="artwork"
    )
    db.add(p)
    db.commit()
    return p


@pytest.fixture(autouse=True)
def _no_player_rate_limit(monkeypatch):
    """Bypass the 1/5s player rate limit so intent semantics are testable."""
    from app.services import rate_limit

    monkeypatch.setattr(
        rate_limit, "check_player_view_rate_limit", lambda key: (True, None)
    )


def _p3a_event(player, post, intent, ts=None):
    return P3AViewEvent(
        post_id=post.id,
        timestamp=ts or datetime.now(timezone.utc).isoformat(),
        timezone="",
        intent=intent,
        play_order=0,
        channel="artwork" if intent == "artwork" else "all",
        player_key=str(player.player_key),
    )


@pytest.fixture
def dispatched(monkeypatch):
    calls: list[dict] = []
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.tasks.write_view_event",
        SimpleNamespace(delay=lambda data: calls.append(data)),
    )
    return calls


def test_artwork_intent_is_a_view(db, player, post, dispatched):
    result = player_views.record_view_event(
        db=db, player=player, event=_p3a_event(player, post, "artwork")
    )
    assert result.status == player_views.RECORDED
    assert dispatched[0]["view_type"] == "view"
    assert dispatched[0]["viewer_user_id"] == str(player.owner_id)


def test_artwork_intent_dedupes_per_owner_per_day(db, player, post, dispatched):
    r1 = player_views.record_view_event(
        db=db, player=player, event=_p3a_event(player, post, "artwork")
    )
    assert r1.status == player_views.RECORDED
    # Second explicit view of the same artwork, same UTC day (new timestamp
    # so the 60s retransmit dedup does not trigger).
    r2 = player_views.record_view_event(
        db=db,
        player=player,
        event=_p3a_event(player, post, "artwork", ts="2099-01-01T00:00:01Z"),
    )
    assert r2.status == player_views.DUPLICATE
    assert len(dispatched) == 1


def test_channel_intent_is_an_undeduped_impression(db, player, post, dispatched):
    for i in range(3):
        result = player_views.record_view_event(
            db=db,
            player=player,
            event=_p3a_event(player, post, "channel", ts=f"2099-01-01T00:00:0{i}Z"),
        )
        assert result.status == player_views.RECORDED
    assert len(dispatched) == 3
    assert all(d["view_type"] == "impression" for d in dispatched)


def test_owner_web_view_and_player_view_share_visitor_identity(
    db, client, owner, player, post, dispatched
):
    """The player's owner is the Visitor: their web View and their player's
    View of the same artwork on the same day collapse to one."""
    from app.auth import create_access_token

    resp = client.post(
        f"/post/{post.id}/view",
        headers={
            "Authorization": f"Bearer {create_access_token(owner)}",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Firefox/128.0",
        },
    )
    assert resp.status_code == 201

    result = player_views.record_view_event(
        db=db, player=player, event=_p3a_event(player, post, "artwork")
    )
    assert result.status == player_views.DUPLICATE


def test_self_view_still_excluded(db, owner, player, dispatched):
    own_post = models.Post(
        owner_id=owner.id, title="mine", storage_key=uuid.uuid4(), kind="artwork"
    )
    db.add(own_post)
    db.commit()
    result = player_views.record_view_event(
        db=db, player=player, event=_p3a_event(player, own_post, "artwork")
    )
    assert result.status == player_views.SELF_VIEW
    assert dispatched == []

"""p3a view-intent mapping tests (docs/artwork-views/ D6).

Every showing is an Impression (undeduped volume). intent="artwork" is ALSO an
Artwork View (owner is the Visitor, once per artwork per UTC day) — D18.
Server-side mapping only — no firmware change.
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
    from app import tasks

    monkeypatch.setattr(
        tasks.write_view_event, "delay", lambda data: calls.append(data)
    )
    return calls


def test_artwork_intent_is_a_view_and_an_impression(db, player, post, dispatched):
    """D18: one event, flagged to write the paired View row too."""
    result = player_views.record_view_event(
        db=db, player=player, event=_p3a_event(player, post, "artwork")
    )
    assert result.status == player_views.RECORDED
    assert len(dispatched) == 1
    assert dispatched[0]["view_type"] == "impression"
    assert dispatched[0]["also_view"] is True
    assert dispatched[0]["viewer_user_id"] == str(player.owner_id)


def test_repeat_artwork_intent_is_an_impression_only(db, player, post, dispatched):
    """The View dedupes per owner per day; the Impression never does (D18)."""
    r1 = player_views.record_view_event(
        db=db, player=player, event=_p3a_event(player, post, "artwork")
    )
    assert r1.status == player_views.RECORDED
    # Second explicit showing of the same artwork, same UTC day (new timestamp
    # so the 60s retransmit dedup does not trigger).
    r2 = player_views.record_view_event(
        db=db,
        player=player,
        event=_p3a_event(player, post, "artwork", ts="2099-01-01T00:00:01Z"),
    )
    assert r2.status == player_views.RECORDED
    assert [d["also_view"] for d in dispatched] == [True, False]
    assert all(d["view_type"] == "impression" for d in dispatched)


def _write(db, monkeypatch, data):
    """Run the write_view_event task body against the test session."""
    from app import tasks

    monkeypatch.setattr("app.db.SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    tasks.write_view_event.run(data)


def test_explicit_showing_bumps_both_counters(
    db, player, post, dispatched, monkeypatch
):
    for ts in ("2099-01-01T00:00:01Z", "2099-01-01T00:00:02Z"):
        player_views.record_view_event(
            db=db, player=player, event=_p3a_event(player, post, "artwork", ts=ts)
        )
    for data in dispatched:
        _write(db, monkeypatch, data)
    db.refresh(post)
    assert post.view_count == 1
    assert post.impression_count == 2
    rows = db.query(models.ViewEvent).filter(models.ViewEvent.post_id == post.id).all()
    assert sorted(r.view_type for r in rows) == ["impression", "impression", "view"]
    assert all(r.player_id == player.id for r in rows)

    # The nightly recompute agrees with the live increments.
    from app.services.view_metrics import (
        recompute_post_impression_counts,
        recompute_post_view_counts,
    )

    recompute_post_view_counts(db, [post.id])
    recompute_post_impression_counts(db, [post.id])
    db.commit()
    db.refresh(post)
    assert (post.view_count, post.impression_count) == (1, 2)


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
    # Still an Impression (D18), but not a second Artwork View.
    assert result.status == player_views.RECORDED
    assert dispatched[-1]["view_type"] == "impression"
    assert dispatched[-1]["also_view"] is False


def test_self_view_still_excluded(db, owner, player, dispatched):
    own_post = models.Post(
        owner_id=owner.id, title="mine", storage_key=uuid.uuid4(), kind="artwork"
    )
    db.add(own_post)
    db.commit()
    for intent in ("artwork", "channel"):
        result = player_views.record_view_event(
            db=db, player=player, event=_p3a_event(player, own_post, intent)
        )
        assert result.status == player_views.SELF_VIEW
    assert dispatched == []

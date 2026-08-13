"""Watermark rollup + recompute tests (docs/artwork-views/ D10/D11/D12).

The rollup is the single owner of view_events: complete UTC days past the
watermark roll into post_stats_daily (Views deduped per Visitor per day,
Impressions counted) and the site-level player slice of site_stats_daily;
posts.view_count is reconciled; deletion is watermark- AND retention-gated;
everything is one transaction.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app import models


@pytest.fixture()
def owner(db):
    user = models.User(
        handle=f"ro_{uuid.uuid4().hex[:6]}", email=f"{uuid.uuid4().hex[:6]}@e.com"
    )
    db.add(user)
    db.commit()
    return user


@pytest.fixture()
def post(db, owner):
    p = models.Post(
        owner_id=owner.id, title="t", storage_key=uuid.uuid4(), kind="artwork"
    )
    db.add(p)
    db.commit()
    return p


def _event(
    db,
    post_id,
    when,
    *,
    view_type="view",
    ip=None,
    user_id=None,
    device="desktop",
    country=None,
    player_id=None,
):
    db.add(
        models.ViewEvent(
            post_id=post_id,
            viewer_user_id=user_id,
            viewer_ip_hash=ip or uuid.uuid4().hex,
            country_code=country,
            device_type=device,
            view_source="player" if device == "player" else "web",
            view_type=view_type,
            player_id=player_id,
            created_at=when,
        )
    )


def _utc_day(days_ago: int, hour: int = 12) -> datetime:
    day = datetime.now(timezone.utc).date() - timedelta(days=days_ago)
    return datetime.combine(day, time(hour=hour), tzinfo=timezone.utc)


def _run(db):
    from app.tasks import rollup_view_events

    result = rollup_view_events.apply().get()
    assert result["status"] == "success"
    db.expire_all()
    return result


def test_rollup_dedupes_views_and_counts_impressions(db, post):
    from app.services.view_metrics import get_view_watermark, set_view_watermark

    set_view_watermark(db, datetime.now(timezone.utc).date() - timedelta(days=3))
    # Day -2: one visitor views twice (dedup -> 1), another once; 2 impressions.
    _event(db, post.id, _utc_day(2, 9), ip="a" * 64, country="US")
    _event(db, post.id, _utc_day(2, 10), ip="a" * 64, country="US")
    _event(db, post.id, _utc_day(2, 11), ip="b" * 64, country="FR", user_id=None)
    _event(db, post.id, _utc_day(2, 12), view_type="impression")
    _event(db, post.id, _utc_day(2, 13), view_type="impression")
    # Today: one view — must stay raw (day not complete).
    _event(db, post.id, _utc_day(0), ip="c" * 64)
    db.commit()

    _run(db)

    rows = (
        db.query(models.PostStatsDaily)
        .filter(models.PostStatsDaily.post_id == post.id)
        .all()
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.total_views == 2  # deduped
    assert row.unique_viewers == 2
    assert row.total_impressions == 2
    assert row.views_by_type == {"view": 2, "impression": 2}
    assert row.views_by_country == {"US": 1, "FR": 1}  # one per visitor

    assert get_view_watermark(db) == datetime.now(timezone.utc).date() - timedelta(
        days=1
    )
    # Nothing deleted: day -2 rows are rolled but inside the 7-day retention,
    # today's row is post-watermark. All 6 events survive.
    assert (
        db.query(models.ViewEvent).filter(models.ViewEvent.post_id == post.id).count()
        == 6
    )
    # view_count reconciled: 2 rolled + 1 raw post-watermark.
    db.refresh(post)
    assert post.view_count == 3


def test_rollup_maps_legacy_view_types(db, post):
    from app.services.view_metrics import set_view_watermark

    set_view_watermark(db, datetime.now(timezone.utc).date() - timedelta(days=3))
    _event(db, post.id, _utc_day(2, 9), view_type="intentional", ip="a" * 64)
    _event(db, post.id, _utc_day(2, 10), view_type="listing")
    _event(db, post.id, _utc_day(2, 11), view_type="widget")
    db.commit()

    _run(db)

    row = (
        db.query(models.PostStatsDaily)
        .filter(models.PostStatsDaily.post_id == post.id)
        .one()
    )
    assert row.views_by_type == {"view": 1, "impression": 2}


def test_rollup_writes_site_player_slice(db, post, owner):
    from app.services.view_metrics import set_view_watermark

    player = models.Player(
        player_key=uuid.uuid4(),
        owner_id=owner.id,
        device_model="TestDevice",
        firmware_version="1.0.0",
        registration_status="registered",
        name="Kitchen",
    )
    db.add(player)
    db.commit()

    set_view_watermark(db, datetime.now(timezone.utc).date() - timedelta(days=3))
    _event(db, post.id, _utc_day(2, 9), device="player", player_id=player.id)
    _event(
        db,
        post.id,
        _utc_day(2, 10),
        device="player",
        player_id=player.id,
        view_type="impression",
    )
    db.commit()

    _run(db)

    day = datetime.now(timezone.utc).date() - timedelta(days=2)
    site_row = (
        db.query(models.SiteStatsDaily).filter(models.SiteStatsDaily.date == day).one()
    )
    assert site_row.total_player_views == 2  # views + impressions = "plays"
    assert site_row.active_players == 1
    assert site_row.views_by_player == {"Kitchen": 2}


def test_rollup_merges_into_legacy_partial_row(db, post):
    """Migration transition: the old pipeline left partially-rolled daily
    rows; the new rollup must MERGE the un-rolled remainder (and JSON
    columns must be reassigned as new objects — appraisal A6)."""
    from app.services.view_metrics import set_view_watermark

    day = datetime.now(timezone.utc).date() - timedelta(days=2)
    db.add(
        models.PostStatsDaily(
            post_id=post.id,
            date=day,
            total_views=2,
            unique_viewers=2,
            views_by_country={"US": 2},
            views_by_device={"desktop": 2},
            views_by_type={"intentional": 2},
        )
    )
    set_view_watermark(db, day - timedelta(days=1))
    _event(db, post.id, _utc_day(2, 20), ip="z" * 64, country="FR")
    db.commit()

    _run(db)

    row = (
        db.query(models.PostStatsDaily)
        .filter(
            models.PostStatsDaily.post_id == post.id,
            models.PostStatsDaily.date == day,
        )
        .one()
    )
    assert row.total_views == 3
    assert row.views_by_country == {"US": 2, "FR": 1}
    assert row.views_by_type == {"intentional": 2, "view": 1}
    db.refresh(post)
    assert post.view_count == 3  # 2 legacy intentional + 1 new view


def test_rollup_retention_delete_is_watermark_and_age_gated(db, post):
    from app.services.view_metrics import set_view_watermark

    set_view_watermark(db, datetime.now(timezone.utc).date() - timedelta(days=12))
    _event(db, post.id, _utc_day(10), ip="a" * 64)  # rolled AND >7d -> deleted
    _event(db, post.id, _utc_day(2), ip="b" * 64)  # rolled but <7d -> retained
    db.commit()

    result = _run(db)
    assert result["deleted"] == 1

    remaining = (
        db.query(models.ViewEvent).filter(models.ViewEvent.post_id == post.id).all()
    )
    assert len(remaining) == 1
    # The retained (rolled) raw row must NOT be double-counted anywhere:
    db.refresh(post)
    assert post.view_count == 2  # both days rolled, one View each


def test_rollup_failure_leaves_everything_intact(db, post, monkeypatch):
    from app.services.view_metrics import get_view_watermark, set_view_watermark

    wm_before = datetime.now(timezone.utc).date() - timedelta(days=3)
    set_view_watermark(db, wm_before)
    _event(db, post.id, _utc_day(2), ip="a" * 64)
    db.commit()

    from app.services import view_metrics

    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(view_metrics, "canonical_view_type", boom)

    from app.tasks import rollup_view_events

    with pytest.raises(Exception):
        rollup_view_events.apply(throw=True).get()

    db.expire_all()
    assert get_view_watermark(db) == wm_before  # not advanced
    assert db.query(models.ViewEvent).count() == 1  # nothing deleted
    assert db.query(models.PostStatsDaily).count() == 0  # nothing rolled


def test_rollup_rerun_is_idempotent(db, post):
    from app.services.view_metrics import set_view_watermark

    set_view_watermark(db, datetime.now(timezone.utc).date() - timedelta(days=3))
    _event(db, post.id, _utc_day(2), ip="a" * 64)
    db.commit()

    _run(db)
    first = (
        db.query(models.PostStatsDaily)
        .filter(models.PostStatsDaily.post_id == post.id)
        .one()
    )
    assert first.total_views == 1

    result = _run(db)  # watermark already at yesterday -> no-op
    assert result["days"] == 0
    again = (
        db.query(models.PostStatsDaily)
        .filter(models.PostStatsDaily.post_id == post.id)
        .one()
    )
    assert again.total_views == 1


def test_rollup_self_seeds_watermark(db, post):
    from app.services.view_metrics import get_view_watermark

    assert get_view_watermark(db) is None
    _event(db, post.id, _utc_day(10), ip="a" * 64)
    db.commit()

    _run(db)

    assert get_view_watermark(db) == datetime.now(timezone.utc).date() - timedelta(
        days=1
    )
    assert (
        db.query(models.PostStatsDaily)
        .filter(models.PostStatsDaily.post_id == post.id)
        .one()
        .total_views
        == 1
    )


# ---------------------------------------------------------------------------
# Backfill callables (migration logic, D12)
# ---------------------------------------------------------------------------


def test_recompute_and_seed_callables(db, post):
    from app.services.view_metrics import (
        get_view_watermark,
        recompute_post_view_counts,
        seed_view_watermark,
    )

    # Historical daily rows with legacy breakdowns + surviving raw events.
    db.add(
        models.PostStatsDaily(
            post_id=post.id,
            date=datetime.now(timezone.utc).date() - timedelta(days=20),
            total_views=10,
            unique_viewers=5,
            views_by_type={"intentional": 7, "listing": 3},
        )
    )
    _event(db, post.id, _utc_day(3, 9), view_type="intentional", ip="a" * 64)
    _event(db, post.id, _utc_day(3, 10), view_type="intentional", ip="a" * 64)
    _event(db, post.id, _utc_day(2), view_type="listing")
    db.commit()

    watermark = seed_view_watermark(db)
    updated = recompute_post_view_counts(db)
    db.commit()
    db.expire_all()

    # Seed = oldest raw UTC day - 1.
    assert watermark == datetime.now(timezone.utc).date() - timedelta(days=4)
    assert get_view_watermark(db) == watermark
    assert updated >= 1
    # 7 historical intentional + 1 deduped raw view-day (2 events, same
    # visitor, same day); listings never count.
    db.refresh(post)
    assert post.view_count == 8


def test_seed_never_rewinds_existing_watermark(db, post):
    from app.services.view_metrics import (
        get_view_watermark,
        seed_view_watermark,
        set_view_watermark,
    )

    wm = datetime.now(timezone.utc).date() - timedelta(days=1)
    set_view_watermark(db, wm)
    db.commit()

    _event(db, post.id, _utc_day(10), ip="a" * 64)
    db.commit()

    effective = seed_view_watermark(db)
    db.commit()
    assert effective == wm
    assert get_view_watermark(db) == wm


# ---------------------------------------------------------------------------
# A7 heritage: schedule + failure semantics
# ---------------------------------------------------------------------------


def test_cleanup_old_view_events_is_not_scheduled():
    from app.tasks import celery_app

    assert "cleanup-old-view-events" not in celery_app.conf.beat_schedule


def test_manual_cleanup_respects_watermark(db, post):
    from app.services.view_metrics import set_view_watermark
    from app.tasks import cleanup_old_view_events

    set_view_watermark(db, datetime.now(timezone.utc).date() - timedelta(days=7))
    _event(db, post.id, _utc_day(8), ip="a" * 64)  # <= wm AND >7d -> deletable
    _event(db, post.id, _utc_day(6), ip="b" * 64)  # after wm -> retained
    db.commit()

    result = cleanup_old_view_events.apply().get()
    assert result["status"] == "success"
    assert result["deleted"] == 1
    db.expire_all()
    assert db.query(models.ViewEvent).count() == 1

"""Regression tests for A6/A7 in the view-events rollup.

A6: merging a second batch into an existing post_stats_daily row rebuilt each
    JSON breakdown dict IN PLACE and reassigned the same object, so SQLAlchemy
    saw no change and never persisted it — every breakdown after the first slice
    was silently dropped.
A7: a separate cleanup_old_view_events beat task with its own `now - 7d` cutoff
    deleted un-rolled-up events; the schedule must no longer contain it, and the
    rollup must raise (not return a success-shaped error dict) on failure.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import models


@pytest.fixture()
def post(db):
    owner = models.User(
        handle=f"r_{uuid.uuid4().hex[:6]}", email=f"{uuid.uuid4().hex[:6]}@e.com"
    )
    db.add(owner)
    db.commit()
    p = models.Post(
        owner_id=owner.id, title="t", storage_key=uuid.uuid4(), kind="artwork"
    )
    db.add(p)
    db.commit()
    return p


def _view(db, post_id, country, when):
    db.add(
        models.ViewEvent(
            post_id=post_id,
            viewer_user_id=None,
            viewer_ip_hash=uuid.uuid4().hex,
            country_code=country,
            device_type="desktop",
            view_source="web",
            view_type="detail",
            created_at=when,
        )
    )


def test_rollup_merges_breakdowns_across_runs(db, post):
    from app.tasks import rollup_view_events

    old = datetime.now(timezone.utc) - timedelta(days=10)

    # Batch 1: two US views on `old`'s date -> creates the daily row.
    _view(db, post.id, "US", old)
    _view(db, post.id, "US", old)
    db.commit()
    assert rollup_view_events.apply().get()["status"] == "success"

    db.expire_all()
    row = (
        db.query(models.PostStatsDaily)
        .filter(models.PostStatsDaily.post_id == post.id)
        .one()
    )
    assert row.views_by_country == {"US": 2}
    assert row.total_views == 2

    # Batch 2 (same post+date): the MERGE branch. Must accumulate, not drop.
    _view(db, post.id, "US", old)
    _view(db, post.id, "FR", old)
    db.commit()
    assert rollup_view_events.apply().get()["status"] == "success"

    db.expire_all()
    row = (
        db.query(models.PostStatsDaily)
        .filter(models.PostStatsDaily.post_id == post.id)
        .one()
    )
    # Before the A6 fix the second slice's breakdown was silently not persisted,
    # leaving {"US": 2}.
    assert row.views_by_country == {"US": 3, "FR": 1}
    assert row.total_views == 4


def test_cleanup_old_view_events_is_not_scheduled():
    """A7: the data-losing separate cleanup task must not be in the beat schedule."""
    from app.tasks import celery_app

    assert "cleanup-old-view-events" not in celery_app.conf.beat_schedule


def test_rollup_raises_on_failure(db, post, monkeypatch):
    """A7: a rollup failure must raise (visible Celery failure), not return a
    success-shaped error dict."""
    from app import tasks

    old = datetime.now(timezone.utc) - timedelta(days=10)
    _view(db, post.id, "US", old)
    db.commit()

    # Force a failure partway through the task.
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(tasks, "visitor_key", boom, raising=False)
    # visitor_key is imported inside the task from utils.view_tracking; patch there.
    from app.utils import view_tracking

    monkeypatch.setattr(view_tracking, "visitor_key", boom)

    with pytest.raises(Exception):
        tasks.rollup_view_events.apply(throw=True).get()

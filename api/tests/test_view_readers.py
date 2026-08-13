"""Reader tests: every surface reads Views from ONE source (docs/artwork-views/ D11).

posts.view_count for totals; the watermark stitch (daily rows <= watermark,
raw events after) for windowed stats. Rolled-but-retained raw rows must
never double count.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app import models
from app.sqids_config import encode_id, encode_user_id
from app.vault import compute_storage_shard


def _make_user(db: Session, prefix: str = "rd") -> models.User:
    uid = uuid.uuid4().hex[:8]
    user = models.User(
        handle=f"{prefix}_{uid}", email=f"{prefix}_{uid}@example.com", roles=["user"]
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    return user


def _make_post(db: Session, owner: models.User, **flags) -> models.Post:
    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
    post = models.Post(
        storage_key=storage_key,
        storage_shard=compute_storage_shard(storage_key),
        owner_id=owner.id,
        kind="artwork",
        title="r",
        description="r",
        hashtags=[],
        art_url="https://example.com/r.png",
        width=64,
        height=64,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=str(storage_key).replace("-", "") + "f" * 32,
        promoted=True,
        visible=True,
        public_visibility=True,
        **flags,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    db.commit()
    db.refresh(post)
    return post


def _event(db, post_id, when, *, view_type="view", ip=None, user_id=None):
    db.add(
        models.ViewEvent(
            post_id=post_id,
            viewer_user_id=user_id,
            viewer_ip_hash=ip or uuid.uuid4().hex,
            device_type="desktop",
            view_source="web",
            view_type=view_type,
            created_at=when,
        )
    )


def _utc_day(days_ago: int, hour: int = 12) -> datetime:
    day = datetime.now(timezone.utc).date() - timedelta(days=days_ago)
    return datetime.combine(day, time(hour=hour), tzinfo=timezone.utc)


def test_get_view_counts_reads_denormalized_column(db):
    from app.services.post_stats import get_view_counts

    owner = _make_user(db)
    p1, p2 = _make_post(db, owner), _make_post(db, owner)
    p1.view_count = 7
    db.commit()

    counts = get_view_counts(db, [p1.id, p2.id, 999999])
    assert counts == {p1.id: 7, p2.id: 0, 999999: 0}


def test_widget_views_count_is_denormalized(client, db):
    owner = _make_user(db)
    post = _make_post(db, owner)
    post.view_count = 11
    db.commit()

    resp = client.get(f"/post/{post.id}/widget-data")
    assert resp.status_code == 200
    assert resp.json()["views_count"] == 11


def test_profile_total_views_sums_visible_posts_only(db):
    from app.services.user_profile_stats import get_user_profile_stats

    owner = _make_user(db)
    visible = _make_post(db, owner)
    hidden = _make_post(db, owner, hidden_by_user=True)
    visible.view_count = 5
    hidden.view_count = 100
    db.commit()

    stats = get_user_profile_stats(db, owner.id)
    assert stats.total_views == 5  # no 7-day lag, hidden posts excluded


def test_post_stats_no_double_count_across_watermark(db):
    """A rolled-but-retained raw row (day <= watermark, < 7 days old) must
    appear once — from its daily row, never from the raw table."""
    from app.services.stats import PostStatsService
    from app.services.view_metrics import set_view_watermark

    owner = _make_user(db)
    viewer = _make_user(db, "vw")
    post = _make_post(db, owner)

    day = datetime.now(timezone.utc).date() - timedelta(days=2)
    set_view_watermark(db, datetime.now(timezone.utc).date() - timedelta(days=1))
    # Rolled daily row for day -2 ...
    db.add(
        models.PostStatsDaily(
            post_id=post.id,
            date=day,
            total_views=1,
            unique_viewers=1,
            total_impressions=4,
            views_by_type={"view": 1, "impression": 4},
        )
    )
    # ... whose raw rows are retained (rolled but < 7 days old) ...
    _event(db, post.id, _utc_day(2, 9), ip="a" * 64)
    _event(db, post.id, _utc_day(2, 10), view_type="impression")
    # ... plus a genuinely-raw view today.
    _event(db, post.id, _utc_day(0), ip="b" * 64, user_id=viewer.id)
    db.commit()

    stats = PostStatsService(db)._compute_stats(post.id)
    assert stats.total_views == 2  # 1 rolled + 1 raw today; retained row NOT re-counted
    assert stats.total_impressions == 4  # from the daily row only
    assert len(stats.daily_views) == 30
    by_date = {d.date: d for d in stats.daily_views}
    assert by_date[day.isoformat()].views == 1
    assert by_date[day.isoformat()].impressions == 4
    today = datetime.now(timezone.utc).date().isoformat()
    assert by_date[today].views == 1
    # Authenticated slice sees only the logged-in viewer's View.
    assert stats.total_views_authenticated == 1


def test_post_stats_normalizes_legacy_breakdowns(db):
    from app.services.stats import PostStatsService
    from app.services.view_metrics import set_view_watermark

    owner = _make_user(db)
    post = _make_post(db, owner)
    day = datetime.now(timezone.utc).date() - timedelta(days=3)
    set_view_watermark(db, datetime.now(timezone.utc).date() - timedelta(days=1))
    db.add(
        models.PostStatsDaily(
            post_id=post.id,
            date=day,
            total_views=10,
            unique_viewers=6,
            views_by_type={"intentional": 7, "listing": 2, "widget": 1},
        )
    )
    db.commit()

    stats = PostStatsService(db)._compute_stats(post.id)
    # Canonical keys only — legacy taxonomy never leaves the server.
    assert stats.views_by_type == {"view": 7, "impression": 3}
    assert stats.total_views == 7
    assert stats.total_impressions == 3


def test_artist_dashboard_daily_series_and_authenticated_rollup_fix(db):
    """The dashboard gains a 30-day series, and its authenticated stats now
    include rolled days (the old code skipped days 8-30 based on a stale
    'PostStatsDaily has no authenticated columns' assumption)."""
    from app.services.artist_dashboard import ArtistDashboardService
    from app.services.view_metrics import set_view_watermark

    owner = _make_user(db)
    post = _make_post(db, owner)
    day = datetime.now(timezone.utc).date() - timedelta(days=10)
    set_view_watermark(db, datetime.now(timezone.utc).date() - timedelta(days=1))
    db.add(
        models.PostStatsDaily(
            post_id=post.id,
            date=day,
            total_views=4,
            unique_viewers=4,
            total_impressions=2,
            views_by_type={"view": 4, "impression": 2},
            total_views_authenticated=3,
            unique_viewers_authenticated=3,
            total_impressions_authenticated=1,
            views_by_type_authenticated={"view": 3, "impression": 1},
        )
    )
    db.commit()

    stats = ArtistDashboardService(db).get_artist_stats(owner.user_key)
    assert stats.total_views == 4
    assert stats.total_impressions == 2
    assert stats.total_views_authenticated == 3  # rolled day included
    assert stats.total_impressions_authenticated == 1
    assert len(stats.daily_views) == 30
    by_date = {d["date"]: d for d in stats.daily_views}
    assert by_date[day.isoformat()]["views"] == 4
    assert by_date[day.isoformat()]["impressions"] == 2


def test_sitewide_player_slice_stitches_on_view_watermark(db):
    from app.services.site_stats import SiteStatsService
    from app.services.view_metrics import set_view_watermark

    owner = _make_user(db)
    post = _make_post(db, owner)
    day = datetime.now(timezone.utc).date() - timedelta(days=2)
    set_view_watermark(db, datetime.now(timezone.utc).date() - timedelta(days=1))
    # Rolled player slice for day -2 (with retained raw rows) ...
    db.add(
        models.SiteStatsDaily(
            date=day,
            total_player_views=5,
            active_players=1,
            views_by_player={"Kitchen": 5},
        )
    )
    db.add(
        models.ViewEvent(
            post_id=post.id,
            viewer_ip_hash="p" * 64,
            device_type="player",
            view_source="player",
            view_type="impression",
            created_at=_utc_day(2, 9),
        )
    )
    # ... plus one genuinely-raw player play today.
    db.add(
        models.ViewEvent(
            post_id=post.id,
            viewer_ip_hash="p" * 64,
            device_type="player",
            view_source="player",
            view_type="impression",
            created_at=_utc_day(0),
        )
    )
    db.commit()

    stats = SiteStatsService(db)._compute_stats()
    assert stats.total_player_artwork_views_14d == 6  # 5 rolled + 1 raw today

"""POST /post/{id}/view contract tests (docs/artwork-views/ D2/D4/D5/D9/D14).

Covers the single-door ingestion semantics: intent resolution, the 201/204
counted-vs-accepted contract, per-day View dedup, the bot gate, the salted
IP hashing, and the rate-limit keying fix (real client IP, not the proxy).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app import models
from app.auth import create_access_token
from app.sqids_config import encode_id, encode_user_id
from app.vault import compute_storage_shard


def _make_user(db: Session, prefix: str = "vu") -> models.User:
    uid = uuid.uuid4().hex[:8]
    user = models.User(
        handle=f"{prefix}_{uid}", email=f"{prefix}_{uid}@example.com", roles=["user"]
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    return user


def _make_post(db: Session, owner: models.User) -> models.Post:
    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
    post = models.Post(
        storage_key=storage_key,
        storage_shard=compute_storage_shard(storage_key),
        owner_id=owner.id,
        kind="artwork",
        title="viewable",
        description="viewable",
        hashtags=[],
        art_url="https://example.com/a.png",
        width=64,
        height=64,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=str(storage_key).replace("-", "") + "e" * 32,
        promoted=True,
        visible=True,
        public_visibility=True,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    db.commit()
    db.refresh(post)
    return post


@pytest.fixture
def owner(db):
    return _make_user(db, "owner")


@pytest.fixture
def viewer(db):
    return _make_user(db, "viewer")


@pytest.fixture
def post(db, owner):
    return _make_post(db, owner)


@pytest.fixture
def record_spy(monkeypatch):
    """Spy on the endpoint's record_view binding; captures call kwargs."""
    calls: list[dict] = []

    def spy(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("app.routers.posts.record_view", lambda **kw: spy(**kw))
    return calls


BROWSER_UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Firefox/128.0"}


def _auth(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user)}", **BROWSER_UA}


# ---------------------------------------------------------------------------
# Salted IP hashing (D14)
# ---------------------------------------------------------------------------


def test_hash_ip_requires_salt(monkeypatch):
    from app.utils.view_tracking import hash_ip

    monkeypatch.delenv("MAKAPIX_IP_HASH_SALT", raising=False)
    with pytest.raises(RuntimeError, match="MAKAPIX_IP_HASH_SALT"):
        hash_ip("203.0.113.5")


def test_hash_ip_salted_and_supports_synthetic_ids(monkeypatch):
    from app.utils.view_tracking import hash_ip

    monkeypatch.setenv("MAKAPIX_IP_HASH_SALT", "salt-a")
    a = hash_ip("203.0.113.5")
    synthetic = hash_ip("player:abc")
    monkeypatch.setenv("MAKAPIX_IP_HASH_SALT", "salt-b")
    b = hash_ip("203.0.113.5")
    assert a != b  # different salts, different hashes
    assert len(a) == 64 and len(synthetic) == 64


# ---------------------------------------------------------------------------
# Intent resolution + 201/204 contract (D2/D4/D5)
# ---------------------------------------------------------------------------


def test_bodyless_post_is_a_counted_view(client, post, viewer, record_spy):
    resp = client.post(f"/post/{post.id}/view", headers=_auth(viewer))
    assert resp.status_code == 201
    assert len(record_spy) == 1
    assert record_spy[0]["view_type"] == "view"


def test_second_view_same_day_is_deduped(client, post, viewer, record_spy):
    assert (
        client.post(f"/post/{post.id}/view", headers=_auth(viewer)).status_code == 201
    )
    resp = client.post(f"/post/{post.id}/view", headers=_auth(viewer))
    assert resp.status_code == 204  # accepted, not counted
    assert len(record_spy) == 1  # no second dispatch


def test_artwork_channel_is_a_view(client, post, viewer, record_spy):
    """The D5 regression: the mobile app's registration was 422-rejected
    since launch because 'artwork' was missing from the channel Literal."""
    resp = client.post(
        f"/post/{post.id}/view", headers=_auth(viewer), json={"channel": "artwork"}
    )
    assert resp.status_code == 201
    assert record_spy[0]["view_type"] == "view"
    assert record_spy[0]["channel"] == "artwork"


def test_other_channels_are_impressions(client, post, viewer, record_spy):
    resp = client.post(
        f"/post/{post.id}/view",
        headers=_auth(viewer),
        json={"channel": "all", "play_order": 2},
    )
    assert resp.status_code == 204
    assert record_spy[0]["view_type"] == "impression"


def test_explicit_intent_wins(client, post, viewer, record_spy):
    resp = client.post(
        f"/post/{post.id}/view",
        headers=_auth(viewer),
        json={"intent": "impression", "channel": "artwork"},
    )
    assert resp.status_code == 204
    assert record_spy[0]["view_type"] == "impression"


def test_unknown_intent_is_422(client, post, viewer, record_spy):
    resp = client.post(
        f"/post/{post.id}/view", headers=_auth(viewer), json={"intent": "bogus"}
    )
    assert resp.status_code == 422
    assert record_spy == []


def test_self_view_accepted_but_not_counted(client, post, owner, record_spy):
    resp = client.post(f"/post/{post.id}/view", headers=_auth(owner))
    assert resp.status_code == 204
    assert record_spy == []


def test_missing_post_is_404(client, viewer):
    resp = client.post("/post/999999999/view", headers=_auth(viewer))
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Bot gate (D9)
# ---------------------------------------------------------------------------


def test_bot_ua_is_never_recorded(client, post, record_spy):
    from app.services.view_metrics import get_view_counter

    before = get_view_counter("bot_dropped")
    resp = client.post(
        f"/post/{post.id}/view",
        headers={"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"},
    )
    assert resp.status_code == 204
    assert record_spy == []
    assert get_view_counter("bot_dropped") == before + 1


def test_headless_browser_ua_is_a_bot():
    from app.utils.bot_detection import is_bot

    assert is_bot("Mozilla/5.0 HeadlessChrome/125.0")
    assert is_bot("python-requests/2.32")
    assert not is_bot(BROWSER_UA["User-Agent"])


def test_site_events_drop_bots(monkeypatch):
    from types import SimpleNamespace

    from app.services.view_metrics import get_view_counter
    from app.utils.site_tracking import record_site_event

    dispatched = []
    monkeypatch.setattr(
        "app.tasks.write_site_event",
        SimpleNamespace(delay=lambda payload: dispatched.append(payload)),
    )

    class FakeURL:
        path = "/p/abc"

    request = SimpleNamespace(
        headers={"User-Agent": "Mozilla/5.0 (compatible; bingbot/2.0)"},
        url=FakeURL(),
        client=None,
    )
    before = get_view_counter("site_bot_dropped")
    record_site_event(request, "page_view", user=None)
    assert dispatched == []
    assert get_view_counter("site_bot_dropped") == before + 1


# ---------------------------------------------------------------------------
# Dedup keying + rate-limit keying (D14/D23b)
# ---------------------------------------------------------------------------


def test_anonymous_dedup_is_per_ip(client, post, record_spy):
    h1 = {**BROWSER_UA, "X-Forwarded-For": "203.0.113.5"}
    h2 = {**BROWSER_UA, "X-Forwarded-For": "203.0.113.6"}
    assert client.post(f"/post/{post.id}/view", headers=h1).status_code == 201
    assert client.post(f"/post/{post.id}/view", headers=h1).status_code == 204
    assert client.post(f"/post/{post.id}/view", headers=h2).status_code == 201
    assert len(record_spy) == 2


def test_impression_rate_limit_keys_on_real_client_ip(client, post, record_spy):
    """Two anonymous visitors behind different IPs must not share one 3s
    bucket (the pre-redesign code keyed on request.client.host — always the
    reverse proxy — putting ALL anonymous viewers in one global bucket)."""
    body = {"channel": "all"}
    h1 = {**BROWSER_UA, "X-Forwarded-For": "203.0.113.7"}
    h2 = {**BROWSER_UA, "X-Forwarded-For": "203.0.113.8"}
    assert (
        client.post(f"/post/{post.id}/view", headers=h1, json=body).status_code == 204
    )
    # Different IP immediately after: must NOT be rate limited.
    assert (
        client.post(f"/post/{post.id}/view", headers=h2, json=body).status_code == 204
    )
    # Same IP again within 3s: rate limited.
    assert (
        client.post(f"/post/{post.id}/view", headers=h1, json=body).status_code == 429
    )


def test_views_are_not_rate_limited_across_posts(client, db, owner, viewer, record_spy):
    """Fast legitimate browsing must not lose first Views (dedup is the
    guard, not a 3s bucket)."""
    posts = [_make_post(db, owner) for _ in range(3)]
    for p in posts:
        assert (
            client.post(f"/post/{p.id}/view", headers=_auth(viewer)).status_code == 201
        )
    assert len(record_spy) == 3


# ---------------------------------------------------------------------------
# GET doors no longer record (D4)
# ---------------------------------------------------------------------------


def test_get_doors_do_not_record_views(client, post, monkeypatch):
    def boom(*a, **k):  # any record_view call via the module is a regression
        raise AssertionError("GET must not record views")

    monkeypatch.setattr("app.utils.view_tracking.record_view", boom)

    resp = client.get(f"/p/{post.public_sqid}", headers=BROWSER_UA)
    assert resp.status_code == 200
    resp = client.get(f"/post/{post.storage_key}", headers=BROWSER_UA)
    assert resp.status_code == 200


def test_get_post_exposes_denormalized_view_count(client, db, post):
    post.view_count = 42
    db.commit()
    resp = client.get(f"/p/{post.public_sqid}", headers=BROWSER_UA)
    assert resp.status_code == 200
    assert resp.json()["view_count"] == 42


# ---------------------------------------------------------------------------
# write_view_event counter increment (D11)
# ---------------------------------------------------------------------------


def _event_data(post_id: int, view_type: str) -> dict:
    return {
        "post_id": str(post_id),
        "viewer_user_id": None,
        "viewer_ip_hash": "0" * 64,
        "country_code": None,
        "device_type": "desktop",
        "view_source": "web",
        "view_type": view_type,
        "user_agent_hash": None,
        "referrer_domain": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def test_write_view_event_increments_counter_for_views(db, post):
    from app.tasks import write_view_event

    write_view_event.apply(args=[_event_data(post.id, "view")]).get()
    db.expire_all()
    db.refresh(post)
    assert post.view_count == 1
    assert db.query(models.ViewEvent).filter_by(post_id=post.id).count() == 1


def test_write_view_event_does_not_count_impressions(db, post):
    from app.tasks import write_view_event

    write_view_event.apply(args=[_event_data(post.id, "impression")]).get()
    db.expire_all()
    db.refresh(post)
    assert post.view_count == 0
    assert db.query(models.ViewEvent).filter_by(post_id=post.id).count() == 1

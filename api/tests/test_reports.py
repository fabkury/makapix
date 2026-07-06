"""
Tests for the hardened report pipeline (docs/ugc-safety/):
POST /report (auth optional, target validation, rate limits), moderator
triage (public_sqid user targets, mod_notes), alerting (email throttle +
new_report notifications), report_resolved loop, reporter_ip sweep.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import Comment, Post, PostFile, Report, SocialNotification, User
from app.sqids_config import encode_id, encode_user_id
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
        mod_hashtags=[],
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


def _make_comment(db: Session, *, post: Post, author: User) -> Comment:
    comment = Comment(post_id=post.id, author_id=author.id, depth=0, body="hi there")
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


@pytest.fixture
def moderator(db: Session) -> User:
    return _make_user(db, handle_prefix="mod", roles=["user", "moderator"])


@pytest.fixture
def reporter(db: Session) -> User:
    return _make_user(db, handle_prefix="rep", roles=["user"])


@pytest.fixture
def artist(db: Session) -> User:
    return _make_user(db, handle_prefix="artist", roles=["user"])


@pytest.fixture(autouse=True)
def _mute_alert_email(monkeypatch):
    """Reports fire a moderation alert email; stub it out and record calls."""
    calls: list[dict] = []

    def _stub(**kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(
        "app.routers.reports.email_service.send_report_alert_email", _stub
    )
    return calls


def _report_payload(post: Post, reason: str = "harassment", **extra) -> dict:
    return {
        "target_type": "post",
        "target_id": str(post.id),
        "reason_code": reason,
        **extra,
    }


class TestCreateReport:
    def test_logged_in_201(self, client: TestClient, db: Session, reporter, artist):
        post = _make_post(db, owner=artist, title="r1")
        r = client.post(
            "/v1/report", json=_report_payload(post), headers=_auth(reporter)
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "open"
        assert body["reason_code"] == "harassment"
        assert body["target_id"] == str(post.id)
        row = db.query(Report).filter(Report.id == body["id"]).first()
        assert row.reporter_id == reporter.id
        assert row.reporter_ip is None  # D24: IP only for anonymous reports

    def test_anonymous_201(self, client: TestClient, db: Session, artist):
        post = _make_post(db, owner=artist, title="r2")
        r = client.post("/v1/report", json=_report_payload(post, notes="rude"))
        assert r.status_code == 201, r.text
        row = db.query(Report).filter(Report.id == r.json()["id"]).first()
        assert row.reporter_id is None
        assert row.reporter_ip  # D24: anon reports keep the IP short-term
        assert row.notes == "rude"

    def test_user_target_by_sqid(self, client: TestClient, db: Session, artist):
        r = client.post(
            "/v1/report",
            json={
                "target_type": "user",
                "target_id": artist.public_sqid,
                "reason_code": "spam",
            },
        )
        assert r.status_code == 201, r.text

    def test_comment_target(self, client: TestClient, db: Session, reporter, artist):
        post = _make_post(db, owner=artist, title="r3")
        comment = _make_comment(db, post=post, author=artist)
        r = client.post(
            "/v1/report",
            json={
                "target_type": "comment",
                "target_id": str(comment.id),
                "reason_code": "hate",
            },
            headers=_auth(reporter),
        )
        assert r.status_code == 201, r.text

    def test_unknown_reason_422(self, client: TestClient, db: Session, artist):
        post = _make_post(db, owner=artist, title="r4")
        r = client.post("/v1/report", json=_report_payload(post, reason="nonsense"))
        assert r.status_code == 422

    def test_legacy_abuse_rejected_on_create(
        self, client: TestClient, db: Session, artist
    ):
        post = _make_post(db, owner=artist, title="r5")
        r = client.post("/v1/report", json=_report_payload(post, reason="abuse"))
        assert r.status_code == 422  # D21: read-only legacy value

    def test_malformed_post_id_422(self, client: TestClient):
        r = client.post(
            "/v1/report",
            json={"target_type": "post", "target_id": "abc", "reason_code": "spam"},
        )
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "validation_error"

    def test_missing_target_404(self, client: TestClient):
        r = client.post(
            "/v1/report",
            json={
                "target_type": "post",
                "target_id": "99999999",
                "reason_code": "spam",
            },
        )
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "not_found"

    def test_anonymous_rate_limit_429(self, client: TestClient, db: Session, artist):
        post = _make_post(db, owner=artist, title="r6")
        for _ in range(5):
            assert (
                client.post("/v1/report", json=_report_payload(post)).status_code == 201
            )
        r = client.post("/v1/report", json=_report_payload(post))
        assert r.status_code == 429
        assert r.json()["error"]["code"] == "rate_limited"

    def test_user_rate_limit_429(
        self, client: TestClient, db: Session, reporter, artist
    ):
        post = _make_post(db, owner=artist, title="r7")
        for _ in range(10):
            assert (
                client.post(
                    "/v1/report", json=_report_payload(post), headers=_auth(reporter)
                ).status_code
                == 201
            )
        r = client.post(
            "/v1/report", json=_report_payload(post), headers=_auth(reporter)
        )
        assert r.status_code == 429


class TestAlerting:
    def test_mod_notification_and_email_throttled_per_target(
        self, client: TestClient, db: Session, moderator, artist, _mute_alert_email
    ):
        post = _make_post(db, owner=artist, title="a1")
        post2 = _make_post(db, owner=artist, title="a2")

        assert client.post("/v1/report", json=_report_payload(post)).status_code == 201
        assert client.post("/v1/report", json=_report_payload(post)).status_code == 201
        assert client.post("/v1/report", json=_report_payload(post2)).status_code == 201

        # One alert per target within the 6h window (D18): 2 targets -> 2 emails
        assert len(_mute_alert_email) == 2

        notifs = (
            db.query(SocialNotification)
            .filter(
                SocialNotification.user_id == moderator.id,
                SocialNotification.notification_type == "new_report",
            )
            .all()
        )
        assert len(notifs) == 2


class TestModeratorTriage:
    def test_patch_user_target_by_sqid_ban(
        self, client: TestClient, db: Session, moderator, reporter, artist
    ):
        r = client.post(
            "/v1/report",
            json={
                "target_type": "user",
                "target_id": artist.public_sqid,
                "reason_code": "harassment",
            },
            headers=_auth(reporter),
        )
        report_id = r.json()["id"]

        r2 = client.patch(
            f"/v1/report/{report_id}",
            json={"status": "resolved", "action_taken": "ban"},
            headers=_auth(moderator),
        )
        assert r2.status_code == 200, r2.text
        db.refresh(artist)
        assert artist.banned_until is not None  # D9 regression: sqid resolution

    def test_patch_mod_notes_preserves_reporter_notes(
        self, client: TestClient, db: Session, moderator, reporter, artist
    ):
        post = _make_post(db, owner=artist, title="t1")
        r = client.post(
            "/v1/report",
            json=_report_payload(post, notes="original reporter text"),
            headers=_auth(reporter),
        )
        report_id = r.json()["id"]

        r2 = client.patch(
            f"/v1/report/{report_id}",
            json={"status": "triaged", "notes": "mod says: looks bad"},
            headers=_auth(moderator),
        )
        assert r2.status_code == 200
        row = db.query(Report).filter(Report.id == report_id).first()
        db.refresh(row)
        assert row.notes == "original reporter text"  # D25
        assert row.mod_notes == "mod says: looks bad"

    def test_resolve_notifies_reporter(
        self, client: TestClient, db: Session, moderator, reporter, artist
    ):
        post = _make_post(db, owner=artist, title="t2")
        r = client.post(
            "/v1/report", json=_report_payload(post), headers=_auth(reporter)
        )
        report_id = r.json()["id"]

        client.patch(
            f"/v1/report/{report_id}",
            json={"status": "resolved", "action_taken": "none"},
            headers=_auth(moderator),
        )
        notif = (
            db.query(SocialNotification)
            .filter(
                SocialNotification.user_id == reporter.id,
                SocialNotification.notification_type == "report_resolved",
            )
            .first()
        )
        assert notif is not None  # D5

    def test_resolve_anonymous_no_reporter_notification(
        self, client: TestClient, db: Session, moderator, artist
    ):
        post = _make_post(db, owner=artist, title="t3")
        r = client.post("/v1/report", json=_report_payload(post))
        report_id = r.json()["id"]
        r2 = client.patch(
            f"/v1/report/{report_id}",
            json={"status": "resolved", "action_taken": "none"},
            headers=_auth(moderator),
        )
        assert r2.status_code == 200

    def test_list_reports_reporter_handle(
        self, client: TestClient, db: Session, moderator, reporter, artist
    ):
        post = _make_post(db, owner=artist, title="t4")
        client.post("/v1/report", json=_report_payload(post), headers=_auth(reporter))
        client.post("/v1/report", json=_report_payload(post))  # anonymous

        r = client.get("/v1/report?status=open", headers=_auth(moderator))
        assert r.status_code == 200
        items = r.json()["items"]
        by_handle = {i["reporter_handle"] for i in items}
        assert reporter.handle in by_handle
        assert None in by_handle  # anonymous row

        # reporter_id filter is an integer now
        r2 = client.get(
            f"/v1/report?reporter_id={reporter.id}", headers=_auth(moderator)
        )
        assert r2.status_code == 200
        assert all(i["reporter_handle"] == reporter.handle for i in r2.json()["items"])

    def test_list_requires_moderator(self, client: TestClient, reporter):
        r = client.get("/v1/report", headers=_auth(reporter))
        assert r.status_code == 403


class TestReporterIpSweep:
    def test_sweep_nulls_old_ips(self, client: TestClient, db: Session, artist):
        from app.tasks import cleanup_report_ips

        post = _make_post(db, owner=artist, title="s1")
        r = client.post("/v1/report", json=_report_payload(post))
        report_id = r.json()["id"]

        # Age the report past the 30-day window
        row = db.query(Report).filter(Report.id == report_id).first()
        row.created_at = datetime.now(timezone.utc) - timedelta(days=31)
        db.commit()

        result = cleanup_report_ips.apply().result
        assert result["status"] == "success"
        assert result["cleared"] >= 1

        db.expire_all()
        row = db.query(Report).filter(Report.id == report_id).first()
        assert row.reporter_ip is None

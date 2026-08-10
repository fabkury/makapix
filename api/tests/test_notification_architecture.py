"""Tests for the plane-separation notification rework
(docs/notification-architecture/): live dispatch via the in-process bus with
block gating, DB-derived unread count, (created_at, id) cursor tiebreaker with
legacy-cursor compatibility, retention task, and comment-preview scrubbing.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import Post, PostFile, SocialNotification, User, UserBlock
from app.services import social_notifications as sn_module
from app.services.social_notifications import SocialNotificationService
from app.sqids_config import encode_id, encode_user_id
from app.vault import compute_storage_shard


def _make_user(db: Session, *, handle_prefix: str) -> User:
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        handle=f"{handle_prefix}_{unique_id}",
        email=f"{handle_prefix}_{unique_id}@example.com",
        roles=["user"],
        email_verified=True,
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


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _seed_notification(
    db: Session,
    *,
    user_id: int,
    actor_id: int | None = None,
    is_read: bool = False,
    created_at: datetime | None = None,
    comment_preview: str | None = None,
) -> SocialNotification:
    n = SocialNotification(
        user_id=user_id,
        notification_type="reaction",
        actor_id=actor_id,
        actor_handle="seed",
        is_read=is_read,
        comment_preview=comment_preview,
    )
    if created_at is not None:
        n.created_at = created_at
    if is_read:
        n.read_at = created_at or datetime.now(timezone.utc)
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


@pytest.fixture
def recipient(db: Session) -> User:
    return _make_user(db, handle_prefix="na_recipient")


@pytest.fixture
def actor(db: Session) -> User:
    return _make_user(db, handle_prefix="na_actor")


@pytest.fixture
def post(db: Session, recipient: User) -> Post:
    return _make_post(db, owner=recipient, title="na_post")


@pytest.fixture
def captured_events(monkeypatch) -> list[tuple[int, dict]]:
    captured: list[tuple[int, dict]] = []
    monkeypatch.setattr(
        sn_module.notification_bus,
        "publish_threadsafe",
        lambda user_id, event: captured.append((user_id, event)),
    )
    return captured


@pytest.fixture
def captured_pushes(monkeypatch, tmp_path) -> list[tuple]:
    """Enable the FCM enqueue guard and record .delay() calls."""
    cred = tmp_path / "fcm.json"
    cred.write_text("{}")
    monkeypatch.setenv("FCM_CREDENTIALS_FILE", str(cred))

    captured: list[tuple] = []
    from app.tasks import send_push_notification

    monkeypatch.setattr(
        send_push_notification,
        "delay",
        lambda *args, **kwargs: captured.append((args, kwargs)),
    )
    return captured


class TestDispatchBlockGating:
    def test_row_created_but_live_delivery_gated_for_blocked_actor(
        self, db, recipient, actor, post, captured_events, captured_pushes
    ):
        db.add(UserBlock(blocker_id=recipient.id, blocked_id=actor.id))
        db.commit()

        notification = SocialNotificationService.create_notification(
            db,
            user_id=recipient.id,
            notification_type="reaction",
            post=post,
            actor=actor,
            emoji="❤️",
        )

        # Row exists (unblock reveals history, D10)...
        assert notification is not None
        assert (
            db.query(SocialNotification)
            .filter(SocialNotification.user_id == recipient.id)
            .count()
            == 1
        )
        # ...but nothing was delivered live.
        assert captured_events == []
        assert captured_pushes == []

    def test_unblocked_actor_dispatches_bus_and_push(
        self, db, recipient, actor, post, captured_events, captured_pushes
    ):
        SocialNotificationService.create_notification(
            db,
            user_id=recipient.id,
            notification_type="reaction",
            post=post,
            actor=actor,
            emoji="❤️",
        )

        assert len(captured_events) == 1
        assert captured_events[0][0] == recipient.id
        assert len(captured_pushes) == 1
        args, _ = captured_pushes[0]
        assert args[0] == recipient.id
        assert args[1] == "reaction"


class TestUnreadCount:
    def test_counts_only_unread(self, client, db, recipient, actor):
        for _ in range(3):
            _seed_notification(db, user_id=recipient.id, actor_id=actor.id)
        _seed_notification(db, user_id=recipient.id, actor_id=actor.id, is_read=True)

        r = client.get(
            "/v1/social-notifications/unread-count", headers=_auth(recipient)
        )
        assert r.status_code == 200
        assert r.json()["unread_count"] == 3

    def test_block_filtered_like_the_list(self, client, db, recipient, actor):
        _seed_notification(db, user_id=recipient.id, actor_id=actor.id)
        # Actor-less system row still counts after the block.
        _seed_notification(db, user_id=recipient.id, actor_id=None)

        db.add(UserBlock(blocker_id=recipient.id, blocked_id=actor.id))
        db.commit()

        r = client.get(
            "/v1/social-notifications/unread-count", headers=_auth(recipient)
        )
        assert r.json()["unread_count"] == 1

        r2 = client.get("/v1/social-notifications/", headers=_auth(recipient))
        assert len(r2.json()["items"]) == 1  # badge and list agree

    def test_reflects_reads_and_deletes_immediately(self, client, db, recipient, actor):
        n1 = _seed_notification(db, user_id=recipient.id, actor_id=actor.id)
        _seed_notification(db, user_id=recipient.id, actor_id=actor.id)

        r = client.post(
            "/v1/social-notifications/mark-read",
            json=[str(n1.id)],
            headers=_auth(recipient),
        )
        assert r.status_code == 204
        r = client.get(
            "/v1/social-notifications/unread-count", headers=_auth(recipient)
        )
        assert r.json()["unread_count"] == 1

        r = client.post(
            "/v1/social-notifications/mark-all-read", headers=_auth(recipient)
        )
        assert r.status_code == 204
        r = client.get(
            "/v1/social-notifications/unread-count", headers=_auth(recipient)
        )
        assert r.json()["unread_count"] == 0


class TestCursorPagination:
    def test_tiebreaker_no_skip_on_shared_timestamp(self, client, db, recipient):
        ts = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
        ids = {
            str(_seed_notification(db, user_id=recipient.id, created_at=ts).id)
            for _ in range(4)
        }

        seen: set[str] = set()
        cursor = None
        for _ in range(3):
            url = "/v1/social-notifications/?limit=2"
            if cursor:
                url += f"&cursor={cursor}"
            r = client.get(url, headers=_auth(recipient))
            assert r.status_code == 200
            data = r.json()
            for item in data["items"]:
                assert item["id"] not in seen  # no duplicates
                seen.add(item["id"])
            cursor = data["next_cursor"]
            if cursor is None:
                break

        assert seen == ids  # no skips

    def test_legacy_timestamp_cursor_still_works(self, client, db, recipient):
        old = _seed_notification(
            db,
            user_id=recipient.id,
            created_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        _seed_notification(
            db,
            user_id=recipient.id,
            created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )

        # A deployed app client echoing a pre-tiebreaker cursor (bare ISO,
        # percent-encoded as real HTTP clients do — a raw '+' would decode
        # to a space).
        from urllib.parse import quote

        legacy_cursor = quote("2026-07-15T00:00:00+00:00", safe="")
        r = client.get(
            f"/v1/social-notifications/?cursor={legacy_cursor}",
            headers=_auth(recipient),
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert [i["id"] for i in items] == [str(old.id)]

    def test_new_cursor_is_opaque_base64(self, client, db, recipient):
        for day in (1, 2, 3):
            _seed_notification(
                db,
                user_id=recipient.id,
                created_at=datetime(2026, 8, day, tzinfo=timezone.utc),
            )

        r = client.get("/v1/social-notifications/?limit=2", headers=_auth(recipient))
        cursor = r.json()["next_cursor"]
        assert cursor is not None
        # Round-trips through base64 JSON with id + sort keys.
        import json as _json

        decoded = _json.loads(base64.b64decode(cursor))
        assert set(decoded) == {"id", "sort"}

        r2 = client.get(
            f"/v1/social-notifications/?limit=2&cursor={cursor}",
            headers=_auth(recipient),
        )
        assert r2.status_code == 200
        assert len(r2.json()["items"]) == 1

    def test_garbage_cursor_400(self, client, db, recipient):
        r = client.get(
            "/v1/social-notifications/?cursor=not-a-cursor",
            headers=_auth(recipient),
        )
        assert r.status_code == 400


class TestRetentionTask:
    def test_retention_windows(self, db, recipient):
        from app.tasks import cleanup_social_notifications

        now = datetime.now(timezone.utc)
        survivors = {
            str(
                _seed_notification(
                    db,
                    user_id=recipient.id,
                    is_read=False,
                    created_at=now - timedelta(days=100),
                ).id
            ),
            str(
                _seed_notification(
                    db,
                    user_id=recipient.id,
                    is_read=True,
                    created_at=now - timedelta(days=10),
                ).id
            ),
        }
        _seed_notification(
            db, user_id=recipient.id, is_read=True, created_at=now - timedelta(days=100)
        )
        _seed_notification(
            db, user_id=recipient.id, is_read=True, created_at=now - timedelta(days=400)
        )
        _seed_notification(
            db,
            user_id=recipient.id,
            is_read=False,
            created_at=now - timedelta(days=400),
        )

        result = cleanup_social_notifications.apply().result
        assert result["status"] == "success"
        assert result["deleted_read"] == 2
        assert result["deleted_old"] == 1  # the unread@400d (read@400d already gone)

        db.expire_all()
        remaining = {
            str(n.id)
            for n in db.query(SocialNotification)
            .filter(SocialNotification.user_id == recipient.id)
            .all()
        }
        assert remaining == survivors


class TestCommentPreviewScrub:
    def test_deleting_comment_scrubs_notification_preview(
        self, client, db, recipient, actor, post, captured_events
    ):
        secret = "something I regret typing"
        r = client.post(
            f"/v1/post/{post.id}/comments",
            json={"body": secret},
            headers=_auth(actor),
        )
        assert r.status_code == 201
        comment_id = r.json()["id"]

        n = (
            db.query(SocialNotification)
            .filter(SocialNotification.user_id == recipient.id)
            .one()
        )
        assert n.comment_preview == secret

        r = client.delete(f"/v1/post/comments/{comment_id}", headers=_auth(actor))
        assert r.status_code == 204

        db.expire_all()
        n = (
            db.query(SocialNotification)
            .filter(SocialNotification.user_id == recipient.id)
            .one()
        )
        assert n.comment_preview is None
        assert n.notification_type == "comment"  # row itself survives

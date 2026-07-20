"""
Tests for `actor_public_sqid` on social notification payloads
(docs/notification-actor-sqid/): present on REST list items and MQTT
broadcasts when the actor exists, null for actor-less rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import Post, PostFile, SocialNotification, User
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


@pytest.fixture
def recipient(db: Session) -> User:
    return _make_user(db, handle_prefix="notif_recipient")


@pytest.fixture
def actor(db: Session) -> User:
    return _make_user(db, handle_prefix="notif_actor")


@pytest.fixture
def post(db: Session, recipient: User) -> Post:
    return _make_post(db, owner=recipient, title="notif_sqid_post")


@pytest.fixture
def captured_publishes(monkeypatch) -> list[tuple[str, dict]]:
    captured: list[tuple[str, dict]] = []

    def fake_publish(topic, payload, qos=1, retain=False):
        captured.append((topic, payload))
        return True

    monkeypatch.setattr(sn_module, "publish", fake_publish)
    return captured


class TestNotificationActorPublicSqid:
    def test_list_includes_actor_public_sqid(
        self, client, db, recipient, actor, post, captured_publishes
    ):
        SocialNotificationService.create_notification(
            db,
            user_id=recipient.id,
            notification_type="reaction",
            post=post,
            actor=actor,
            emoji="❤️",
        )

        r = client.get("/v1/social-notifications/", headers=_auth(recipient))
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["actor_public_sqid"] == actor.public_sqid

    def test_actorless_row_has_null_actor_public_sqid(self, client, db, recipient):
        db.add(
            SocialNotification(
                user_id=recipient.id,
                notification_type="reaction",
                actor_id=None,
                actor_handle="Anonymous",
            )
        )
        db.commit()

        r = client.get("/v1/social-notifications/", headers=_auth(recipient))
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["actor_public_sqid"] is None

    def test_mqtt_broadcast_includes_actor_public_sqid(
        self, db, recipient, actor, post, captured_publishes
    ):
        SocialNotificationService.create_notification(
            db,
            user_id=recipient.id,
            notification_type="comment",
            post=post,
            actor=actor,
        )

        assert len(captured_publishes) == 1
        topic, payload = captured_publishes[0]
        assert topic == f"makapix/social-notifications/user/{recipient.id}"
        assert payload["actor_public_sqid"] == actor.public_sqid

    def test_system_notification_broadcast_includes_actor_public_sqid(
        self, db, recipient, actor, captured_publishes
    ):
        SocialNotificationService.create_system_notification(
            db,
            user_id=recipient.id,
            notification_type="follow",
            actor=actor,
        )

        assert len(captured_publishes) == 1
        _, payload = captured_publishes[0]
        assert payload["actor_public_sqid"] == actor.public_sqid

    def test_anonymous_broadcast_has_null_actor_public_sqid(
        self, db, recipient, post, captured_publishes
    ):
        SocialNotificationService.create_notification(
            db,
            user_id=recipient.id,
            notification_type="reaction",
            post=post,
            actor=None,
            emoji="👍",
        )

        assert len(captured_publishes) == 1
        _, payload = captured_publishes[0]
        assert payload["actor_public_sqid"] is None

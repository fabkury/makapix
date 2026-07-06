"""Tests for new-post / category-promotion MQTT notifications.

Regression coverage for the 2025-10 → 2026-07 silent breakage: when post/user
ids migrated from UUID to integer, the publishers kept passing the integer
``post.owner_id`` into ``PostNotificationPayload.owner_id: UUID``, so payload
construction raised on every new post — caught upstream and only logged, so
no follower ever received a notification. ``owner_id`` must carry the owner's
``user_key`` UUID (the documented wire contract in
docs/mqtt-protocol/03-notifications.md).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.models import CategoryFollow, Follow, Post, PostFile, User
from app.mqtt.notifications import (
    publish_category_promotion_notification,
    publish_new_post_notification,
)
from app.sqids_config import encode_id, encode_user_id
from app.vault import compute_storage_shard


def _make_user(db: Session, *, handle_prefix: str, **extra) -> User:
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        handle=f"{handle_prefix}_{unique_id}",
        email=f"{handle_prefix}_{unique_id}@example.com",
        roles=["user"],
        **extra,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    return user


def _make_post(db: Session, *, owner: User, title: str, hashtags=None) -> Post:
    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
    post = Post(
        storage_key=storage_key,
        storage_shard=compute_storage_shard(storage_key),
        owner_id=owner.id,
        kind="artwork",
        title=title,
        description=title,
        hashtags=hashtags or [],
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


@pytest.fixture
def captured_publishes(monkeypatch) -> list[tuple[str, dict]]:
    """Capture (topic, payload) of every MQTT publish; no broker involved."""
    captured: list[tuple[str, dict]] = []

    def _fake_publish(topic, payload, qos=0, retain=False):
        captured.append((topic, payload))
        return True

    monkeypatch.setattr("app.mqtt.notifications.publish", _fake_publish)
    return captured


class TestNewPostNotification:
    def test_payload_constructs_and_owner_id_is_user_key(
        self, db: Session, captured_publishes
    ):
        """THE regression: integer owner_id used to crash payload construction."""
        artist = _make_user(db, handle_prefix="artist")
        follower = _make_user(db, handle_prefix="fan")
        db.add(Follow(follower_id=follower.id, following_id=artist.id))
        db.commit()
        post = _make_post(db, owner=artist, title="np1")

        publish_new_post_notification(post.id, db)

        assert captured_publishes, "nothing was published (payload crash?)"
        topics = [t for t, _ in captured_publishes]
        assert f"makapix/post/new/user/{follower.id}/{post.id}" in topics
        assert f"makapix/post/new/{post.id}" in topics  # generic topic

        _, payload = captured_publishes[0]
        assert payload["owner_id"] == str(artist.user_key)  # NOT the int id
        assert payload["owner_sqid"] == artist.public_sqid
        assert payload["owner_handle"] == artist.handle
        assert payload["post_id"] == post.id

    def test_monitored_hashtag_follower_skipped(self, db: Session, captured_publishes):
        artist = _make_user(db, handle_prefix="artist")
        opted_in = _make_user(db, handle_prefix="optin", approved_hashtags=["nsfw"])
        not_opted = _make_user(db, handle_prefix="noopt")
        db.add(Follow(follower_id=opted_in.id, following_id=artist.id))
        db.add(Follow(follower_id=not_opted.id, following_id=artist.id))
        db.commit()
        post = _make_post(db, owner=artist, title="np2", hashtags=["nsfw"])

        publish_new_post_notification(post.id, db)

        topics = [t for t, _ in captured_publishes]
        assert f"makapix/post/new/user/{opted_in.id}/{post.id}" in topics
        assert f"makapix/post/new/user/{not_opted.id}/{post.id}" not in topics


class TestCategoryPromotionNotification:
    def test_publishes_exactly_once_with_valid_payload(
        self, db: Session, captured_publishes
    ):
        """Shared category topic: one publish total, not one per follower."""
        artist = _make_user(db, handle_prefix="artist")
        for i in range(3):
            f = _make_user(db, handle_prefix=f"catfan{i}")
            db.add(CategoryFollow(user_id=f.id, category="daily's-best"))
        db.commit()
        post = _make_post(db, owner=artist, title="cp1")

        publish_category_promotion_notification(post.id, "daily's-best", db)

        expected_topic = f"makapix/post/new/category/daily's-best/{post.id}"
        matching = [(t, p) for t, p in captured_publishes if t == expected_topic]
        assert len(matching) == 1  # previously N followers + 1 = duplicates
        _, payload = matching[0]
        assert payload["owner_id"] == str(artist.user_key)
        assert payload["promoted_category"] == "daily's-best"

"""
Tests for moderator hashtags (docs/mod-hashtags/): PUT /post/{id}/mod-hashtags,
the mod_hashtags <= hashtags invariant, artist-PATCH merge semantics, and the
shared hashtag normalization.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import AuditLog, Post, PostFile, SocialNotification, User
from app.sqids_config import encode_id, encode_user_id
from app.utils.hashtags import normalize_hashtags
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


def _make_post(
    db: Session,
    *,
    owner: User,
    title: str,
    hashtags: list[str] | None = None,
    mod_hashtags: list[str] | None = None,
    kind: str = "artwork",
    deleted_by_user: bool = False,
) -> Post:
    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
    post = Post(
        storage_key=storage_key,
        storage_shard=compute_storage_shard(storage_key),
        owner_id=owner.id,
        kind=kind,
        title=title,
        description=title,
        hashtags=hashtags or [],
        mod_hashtags=mod_hashtags or [],
        art_url=f"https://example.com/{title}.png",
        width=64 if kind == "artwork" else None,
        height=64 if kind == "artwork" else None,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=str(storage_key).replace("-", "") + "d" * 32,
        visible=True,
        public_visibility=True,
        deleted_by_user=deleted_by_user,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    if kind == "artwork":
        db.add(
            PostFile(post_id=post.id, format="png", file_bytes=32000, is_native=True)
        )
    db.commit()
    db.refresh(post)
    return post


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _put_mod_hashtags(
    client: TestClient, post: Post, user: User, tags: list[str], **extra
):
    return client.put(
        f"/post/{post.id}/mod-hashtags",
        json={"hashtags": tags, **extra},
        headers=_auth(user),
    )


@pytest.fixture
def moderator(db: Session) -> User:
    return _make_user(db, handle_prefix="mod", roles=["user", "moderator"])


@pytest.fixture
def artist(db: Session) -> User:
    return _make_user(db, handle_prefix="artist", roles=["user"])


class TestNormalizeHashtags:
    def test_pipeline(self):
        assert normalize_hashtags([" #NSFW ", "# nsfw", "Foo", "", "#", "foo"], 64) == [
            "nsfw",
            "foo",
        ]

    def test_cap(self):
        assert normalize_hashtags([f"t{i}" for i in range(10)], 3) == ["t0", "t1", "t2"]

    def test_no_cap(self):
        assert len(normalize_hashtags([f"t{i}" for i in range(70)], None)) == 70


class TestModHashtagsAuth:
    def test_requires_auth(self, client: TestClient, db: Session, artist: User):
        post = _make_post(db, owner=artist, title="a1")
        r = client.put(f"/post/{post.id}/mod-hashtags", json={"hashtags": ["x"]})
        assert r.status_code == 401

    def test_requires_moderator(self, client: TestClient, db: Session, artist: User):
        post = _make_post(db, owner=artist, title="a2")
        r = _put_mod_hashtags(client, post, artist, ["x"])
        assert r.status_code == 403

    def test_unknown_post(self, client: TestClient, moderator: User):
        r = client.put(
            "/post/99999999/mod-hashtags",
            json={"hashtags": ["x"]},
            headers=_auth(moderator),
        )
        assert r.status_code == 404


class TestModHashtagsPut:
    def test_set_and_effective(
        self, client: TestClient, db: Session, moderator: User, artist: User
    ):
        post = _make_post(db, owner=artist, title="b1", hashtags=["pixelart"])
        r = _put_mod_hashtags(client, post, moderator, ["nsfw"])
        assert r.status_code == 200
        body = r.json()
        assert body["mod_hashtags"] == ["nsfw"]
        assert body["hashtags"] == ["pixelart", "nsfw"]

    def test_normalization(
        self, client: TestClient, db: Session, moderator: User, artist: User
    ):
        post = _make_post(db, owner=artist, title="b2")
        r = _put_mod_hashtags(client, post, moderator, [" #NSFW ", "# nsfw", "nsfw"])
        assert r.status_code == 200
        assert r.json()["mod_hashtags"] == ["nsfw"]

    def test_cap_after_normalization(
        self, client: TestClient, db: Session, moderator: User, artist: User
    ):
        post = _make_post(db, owner=artist, title="b3")
        # 20 raw variants deduping to 2 tags: accepted
        raw = ["#a", "A", " a "] * 6 + ["b", "#B"]
        r = _put_mod_hashtags(client, post, moderator, raw)
        assert r.status_code == 200
        assert r.json()["mod_hashtags"] == ["a", "b"]
        # 17 distinct tags after normalization: rejected
        r = _put_mod_hashtags(client, post, moderator, [f"t{i}" for i in range(17)])
        assert r.status_code == 422

    def test_tag_too_long(
        self, client: TestClient, db: Session, moderator: User, artist: User
    ):
        post = _make_post(db, owner=artist, title="b4")
        r = _put_mod_hashtags(client, post, moderator, ["x" * 65])
        assert r.status_code == 422

    def test_claim_and_release(
        self, client: TestClient, db: Session, moderator: User, artist: User
    ):
        post = _make_post(db, owner=artist, title="b5", hashtags=["nsfw", "art"])
        # Claiming an artist tag: no duplicate, becomes mod-owned
        r = _put_mod_hashtags(client, post, moderator, ["nsfw"])
        body = r.json()
        assert body["hashtags"] == ["nsfw", "art"]
        assert body["mod_hashtags"] == ["nsfw"]
        # Removing the mod tag removes it entirely
        r = _put_mod_hashtags(client, post, moderator, [])
        body = r.json()
        assert body["hashtags"] == ["art"]
        assert body["mod_hashtags"] == []

    def test_playlist_and_deleted_are_404(
        self, client: TestClient, db: Session, moderator: User, artist: User
    ):
        playlist = _make_post(db, owner=artist, title="pl", kind="playlist")
        r = _put_mod_hashtags(client, playlist, moderator, ["x"])
        assert r.status_code == 404
        db.refresh(playlist)
        assert playlist.mod_hashtags == []

        deleted = _make_post(db, owner=artist, title="del", deleted_by_user=True)
        r = _put_mod_hashtags(client, deleted, moderator, ["x"])
        assert r.status_code == 404

    def test_same_set_put_repairs_invariant(
        self, client: TestClient, db: Session, moderator: User, artist: User
    ):
        # Manually corrupted row: mod tag missing from effective hashtags
        post = _make_post(
            db, owner=artist, title="b6", hashtags=["art"], mod_hashtags=["nsfw"]
        )
        r = _put_mod_hashtags(client, post, moderator, ["nsfw"])
        body = r.json()
        assert "nsfw" in body["hashtags"]
        assert body["mod_hashtags"] == ["nsfw"]


class TestAuditAndNotification:
    def _audit_rows(self, db: Session, post: Post) -> list[AuditLog]:
        return (
            db.query(AuditLog)
            .filter(
                AuditLog.action == "update_mod_hashtags",
                AuditLog.target_id == str(post.id),
            )
            .all()
        )

    def _notifications(self, db: Session, user: User) -> list[SocialNotification]:
        return (
            db.query(SocialNotification)
            .filter(
                SocialNotification.user_id == user.id,
                SocialNotification.notification_type == "mod_hashtags_updated",
            )
            .all()
        )

    def test_audit_and_notify_on_add_and_remove(
        self, client: TestClient, db: Session, moderator: User, artist: User
    ):
        post = _make_post(db, owner=artist, title="c1")
        _put_mod_hashtags(client, post, moderator, ["nsfw"], note="missing tag")
        _put_mod_hashtags(client, post, moderator, [])
        rows = self._audit_rows(db, post)
        assert len(rows) == 2
        assert "+#nsfw" in rows[0].note
        assert "−#nsfw" in rows[1].note
        notifs = self._notifications(db, artist)
        assert len(notifs) == 2

    def test_noop_is_silent(
        self, client: TestClient, db: Session, moderator: User, artist: User
    ):
        post = _make_post(db, owner=artist, title="c2", hashtags=["nsfw"])
        _put_mod_hashtags(client, post, moderator, ["nsfw"])
        _put_mod_hashtags(client, post, moderator, ["nsfw"])  # no-op replace
        assert len(self._audit_rows(db, post)) == 1
        assert len(self._notifications(db, artist)) == 1

    def test_no_notification_for_own_post(
        self, client: TestClient, db: Session, moderator: User
    ):
        post = _make_post(db, owner=moderator, title="c3")
        r = _put_mod_hashtags(client, post, moderator, ["nsfw"])
        assert r.status_code == 200
        assert len(self._notifications(db, moderator)) == 0


class TestArtistPatchMerge:
    def test_patch_preserves_mod_tags(
        self, client: TestClient, db: Session, moderator: User, artist: User
    ):
        post = _make_post(db, owner=artist, title="d1", hashtags=["art"])
        _put_mod_hashtags(client, post, moderator, ["nsfw"])
        # Artist replaces their tags, omitting the mod tag
        r = client.patch(
            f"/post/{post.id}", json={"hashtags": ["retro"]}, headers=_auth(artist)
        )
        assert r.status_code == 200
        body = r.json()
        assert body["hashtags"] == ["retro", "nsfw"]
        assert body["mod_hashtags"] == ["nsfw"]
        # Artist submitting the mod tag too: no duplicate
        r = client.patch(
            f"/post/{post.id}",
            json={"hashtags": ["retro", "nsfw"]},
            headers=_auth(artist),
        )
        body = r.json()
        assert body["hashtags"] == ["retro", "nsfw"]

    def test_patch_normalizes(self, client: TestClient, db: Session, artist: User):
        post = _make_post(db, owner=artist, title="d2")
        r = client.patch(
            f"/post/{post.id}",
            json={"hashtags": ["#Foo", "FOO", " bar "]},
            headers=_auth(artist),
        )
        assert r.status_code == 200
        assert r.json()["hashtags"] == ["foo", "bar"]

    def test_moderator_patch_preserves_mod_tags(
        self, client: TestClient, db: Session, moderator: User, artist: User
    ):
        post = _make_post(db, owner=artist, title="d3")
        _put_mod_hashtags(client, post, moderator, ["nsfw"])
        r = client.patch(
            f"/post/{post.id}", json={"hashtags": ["clean"]}, headers=_auth(moderator)
        )
        assert r.status_code == 200
        body = r.json()
        assert body["hashtags"] == ["clean", "nsfw"]
        assert body["mod_hashtags"] == ["nsfw"]

    def test_artist_cannot_clear_hidden_by_mod(
        self, client: TestClient, db: Session, moderator: User, artist: User
    ):
        post = _make_post(db, owner=artist, title="d4")
        post.hidden_by_mod = True
        db.commit()
        r = client.patch(
            f"/post/{post.id}", json={"hidden_by_mod": False}, headers=_auth(artist)
        )
        assert r.status_code == 200
        db.refresh(post)
        assert post.hidden_by_mod is True
        # Moderator can
        r = client.patch(
            f"/post/{post.id}",
            json={"hidden_by_mod": False},
            headers=_auth(moderator),
        )
        assert r.status_code == 200
        db.refresh(post)
        assert post.hidden_by_mod is False

    def test_caps_are_independent(
        self, client: TestClient, db: Session, moderator: User, artist: User
    ):
        post = _make_post(db, owner=artist, title="d5")
        _put_mod_hashtags(client, post, moderator, [f"m{i}" for i in range(16)])
        r = client.patch(
            f"/post/{post.id}",
            json={"hashtags": [f"a{i}" for i in range(64)]},
            headers=_auth(artist),
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["hashtags"]) == 80
        assert len(body["mod_hashtags"]) == 16

    def test_invariant_holds_after_sequences(
        self, client: TestClient, db: Session, moderator: User, artist: User
    ):
        post = _make_post(db, owner=artist, title="d6", hashtags=["a", "b"])
        _put_mod_hashtags(client, post, moderator, ["nsfw", "b"])
        client.patch(
            f"/post/{post.id}", json={"hashtags": ["c"]}, headers=_auth(artist)
        )
        _put_mod_hashtags(client, post, moderator, ["nsfw"])
        db.refresh(post)
        assert set(post.mod_hashtags) <= set(post.hashtags)


class TestMonitoredIntegration:
    def test_mod_added_monitored_tag_hides_post(
        self, client: TestClient, db: Session, moderator: User, artist: User
    ):
        post = _make_post(db, owner=artist, title="e1", hashtags=["pixelart"])
        # Visible to anonymous users before
        r = client.get("/post")
        assert post.id in [p["id"] for p in r.json()["items"]]

        _put_mod_hashtags(client, post, moderator, ["nsfw"])

        # Hidden from anonymous users after
        r = client.get("/post")
        assert post.id not in [p["id"] for p in r.json()["items"]]

        # Visible to an opted-in user
        viewer = _make_user(db, handle_prefix="viewer", roles=["user"])
        viewer.approved_hashtags = ["nsfw"]
        db.commit()
        r = client.get("/post", headers=_auth(viewer))
        assert post.id in [p["id"] for p in r.json()["items"]]


class TestConfig:
    def test_config_exposes_mod_cap(self, client: TestClient):
        r = client.get("/config")
        assert r.status_code == 200
        assert r.json()["max_mod_hashtags_per_post"] == 16

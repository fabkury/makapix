"""
Tests for moderator-vs-owner comment deletion attribution:
deleted_by_mod flag, original_body preservation + restore on undelete,
the purge-original endpoint, audit logging of direct mod deletions, and
tombstoning of mod-deleted comments in listings.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import AuditLog, Comment, Post, PostFile, User
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


def _make_comment(
    db: Session,
    *,
    post: Post,
    author: User,
    body: str = "original text",
    parent: Comment | None = None,
) -> Comment:
    comment = Comment(
        post_id=post.id,
        author_id=author.id,
        depth=parent.depth + 1 if parent else 0,
        parent_id=parent.id if parent else None,
        body=body,
    )
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
def author(db: Session) -> User:
    return _make_user(db, handle_prefix="author", roles=["user"])


@pytest.fixture
def artist(db: Session) -> User:
    return _make_user(db, handle_prefix="artist", roles=["user"])


@pytest.fixture(autouse=True)
def _mute_alert_email(monkeypatch):
    monkeypatch.setattr(
        "app.routers.reports.email_service.send_report_alert_email",
        lambda **kwargs: None,
    )


def _audit_entries(db: Session, comment: Comment, action: str) -> list[AuditLog]:
    return (
        db.query(AuditLog)
        .filter(AuditLog.target_id == str(comment.id), AuditLog.action == action)
        .all()
    )


class TestDeleteAttribution:
    def test_owner_delete(self, client: TestClient, db: Session, author, artist):
        post = _make_post(db, owner=artist, title="od1")
        comment = _make_comment(db, post=post, author=author)

        r = client.delete(f"/v1/post/comments/{comment.id}", headers=_auth(author))
        assert r.status_code == 204, r.text

        db.refresh(comment)
        assert comment.deleted_by_owner is True
        assert comment.deleted_by_mod is False
        assert comment.body == "[deleted]"
        assert comment.original_body == "original text"
        assert _audit_entries(db, comment, "take_down_comment") == []

    def test_mod_delete(
        self, client: TestClient, db: Session, moderator, author, artist
    ):
        post = _make_post(db, owner=artist, title="md1")
        comment = _make_comment(db, post=post, author=author)

        r = client.delete(f"/v1/post/comments/{comment.id}", headers=_auth(moderator))
        assert r.status_code == 204, r.text

        db.refresh(comment)
        assert comment.deleted_by_mod is True
        assert comment.deleted_by_owner is False
        assert comment.body == "[deleted by moderator]"
        assert comment.original_body == "original text"

        entries = _audit_entries(db, comment, "take_down_comment")
        assert len(entries) == 1
        assert entries[0].actor_id == moderator.id

    def test_mod_deleting_own_comment_is_owner_delete(
        self, client: TestClient, db: Session, moderator, artist
    ):
        post = _make_post(db, owner=artist, title="md2")
        comment = _make_comment(db, post=post, author=moderator)

        r = client.delete(f"/v1/post/comments/{comment.id}", headers=_auth(moderator))
        assert r.status_code == 204, r.text

        db.refresh(comment)
        assert comment.deleted_by_owner is True
        assert comment.deleted_by_mod is False
        assert comment.body == "[deleted]"

    def test_second_delete_keeps_original_attribution(
        self, client: TestClient, db: Session, moderator, author, artist
    ):
        post = _make_post(db, owner=artist, title="dd1")
        comment = _make_comment(db, post=post, author=author)

        client.delete(f"/v1/post/comments/{comment.id}", headers=_auth(author))
        r = client.delete(f"/v1/post/comments/{comment.id}", headers=_auth(moderator))
        assert r.status_code == 204, r.text

        db.refresh(comment)
        assert comment.deleted_by_owner is True
        assert comment.deleted_by_mod is False
        assert comment.body == "[deleted]"
        assert comment.original_body == "original text"


class TestUndelete:
    def test_undelete_restores_body(
        self, client: TestClient, db: Session, moderator, author, artist
    ):
        post = _make_post(db, owner=artist, title="ud1")
        comment = _make_comment(db, post=post, author=author)

        client.delete(f"/v1/post/comments/{comment.id}", headers=_auth(moderator))
        r = client.post(
            f"/v1/post/comments/{comment.id}/undelete", headers=_auth(moderator)
        )
        assert r.status_code == 201, r.text

        db.refresh(comment)
        assert comment.deleted_by_owner is False
        assert comment.deleted_by_mod is False
        assert comment.body == "original text"
        assert comment.original_body is None

    def test_undelete_after_purge_leaves_tombstone(
        self, client: TestClient, db: Session, moderator, author, artist
    ):
        post = _make_post(db, owner=artist, title="ud2")
        comment = _make_comment(db, post=post, author=author)

        client.delete(f"/v1/post/comments/{comment.id}", headers=_auth(moderator))
        client.post(
            f"/v1/post/comments/{comment.id}/purge-original", headers=_auth(moderator)
        )
        r = client.post(
            f"/v1/post/comments/{comment.id}/undelete", headers=_auth(moderator)
        )
        assert r.status_code == 201, r.text

        db.refresh(comment)
        assert comment.deleted_by_mod is False
        assert comment.body == "[deleted by moderator]"  # unrecoverable by design
        assert comment.original_body is None


class TestPurgeOriginal:
    def test_purge(self, client: TestClient, db: Session, moderator, author, artist):
        post = _make_post(db, owner=artist, title="pg1")
        comment = _make_comment(db, post=post, author=author, body="my@email.com")

        client.delete(f"/v1/post/comments/{comment.id}", headers=_auth(moderator))
        r = client.post(
            f"/v1/post/comments/{comment.id}/purge-original", headers=_auth(moderator)
        )
        assert r.status_code == 204, r.text

        db.refresh(comment)
        assert comment.original_body is None
        assert comment.deleted_by_mod is True  # deletion state untouched

        entries = _audit_entries(db, comment, "purge_comment_body")
        assert len(entries) == 1
        assert entries[0].actor_id == moderator.id

    def test_purge_requires_moderator(
        self, client: TestClient, db: Session, author, artist
    ):
        post = _make_post(db, owner=artist, title="pg2")
        comment = _make_comment(db, post=post, author=author)

        client.delete(f"/v1/post/comments/{comment.id}", headers=_auth(author))
        r = client.post(
            f"/v1/post/comments/{comment.id}/purge-original", headers=_auth(author)
        )
        assert r.status_code == 403, r.text

    def test_purge_not_deleted_400(
        self, client: TestClient, db: Session, moderator, author, artist
    ):
        post = _make_post(db, owner=artist, title="pg3")
        comment = _make_comment(db, post=post, author=author)

        r = client.post(
            f"/v1/post/comments/{comment.id}/purge-original", headers=_auth(moderator)
        )
        assert r.status_code == 400, r.text


class TestReportTakeDown:
    def test_take_down_sets_mod_flag(
        self, client: TestClient, db: Session, moderator, author, artist
    ):
        post = _make_post(db, owner=artist, title="rtd1")
        comment = _make_comment(db, post=post, author=author)

        r = client.post(
            "/v1/report",
            json={
                "target_type": "comment",
                "target_id": str(comment.id),
                "reason_code": "harassment",
            },
            headers=_auth(artist),
        )
        assert r.status_code == 201, r.text
        report_id = r.json()["id"]

        r2 = client.patch(
            f"/v1/report/{report_id}",
            json={"status": "resolved", "action_taken": "take_down"},
            headers=_auth(moderator),
        )
        assert r2.status_code == 200, r2.text

        db.refresh(comment)
        assert comment.deleted_by_mod is True
        assert comment.deleted_by_owner is False
        assert comment.body == "[deleted by moderator]"
        assert comment.original_body == "original text"


class TestListingTombstones:
    def test_mod_deleted_leaf_is_hidden(
        self, client: TestClient, db: Session, moderator, author, artist
    ):
        post = _make_post(db, owner=artist, title="lt1")
        comment = _make_comment(db, post=post, author=author)

        client.delete(f"/v1/post/comments/{comment.id}", headers=_auth(moderator))

        r = client.get(f"/v1/post/{post.id}/comments")
        assert r.status_code == 200, r.text
        assert str(comment.id) not in [c["id"] for c in r.json()["items"]]

    def test_mod_deleted_parent_is_tombstoned(
        self, client: TestClient, db: Session, moderator, author, artist
    ):
        post = _make_post(db, owner=artist, title="lt2")
        parent = _make_comment(db, post=post, author=author)
        _make_comment(db, post=post, author=artist, body="a reply", parent=parent)

        client.delete(f"/v1/post/comments/{parent.id}", headers=_auth(moderator))

        r = client.get(f"/v1/post/{post.id}/comments")
        assert r.status_code == 200, r.text
        items = {c["id"]: c for c in r.json()["items"]}
        assert str(parent.id) in items
        tombstone = items[str(parent.id)]
        assert tombstone["deleted_by_mod"] is True
        assert tombstone["deleted_by_owner"] is False
        assert tombstone["body"] == "[deleted by moderator]"

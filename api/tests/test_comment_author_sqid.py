"""
Tests for `author_public_sqid` on comment payloads (docs/comment-author-sqid/):
present for authenticated authors in list (flat + tree) and create responses,
null for anonymous/IP-attributed comments.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import Comment, Post, PostFile, User
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
def author(db: Session) -> User:
    return _make_user(db, handle_prefix="sqid_author")


@pytest.fixture
def post(db: Session, author: User) -> Post:
    return _make_post(db, owner=author, title="sqid_post")


class TestCommentAuthorPublicSqid:
    def test_list_flat_includes_author_public_sqid(self, client, db, author, post):
        db.add(Comment(post_id=post.id, author_id=author.id, depth=0, body="hi"))
        db.commit()

        r = client.get(f"/v1/post/{post.id}/comments?view=flat")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["author_public_sqid"] == author.public_sqid

    def test_list_tree_includes_author_public_sqid(self, client, db, author, post):
        top = Comment(post_id=post.id, author_id=author.id, depth=0, body="top")
        db.add(top)
        db.commit()
        replier = _make_user(db, handle_prefix="sqid_replier")
        db.add(
            Comment(
                post_id=post.id,
                author_id=replier.id,
                parent_id=top.id,
                depth=1,
                body="reply",
            )
        )
        db.commit()

        r = client.get(f"/v1/post/{post.id}/comments?view=tree")
        assert r.status_code == 200
        sqids = {c["author_public_sqid"] for c in r.json()["items"]}
        assert sqids == {author.public_sqid, replier.public_sqid}

    def test_anonymous_comment_has_null_author_public_sqid(
        self, client, db, author, post
    ):
        db.add(
            Comment(
                post_id=post.id,
                author_id=None,
                author_ip="203.0.113.7",
                depth=0,
                body="anon",
            )
        )
        db.commit()

        r = client.get(f"/v1/post/{post.id}/comments")
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["author_public_sqid"] is None
        assert items[0]["author_handle"].startswith("Guest_")

    def test_create_response_includes_author_public_sqid(self, client, author, post):
        r = client.post(
            f"/v1/post/{post.id}/comments",
            json={"body": "fresh comment"},
            headers=_auth(author),
        )
        assert r.status_code == 201
        assert r.json()["author_public_sqid"] == author.public_sqid

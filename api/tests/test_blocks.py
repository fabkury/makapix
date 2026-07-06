"""
Tests for user blocking (docs/ugc-safety/): block/unblock endpoints,
/me/blocks, unfollow-on-block, list-surface filtering (feed, search users,
comments incl. reply-orphan rule, who-reacted, notifications), symmetric
interaction guards (comment, reaction, comment like, follow), and the
is_blocked_by_viewer profile field.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import (
    Comment,
    Follow,
    Post,
    PostFile,
    Reaction,
    SocialNotification,
    User,
    UserBlock,
)
from app.sqids_config import encode_id, encode_user_id
from app.vault import compute_storage_shard


def _make_user(
    db: Session, *, handle_prefix: str, roles: list[str] | None = None
) -> User:
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        handle=f"{handle_prefix}_{unique_id}",
        email=f"{handle_prefix}_{unique_id}@example.com",
        roles=roles or ["user"],
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


def _make_comment(
    db: Session,
    *,
    post: Post,
    author: User,
    parent: Comment | None = None,
    body: str = "hello",
) -> Comment:
    comment = Comment(
        post_id=post.id,
        author_id=author.id,
        parent_id=parent.id if parent else None,
        depth=(parent.depth + 1) if parent else 0,
        body=body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _block(client: TestClient, blocker: User, target: User):
    return client.post(f"/v1/user/u/{target.public_sqid}/block", headers=_auth(blocker))


@pytest.fixture
def alice(db: Session) -> User:
    return _make_user(db, handle_prefix="alice")


@pytest.fixture
def bob(db: Session) -> User:
    return _make_user(db, handle_prefix="bob")


class TestBlockEndpoints:
    def test_block_unblock_idempotent(self, client, db, alice, bob):
        assert _block(client, alice, bob).status_code == 204
        assert _block(client, alice, bob).status_code == 204  # idempotent
        assert (
            db.query(UserBlock)
            .filter(UserBlock.blocker_id == alice.id, UserBlock.blocked_id == bob.id)
            .count()
            == 1
        )
        r = client.delete(f"/v1/user/u/{bob.public_sqid}/block", headers=_auth(alice))
        assert r.status_code == 204
        r = client.delete(f"/v1/user/u/{bob.public_sqid}/block", headers=_auth(alice))
        assert r.status_code == 204  # idempotent

    def test_block_self_400(self, client, alice):
        r = _block(client, alice, alice)
        assert r.status_code == 400

    def test_block_unknown_user_404(self, client, alice):
        r = client.post("/v1/user/u/zzzzzzzz/block", headers=_auth(alice))
        assert r.status_code == 404

    def test_block_requires_auth(self, client, bob):
        r = client.post(f"/v1/user/u/{bob.public_sqid}/block")
        assert r.status_code == 401

    def test_block_removes_follows_both_ways(self, client, db, alice, bob):
        db.add(Follow(follower_id=alice.id, following_id=bob.id))
        db.add(Follow(follower_id=bob.id, following_id=alice.id))
        db.commit()

        assert _block(client, alice, bob).status_code == 204
        remaining = (
            db.query(Follow)
            .filter(
                Follow.follower_id.in_([alice.id, bob.id]),
                Follow.following_id.in_([alice.id, bob.id]),
            )
            .count()
        )
        assert remaining == 0  # D12

    def test_me_blocks_listing(self, client, db, alice, bob):
        _block(client, alice, bob)
        r = client.get("/v1/me/blocks", headers=_auth(alice))
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["public_sqid"] == bob.public_sqid
        assert items[0]["handle"] == bob.handle
        assert items[0]["blocked_at"]

    def test_profile_is_blocked_by_viewer(self, client, db, alice, bob):
        _block(client, alice, bob)
        r = client.get(f"/v1/user/u/{bob.public_sqid}/profile", headers=_auth(alice))
        assert r.status_code == 200
        assert r.json()["is_blocked_by_viewer"] is True  # D14

        r2 = client.get(f"/v1/user/u/{bob.public_sqid}/profile", headers=_auth(bob))
        assert r2.json()["is_blocked_by_viewer"] is False


class TestVisibilityFiltering:
    def test_feed_hides_blocked_users_posts(self, client, db, alice, bob):
        post = _make_post(db, owner=bob, title="bobart")
        _block(client, alice, bob)

        r = client.get("/v1/post", headers=_auth(alice))
        assert r.status_code == 200
        ids = [p["id"] for p in r.json()["items"]]
        assert post.id not in ids  # D10

        # One-way: bob still sees his own post; logged-out unaffected
        r2 = client.get("/v1/post", headers=_auth(bob))
        assert post.id in [p["id"] for p in r2.json()["items"]]
        r3 = client.get("/v1/post")
        assert post.id in [p["id"] for p in r3.json()["items"]]

    def test_user_browse_hides_blocked(self, client, db, alice, bob):
        _block(client, alice, bob)
        r = client.get("/v1/user/browse", headers=_auth(alice))
        assert r.status_code == 200
        handles = [u["handle"] for u in r.json()["items"]]
        assert bob.handle not in handles

    def test_comments_blocked_toplevel_drops_with_replies(self, client, db, alice, bob):
        carol = _make_user(db, handle_prefix="carol")
        post = _make_post(db, owner=carol, title="thread")
        top = _make_comment(db, post=post, author=bob, body="top by bob")
        _make_comment(db, post=post, author=carol, parent=top, body="reply by carol")
        keep = _make_comment(db, post=post, author=carol, body="carol standalone")

        _block(client, alice, bob)

        r = client.get(f"/v1/post/{post.id}/comments", headers=_auth(alice))
        assert r.status_code == 200
        bodies = [c["body"] for c in r.json()["items"]]
        # Blocked top-level comment AND its reply are gone (contract §5)
        assert "top by bob" not in bodies
        assert "reply by carol" not in bodies
        assert "carol standalone" in bodies

        # Bob's view is unaffected (one-way filtering)
        r2 = client.get(f"/v1/post/{post.id}/comments", headers=_auth(bob))
        assert "top by bob" in [c["body"] for c in r2.json()["items"]]

    def test_comments_blocked_reply_drops_alone(self, client, db, alice, bob):
        carol = _make_user(db, handle_prefix="carol")
        post = _make_post(db, owner=carol, title="thread2")
        top = _make_comment(db, post=post, author=carol, body="top by carol")
        _make_comment(db, post=post, author=bob, parent=top, body="reply by bob")

        _block(client, alice, bob)

        r = client.get(f"/v1/post/{post.id}/comments", headers=_auth(alice))
        bodies = [c["body"] for c in r.json()["items"]]
        assert "top by carol" in bodies
        assert "reply by bob" not in bodies

    def test_reaction_users_filtered(self, client, db, alice, bob):
        carol = _make_user(db, handle_prefix="carol")
        post = _make_post(db, owner=carol, title="reactedpost")
        db.add(Reaction(post_id=post.id, user_id=bob.id, emoji="🔥"))
        db.commit()

        _block(client, alice, bob)

        r = client.get(f"/v1/post/{post.id}/reaction-users", headers=_auth(alice))
        assert r.status_code == 200
        handles = [i["user_handle"] for i in r.json()["items"]]
        assert bob.handle not in handles

        # Logged-out sees everything
        r2 = client.get(f"/v1/post/{post.id}/reaction-users")
        assert bob.handle in [i["user_handle"] for i in r2.json()["items"]]

    def test_notifications_from_blocked_actor_hidden(self, client, db, alice, bob):
        post = _make_post(db, owner=alice, title="alicepost")
        # Bob comments on alice's post BEFORE the block -> notification exists
        r = client.post(
            f"/v1/post/{post.id}/comments",
            json={"body": "nice art!"},
            headers=_auth(bob),
        )
        assert r.status_code == 201
        assert (
            db.query(SocialNotification)
            .filter(SocialNotification.user_id == alice.id)
            .count()
            >= 1
        )

        _block(client, alice, bob)

        r2 = client.get("/v1/social-notifications/", headers=_auth(alice))
        assert r2.status_code == 200
        actor_handles = [n["actor_handle"] for n in r2.json()["items"]]
        assert bob.handle not in actor_handles


class TestInteractionGuards:
    def test_blocked_cannot_comment_on_blockers_post(self, client, db, alice, bob):
        post = _make_post(db, owner=alice, title="apost")
        _block(client, alice, bob)

        r = client.post(
            f"/v1/post/{post.id}/comments",
            json={"body": "let me in"},
            headers=_auth(bob),
        )
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "blocked"  # D11/D20

    def test_blocker_cannot_comment_on_blockeds_post(self, client, db, alice, bob):
        post = _make_post(db, owner=bob, title="bpost")
        _block(client, alice, bob)

        r = client.post(
            f"/v1/post/{post.id}/comments",
            json={"body": "symmetric"},
            headers=_auth(alice),
        )
        assert r.status_code == 403  # symmetric (D11)

    def test_blocked_cannot_reply_to_blockers_comment(self, client, db, alice, bob):
        carol = _make_user(db, handle_prefix="carol")
        post = _make_post(db, owner=carol, title="cpost")
        top = _make_comment(db, post=post, author=alice, body="alice comment")
        _block(client, alice, bob)

        r = client.post(
            f"/v1/post/{post.id}/comments",
            json={"body": "reply", "parent_id": str(top.id)},
            headers=_auth(bob),
        )
        assert r.status_code == 403

    def test_blocked_cannot_react(self, client, db, alice, bob):
        post = _make_post(db, owner=alice, title="rpost")
        _block(client, alice, bob)

        r = client.put(f"/v1/post/{post.id}/reactions/🔥", headers=_auth(bob))
        assert r.status_code == 403
        assert r.json()["error"]["code"] == "blocked"

    def test_blocked_cannot_like_comment(self, client, db, alice, bob):
        carol = _make_user(db, handle_prefix="carol")
        post = _make_post(db, owner=carol, title="lpost")
        comment = _make_comment(db, post=post, author=alice, body="likeable")
        _block(client, alice, bob)

        r = client.put(f"/v1/post/comments/{comment.id}/like", headers=_auth(bob))
        assert r.status_code == 403

    def test_blocked_cannot_follow(self, client, db, alice, bob):
        _block(client, alice, bob)

        r = client.post(f"/v1/user/u/{alice.public_sqid}/follow", headers=_auth(bob))
        assert r.status_code == 403
        r2 = client.post(f"/v1/user/u/{bob.public_sqid}/follow", headers=_auth(alice))
        assert r2.status_code == 403

    def test_unblock_restores_interaction(self, client, db, alice, bob):
        post = _make_post(db, owner=alice, title="upost")
        _block(client, alice, bob)
        client.delete(f"/v1/user/u/{bob.public_sqid}/block", headers=_auth(alice))

        r = client.post(
            f"/v1/post/{post.id}/comments",
            json={"body": "friends again"},
            headers=_auth(bob),
        )
        assert r.status_code == 201

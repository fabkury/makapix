"""Test MQTT player request handlers."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models import Player, User, Post, PostFile, Reaction, Comment
from app.mqtt.player_requests import (
    _authenticate_player,
    _handle_submit_reaction,
    _handle_revoke_reaction,
    _handle_get_comments,
    _handle_query_posts,
)
from app.mqtt.schemas import (
    SubmitReactionRequest,
    RevokeReactionRequest,
    GetCommentsRequest,
    QueryPostsRequest,
)


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user."""
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        handle=f"testuser_{unique_id}",
        email=f"test_{unique_id}@example.com",
        roles=["user"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_player(test_user: User, db: Session) -> Player:
    """Create a test player."""
    player_key = uuid.uuid4()
    player = Player(
        player_key=player_key,
        owner_id=test_user.id,
        device_model="TestDevice",
        firmware_version="1.0.0",
        registration_status="registered",
        name="Test Player",
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


@pytest.fixture
def test_posts(test_user: User, db: Session) -> list[Post]:
    """Create test posts."""
    from app.vault import compute_storage_shard

    now = datetime.now(timezone.utc)
    posts = []
    for i in range(5):
        storage_key = uuid.uuid4()
        post = Post(
            storage_key=storage_key,
            storage_shard=compute_storage_shard(storage_key),
            owner_id=test_user.id,
            kind="artwork",
            title=f"Test Art {i}",
            description=f"Test artwork {i}",
            hashtags=["test", "art"],
            art_url=f"https://example.com/test{i}.png",
            width=64,
            height=64,
            frame_count=1,
            transparency_meta=False,
            alpha_meta=False,
            metadata_modified_at=now,
            artwork_modified_at=now,
            hash=str(storage_key).replace("-", "") + "a" * 32,  # Unique hash
            visible=True,
            promoted=(i % 2 == 0),  # Every other post is promoted
        )
        db.add(post)
        db.flush()
        db.add(
            PostFile(post_id=post.id, format="png", file_bytes=32000, is_native=True)
        )
        posts.append(post)
    db.commit()
    for post in posts:
        db.refresh(post)
    return posts


@pytest.fixture
def other_user(db: Session) -> User:
    """Create another test user."""
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        handle=f"otheruser_{unique_id}",
        email=f"other_{unique_id}@example.com",
        roles=["user"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def other_user_post(other_user: User, db: Session) -> Post:
    """Create a post by another user."""
    from app.vault import compute_storage_shard

    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
    post = Post(
        storage_key=storage_key,
        storage_shard=compute_storage_shard(storage_key),
        owner_id=other_user.id,
        kind="artwork",
        title="Other User Art",
        description="Art by other user",
        hashtags=["other"],
        art_url="https://example.com/other.png",
        width=64,
        height=64,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=str(storage_key).replace("-", "") + "b" * 32,  # Unique hash
        visible=True,
    )
    db.add(post)
    db.flush()
    db.add(PostFile(post_id=post.id, format="png", file_bytes=32000, is_native=True))
    db.commit()
    db.refresh(post)
    return post


class TestAuthentication:
    """Test player authentication."""

    def test_authenticate_valid_player(self, test_player: Player, db: Session):
        """Test authentication with valid registered player."""
        player = _authenticate_player(test_player.player_key, db)
        assert player is not None
        assert player.id == test_player.id
        assert player.owner is not None

    def test_authenticate_invalid_key(self, db: Session):
        """Test authentication with invalid player key."""
        invalid_key = uuid.uuid4()
        player = _authenticate_player(invalid_key, db)
        assert player is None

    def test_authenticate_pending_player(self, test_user: User, db: Session):
        """Test authentication with pending (not registered) player."""
        pending_player = Player(
            player_key=uuid.uuid4(),
            owner_id=test_user.id,
            device_model="TestDevice",
            firmware_version="1.0.0",
            registration_status="pending",
            name="Pending Player",
        )
        db.add(pending_player)
        db.commit()

        player = _authenticate_player(pending_player.player_key, db)
        assert player is None


class TestReactions:
    """Test reaction functionality."""

    @patch("app.mqtt.player_requests.publish")
    def test_submit_reaction_success(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        other_user_post: Post,
        db: Session,
    ):
        """Test adding a reaction."""
        request = SubmitReactionRequest(
            request_id="test-react-1",
            player_key=test_player.player_key,
            post_id=other_user_post.id,
            emoji="❤️",
        )

        _handle_submit_reaction(test_player, request, db)

        # Verify reaction was created
        reaction = (
            db.query(Reaction)
            .filter(
                Reaction.post_id == other_user_post.id,
                Reaction.user_id == test_player.owner_id,
                Reaction.emoji == "❤️",
            )
            .first()
        )
        assert reaction is not None

        # Verify success response
        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True

    @patch("app.mqtt.player_requests.publish")
    def test_submit_reaction_idempotent(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        other_user_post: Post,
        db: Session,
    ):
        """Test that adding same reaction twice is idempotent."""
        # Add reaction first time
        reaction = Reaction(
            post_id=other_user_post.id,
            user_id=test_player.owner_id,
            emoji="👍",
        )
        db.add(reaction)
        db.commit()

        request = SubmitReactionRequest(
            request_id="test-react-2",
            player_key=test_player.player_key,
            post_id=other_user_post.id,
            emoji="👍",
        )

        _handle_submit_reaction(test_player, request, db)

        # Should still return success
        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True

        # Should not create duplicate
        count = (
            db.query(Reaction)
            .filter(
                Reaction.post_id == other_user_post.id,
                Reaction.user_id == test_player.owner_id,
                Reaction.emoji == "👍",
            )
            .count()
        )
        assert count == 1

    @patch("app.mqtt.player_requests.publish")
    def test_revoke_reaction_success(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        other_user_post: Post,
        db: Session,
    ):
        """Test revoking a reaction."""
        # Add reaction first
        reaction = Reaction(
            post_id=other_user_post.id,
            user_id=test_player.owner_id,
            emoji="😊",
        )
        db.add(reaction)
        db.commit()

        request = RevokeReactionRequest(
            request_id="test-revoke-1",
            player_key=test_player.player_key,
            post_id=other_user_post.id,
            emoji="😊",
        )

        _handle_revoke_reaction(test_player, request, db)

        # Verify reaction was deleted
        exists = (
            db.query(Reaction)
            .filter(
                Reaction.post_id == other_user_post.id,
                Reaction.user_id == test_player.owner_id,
                Reaction.emoji == "😊",
            )
            .first()
        )
        assert exists is None

        # Verify success response
        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True

    @patch("app.mqtt.player_requests.publish")
    def test_revoke_reaction_idempotent(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        other_user_post: Post,
        db: Session,
    ):
        """Test that revoking non-existent reaction is idempotent."""
        request = RevokeReactionRequest(
            request_id="test-revoke-2",
            player_key=test_player.player_key,
            post_id=other_user_post.id,
            emoji="🎉",
        )

        _handle_revoke_reaction(test_player, request, db)

        # Should still return success
        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True


class TestGetComments:
    """Test get_comments functionality."""

    @pytest.fixture
    def test_comments(
        self, other_user_post: Post, test_user: User, db: Session
    ) -> list[Comment]:
        """Create test comments."""
        comments = []
        for i in range(3):
            comment = Comment(
                post_id=other_user_post.id,
                author_id=test_user.id,
                body=f"Test comment {i}",
                depth=0,
            )
            db.add(comment)
            comments.append(comment)
        db.commit()
        for comment in comments:
            db.refresh(comment)
        return comments

    @patch("app.mqtt.player_requests.publish")
    def test_get_comments_success(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        other_user_post: Post,
        test_comments: list[Comment],
        db: Session,
    ):
        """Test retrieving comments."""
        request = GetCommentsRequest(
            request_id="test-comment-1",
            player_key=test_player.player_key,
            post_id=other_user_post.id,
            limit=10,
        )

        _handle_get_comments(test_player, request, db)

        # Verify success response
        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True
        assert len(payload["comments"]) == len(test_comments)

        # Verify comment data
        for comment_data in payload["comments"]:
            assert "body" in comment_data
            assert "author_handle" in comment_data

    @patch("app.mqtt.player_requests.publish")
    def test_get_comments_pagination(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        other_user_post: Post,
        test_comments: list[Comment],
        db: Session,
    ):
        """Test comment pagination."""
        request = GetCommentsRequest(
            request_id="test-comment-2",
            player_key=test_player.player_key,
            post_id=other_user_post.id,
            limit=2,
        )

        _handle_get_comments(test_player, request, db)

        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]

        # Should return only 2 comments
        assert len(payload["comments"]) == 2
        # Should have more results
        assert payload["has_more"] is True
        assert payload["next_cursor"] is not None


class TestReactionsChannel:
    """Test the `reactions` channel in _handle_query_posts."""

    @pytest.fixture
    def reactor(self, db: Session) -> User:
        """A user whose reactions the player will query."""
        unique_id = str(uuid.uuid4())[:8]
        user = User(
            handle=f"reactor_{unique_id}",
            email=f"reactor_{unique_id}@example.com",
            roles=["user"],
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def _make_post(
        self,
        db: Session,
        *,
        owner: User,
        title: str,
        public_visibility: bool = True,
        visible: bool = True,
        deleted_by_user: bool = False,
        hidden_by_mod: bool = False,
        hidden_by_user: bool = False,
        non_conformant: bool = False,
        kind: str = "artwork",
    ) -> Post:
        """Helper that creates a post with a valid public_sqid."""
        from app.vault import compute_storage_shard
        from app.sqids_config import encode_id

        storage_key = uuid.uuid4()
        now = datetime.now(timezone.utc)
        post = Post(
            storage_key=storage_key,
            storage_shard=compute_storage_shard(storage_key),
            owner_id=owner.id,
            kind=kind,
            title=title,
            description=title,
            hashtags=[],
            art_url=f"https://example.com/{title}.png",
            width=64,
            height=64,
            frame_count=1,
            transparency_meta=False,
            alpha_meta=False,
            metadata_modified_at=now,
            artwork_modified_at=now,
            hash=str(storage_key).replace("-", "") + "c" * 32,
            visible=visible,
            public_visibility=public_visibility,
            deleted_by_user=deleted_by_user,
            hidden_by_mod=hidden_by_mod,
            hidden_by_user=hidden_by_user,
            non_conformant=non_conformant,
        )
        db.add(post)
        db.flush()
        post.public_sqid = encode_id(post.id)
        db.add(
            PostFile(
                post_id=post.id, format="png", file_bytes=32000, is_native=True
            )
        )
        db.commit()
        db.refresh(post)
        return post

    def _react(
        self,
        db: Session,
        *,
        user: User | None,
        post: Post,
        emoji: str,
    ) -> Reaction:
        """Create a reaction row. user=None inserts an anonymous reaction."""
        r = Reaction(
            post_id=post.id,
            user_id=user.id if user is not None else None,
            user_ip="1.2.3.4" if user is None else None,
            emoji=emoji,
        )
        db.add(r)
        db.commit()
        db.refresh(r)
        return r

    @patch("app.mqtt.player_requests.publish")
    def test_happy_path_returns_reacted_posts(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        other_user: User,
        reactor: User,
        db: Session,
    ):
        """Reactor reacted to three public posts → all three returned."""
        posts = [
            self._make_post(db, owner=other_user, title=f"public-{i}")
            for i in range(3)
        ]
        for p in posts:
            self._react(db, user=reactor, post=p, emoji="❤️")

        request = QueryPostsRequest(
            request_id="rx-happy",
            player_key=test_player.player_key,
            channel="reactions",
            user_handle=reactor.handle,
        )
        _handle_query_posts(test_player, request, db)

        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload.get("success") is True
        returned_ids = [p["post_id"] for p in payload["posts"]]
        assert set(returned_ids) == {p.id for p in posts}
        # Sort: latest-reacted-first (reactor reacted to post 2 last)
        assert returned_ids == [posts[2].id, posts[1].id, posts[0].id]

    @patch("app.mqtt.player_requests.publish")
    def test_dedupes_across_emojis(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        other_user: User,
        reactor: User,
        db: Session,
    ):
        """Reacting with two emojis on the same post yields one result row."""
        post = self._make_post(db, owner=other_user, title="dual-emoji")
        self._react(db, user=reactor, post=post, emoji="❤️")
        self._react(db, user=reactor, post=post, emoji="🔥")

        request = QueryPostsRequest(
            request_id="rx-dedupe",
            player_key=test_player.player_key,
            channel="reactions",
            user_handle=reactor.handle,
        )
        _handle_query_posts(test_player, request, db)

        payload = mock_publish.call_args[1]["payload"]
        assert len(payload["posts"]) == 1
        assert payload["posts"][0]["post_id"] == post.id

    @patch("app.mqtt.player_requests.publish")
    def test_latest_reaction_wins_for_ordering(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        other_user: User,
        reactor: User,
        db: Session,
    ):
        """Re-reacting to an older post bumps it to the top of the list."""
        post_a = self._make_post(db, owner=other_user, title="a")
        post_b = self._make_post(db, owner=other_user, title="b")
        self._react(db, user=reactor, post=post_a, emoji="❤️")
        self._react(db, user=reactor, post=post_b, emoji="❤️")
        self._react(db, user=reactor, post=post_a, emoji="🔥")  # latest overall

        request = QueryPostsRequest(
            request_id="rx-latest",
            player_key=test_player.player_key,
            channel="reactions",
            user_handle=reactor.handle,
        )
        _handle_query_posts(test_player, request, db)

        payload = mock_publish.call_args[1]["payload"]
        returned_ids = [p["post_id"] for p in payload["posts"]]
        assert returned_ids == [post_a.id, post_b.id]

    @patch("app.mqtt.player_requests.publish")
    def test_cursor_pagination(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        other_user: User,
        reactor: User,
        db: Session,
    ):
        """Pagination returns two full pages + a partial third."""
        posts = [
            self._make_post(db, owner=other_user, title=f"p{i}") for i in range(10)
        ]
        for p in posts:
            self._react(db, user=reactor, post=p, emoji="👍")

        # Page 1
        request = QueryPostsRequest(
            request_id="rx-pg-1",
            player_key=test_player.player_key,
            channel="reactions",
            user_handle=reactor.handle,
            limit=4,
        )
        _handle_query_posts(test_player, request, db)
        page1 = mock_publish.call_args[1]["payload"]
        assert len(page1["posts"]) == 4
        assert page1["has_more"] is True
        assert page1["next_cursor"] is not None

        # Page 2
        request_2 = QueryPostsRequest(
            request_id="rx-pg-2",
            player_key=test_player.player_key,
            channel="reactions",
            user_handle=reactor.handle,
            limit=4,
            cursor=page1["next_cursor"],
        )
        _handle_query_posts(test_player, request_2, db)
        page2 = mock_publish.call_args[1]["payload"]
        assert len(page2["posts"]) == 4
        assert page2["has_more"] is True

        # Page 3 (partial, 2 items)
        request_3 = QueryPostsRequest(
            request_id="rx-pg-3",
            player_key=test_player.player_key,
            channel="reactions",
            user_handle=reactor.handle,
            limit=4,
            cursor=page2["next_cursor"],
        )
        _handle_query_posts(test_player, request_3, db)
        page3 = mock_publish.call_args[1]["payload"]
        assert len(page3["posts"]) == 2
        assert page3["has_more"] is False
        assert page3.get("next_cursor") is None

        # Pages together cover all 10 posts, no duplicates
        all_ids = [
            p["post_id"]
            for page in (page1, page2, page3)
            for p in page["posts"]
        ]
        assert len(all_ids) == 10
        assert len(set(all_ids)) == 10

    @patch("app.mqtt.player_requests.publish")
    def test_private_post_excluded_for_non_owner(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        other_user: User,
        reactor: User,
        db: Session,
    ):
        """A non-public post by a third user isn't leaked via reactions."""
        public_post = self._make_post(db, owner=other_user, title="public")
        private_post = self._make_post(
            db, owner=other_user, title="private", public_visibility=False
        )
        self._react(db, user=reactor, post=public_post, emoji="❤️")
        self._react(db, user=reactor, post=private_post, emoji="❤️")

        request = QueryPostsRequest(
            request_id="rx-privacy",
            player_key=test_player.player_key,
            channel="reactions",
            user_handle=reactor.handle,
        )
        _handle_query_posts(test_player, request, db)

        payload = mock_publish.call_args[1]["payload"]
        returned_ids = {p["post_id"] for p in payload["posts"]}
        assert returned_ids == {public_post.id}

    @patch("app.mqtt.player_requests.publish")
    def test_player_owner_private_post_included(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        test_user: User,
        reactor: User,
        db: Session,
    ):
        """Player-owner sees their own private posts that target reacted to."""
        own_private = self._make_post(
            db, owner=test_user, title="own-private", public_visibility=False
        )
        self._react(db, user=reactor, post=own_private, emoji="❤️")

        request = QueryPostsRequest(
            request_id="rx-own-private",
            player_key=test_player.player_key,
            channel="reactions",
            user_handle=reactor.handle,
        )
        _handle_query_posts(test_player, request, db)

        payload = mock_publish.call_args[1]["payload"]
        returned_ids = {p["post_id"] for p in payload["posts"]}
        assert returned_ids == {own_private.id}

    @patch("app.mqtt.player_requests.publish")
    def test_hidden_and_deleted_posts_excluded(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        other_user: User,
        reactor: User,
        db: Session,
    ):
        """deleted_by_user / hidden_by_mod / non_conformant / hidden_by_user all filtered."""
        good = self._make_post(db, owner=other_user, title="good")
        deleted = self._make_post(
            db, owner=other_user, title="deleted", deleted_by_user=True
        )
        mod_hidden = self._make_post(
            db, owner=other_user, title="mod-hidden", hidden_by_mod=True
        )
        user_hidden = self._make_post(
            db, owner=other_user, title="user-hidden", hidden_by_user=True
        )
        nc = self._make_post(
            db, owner=other_user, title="nc", non_conformant=True
        )
        for p in (good, deleted, mod_hidden, user_hidden, nc):
            self._react(db, user=reactor, post=p, emoji="❤️")

        request = QueryPostsRequest(
            request_id="rx-hidden",
            player_key=test_player.player_key,
            channel="reactions",
            user_handle=reactor.handle,
        )
        _handle_query_posts(test_player, request, db)

        payload = mock_publish.call_args[1]["payload"]
        returned_ids = {p["post_id"] for p in payload["posts"]}
        assert returned_ids == {good.id}

    @patch("app.mqtt.player_requests.publish")
    def test_anonymous_reactions_excluded(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        other_user: User,
        reactor: User,
        db: Session,
    ):
        """Reactions with user_id=NULL (anon IP-based) never leak into any channel."""
        post = self._make_post(db, owner=other_user, title="anon-only")
        self._react(db, user=None, post=post, emoji="❤️")

        request = QueryPostsRequest(
            request_id="rx-anon",
            player_key=test_player.player_key,
            channel="reactions",
            user_handle=reactor.handle,  # reactor itself has no reactions
        )
        _handle_query_posts(test_player, request, db)

        payload = mock_publish.call_args[1]["payload"]
        assert payload["posts"] == []

    @patch("app.mqtt.player_requests.publish")
    def test_missing_user_identifier_errors(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        db: Session,
    ):
        """channel=reactions with no user_handle or user_sqid → error."""
        request = QueryPostsRequest(
            request_id="rx-missing",
            player_key=test_player.player_key,
            channel="reactions",
        )
        _handle_query_posts(test_player, request, db)

        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is False
        assert payload.get("error_code") == "missing_user_identifier"

    @patch("app.mqtt.player_requests.publish")
    def test_unknown_user_errors(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        db: Session,
    ):
        """Nonexistent user_sqid → user_not_found error."""
        request = QueryPostsRequest(
            request_id="rx-unknown",
            player_key=test_player.player_key,
            channel="reactions",
            user_sqid="does-not-exist",
        )
        _handle_query_posts(test_player, request, db)

        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is False
        assert payload.get("error_code") == "user_not_found"

    @patch("app.mqtt.player_requests.publish")
    def test_empty_result(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        reactor: User,
        db: Session,
    ):
        """Reactor has zero reactions → empty list."""
        request = QueryPostsRequest(
            request_id="rx-empty",
            player_key=test_player.player_key,
            channel="reactions",
            user_handle=reactor.handle,
        )
        _handle_query_posts(test_player, request, db)

        payload = mock_publish.call_args[1]["payload"]
        assert payload["posts"] == []
        assert payload["has_more"] is False
        assert payload.get("next_cursor") is None

    @patch("app.mqtt.player_requests.publish")
    def test_playlist_reaction_returned(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        other_user: User,
        reactor: User,
        db: Session,
    ):
        """Reactions on playlist posts come back as PlaylistPostPayload."""
        playlist = self._make_post(
            db, owner=other_user, title="my-playlist", kind="playlist"
        )
        self._react(db, user=reactor, post=playlist, emoji="❤️")

        request = QueryPostsRequest(
            request_id="rx-playlist",
            player_key=test_player.player_key,
            channel="reactions",
            user_handle=reactor.handle,
        )
        _handle_query_posts(test_player, request, db)

        payload = mock_publish.call_args[1]["payload"]
        assert len(payload["posts"]) == 1
        assert payload["posts"][0]["kind"] == "playlist"
        assert payload["posts"][0]["post_id"] == playlist.id

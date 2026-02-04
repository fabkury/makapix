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
)
from app.mqtt.schemas import (
    SubmitReactionRequest,
    RevokeReactionRequest,
    GetCommentsRequest,
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
        db.add(PostFile(post_id=post.id, format="png", file_bytes=32000, is_native=True))
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

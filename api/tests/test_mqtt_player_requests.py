"""Test MQTT player request handlers."""

import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models import Player, User, Post, Reaction, Comment
from app.mqtt.player_requests import (
    _authenticate_player,
    _handle_query_posts,
    _handle_get_post,
    _handle_submit_view,
    _handle_submit_reaction,
    _handle_revoke_reaction,
    _handle_get_comments,
)
from app.mqtt.schemas import (
    QueryPostsRequest,
    GetPostRequest,
    SubmitViewRequest,
    SubmitReactionRequest,
    RevokeReactionRequest,
    GetCommentsRequest,
    FilterCriterion,
)


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user."""
    user = User(
        handle="testuser",
        email="test@example.com",
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
    posts = []
    for i in range(5):
        storage_key = uuid.uuid4()
        post = Post(
            storage_key=storage_key,
            owner_id=test_user.id,
            kind="artwork",
            title=f"Test Art {i}",
            description=f"Test artwork {i}",
            hashtags=["test", "art"],
            art_url=f"https://example.com/test{i}.png",
            canvas="64x64",
            width=64,
            height=64,
            file_bytes=32000,
            frame_count=1,
            uses_transparency=False,
            uses_alpha=False,
            visible=True,
            promoted=(i % 2 == 0),  # Every other post is promoted
        )
        db.add(post)
        posts.append(post)
    db.commit()
    for post in posts:
        db.refresh(post)
    return posts


@pytest.fixture
def other_user(db: Session) -> User:
    """Create another test user."""
    user = User(
        handle="otheruser",
        email="other@example.com",
        roles=["user"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def other_user_post(other_user: User, db: Session) -> Post:
    """Create a post by another user."""
    storage_key = uuid.uuid4()
    post = Post(
        storage_key=storage_key,
        owner_id=other_user.id,
        kind="artwork",
        title="Other User Art",
        description="Art by other user",
        hashtags=["other"],
        art_url="https://example.com/other.png",
        canvas="64x64",
        width=64,
        height=64,
        file_bytes=32000,
        frame_count=1,
        uses_transparency=False,
        uses_alpha=False,
        visible=True,
    )
    db.add(post)
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


class TestQueryPosts:
    """Test query_posts functionality."""

    @patch("app.mqtt.player_requests.publish")
    def test_query_all_posts(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        test_posts: list[Post],
        db: Session,
    ):
        """Test querying all posts."""
        request = QueryPostsRequest(
            request_id="test-req-1",
            player_key=test_player.player_key,
            channel="all",
            sort="server_order",
            limit=10,
        )
        
        _handle_query_posts(test_player, request, db)
        
        # Verify publish was called
        assert mock_publish.called
        call_args = mock_publish.call_args
        assert "response" in call_args[1]["topic"]
        
        # Check response payload
        payload = call_args[1]["payload"]
        assert payload["success"] is True
        assert len(payload["posts"]) == len(test_posts)

    @patch("app.mqtt.player_requests.publish")
    def test_query_promoted_posts(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        test_posts: list[Post],
        db: Session,
    ):
        """Test querying only promoted posts."""
        request = QueryPostsRequest(
            request_id="test-req-2",
            player_key=test_player.player_key,
            channel="promoted",
            sort="server_order",
            limit=10,
        )
        
        _handle_query_posts(test_player, request, db)
        
        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        
        # Only promoted posts should be returned
        promoted_count = sum(1 for p in test_posts if p.promoted)
        assert len(payload["posts"]) == promoted_count

    @patch("app.mqtt.player_requests.publish")
    def test_query_user_posts(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        test_posts: list[Post],
        db: Session,
    ):
        """Test querying user's own posts."""
        request = QueryPostsRequest(
            request_id="test-req-3",
            player_key=test_player.player_key,
            channel="user",
            sort="created_at",
            limit=10,
        )
        
        _handle_query_posts(test_player, request, db)
        
        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        
        # All returned posts should belong to the player's owner
        assert all(p["owner_handle"] == test_player.owner.handle for p in payload["posts"])

    @patch("app.mqtt.player_requests.publish")
    def test_query_with_pagination(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        test_posts: list[Post],
        db: Session,
    ):
        """Test query with pagination."""
        request = QueryPostsRequest(
            request_id="test-req-4",
            player_key=test_player.player_key,
            channel="all",
            sort="server_order",
            limit=2,
        )
        
        _handle_query_posts(test_player, request, db)
        
        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        
        # Should return only 2 posts
        assert len(payload["posts"]) == 2
        # Should have more results
        assert payload["has_more"] is True
        assert payload["next_cursor"] is not None

    @patch("app.mqtt.player_requests.publish")
    def test_query_by_user_handle(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        other_user: User,
        other_user_post: Post,
        db: Session,
    ):
        """Test querying posts by arbitrary user handle."""
        request = QueryPostsRequest(
            request_id="test-req-5",
            player_key=test_player.player_key,
            channel="by_user",
            user_handle=other_user.handle,
            sort="server_order",
            limit=10,
        )
        
        _handle_query_posts(test_player, request, db)
        
        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        
        # Should return posts from the specified user
        assert payload["success"] is True
        assert len(payload["posts"]) == 1
        assert payload["posts"][0]["owner_handle"] == other_user.handle

    @patch("app.mqtt.player_requests._send_error_response")
    def test_query_by_user_handle_missing(
        self,
        mock_error: MagicMock,
        test_player: Player,
        db: Session,
    ):
        """Test querying by user without providing user_handle."""
        request = QueryPostsRequest(
            request_id="test-req-6",
            player_key=test_player.player_key,
            channel="by_user",
            # user_handle not provided
            sort="server_order",
            limit=10,
        )
        
        _handle_query_posts(test_player, request, db)
        
        # Error response should be sent
        assert mock_error.called
        assert "user_handle or user_sqid is required" in mock_error.call_args[0][2]

    @patch("app.mqtt.player_requests._send_error_response")
    def test_query_by_user_handle_not_found(
        self,
        mock_error: MagicMock,
        test_player: Player,
        db: Session,
    ):
        """Test querying by non-existent user handle."""
        request = QueryPostsRequest(
            request_id="test-req-7",
            player_key=test_player.player_key,
            channel="by_user",
            user_handle="nonexistentuser",
            sort="server_order",
            limit=10,
        )
        
        _handle_query_posts(test_player, request, db)
        
        # Error response should be sent
        assert mock_error.called
        assert "not found" in mock_error.call_args[0][2]


class TestSubmitView:
    """Test submit_view functionality."""

    @patch("app.mqtt.player_requests.publish")
    @patch("app.mqtt.player_requests.write_view_event")
    def test_submit_view_success(
        self,
        mock_write_view: MagicMock,
        mock_publish: MagicMock,
        test_player: Player,
        other_user_post: Post,
        db: Session,
    ):
        """Test submitting a view event."""
        request = SubmitViewRequest(
            request_id="test-view-1",
            player_key=test_player.player_key,
            post_id=other_user_post.id,
            view_intent="intentional",
        )
        
        _handle_submit_view(test_player, request, db)
        
        # Verify view event was queued
        assert mock_write_view.delay.called
        event_data = mock_write_view.delay.call_args[0][0]
        assert event_data["post_id"] == str(other_user_post.id)
        assert event_data["device_type"] == "player"
        assert event_data["view_type"] == "intentional"
        
        # Verify success response
        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True

    @patch("app.mqtt.player_requests.publish")
    @patch("app.mqtt.player_requests.write_view_event")
    def test_submit_view_own_post(
        self,
        mock_write_view: MagicMock,
        mock_publish: MagicMock,
        test_player: Player,
        test_posts: list[Post],
        db: Session,
    ):
        """Test that views on own posts are not recorded."""
        request = SubmitViewRequest(
            request_id="test-view-2",
            player_key=test_player.player_key,
            post_id=test_posts[0].id,
            view_intent="automated",
        )
        
        _handle_submit_view(test_player, request, db)
        
        # View event should NOT be queued (owner's post)
        assert not mock_write_view.delay.called
        
        # But success response should still be sent
        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True

    @patch("app.mqtt.player_requests._send_error_response")
    def test_submit_view_invalid_post(
        self,
        mock_error: MagicMock,
        test_player: Player,
        db: Session,
    ):
        """Test submitting view for non-existent post."""
        request = SubmitViewRequest(
            request_id="test-view-3",
            player_key=test_player.player_key,
            post_id=99999,
            view_intent="intentional",
        )
        
        _handle_submit_view(test_player, request, db)
        
        # Error response should be sent
        assert mock_error.called


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
        reaction = db.query(Reaction).filter(
            Reaction.post_id == other_user_post.id,
            Reaction.user_id == test_player.owner_id,
            Reaction.emoji == "❤️",
        ).first()
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
        count = db.query(Reaction).filter(
            Reaction.post_id == other_user_post.id,
            Reaction.user_id == test_player.owner_id,
            Reaction.emoji == "👍",
        ).count()
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
        exists = db.query(Reaction).filter(
            Reaction.post_id == other_user_post.id,
            Reaction.user_id == test_player.owner_id,
            Reaction.emoji == "😊",
        ).first()
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
    def test_comments(self, other_user_post: Post, test_user: User, db: Session) -> list[Comment]:
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


class TestQueryPostsCriteria:
    """Test query_posts with AMP criteria filtering."""

    @pytest.fixture
    def amp_posts(self, test_user: User, db: Session) -> list[Post]:
        """Create posts with varied AMP metadata for testing."""
        configs = [
            # Post 0: Small PNG, static, no transparency
            {
                "width": 64,
                "height": 64,
                "file_bytes": 1000,
                "frame_count": 1,
                "transparency_actual": False,
                "alpha_actual": False,
                "mime_type": "image/png",
                "min_frame_duration_ms": None,
                "max_frame_duration_ms": None,
            },
            # Post 1: Medium PNG, static, with transparency
            {
                "width": 128,
                "height": 128,
                "file_bytes": 5000,
                "frame_count": 1,
                "transparency_actual": True,
                "alpha_actual": False,
                "mime_type": "image/png",
                "min_frame_duration_ms": None,
                "max_frame_duration_ms": None,
            },
            # Post 2: Large GIF, animated
            {
                "width": 256,
                "height": 256,
                "file_bytes": 50000,
                "frame_count": 10,
                "transparency_actual": False,
                "alpha_actual": False,
                "mime_type": "image/gif",
                "min_frame_duration_ms": 100,
                "max_frame_duration_ms": 200,
            },
            # Post 3: WebP animated with alpha
            {
                "width": 128,
                "height": 64,
                "file_bytes": 20000,
                "frame_count": 5,
                "transparency_actual": True,
                "alpha_actual": True,
                "mime_type": "image/webp",
                "min_frame_duration_ms": 50,
                "max_frame_duration_ms": 100,
            },
            # Post 4: BMP static
            {
                "width": 32,
                "height": 32,
                "file_bytes": 3000,
                "frame_count": 1,
                "transparency_actual": False,
                "alpha_actual": False,
                "mime_type": "image/bmp",
                "min_frame_duration_ms": None,
                "max_frame_duration_ms": None,
            },
        ]
        posts = []
        for i, cfg in enumerate(configs):
            post = Post(
                storage_key=uuid.uuid4(),
                owner_id=test_user.id,
                kind="artwork",
                title=f"AMP Test {i}",
                hashtags=["test"],
                art_url=f"https://example.com/amp{i}.png",
                canvas=f"{cfg['width']}x{cfg['height']}",
                visible=True,
                **cfg,
            )
            db.add(post)
            posts.append(post)
        db.commit()
        for p in posts:
            db.refresh(p)
        return posts

    @patch("app.mqtt.player_requests.publish")
    def test_criteria_width_range(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        amp_posts: list[Post],
        db: Session,
    ):
        """Test filtering by width range (64-128)."""
        request = QueryPostsRequest(
            request_id="criteria-1",
            player_key=test_player.player_key,
            channel="all",
            criteria=[
                FilterCriterion(field="width", op="gte", value=64),
                FilterCriterion(field="width", op="lte", value=128),
            ],
            limit=50,
        )

        _handle_query_posts(test_player, request, db)

        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True
        # Should match posts with width 64, 128, 128 (posts 0, 1, 3)
        assert len(payload["posts"]) == 3
        widths = {p["width"] for p in payload["posts"]}
        assert widths == {64, 128}

    @patch("app.mqtt.player_requests.publish")
    def test_criteria_file_format_in(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        amp_posts: list[Post],
        db: Session,
    ):
        """Test filtering by file_format IN list."""
        request = QueryPostsRequest(
            request_id="criteria-2",
            player_key=test_player.player_key,
            channel="all",
            criteria=[
                FilterCriterion(field="file_format", op="in", value=["png", "bmp"]),
            ],
            limit=50,
        )

        _handle_query_posts(test_player, request, db)

        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True
        # PNG posts (0, 1) + BMP post (4) = 3 posts
        assert len(payload["posts"]) == 3

    @patch("app.mqtt.player_requests.publish")
    def test_criteria_boolean_filter(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        amp_posts: list[Post],
        db: Session,
    ):
        """Test filtering by boolean field."""
        request = QueryPostsRequest(
            request_id="criteria-3",
            player_key=test_player.player_key,
            channel="all",
            criteria=[
                FilterCriterion(field="transparency_actual", op="eq", value=True),
            ],
            limit=50,
        )

        _handle_query_posts(test_player, request, db)

        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True
        # Posts with transparency: 1, 3
        assert len(payload["posts"]) == 2

    @patch("app.mqtt.player_requests.publish")
    def test_criteria_is_null(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        amp_posts: list[Post],
        db: Session,
    ):
        """Test IS NULL operator for nullable fields."""
        request = QueryPostsRequest(
            request_id="criteria-4",
            player_key=test_player.player_key,
            channel="all",
            criteria=[
                FilterCriterion(field="min_frame_duration_ms", op="is_null"),
            ],
            limit=50,
        )

        _handle_query_posts(test_player, request, db)

        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True
        # Static images have NULL frame duration: 0, 1, 4
        assert len(payload["posts"]) == 3

    @patch("app.mqtt.player_requests.publish")
    def test_criteria_is_not_null(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        amp_posts: list[Post],
        db: Session,
    ):
        """Test IS NOT NULL operator for nullable fields."""
        request = QueryPostsRequest(
            request_id="criteria-5",
            player_key=test_player.player_key,
            channel="all",
            criteria=[
                FilterCriterion(field="min_frame_duration_ms", op="is_not_null"),
            ],
            limit=50,
        )

        _handle_query_posts(test_player, request, db)

        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True
        # Animated images have non-NULL frame duration: 2, 3
        assert len(payload["posts"]) == 2

    @patch("app.mqtt.player_requests.publish")
    def test_criteria_combined(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        amp_posts: list[Post],
        db: Session,
    ):
        """Test multiple criteria combined (AND logic)."""
        request = QueryPostsRequest(
            request_id="criteria-6",
            player_key=test_player.player_key,
            channel="all",
            criteria=[
                FilterCriterion(field="frame_count", op="gt", value=1),
                FilterCriterion(field="transparency_actual", op="eq", value=False),
            ],
            limit=50,
        )

        _handle_query_posts(test_player, request, db)

        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True
        # Animated + no transparency: only post 2 (GIF)
        assert len(payload["posts"]) == 1

    @patch("app.mqtt.player_requests.publish")
    def test_criteria_empty_returns_all(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        amp_posts: list[Post],
        db: Session,
    ):
        """Test that empty criteria returns all posts (backward compatible)."""
        request = QueryPostsRequest(
            request_id="criteria-7",
            player_key=test_player.player_key,
            channel="all",
            criteria=[],
            limit=50,
        )

        _handle_query_posts(test_player, request, db)

        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True
        assert len(payload["posts"]) == 5

    @patch("app.mqtt.player_requests.publish")
    def test_criteria_numeric_in_operator(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        amp_posts: list[Post],
        db: Session,
    ):
        """Test IN operator with numeric values."""
        request = QueryPostsRequest(
            request_id="criteria-8",
            player_key=test_player.player_key,
            channel="all",
            criteria=[
                FilterCriterion(field="width", op="in", value=[64, 256]),
            ],
            limit=50,
        )

        _handle_query_posts(test_player, request, db)

        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True
        # Posts with width 64 or 256: 0, 2
        assert len(payload["posts"]) == 2

    @patch("app.mqtt.player_requests.publish")
    def test_criteria_file_bytes_less_than(
        self,
        mock_publish: MagicMock,
        test_player: Player,
        amp_posts: list[Post],
        db: Session,
    ):
        """Test filtering by file_bytes < value."""
        request = QueryPostsRequest(
            request_id="criteria-9",
            player_key=test_player.player_key,
            channel="all",
            criteria=[
                FilterCriterion(field="file_bytes", op="lt", value=10000),
            ],
            limit=50,
        )

        _handle_query_posts(test_player, request, db)

        assert mock_publish.called
        payload = mock_publish.call_args[1]["payload"]
        assert payload["success"] is True
        # Posts with file_bytes < 10000: 0 (1000), 1 (5000), 4 (3000)
        assert len(payload["posts"]) == 3

    def test_criteria_invalid_operator_for_boolean(self):
        """Test error when using invalid operator for boolean field."""
        with pytest.raises(ValueError) as exc_info:
            FilterCriterion(field="transparency_actual", op="gt", value=True)
        assert "not valid for boolean field" in str(exc_info.value)

    def test_criteria_invalid_file_format_value(self):
        """Test error for invalid file_format enum value."""
        with pytest.raises(ValueError) as exc_info:
            FilterCriterion(field="file_format", op="eq", value="jpeg")
        assert "Invalid file_format" in str(exc_info.value)

    def test_criteria_missing_value_for_eq(self):
        """Test error when value is missing for eq operator."""
        with pytest.raises(ValueError) as exc_info:
            FilterCriterion(field="width", op="eq", value=None)
        assert "requires a value" in str(exc_info.value)

    def test_criteria_value_provided_for_is_null(self):
        """Test error when value is provided for is_null operator."""
        with pytest.raises(ValueError) as exc_info:
            FilterCriterion(field="min_frame_duration_ms", op="is_null", value=100)
        assert "does not accept a value" in str(exc_info.value)

    def test_criteria_in_requires_array(self):
        """Test error when IN operator is given non-array value."""
        with pytest.raises(ValueError) as exc_info:
            FilterCriterion(field="width", op="in", value=64)
        assert "requires an array" in str(exc_info.value)

    def test_criteria_is_null_on_non_nullable_field(self):
        """Test error when using is_null on non-nullable field."""
        with pytest.raises(ValueError) as exc_info:
            FilterCriterion(field="width", op="is_null")
        assert "not nullable" in str(exc_info.value)

    def test_criteria_max_64_items(self):
        """Test that max 64 criteria are accepted."""
        # 64 criteria should work
        criteria = [
            FilterCriterion(field="width", op="gte", value=1) for _ in range(64)
        ]
        request = QueryPostsRequest(
            request_id="criteria-max",
            player_key=uuid.uuid4(),
            channel="all",
            criteria=criteria,
            limit=50,
        )
        assert len(request.criteria) == 64

    def test_criteria_exceeds_limit(self):
        """Test that >64 criteria raises validation error."""
        criteria = [
            FilterCriterion(field="width", op="gte", value=1) for _ in range(65)
        ]
        with pytest.raises(ValueError):
            QueryPostsRequest(
                request_id="criteria-over-limit",
                player_key=uuid.uuid4(),
                channel="all",
                criteria=criteria,
            )

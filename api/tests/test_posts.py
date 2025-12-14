"""Test post CRUD operations."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.main import app
from app.models import Post, User


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user."""
    user = User(
        handle="testuser",
        email="test@example.com",
        roles=["user"]
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_post(test_user: User, db: Session) -> Post:
    """Create a test post."""
    import uuid
    from app.sqids_config import encode_id
    
    storage_key = uuid.uuid4()
    post = Post(
        storage_key=storage_key,
        owner_id=test_user.id,
        kind="artwork",
        title="Test Art",
        description="A test artwork",
        hashtags=["test", "art"],
        art_url="https://example.com/test.png",
        canvas="64x64",
        width=64,
        height=64,
        file_bytes=32 * 1024,
        frame_count=1,
        uses_transparency=False,
        uses_alpha=False,
        promoted=True,  # Make it visible without auth
    )
    db.add(post)
    db.flush()  # Get the post ID
    post.public_sqid = encode_id(post.id)
    db.commit()
    db.refresh(post)
    return post


def test_create_post_requires_auth():
    """Test that creating a post requires authentication."""
    client = TestClient(app)
    response = client.post("/post", json={
        "title": "Test Post",
        "art_url": "https://example.com/test.png",
        "canvas": "64x64",
        "file_bytes": 32 * 1024
    })
    
    assert response.status_code == 401


def test_create_post_with_valid_data(test_user: User):
    """Test creating a post with valid data."""
    client = TestClient(app)
    token = create_access_token(test_user.id)
    
    response = client.post("/post", 
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Test Art",
            "description": "A test artwork",
            "hashtags": ["test", "art"],
            "art_url": "https://example.com/test.png",
            "canvas": "64x64",
            "file_bytes": 32 * 1024
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Art"
    assert data["owner_id"] == test_user.id
    assert data["canvas"] == "64x64"
    assert data["width"] == 64
    assert data["height"] == 64


def test_create_post_invalid_canvas(test_user: User):
    """Test creating a post with invalid canvas size."""
    client = TestClient(app)
    token = create_access_token(test_user.id)
    
    response = client.post("/post", 
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Test Art",
            "art_url": "https://example.com/test.png",
            "canvas": "999x999",  # Invalid canvas size
            "file_bytes": 32 * 1024
        }
    )
    
    assert response.status_code == 400
    assert "not allowed" in response.json()["detail"]


def test_create_post_file_too_large(test_user: User):
    """Test creating a post with file size exceeding limit."""
    client = TestClient(app)
    token = create_access_token(test_user.id)
    
    response = client.post("/post", 
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Test Art",
            "art_url": "https://example.com/test.png",
            "canvas": "64x64",
            "file_bytes": 6 * 1024 * 1024  # Too large (global limit is 5 MiB)
        }
    )
    
    assert response.status_code == 400
    assert "exceeds limit" in response.json()["detail"]


def test_list_posts_public():
    """Test listing posts without authentication."""
    client = TestClient(app)
    response = client.get("/post")
    
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "next_cursor" in data


def test_list_posts_with_hashtag_filter(test_post: Post):
    """Test listing posts with hashtag filter."""
    client = TestClient(app)
    response = client.get("/post?hashtag=test")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 1
    # The test post should be in the results
    post_ids = [item["id"] for item in data["items"]]
    assert test_post.id in post_ids


def test_get_post_by_storage_key(test_post: Post):
    """Test getting a post by storage key (legacy route, redirects to canonical URL)."""
    client = TestClient(app, follow_redirects=False)
    response = client.get(f"/post/{test_post.storage_key}")
    
    # Legacy route should redirect to canonical URL
    assert response.status_code == 301
    assert f"/p/{test_post.public_sqid}" in response.headers["location"]


def test_get_nonexistent_post():
    """Test getting a nonexistent post."""
    client = TestClient(app)
    response = client.get("/post/00000000-0000-0000-0000-000000000000")
    
    assert response.status_code == 404


def test_update_post_requires_auth(test_post: Post):
    """Test that updating a post requires authentication."""
    client = TestClient(app)
    response = client.patch(f"/post/{test_post.id}", json={
        "title": "Updated Title"
    })
    
    assert response.status_code == 401


def test_update_post_requires_ownership(test_user: User, db: Session):
    """Test that updating a post requires ownership."""
    import uuid
    from app.sqids_config import encode_id
    
    # Create another user
    other_user = User(
        handle="otheruser",
        email="other@example.com",
        roles=["user"]
    )
    db.add(other_user)
    db.commit()
    db.refresh(other_user)
    
    # Create post owned by other user
    storage_key = uuid.uuid4()
    post = Post(
        storage_key=storage_key,
        owner_id=other_user.id,
        kind="artwork",
        title="Other's Post",
        art_url="https://example.com/other.png",
        canvas="64x64",
        width=64,
        height=64,
        file_bytes=32 * 1024,
        frame_count=1,
        uses_transparency=False,
        uses_alpha=False,
        promoted=True,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    db.commit()
    db.refresh(post)
    
    # Try to update with test_user's token
    client = TestClient(app)
    token = create_access_token(test_user.id)
    
    response = client.patch(f"/post/{post.id}", 
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Hacked Title"}
    )
    
    assert response.status_code == 403


def test_update_post_success(test_user: User, test_post: Post):
    """Test successfully updating a post."""
    client = TestClient(app)
    token = create_access_token(test_user.id)
    
    response = client.patch(f"/post/{test_post.id}", 
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Updated Title"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"


def test_delete_post_requires_auth(test_post: Post):
    """Test that deleting a post requires authentication."""
    client = TestClient(app)
    response = client.delete(f"/post/{test_post.id}")
    
    assert response.status_code == 401


def test_delete_post_requires_ownership(test_user: User, db: Session):
    """Test that deleting a post requires ownership."""
    import uuid
    from app.sqids_config import encode_id
    
    # Create another user
    other_user = User(
        handle="otheruser",
        email="other@example.com",
        roles=["user"]
    )
    db.add(other_user)
    db.commit()
    db.refresh(other_user)
    
    # Create post owned by other user
    storage_key = uuid.uuid4()
    post = Post(
        storage_key=storage_key,
        owner_id=other_user.id,
        kind="artwork",
        title="Other's Post",
        art_url="https://example.com/other.png",
        canvas="64x64",
        width=64,
        height=64,
        file_bytes=32 * 1024,
        frame_count=1,
        uses_transparency=False,
        uses_alpha=False,
        promoted=True,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    db.commit()
    db.refresh(post)
    
    # Try to delete with test_user's token
    client = TestClient(app)
    token = create_access_token(test_user.id)
    
    response = client.delete(f"/post/{post.id}", 
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 403


def test_delete_post_success(test_user: User, test_post: Post):
    """Test successfully deleting a post."""
    client = TestClient(app)
    token = create_access_token(test_user.id)
    
    response = client.delete(f"/post/{test_post.id}", 
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 204
    
    # Verify post is soft deleted (use storage_key for the GET route)
    response = client.get(f"/post/{test_post.storage_key}")
    assert response.status_code == 404


def test_create_post_with_64_hashtags(test_user: User):
    """Test creating a post with 64 hashtags (new limit)."""
    client = TestClient(app)
    token = create_access_token(test_user.id)
    
    # Create 64 hashtags
    hashtags = [f"tag{i}" for i in range(64)]
    
    response = client.post("/post", 
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Test Art with Many Hashtags",
            "description": "Testing hashtag limit",
            "hashtags": hashtags,
            "art_url": "https://example.com/test.png",
            "canvas": "64x64",
            "file_bytes": 32 * 1024
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert len(data["hashtags"]) == 64


def test_create_post_trims_excess_hashtags(test_user: User):
    """Test that posts with more than 64 hashtags are trimmed."""
    client = TestClient(app)
    token = create_access_token(test_user.id)
    
    # Create 100 hashtags (should be trimmed to 64)
    hashtags = [f"tag{i}" for i in range(100)]
    
    response = client.post("/post", 
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Test Art with Too Many Hashtags",
            "description": "Testing hashtag trimming",
            "hashtags": hashtags,
            "art_url": "https://example.com/test.png",
            "canvas": "64x64",
            "file_bytes": 32 * 1024
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    # Should be trimmed to 64
    assert len(data["hashtags"]) == 64
    # Should have the first 64 tags
    assert data["hashtags"][0] == "tag0"
    assert data["hashtags"][63] == "tag63"

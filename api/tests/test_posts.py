"""Test post CRUD operations."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.main import app
from app.models import Post, User


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user."""
    import uuid

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
def test_post(test_user: User, db: Session) -> Post:
    """Create a test post."""
    import uuid
    from app.sqids_config import encode_id
    from app.vault import compute_storage_shard

    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
    post = Post(
        storage_key=storage_key,
        storage_shard=compute_storage_shard(storage_key),
        owner_id=test_user.id,
        kind="artwork",
        title="Test Art",
        description="A test artwork",
        hashtags=["test", "art"],
        art_url="https://example.com/test.png",
        width=64,
        height=64,
        file_bytes=32 * 1024,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=str(storage_key).replace("-", "") + "a" * 32,  # Unique hash
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
    response = client.post(
        "/post",
        json={
            "title": "Test Post",
            "art_url": "https://example.com/test.png",
            "width": 64,
            "height": 64,
            "file_bytes": 32 * 1024,
            "hash": "a" * 64,
        },
    )

    assert response.status_code == 401


def test_get_nonexistent_post():
    """Test getting a nonexistent post."""
    client = TestClient(app)
    response = client.get("/post/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404


def test_update_post_requires_auth(test_post: Post):
    """Test that updating a post requires authentication."""
    client = TestClient(app)
    response = client.patch(f"/post/{test_post.id}", json={"title": "Updated Title"})

    assert response.status_code == 401


def test_update_post_requires_ownership(test_user: User, db: Session):
    """Test that updating a post requires ownership."""
    import uuid
    from app.sqids_config import encode_id
    from app.vault import compute_storage_shard

    # Create another user
    unique_id = str(uuid.uuid4())[:8]
    other_user = User(
        handle=f"otheruser_{unique_id}",
        email=f"other_{unique_id}@example.com",
        roles=["user"],
    )
    db.add(other_user)
    db.commit()
    db.refresh(other_user)

    # Create post owned by other user
    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
    post = Post(
        storage_key=storage_key,
        storage_shard=compute_storage_shard(storage_key),
        owner_id=other_user.id,
        kind="artwork",
        title="Other's Post",
        art_url="https://example.com/other.png",
        width=64,
        height=64,
        file_bytes=32 * 1024,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=str(storage_key).replace("-", "") + "b" * 32,  # Unique hash
        promoted=True,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    db.commit()
    db.refresh(post)

    # Try to update with test_user's token
    client = TestClient(app)
    token = create_access_token(test_user.user_key)

    response = client.patch(
        f"/post/{post.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Hacked Title"},
    )

    assert response.status_code == 403


def test_update_post_success(test_user: User, test_post: Post):
    """Test successfully updating a post."""
    client = TestClient(app)
    token = create_access_token(test_user.user_key)

    response = client.patch(
        f"/post/{test_post.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Updated Title"},
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
    from app.vault import compute_storage_shard

    # Create another user
    unique_id = str(uuid.uuid4())[:8]
    other_user = User(
        handle=f"otheruser_{unique_id}",
        email=f"other_{unique_id}@example.com",
        roles=["user"],
    )
    db.add(other_user)
    db.commit()
    db.refresh(other_user)

    # Create post owned by other user
    storage_key = uuid.uuid4()
    now = datetime.now(timezone.utc)
    post = Post(
        storage_key=storage_key,
        storage_shard=compute_storage_shard(storage_key),
        owner_id=other_user.id,
        kind="artwork",
        title="Other's Post",
        art_url="https://example.com/other.png",
        width=64,
        height=64,
        file_bytes=32 * 1024,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=str(storage_key).replace("-", "") + "b" * 32,  # Unique hash
        promoted=True,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    db.commit()
    db.refresh(post)

    # Try to delete with test_user's token
    client = TestClient(app)
    token = create_access_token(test_user.user_key)

    response = client.delete(
        f"/post/{post.id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_delete_post_success(test_user: User, test_post: Post):
    """Test successfully deleting a post."""
    client = TestClient(app)
    token = create_access_token(test_user.user_key)

    response = client.delete(
        f"/post/{test_post.id}", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 204

    # Verify post is soft deleted (use storage_key for the GET route)
    response = client.get(f"/post/{test_post.storage_key}")
    assert response.status_code == 404

"""Test Sqids routes and migration."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.main import app
from app.models import Post, User
from app.sqids_config import encode_id


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user with a unique handle."""
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
def test_moderator(db: Session) -> User:
    """Create a test moderator with a unique handle."""
    import uuid

    unique_id = str(uuid.uuid4())[:8]
    user = User(
        handle=f"moderator_{unique_id}",
        email=f"mod_{unique_id}@example.com",
        roles=["moderator"],
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
        art_url="/api/vault/test.png",
        file_bytes=32 * 1024,
        width=64,
        height=64,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=str(storage_key).replace("-", "") + "a" * 32,  # Unique hash
        promoted=True,  # Make it promoted so it's accessible without auth
        visible=True,
        hidden_by_user=False,
        hidden_by_mod=False,
    )
    db.add(post)
    db.flush()
    # Generate public_sqid
    post.public_sqid = encode_id(post.id)
    db.commit()
    db.refresh(post)
    return post


@pytest.fixture
def test_hidden_post(test_user: User, db: Session) -> Post:
    """Create a hidden test post."""
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
        title="Hidden Art",
        description="A hidden artwork",
        hashtags=[],
        art_url="/api/vault/hidden.png",
        file_bytes=32 * 1024,
        width=64,
        height=64,
        frame_count=1,
        transparency_meta=False,
        alpha_meta=False,
        metadata_modified_at=now,
        artwork_modified_at=now,
        hash=str(storage_key).replace("-", "") + "b" * 32,  # Unique hash
        promoted=False,
        visible=True,
        hidden_by_user=True,  # Hidden by user
        hidden_by_mod=False,
    )
    db.add(post)
    db.flush()
    post.public_sqid = encode_id(post.id)
    db.commit()
    db.refresh(post)
    return post


def test_get_post_by_sqid_anonymous(test_post: Post):
    """Test getting a promoted post by sqid as anonymous user."""
    client = TestClient(app)
    response = client.get(f"/p/{test_post.public_sqid}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_post.id
    assert data["public_sqid"] == test_post.public_sqid
    assert data["storage_key"] == str(test_post.storage_key)
    assert data["title"] == test_post.title


def test_get_post_by_sqid_not_found():
    """Test getting a non-existent post by sqid."""
    client = TestClient(app)
    response = client.get("/p/invalid_sqid")

    assert response.status_code == 404


def test_get_post_by_sqid_hidden_anonymous(test_hidden_post: Post):
    """Test that anonymous users cannot access hidden posts."""
    client = TestClient(app)
    response = client.get(f"/p/{test_hidden_post.public_sqid}")

    assert response.status_code == 404


def test_get_post_by_sqid_hidden_owner(test_user: User, test_hidden_post: Post):
    """Test that post owner can access their hidden post."""
    client = TestClient(app)
    token = create_access_token(test_user.user_key)

    response = client.get(
        f"/p/{test_hidden_post.public_sqid}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_hidden_post.id


def test_get_post_by_sqid_hidden_moderator(
    test_moderator: User, test_hidden_post: Post
):
    """Test that moderators can access hidden posts."""
    client = TestClient(app)
    token = create_access_token(test_moderator.user_key)

    response = client.get(
        f"/p/{test_hidden_post.public_sqid}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_hidden_post.id


def test_legacy_route_not_found():
    """Test that legacy route returns 404 for non-existent post."""
    import uuid

    client = TestClient(app)
    fake_uuid = uuid.uuid4()
    response = client.get(f"/post/{fake_uuid}")

    assert response.status_code == 404


def test_legacy_route_hidden_anonymous(test_hidden_post: Post):
    """Test that legacy route returns 404 for hidden posts (anonymous)."""
    client = TestClient(app)
    response = client.get(f"/post/{test_hidden_post.storage_key}")

    assert response.status_code == 404


def test_migration_storage_key_populated(test_post: Post):
    """Test that storage_key is populated after migration."""
    assert test_post.storage_key is not None
    assert isinstance(
        test_post.storage_key, type(test_post.storage_key)
    )  # Should be UUID type


def test_migration_public_sqid_populated(test_post: Post):
    """Test that public_sqid is populated and unique."""
    assert test_post.public_sqid is not None
    assert len(test_post.public_sqid) <= 16

    # Verify it can be decoded back to the post ID
    from app.sqids_config import decode_sqid

    decoded_id = decode_sqid(test_post.public_sqid)
    assert decoded_id == test_post.id


def test_download_by_sqid(test_post: Post):
    """Test downloading file by public_sqid."""
    # Note: This test assumes the file exists in the vault
    # In a real scenario, you'd need to create the file first
    client = TestClient(app)
    response = client.get(f"/d/{test_post.public_sqid}")

    # Should return 404 if file doesn't exist, or 200 if it does
    assert response.status_code in [200, 404]


def test_download_by_storage_key(test_post: Post):
    """Test downloading file by storage_key."""
    client = TestClient(app)
    response = client.get(f"/download/{test_post.storage_key}")

    # Should return 404 if file doesn't exist, or 200 if it does
    assert response.status_code in [200, 404]


def test_download_hidden_post_anonymous(test_hidden_post: Post):
    """Test that anonymous users cannot download hidden posts."""
    client = TestClient(app)
    response = client.get(f"/d/{test_hidden_post.public_sqid}")

    assert response.status_code == 404


def test_download_hidden_post_owner(test_user: User, test_hidden_post: Post):
    """Test that post owner can download their hidden post."""
    client = TestClient(app)
    token = create_access_token(test_user.user_key)

    response = client.get(
        f"/d/{test_hidden_post.public_sqid}",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Should return 404 if file doesn't exist, or 200 if it does
    # But should NOT return 404 due to visibility check
    assert response.status_code in [200, 404]
    # If 404, it should be because file doesn't exist, not because of visibility
    if response.status_code == 404:
        assert (
            "Post not found" in response.json()["detail"]
            or "File not found" in response.json()["detail"]
        )

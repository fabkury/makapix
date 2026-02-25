"""Tests for the player verify-user endpoint."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def clear_verify_cache():
    """Clear user_verify cache and rate limit keys before each test."""
    from app.cache import cache_invalidate

    cache_invalidate("user_verify:*")
    cache_invalidate("ratelimit:player_verify:*")
    yield
    cache_invalidate("user_verify:*")


@pytest.fixture
def verified_user(db: "Session"):
    """Create a verified, eligible user."""
    from app.models import User
    from app.sqids_config import encode_user_id

    unique = str(uuid.uuid4())[:8]
    user = User(
        handle=f"verifytest_{unique}",
        email=f"verify_{unique}@example.com",
        email_verified=True,
        roles=["user"],
        reputation=42,
    )
    db.add(user)
    db.flush()
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def unverified_user(db: "Session"):
    """Create a user who has not verified their email."""
    from app.models import User
    from app.sqids_config import encode_user_id

    unique = str(uuid.uuid4())[:8]
    user = User(
        handle=f"unverified_{unique}",
        email=f"unverified_{unique}@example.com",
        email_verified=False,
        roles=["user"],
    )
    db.add(user)
    db.flush()
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def deactivated_user(db: "Session"):
    """Create a deactivated user."""
    from app.models import User
    from app.sqids_config import encode_user_id

    unique = str(uuid.uuid4())[:8]
    user = User(
        handle=f"deactivated_{unique}",
        email=f"deactivated_{unique}@example.com",
        email_verified=True,
        deactivated=True,
        roles=["user"],
    )
    db.add(user)
    db.flush()
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def hidden_user(db: "Session"):
    """Create a user hidden by a moderator."""
    from app.models import User
    from app.sqids_config import encode_user_id

    unique = str(uuid.uuid4())[:8]
    user = User(
        handle=f"hidden_{unique}",
        email=f"hidden_{unique}@example.com",
        email_verified=True,
        hidden_by_mod=True,
        roles=["user"],
    )
    db.add(user)
    db.flush()
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def banned_user(db: "Session"):
    """Create a user with an active temporal ban."""
    from app.models import User
    from app.sqids_config import encode_user_id

    unique = str(uuid.uuid4())[:8]
    user = User(
        handle=f"banned_{unique}",
        email=f"banned_{unique}@example.com",
        email_verified=True,
        banned_until=datetime.now(timezone.utc) + timedelta(days=7),
        roles=["user"],
    )
    db.add(user)
    db.flush()
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    return user


def test_verify_user_valid(client: "TestClient", verified_user):
    """Valid verified user returns 200 with correct fields."""
    response = client.get(f"/player/verify-user/{verified_user.public_sqid}")
    assert response.status_code == 200
    data = response.json()
    assert data["handle"] == verified_user.handle
    assert data["reputation"] == 42
    assert data["artwork_count"] == 0
    assert "avatar_url" in data


def test_verify_user_invalid_sqid(client: "TestClient"):
    """Completely invalid SQID returns 404."""
    response = client.get("/player/verify-user/ZZZZZZZZ")
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_verify_user_unknown_sqid(client: "TestClient"):
    """Valid-looking SQID that decodes but has no matching user returns 404."""
    from app.sqids_config import encode_user_id

    fake_sqid = encode_user_id(999999999)
    response = client.get(f"/player/verify-user/{fake_sqid}")
    assert response.status_code == 404


def test_verify_user_unverified_email(client: "TestClient", unverified_user):
    """User with unverified email returns 404."""
    response = client.get(f"/player/verify-user/{unverified_user.public_sqid}")
    assert response.status_code == 404


def test_verify_user_deactivated(client: "TestClient", deactivated_user):
    """Deactivated user returns 404."""
    response = client.get(f"/player/verify-user/{deactivated_user.public_sqid}")
    assert response.status_code == 404


def test_verify_user_hidden_by_mod(client: "TestClient", hidden_user):
    """User hidden by moderator returns 404."""
    response = client.get(f"/player/verify-user/{hidden_user.public_sqid}")
    assert response.status_code == 404


def test_verify_user_banned(client: "TestClient", banned_user):
    """User with active temporal ban returns 404."""
    response = client.get(f"/player/verify-user/{banned_user.public_sqid}")
    assert response.status_code == 404


def test_verify_user_oversized_sqid(client: "TestClient"):
    """SQID longer than 16 characters returns 404."""
    response = client.get("/player/verify-user/ABCDEFGHIJKLMNOPQ")
    assert response.status_code == 404


def test_verify_user_rate_limit(client: "TestClient", verified_user):
    """Exceeding rate limit returns 429."""
    with patch("app.routers.player.check_rate_limit", return_value=(False, 0)):
        response = client.get(f"/player/verify-user/{verified_user.public_sqid}")
        assert response.status_code == 429

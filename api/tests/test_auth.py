"""Test authentication functionality."""

import pytest
import base64
import json
from sqlalchemy.orm import Session

from app.auth import create_access_token, create_refresh_token
from app.routers import auth as auth_router
from app.models import User


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


def test_create_access_token(test_user: User):
    """Test JWT access token creation."""
    token = create_access_token(test_user.user_key)
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_refresh_token(test_user: User, db: Session):
    """Test refresh token creation."""
    token = create_refresh_token(test_user.user_key, db)
    assert isinstance(token, str)
    assert len(token) > 0


def test_github_login_redirect():
    """Test GitHub OAuth login redirect."""
    # GitHub login only needs client_id configured
    auth_router.GITHUB_CLIENT_ID = "test_client_id"
    auth_router.GITHUB_REDIRECT_URI = "http://localhost/auth/github/callback"

    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/auth/github/login", follow_redirects=False)

    # Should redirect to GitHub
    assert response.status_code == 307
    assert "github.com" in response.headers["location"]
    # Should set OAuth state cookie for CSRF protection
    set_cookie = response.headers.get("set-cookie", "")
    assert "oauth_state=" in set_cookie
    assert "HttpOnly" in set_cookie


def test_github_callback_rejects_invalid_state_before_network_call():
    """Callback should reject invalid/mismatched state before contacting GitHub."""
    # Configure dummy credentials so the handler doesn't exit early
    auth_router.GITHUB_CLIENT_ID = "test_client_id"
    auth_router.GITHUB_CLIENT_SECRET = "test_client_secret"
    auth_router.GITHUB_REDIRECT_URI = "http://localhost/auth/github/callback"

    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Build a state with nonce=abc, but set a different cookie nonce
    state = (
        base64.urlsafe_b64encode(json.dumps({"nonce": "abc"}).encode())
        .decode()
        .rstrip("=")
    )
    client.cookies.set("oauth_state", "different")

    resp = client.get(
        f"/auth/github/callback?code=test_code&state={state}", follow_redirects=False
    )
    assert resp.status_code == 400
    assert resp.json().get("detail") == "Invalid OAuth state. Please try again."


def test_me_endpoint_requires_auth():
    """Test that /auth/me requires authentication."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/auth/me")

    assert response.status_code == 401


def test_me_endpoint_with_invalid_token():
    """Test /auth/me with invalid JWT token."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    response = client.get("/auth/me", headers={"Authorization": "Bearer invalid_token"})

    assert response.status_code == 401


def test_me_endpoint_with_expired_token(test_user: User):
    """Test /auth/me with expired JWT token."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    # Create token with very short expiration
    token = create_access_token(test_user.user_key, expires_in_seconds=-1)

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_refresh_token_returns_complete_response(test_user: User, db: Session):
    """Test that refresh token endpoint returns required fields and rotates cookie."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Create a refresh token for the user
    refresh_token = create_refresh_token(test_user.user_key, db)

    # Put refresh token into HttpOnly cookie (how the API expects it)
    client.cookies.set("refresh_token", refresh_token)

    # Call the refresh endpoint (cookie-based)
    response = client.post("/auth/refresh")

    assert response.status_code == 200
    data = response.json()

    # Verify all required fields are present
    assert "token" in data, "Missing 'token' field"
    # refresh_token is stored in HttpOnly cookie, not returned in body
    assert "refresh_token" in data, "Missing 'refresh_token' field"
    assert "user_id" in data, "Missing 'user_id' field"
    assert "user_key" in data, "Missing 'user_key' field"
    assert "public_sqid" in data, "Missing 'public_sqid' field"
    assert "user_handle" in data, "Missing 'user_handle' field"
    assert "expires_at" in data, "Missing 'expires_at' field"

    # Verify field values are correct
    assert data["user_id"] == test_user.id
    assert data["user_key"] == str(test_user.user_key)
    assert data["user_handle"] == test_user.handle

    # Verify tokens are valid strings
    assert isinstance(data["token"], str) and len(data["token"]) > 0
    assert data["refresh_token"] is None

    # Verify refresh token rotation occurred via Set-Cookie
    set_cookie = response.headers.get("set-cookie", "")
    assert "refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie

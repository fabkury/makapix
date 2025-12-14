"""Test authentication functionality."""

import pytest
import base64
import json
from sqlalchemy.orm import Session

from app.auth import create_access_token, create_refresh_token
from app.routers import auth as auth_router
from app.models import User
from app.services.auth_identities import create_oauth_identity


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user."""
    user = User(
        handle="testuser",
        display_name="Test User",
        email="test@example.com",
        roles=["user"]
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


def test_github_exchange_missing_credentials():
    """Test GitHub OAuth exchange with missing credentials."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post("/auth/github/exchange", json={
        "code": "test_code",
        "redirect_uri": "http://localhost/auth/github/callback"
    })
    
    # Should fail with 500 if GitHub OAuth not configured
    assert response.status_code == 500


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
    state = base64.urlsafe_b64encode(json.dumps({"nonce": "abc"}).encode()).decode().rstrip("=")
    client.cookies.set("oauth_state", "different")

    resp = client.get(f"/auth/github/callback?code=test_code&state={state}", follow_redirects=False)
    assert resp.status_code == 400
    assert resp.json().get("detail") == "Invalid OAuth state. Please try again."


def test_github_callback_does_not_overwrite_profile_on_login(
    db: Session, test_user: User, monkeypatch: pytest.MonkeyPatch
):
    """
    Returning GitHub users should NOT have profile fields (bio/avatar) overwritten on login.
    Those fields are only set once at registration.
    """
    # Configure dummy credentials so the handler doesn't exit early
    auth_router.GITHUB_CLIENT_ID = "test_client_id"
    auth_router.GITHUB_CLIENT_SECRET = "test_client_secret"
    auth_router.GITHUB_REDIRECT_URI = "http://localhost/auth/github/callback"

    # Seed a user with custom profile fields (simulates user-edited values)
    test_user.bio = "my custom bio"
    test_user.avatar_url = "https://cdn.example.com/my-avatar.png"
    db.commit()
    db.refresh(test_user)

    # Link an existing GitHub identity to that user
    github_user_id = "12345"
    create_oauth_identity(
        db=db,
        user_id=test_user.id,
        provider="github",
        provider_user_id=github_user_id,
        email="test@example.com",
        provider_metadata={"username": "oldname", "avatar_url": "https://old.example/a.png"},
    )

    # Stub httpx.Client used inside the router so we don't hit the network
    class _FakeResponse:
        def __init__(self, payload: object, status_code: int = 200):
            self._payload = payload
            self.status_code = status_code

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                # Not expected in this test path; keep it simple.
                raise RuntimeError("HTTP error")

    class _FakeHttpxClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url: str, data=None, headers=None):
            assert "github.com/login/oauth/access_token" in url
            return _FakeResponse({"access_token": "gh_access_token"})

        def get(self, url: str, headers=None):
            if url == "https://api.github.com/user":
                return _FakeResponse(
                    {
                        "id": int(github_user_id),
                        "login": "newname",
                        "bio": "github bio that should not overwrite",
                        "avatar_url": "https://avatars.githubusercontent.com/u/12345?v=4",
                        "email": "test@example.com",
                    }
                )
            if url == "https://api.github.com/user/emails":
                return _FakeResponse(
                    [{"email": "test@example.com", "primary": True, "verified": True}]
                )
            raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(auth_router.httpx, "Client", _FakeHttpxClient)

    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    # Build a valid state + matching cookie nonce
    nonce = "abc"
    state = base64.urlsafe_b64encode(json.dumps({"nonce": nonce}).encode()).decode().rstrip("=")
    client.cookies.set("oauth_state", nonce)

    resp = client.get(f"/auth/github/callback?code=test_code&state={state}", follow_redirects=False)
    assert resp.status_code == 200

    # Reload user and verify profile fields were NOT overwritten by GitHub values
    db.refresh(test_user)
    assert test_user.bio == "my custom bio"
    assert test_user.avatar_url == "https://cdn.example.com/my-avatar.png"


def test_me_endpoint_requires_auth():
    """Test that /auth/me requires authentication."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/auth/me")
    
    assert response.status_code == 401


def test_me_endpoint_with_valid_token(test_user: User):
    """Test /auth/me with valid JWT token."""
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    token = create_access_token(test_user.user_key)
    
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["id"] == str(test_user.id)
    assert data["user"]["handle"] == test_user.handle


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

"""Test authentication functionality."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import create_access_token, create_refresh_token
from app.main import app
from app.models import User


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
    token = create_access_token(test_user.id)
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_refresh_token(test_user: User, db: Session):
    """Test refresh token creation."""
    token = create_refresh_token(test_user.id, db)
    assert isinstance(token, str)
    assert len(token) > 0


def test_github_login_redirect():
    """Test GitHub OAuth login redirect."""
    client = TestClient(app)
    response = client.get("/auth/github/login")
    
    # Should redirect to GitHub
    assert response.status_code == 307
    assert "github.com" in response.headers["location"]


def test_github_exchange_missing_credentials():
    """Test GitHub OAuth exchange with missing credentials."""
    client = TestClient(app)
    response = client.post("/auth/github/exchange", json={
        "code": "test_code",
        "redirect_uri": "http://localhost/auth/github/callback"
    })
    
    # Should fail with 500 if GitHub OAuth not configured
    assert response.status_code == 500


def test_me_endpoint_requires_auth():
    """Test that /auth/me requires authentication."""
    client = TestClient(app)
    response = client.get("/auth/me")
    
    assert response.status_code == 401


def test_me_endpoint_with_valid_token(test_user: User):
    """Test /auth/me with valid JWT token."""
    client = TestClient(app)
    token = create_access_token(test_user.id)
    
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["id"] == str(test_user.id)
    assert data["user"]["handle"] == test_user.handle


def test_me_endpoint_with_invalid_token():
    """Test /auth/me with invalid JWT token."""
    client = TestClient(app)
    
    response = client.get("/auth/me", headers={"Authorization": "Bearer invalid_token"})
    
    assert response.status_code == 401


def test_me_endpoint_with_expired_token(test_user: User):
    """Test /auth/me with expired JWT token."""
    client = TestClient(app)
    # Create token with very short expiration
    token = create_access_token(test_user.id, expires_in_seconds=-1)
    
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 401


def test_refresh_token_returns_complete_response(test_user: User, db: Session):
    """Test that refresh token endpoint returns all required fields."""
    client = TestClient(app)
    
    # Create a refresh token for the user
    refresh_token = create_refresh_token(test_user.user_key, db)
    
    # Call the refresh endpoint
    response = client.post("/api/auth/refresh", json={
        "refresh_token": refresh_token
    })
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify all required fields are present
    assert "token" in data, "Missing 'token' field"
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
    assert isinstance(data["refresh_token"], str) and len(data["refresh_token"]) > 0
    
    # Verify new refresh token is different from the old one (token rotation)
    assert data["refresh_token"] != refresh_token

"""Tests for the PATCH /user/{id} profile-update endpoint.

Focus: avatar_url must NOT be settable through this endpoint. Avatars are
mutated only via POST/DELETE /user/{id}/avatar, which enforce format/size
limits and store bytes in our vault. A free-form avatar_url through PATCH
would let a user point their avatar at an arbitrary off-site resource,
bypassing the upload pipeline.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.auth import create_access_token

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_user(db: "Session"):
    """Create a test user with a vault-hosted avatar already set."""
    from app.models import User

    unique = str(uuid.uuid4())[:8]
    user = User(
        handle=f"patchtest_{unique}",
        email=f"patch_{unique}@example.com",
        roles=["user"],
        bio="original bio",
        avatar_url="/api/vault/avatar/00/00/original.png",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _auth(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.user_key)}"}


def test_patch_ignores_avatar_url(client: "TestClient", db: "Session", test_user):
    """avatar_url in the PATCH body is ignored; other fields still apply."""
    original_avatar = test_user.avatar_url

    response = client.patch(
        f"/user/{test_user.user_key}",
        headers=_auth(test_user),
        json={
            "bio": "updated bio",
            "avatar_url": "https://evil.example.com/tracking-pixel.gif",
        },
    )

    assert response.status_code == 200
    data = response.json()
    # The legitimate field was applied...
    assert data["bio"] == "updated bio"
    # ...but the avatar was NOT hijacked to the external URL.
    assert data["avatar_url"] == original_avatar

    # Confirm it's persisted, not just absent from the response.
    db.expire_all()
    from app.models import User

    refreshed = db.query(User).filter(User.id == test_user.id).first()
    assert refreshed.avatar_url == original_avatar


def test_patch_avatar_only_is_noop(client: "TestClient", db: "Session", test_user):
    """A PATCH carrying only avatar_url changes nothing."""
    original_avatar = test_user.avatar_url

    response = client.patch(
        f"/user/{test_user.user_key}",
        headers=_auth(test_user),
        json={"avatar_url": "https://evil.example.com/x.png"},
    )

    assert response.status_code == 200
    assert response.json()["avatar_url"] == original_avatar

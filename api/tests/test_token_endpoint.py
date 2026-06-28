"""Tests for the native body-based token endpoint (change-request §3.1)."""

from __future__ import annotations

import uuid

from app.models import User
from app.services.auth_identities import create_password_identity
from app.sqids_config import encode_user_id


def _password_user(db, *, password="s3cret-passw0rd", verified=True):
    uid = str(uuid.uuid4())[:8]
    email = f"tok_{uid}@example.com"
    user = User(
        handle=f"tok_{uid}", email=email, roles=["user"], email_verified=verified
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    create_password_identity(db, user.id, email, password)  # user_id is the int id
    return user, email, password


def test_password_grant_returns_body_refresh_token(client, db):
    user, email, password = _password_user(db)
    r = client.post(
        "/v1/auth/token",
        json={"grant_type": "password", "email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "Bearer"
    assert body["access_token"]
    assert body["refresh_token"]  # returned in the BODY, not just a cookie
    assert body["expires_in"] == 3600
    assert body["user"]["handle"] == user.handle
    # The issued access token actually authenticates.
    me = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200


def test_refresh_grant_rotates(client, db):
    _, email, password = _password_user(db)
    first = client.post(
        "/v1/auth/token",
        json={"grant_type": "password", "email": email, "password": password},
    ).json()
    rt = first["refresh_token"]
    r = client.post(
        "/v1/auth/token",
        json={"grant_type": "refresh_token", "refresh_token": rt},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["refresh_token"] and body["refresh_token"] != rt  # rotated


def test_password_grant_wrong_password(client, db):
    _, email, _ = _password_user(db)
    r = client.post(
        "/v1/auth/token",
        json={"grant_type": "password", "email": email, "password": "wrong-pw"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_password_grant_unverified_email(client, db):
    _, email, password = _password_user(db, verified=False)
    r = client.post(
        "/v1/auth/token",
        json={"grant_type": "password", "email": email, "password": password},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "email_not_verified"


def test_invalid_refresh_token(client, db):
    r = client.post(
        "/v1/auth/token",
        json={"grant_type": "refresh_token", "refresh_token": "not-a-real-token"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "token_invalid"


def test_authorization_code_grant_not_yet_enabled(client, db):
    r = client.post(
        "/v1/auth/token",
        json={"grant_type": "authorization_code", "code": "x", "code_verifier": "y"},
    )
    assert r.status_code == 400

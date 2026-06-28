"""Tests for the JWT claim contract (change-request §3.2): sub=public_sqid + roles,
with a transitional legacy user_id fallback."""

from __future__ import annotations

import datetime as _dt
import uuid

import jwt

from app.auth import JWT_ALGORITHM, JWT_SECRET_KEY, create_access_token
from app.models import User
from app.sqids_config import encode_user_id


def _user(db, *, roles=None, with_sqid=True) -> User:
    uid = str(uuid.uuid4())[:8]
    u = User(
        handle=f"tok_{uid}",
        email=f"tok_{uid}@example.com",
        roles=roles or ["user"],
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    if with_sqid:
        u.public_sqid = encode_user_id(u.id)
        db.commit()
        db.refresh(u)
    return u


def test_access_token_claims(db):
    u = _user(db, roles=["user", "moderator"])
    claims = jwt.decode(
        create_access_token(u), JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]
    )
    assert claims["sub"] == u.public_sqid
    assert claims["roles"] == ["user", "moderator"]
    assert claims["type"] == "access"
    # Transitional legacy claim retained during the migration window.
    assert claims["user_id"] == str(u.user_key)


def test_get_current_user_resolves_via_sub(client, db):
    u = _user(db)
    token = create_access_token(u)
    r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["user"]["public_sqid"] == u.public_sqid


def test_legacy_user_id_only_token_still_resolves(client, db):
    # Simulate a pre-cutover token that carries only the legacy user_id claim.
    u = _user(db, with_sqid=False)
    now = _dt.datetime.utcnow()
    legacy = jwt.encode(
        {
            "user_id": str(u.user_key),
            "exp": now + _dt.timedelta(minutes=5),
            "iat": now,
            "type": "access",
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )
    r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {legacy}"})
    assert r.status_code == 200
    assert r.json()["user"]["handle"] == u.handle

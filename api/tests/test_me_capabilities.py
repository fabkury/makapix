"""Tests for the /auth/me capabilities & quotas block (change-request §3.5)."""

from __future__ import annotations

import uuid

from app.auth import create_access_token
from app.models import User


def _make_user(db, *, roles=None, reputation=0, auto_public_approval=False) -> User:
    uid = str(uuid.uuid4())[:8]
    user = User(
        handle=f"caps_{uid}",
        email=f"caps_{uid}@example.com",
        roles=roles or ["user"],
        reputation=reputation,
        auto_public_approval=auto_public_approval,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _me(client, user):
    token = create_access_token(user)
    return client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})


def test_me_includes_capabilities_and_quotas(client, db):
    user = _make_user(db, auto_public_approval=True, reputation=0)
    r = _me(client, user)
    assert r.status_code == 200
    body = r.json()

    caps = body["capabilities"]
    assert caps["can_post_public"] is True
    assert caps["can_moderate"] is False
    assert caps["can_own_players"] is True

    q = body["quotas"]
    assert q["storage"]["limit_bytes"] == 100 * 1024 * 1024  # reputation < 100 tier
    assert q["storage"]["used_bytes"] == 0
    assert q["uploads"]["limit"] == 4
    assert q["uploads"]["window"] == "1h"
    assert q["players"]["limit"] == 128
    assert q["players"]["used"] == 0

    assert body["moderation"]["deactivated"] is False
    assert body["moderation"]["banned_until"] is None
    assert body["needs_welcome"] is True


def test_me_moderator_and_higher_tiers(client, db):
    user = _make_user(db, roles=["user", "moderator"], reputation=600)
    body = _me(client, user).json()
    assert body["capabilities"]["can_moderate"] is True
    assert body["quotas"]["uploads"]["limit"] == 64  # reputation >= 500
    assert body["quotas"]["storage"]["limit_bytes"] == 500 * 1024 * 1024

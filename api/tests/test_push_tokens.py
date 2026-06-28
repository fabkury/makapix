"""Tests for the /me push-token + notification-preference endpoints (§4)."""

from __future__ import annotations

import uuid

from app.auth import create_access_token
from app.models import User
from app.sqids_config import encode_user_id


def _auth(db):
    uid = str(uuid.uuid4())[:8]
    u = User(handle=f"push_{uid}", email=f"push_{uid}@example.com", roles=["user"])
    db.add(u)
    db.commit()
    db.refresh(u)
    u.public_sqid = encode_user_id(u.id)
    db.commit()
    db.refresh(u)
    return {"Authorization": f"Bearer {create_access_token(u)}"}


def test_push_tokens_require_auth(client):
    assert client.get("/v1/me/notification-preferences").status_code == 401
    assert (
        client.post(
            "/v1/me/push-tokens", json={"platform": "fcm", "token": "x"}
        ).status_code
        == 401
    )


def test_register_idempotent_and_delete(client, db):
    h = _auth(db)
    body = {"platform": "fcm", "token": "device-token-ABC:123", "device_label": "Pixel"}
    r = client.post("/v1/me/push-tokens", json=body, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["platform"] == "fcm"
    assert r.json()["device_label"] == "Pixel"

    # Re-registering the same token is idempotent (no duplicate / no 409).
    r2 = client.post(
        "/v1/me/push-tokens",
        json={"platform": "fcm", "token": "device-token-ABC:123"},
        headers=h,
    )
    assert r2.status_code == 201

    d = client.delete("/v1/me/push-tokens/device-token-ABC:123", headers=h)
    assert d.status_code == 204


def test_send_push_returns_zero_without_tokens(db):
    # A user with no registered tokens gets nothing sent (works whether or not
    # FCM is configured in this environment).
    from app.services.push import send_push_to_user

    assert send_push_to_user(db, 999999, "reaction", {}) == 0


def test_notification_preferences_roundtrip(client, db):
    h = _auth(db)
    assert (
        client.get("/v1/me/notification-preferences", headers=h).json()["preferences"]
        == {}
    )
    p = client.put(
        "/v1/me/notification-preferences",
        json={"preferences": {"reaction": False, "follow": True}},
        headers=h,
    )
    assert p.status_code == 200
    got = client.get("/v1/me/notification-preferences", headers=h).json()
    assert got["preferences"] == {"reaction": False, "follow": True}

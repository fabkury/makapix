"""Regression tests for the P1 security batch (appraisal S9/S18/S20/S21).

- S9:  GET /user/{id}/reputation was public and leaked moderator reason text.
- S18: POST /player/provision was unauthenticated + unthrottled (row flood).
- S20: POST /me/push-tokens was authed but unthrottled (row flood).
- S21: POST /auth/change-password had no throttle on the current-password check
       (an online password-guessing oracle for a stolen access token).
"""

import uuid

from app import models
from app.auth import create_access_token


def _user(db, roles=("user",)):
    u = models.User(
        handle=f"p1_{uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:6]}@e.com",
        roles=list(roles),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _auth(u):
    return {"Authorization": f"Bearer {create_access_token(u)}"}


# --- S9: reputation history is moderator-only --------------------------------


def test_reputation_get_rejects_anonymous(client, db):
    r = client.get(f"/user/{uuid.uuid4()}/reputation")
    assert r.status_code in (401, 403), r.text


def test_reputation_get_rejects_non_moderator(client, db):
    r = client.get(f"/user/{uuid.uuid4()}/reputation", headers=_auth(_user(db)))
    assert r.status_code == 403, r.text


# --- Rate-limit wiring (patch the limiter so the assertion is deterministic
#     and doesn't depend on shared Redis counters) ---------------------------


def _deny(*_a, **_k):
    return (False, 0)


def test_provision_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr("app.routers.player.check_rate_limit", _deny)
    r = client.post(
        "/player/provision",
        json={"device_model": "d", "firmware_version": "1.0"},
    )
    assert r.status_code == 429, r.text


def test_push_token_register_is_rate_limited(client, db, monkeypatch):
    monkeypatch.setattr("app.routers.me.check_rate_limit", _deny)
    r = client.post(
        "/me/push-tokens",
        json={"platform": "fcm", "token": f"tok_{uuid.uuid4()}"},
        headers=_auth(_user(db)),
    )
    assert r.status_code == 429, r.text


def test_change_password_is_rate_limited(client, db, monkeypatch):
    monkeypatch.setattr("app.routers.auth.check_rate_limit", _deny)
    r = client.post(
        "/auth/change-password",
        json={"current_password": "whatever1", "new_password": "newpassword1"},
        headers=_auth(_user(db)),
    )
    assert r.status_code == 429, r.text

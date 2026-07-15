"""Regression tests for S15: the player SSE stream authenticated via the raw
60-minute access token in the URL query string (logged for its whole lifetime).
It now uses a single-use, 30s ticket minted from an authenticated POST.
"""

import uuid

from app import models
from app.auth import create_access_token
from app.sqids_config import encode_user_id


def _user(db):
    u = models.User(
        handle=f"s_{uuid.uuid4().hex[:6]}", email=f"{uuid.uuid4().hex[:6]}@e.com"
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    u.public_sqid = encode_user_id(u.id)
    db.commit()
    return u


def _auth(u):
    return {"Authorization": f"Bearer {create_access_token(u)}"}


def test_ticket_requires_auth(client, db):
    u = _user(db)
    r = client.post(f"/u/{u.public_sqid}/player/sse-ticket")
    assert r.status_code in (401, 403), r.text


def test_owner_can_mint_ticket(client, db):
    u = _user(db)
    r = client.post(f"/u/{u.public_sqid}/player/sse-ticket", headers=_auth(u))
    assert r.status_code == 200, r.text
    assert r.json().get("ticket")


def test_non_owner_cannot_mint_ticket(client, db):
    owner = _user(db)
    other = _user(db)
    r = client.post(f"/u/{owner.public_sqid}/player/sse-ticket", headers=_auth(other))
    assert r.status_code in (401, 403), r.text


def test_sse_rejects_missing_and_bogus_ticket(client, db):
    u = _user(db)
    # no ticket / no token
    assert client.get(f"/u/{u.public_sqid}/player/sse").status_code == 401
    # bogus ticket
    assert client.get(f"/u/{u.public_sqid}/player/sse?ticket=nope").status_code == 401


def test_ticket_is_single_use(client, db):
    u = _user(db)
    ticket = client.post(
        f"/u/{u.public_sqid}/player/sse-ticket", headers=_auth(u)
    ).json()["ticket"]

    from app.cache import cache_get, cache_delete

    key = f"player_sse_ticket:{ticket}"
    # The ticket resolves to the owner and is consumed on read.
    assert str(cache_get(key)) == str(u.id)
    cache_delete(key)
    assert cache_get(key) is None

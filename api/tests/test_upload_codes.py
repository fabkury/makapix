"""Tests for typed upload error codes (F remainder: dimensions_invalid)."""

from __future__ import annotations

import uuid

from app.auth import create_access_token
from app.models import User
from app.sqids_config import encode_user_id


def _auth(db):
    uid = str(uuid.uuid4())[:8]
    u = User(handle=f"up_{uid}", email=f"up_{uid}@example.com", roles=["user"])
    db.add(u)
    db.commit()
    db.refresh(u)
    u.public_sqid = encode_user_id(u.id)
    db.commit()
    db.refresh(u)
    return {"Authorization": f"Bearer {create_access_token(u)}"}


def test_create_post_invalid_dimensions(client, db):
    # 100x100 passes the schema bounds (<=256) but is not a whitelisted size
    # below the 128 free-form band -> typed dimensions_invalid.
    r = client.post(
        "/v1/post",
        json={
            "title": "t",
            "art_url": "/vault/x.png",
            "width": 100,
            "height": 100,
            "file_bytes": 1000,
            "hash": "a" * 64,
        },
        headers=_auth(db),
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "dimensions_invalid"

"""Tests for upload dimension-rule rejection.

Historically this covered the typed `dimensions_invalid` code on the legacy
JSON create endpoint (removed 2026-07-22, docs/remove-external-hosting/). On
the surviving upload path, dimension failures are detected by the AMP
inspector and surface as a generic 400 with a descriptive message.
"""

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


def test_upload_invalid_dimensions(client, db):
    # 100x100 is inside the schema bounds (<=256) but is not a whitelisted size
    # below the 128 free-form band -> typed dimensions_invalid.
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (100, 100), (200, 30, 90, 255)).save(buf, format="PNG")
    r = client.post(
        "/v1/post/upload",
        files={"image": ("bad-dims.png", buf.getvalue(), "image/png")},
        data={"title": "t"},
        headers=_auth(db),
    )
    assert r.status_code == 400
    body = r.json()
    assert body["error"]["code"] == "bad_request"
    assert "100x100 is not allowed" in body["error"]["message"]

"""Regression tests for S7: the avatar upload endpoint had no byte validation
(arbitrary bytes were served from the vault with an image MIME) and orphaned the
previous avatar file on every replace.
"""

import io
import uuid

import pytest

from app import models
from app.auth import create_access_token


def _png_bytes():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (16, 16), (0, 128, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def vault_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


@pytest.fixture()
def user(db):
    u = models.User(
        handle=f"av_{uuid.uuid4().hex[:6]}", email=f"{uuid.uuid4().hex[:6]}@e.com"
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _auth(u):
    return {"Authorization": f"Bearer {create_access_token(u)}"}


def test_non_image_bytes_rejected(client, db, user, vault_tmp):
    resp = client.post(
        f"/user/{user.user_key}/avatar",
        files={"image": ("evil.png", b"this is not an image", "image/png")},
        headers=_auth(user),
    )
    assert resp.status_code == 400, resp.text


def test_replacing_avatar_deletes_old_file(client, db, user, vault_tmp):
    from app.avatar_vault import get_avatar_vault_location

    def _upload():
        return client.post(
            f"/user/{user.user_key}/avatar",
            files={"image": ("a.png", _png_bytes(), "image/png")},
            headers=_auth(user),
        )

    r1 = _upload()
    assert r1.status_code == 201, r1.text
    files_after_first = list(get_avatar_vault_location().rglob("*.png"))
    assert len(files_after_first) == 1

    r2 = _upload()
    assert r2.status_code == 201, r2.text
    # The old file must be gone — exactly one avatar file on disk, not two.
    files_after_second = list(get_avatar_vault_location().rglob("*.png"))
    assert len(files_after_second) == 1, files_after_second

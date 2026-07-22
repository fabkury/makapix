"""Tests for mirror_github_avatar (docs/remove-external-hosting/).

GitHub OAuth stores avatars.githubusercontent.com URLs at signup; the mirror
task re-homes the image in the avatar sub-vault so no user-facing imagery is
served from a foreign host. Fail-open: any failure leaves the (still working)
external URL in place.
"""

import io
import uuid

import pytest

from app import models
from app.tasks import mirror_github_avatar_sync

GH_URL = "https://avatars.githubusercontent.com/u/12345?v=4"


def _png_bytes(size=(16, 16)):
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", size, (0, 128, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, body: bytes, content_type: str = "image/png"):
        self._body = body
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i : i + chunk_size]


@pytest.fixture()
def vault_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


def _make_user(db, avatar_url=GH_URL):
    u = models.User(
        handle=f"gam_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@e.com",
        roles=["user"],
        avatar_url=avatar_url,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_mirrors_png_avatar_into_vault(db, vault_tmp, monkeypatch):
    body = _png_bytes()
    monkeypatch.setattr("requests.get", lambda url, **kw: _FakeResponse(body))

    user = _make_user(db)
    result = mirror_github_avatar_sync(db, user.id)

    assert result["status"] == "mirrored"
    db.refresh(user)
    assert "githubusercontent" not in user.avatar_url
    assert user.avatar_url.endswith(".png")
    # The bytes landed in the avatar sub-vault, unmodified.
    stored = list((vault_tmp / "avatar").rglob("*.png"))
    assert len(stored) == 1
    assert stored[0].read_bytes() == body


def test_noop_for_non_github_avatar(db, vault_tmp, monkeypatch):
    def _boom(*a, **kw):
        raise AssertionError("must not fetch")

    monkeypatch.setattr("requests.get", _boom)
    user = _make_user(db, avatar_url="/api/vault/avatar/0a/1b/x.png")

    result = mirror_github_avatar_sync(db, user.id)

    assert result["status"] == "skipped"
    db.refresh(user)
    assert user.avatar_url == "/api/vault/avatar/0a/1b/x.png"


def test_skips_unsupported_content_type(db, vault_tmp, monkeypatch):
    monkeypatch.setattr(
        "requests.get",
        lambda url, **kw: _FakeResponse(b"<svg/>", content_type="image/svg+xml"),
    )
    user = _make_user(db)

    result = mirror_github_avatar_sync(db, user.id)

    assert result["status"] == "skipped"
    db.refresh(user)
    assert user.avatar_url == GH_URL


def test_skips_oversized_avatar(db, vault_tmp, monkeypatch):
    from app.avatar_vault import MAX_AVATAR_SIZE_BYTES

    big = b"\x00" * (MAX_AVATAR_SIZE_BYTES + 1)
    monkeypatch.setattr("requests.get", lambda url, **kw: _FakeResponse(big))
    user = _make_user(db)

    result = mirror_github_avatar_sync(db, user.id)

    assert result["status"] == "skipped"
    db.refresh(user)
    assert user.avatar_url == GH_URL


def test_fetch_failure_leaves_external_url(db, vault_tmp, monkeypatch):
    def _boom(*a, **kw):
        raise ConnectionError("cdn unreachable")

    monkeypatch.setattr("requests.get", _boom)
    user = _make_user(db)

    from app.tasks import mirror_github_avatar

    result = mirror_github_avatar.apply(args=[user.id]).get()

    assert result["status"] == "error"
    db.refresh(user)
    assert user.avatar_url == GH_URL


def test_task_wrapper_mirrors(db, vault_tmp, monkeypatch):
    body = _png_bytes()
    monkeypatch.setattr("requests.get", lambda url, **kw: _FakeResponse(body))
    user = _make_user(db)

    from app.tasks import mirror_github_avatar

    result = mirror_github_avatar.apply(args=[user.id]).get()

    assert result["status"] == "mirrored"
    db.refresh(user)
    assert "githubusercontent" not in user.avatar_url

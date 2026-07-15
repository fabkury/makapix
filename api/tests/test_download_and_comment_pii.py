"""Regression tests for two content-serving defects:

A9 — download endpoints built Content-Disposition by hand, so any artwork
     whose title contained a non-Latin-1 character (emoji/CJK — common on a
     pixel-art site) 500'd instead of downloading.
S3 — the public Comment schema serialized author_ip verbatim, leaking every
     anonymous commenter's raw IP to any visitor. It must drive the guest
     handle but never appear in the payload.
"""

import uuid

import pytest


def make_png_bytes() -> bytes:
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGBA", (16, 16), (255, 0, 0, 255)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture()
def vault_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


def test_download_with_emoji_title_does_not_500(client, db, vault_tmp):
    """A9: an emoji/CJK title must download (200), not raise UnicodeEncodeError."""
    from app import models
    from app.sqids_config import encode_id
    from app.vault import compute_storage_shard, save_artwork_to_vault

    owner = models.User(
        handle=f"dl_{uuid.uuid4().hex[:8]}", email=f"{uuid.uuid4().hex[:8]}@e.com"
    )
    db.add(owner)
    db.commit()

    key = uuid.uuid4()
    shard = compute_storage_shard(key)
    save_artwork_to_vault(key, make_png_bytes(), "png", storage_shard=shard)

    post = models.Post(
        owner_id=owner.id,
        title="日本語 🎨 pixel",  # non-Latin-1
        storage_key=key,
        storage_shard=shard,
        kind="artwork",
        public_visibility=True,
    )
    db.add(post)
    db.commit()
    post.public_sqid = encode_id(post.id)
    db.add(
        models.PostFile(post_id=post.id, format="png", file_bytes=123, is_native=True)
    )
    db.commit()

    resp = client.get(f"/d/{post.public_sqid}.png")
    assert resp.status_code == 200, resp.text
    # The response carries a (correctly encoded) attachment disposition.
    assert "attachment" in resp.headers.get("content-disposition", "").lower()


def test_public_comment_schema_omits_author_ip():
    """S3: author_ip must not serialize, but must still yield the Guest handle."""
    import hashlib
    from types import SimpleNamespace

    from app.schemas import Comment

    ip = "203.0.113.7"
    orm = SimpleNamespace(
        id=uuid.uuid4(),
        post_id=1,
        author_id=None,
        author_ip=ip,
        author=None,
        parent_id=None,
        depth=0,
        body="hi",
        hidden_by_mod=False,
        deleted_by_owner=False,
        deleted_by_mod=False,
        created_at=__import__("datetime").datetime.now(),
        updated_at=None,
    )
    dumped = Comment.model_validate(orm).model_dump()

    assert "author_ip" not in dumped  # the leak is closed
    expected = "Guest_" + hashlib.sha256(ip.encode()).hexdigest()[:6]
    assert dumped["author_handle"] == expected  # handle still derived from the IP

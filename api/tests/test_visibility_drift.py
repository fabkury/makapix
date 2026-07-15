"""Regression tests for A13: per-endpoint visibility filters had drifted, so
author-hidden posts leaked into the following feed and hashtag counts, and
banned users (who 404 on their profile) stayed discoverable via search.
"""

import uuid

import pytest

from app import models
from app.auth import create_access_token
from app.sqids_config import encode_id, encode_user_id


def _user(db, **kw):
    u = models.User(
        handle=kw.pop("handle", f"vd_{uuid.uuid4().hex[:6]}"),
        email=f"{uuid.uuid4().hex[:6]}@e.com",
        email_verified=True,
        **kw,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    u.public_sqid = encode_user_id(u.id)
    db.commit()
    return u


def _post(db, owner, tags=None, **flags):
    key = uuid.uuid4()
    p = models.Post(
        owner_id=owner.id,
        title="t",
        storage_key=key,
        art_url=f"https://example.com/{key}.png",
        hash=str(key).replace("-", "") + "c" * 32,
        kind="artwork",
        hashtags=tags or [],
        visible=True,
        public_visibility=True,
        width=64,
        height=64,
        frame_count=1,
        **flags,
    )
    db.add(p)
    db.commit()
    p.public_sqid = encode_id(p.id)
    db.commit()
    return p


def _auth(u):
    return {"Authorization": f"Bearer {create_access_token(u)}"}


def test_following_feed_excludes_author_hidden_posts(client, db):
    author = _user(db)
    viewer = _user(db)
    db.add(models.Follow(follower_id=viewer.id, following_id=author.id))
    db.commit()

    shown = _post(db, author)
    hidden = _post(db, author, hidden_by_user=True)

    resp = client.get("/feed/following", headers=_auth(viewer))
    assert resp.status_code == 200, resp.text
    ids = {i["public_sqid"] for i in resp.json()["items"]}
    assert shown.public_sqid in ids
    assert hidden.public_sqid not in ids  # was leaking


def test_hashtag_counts_exclude_author_hidden_posts(client, db):
    author = _user(db)
    tag = f"vd{uuid.uuid4().hex[:8]}"
    _post(db, author, tags=[tag])
    _post(db, author, tags=[tag], hidden_by_user=True)

    resp = client.get(f"/hashtags?q={tag}")
    assert resp.status_code == 200, resp.text
    counts = {h["tag"]: h["count"] for h in resp.json()["items"]}
    # Only the one visible post should count, not the hidden one.
    assert counts.get(tag) == 1, counts


def test_search_excludes_banned_users(client, db):
    searcher = _user(db)
    handle = f"bannedvd{uuid.uuid4().hex[:6]}"
    _user(db, handle=handle, banned_until=models.PERMANENT_BAN_UNTIL)

    resp = client.get(f"/search?q={handle}&types=users", headers=_auth(searcher))
    assert resp.status_code == 200, resp.text
    handles = {u["handle"] for u in resp.json().get("users", [])}
    assert handle not in handles

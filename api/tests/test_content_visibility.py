"""Regression tests for A11/A12: comment & reaction endpoints must enforce post
visibility, and the widget-data endpoint must apply the block filter.

Post ids are sequential integers, so before this fix anyone could read (and
write) comments/reactions of hidden/unlisted/deleted posts by enumeration, and
the embeddable widget still showed comments from users the viewer had blocked.
"""

import uuid

import pytest

from app import models
from app.auth import create_access_token
from app.sqids_config import encode_id


def _user(db, roles=("user",)):
    u = models.User(
        handle=f"v_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@e.com",
        roles=list(roles),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _post(db, owner, **flags):
    p = models.Post(
        owner_id=owner.id,
        title="t",
        storage_key=uuid.uuid4(),
        kind="artwork",
        **flags,
    )
    db.add(p)
    db.commit()
    p.public_sqid = encode_id(p.id)
    db.commit()
    return p


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(user)}"}


# --- A11: hidden posts don't leak via comment/reaction endpoints --------------


@pytest.mark.parametrize("path", ["comments", "reactions", "widget-data"])
def test_hidden_post_reads_404_for_anonymous(client, db, path):
    owner = _user(db)
    hidden = _post(db, owner, public_visibility=False, visible=True)
    resp = client.get(f"/post/{hidden.id}/{path}")
    assert resp.status_code == 404, resp.text


@pytest.mark.parametrize("path", ["comments", "reactions", "widget-data"])
def test_public_post_reads_200(client, db, path):
    owner = _user(db)
    pub = _post(db, owner, public_visibility=True, visible=True)
    resp = client.get(f"/post/{pub.id}/{path}")
    assert resp.status_code == 200, resp.text


def test_owner_can_read_own_hidden_post(client, db):
    owner = _user(db)
    hidden = _post(db, owner, public_visibility=False, visible=True)
    resp = client.get(f"/post/{hidden.id}/widget-data", headers=_auth(owner))
    assert resp.status_code == 200, resp.text


def test_cannot_comment_or_react_on_hidden_post(client, db):
    owner = _user(db)
    actor = _user(db)
    hidden = _post(db, owner, public_visibility=False, visible=True)

    r1 = client.post(
        f"/post/{hidden.id}/comments", json={"body": "hi"}, headers=_auth(actor)
    )
    assert r1.status_code == 404, r1.text

    r2 = client.put(f"/post/{hidden.id}/reactions/%F0%9F%98%80", headers=_auth(actor))
    assert r2.status_code == 404, r2.text


def test_nonexistent_post_is_404_not_500(client, db):
    # Enumerating a nonexistent id must 404, not 500 on a later FK violation.
    actor = _user(db)
    r = client.post(
        "/post/99999999/comments", json={"body": "hi"}, headers=_auth(actor)
    )
    assert r.status_code == 404, r.text


# --- A12: widget-data applies the block filter --------------------------------


def test_widget_data_hides_blocked_commenter(client, db):
    owner = _user(db)
    viewer = _user(db)
    blocked = _user(db)
    pub = _post(db, owner, public_visibility=True, visible=True)

    db.add(models.Comment(post_id=pub.id, author_id=blocked.id, depth=0, body="spam"))
    db.add(models.UserBlock(blocker_id=viewer.id, blocked_id=blocked.id))
    db.commit()

    # Anonymous viewer sees the comment...
    anon = client.get(f"/post/{pub.id}/widget-data")
    assert anon.status_code == 200
    assert any(c["body"] == "spam" for c in anon.json()["comments"])

    # ...but the blocking viewer does not (was a drifted copy missing the filter).
    seen = client.get(f"/post/{pub.id}/widget-data", headers=_auth(viewer))
    assert seen.status_code == 200
    assert not any(c["body"] == "spam" for c in seen.json()["comments"])

"""Regression test for S14: a moderator's PMD batch action on another user's
posts was attributed as the USER's own action (hidden_by_user) with no audit
entry. It must set hidden_by_mod and write an audit-log row.
"""

import uuid

from app import models
from app.auth import create_access_token
from app.sqids_config import encode_user_id


def _user(db, roles=("user",)):
    u = models.User(
        handle=f"pmd_{uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:6]}@e.com",
        roles=list(roles),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    u.public_sqid = encode_user_id(u.id)
    db.commit()
    return u


def _post(db, owner):
    p = models.Post(
        owner_id=owner.id, title="t", storage_key=uuid.uuid4(), kind="artwork"
    )
    db.add(p)
    db.commit()
    return p


def _auth(u):
    return {"Authorization": f"Bearer {create_access_token(u)}"}


def test_mod_batch_hide_sets_hidden_by_mod_and_audits(client, db):
    author = _user(db)
    mod = _user(db, roles=["moderator"])
    post = _post(db, author)
    post_id = post.id

    resp = client.post(
        f"/pmd/action?target_sqid={author.public_sqid}",
        json={"action": "hide", "post_ids": [post_id]},
        headers=_auth(mod),
    )
    assert resp.status_code == 200, resp.text

    db.expire_all()
    p = db.query(models.Post).filter(models.Post.id == post_id).one()
    # Attributed to the moderator, not the author.
    assert p.hidden_by_mod is True
    assert p.hidden_by_user is False

    # An audit entry names the moderator as actor.
    audit = (
        db.query(models.AuditLog)
        .filter(
            models.AuditLog.actor_id == mod.id,
            models.AuditLog.action == "pmd_batch_hide",
        )
        .all()
    )
    assert len(audit) == 1, "expected exactly one audit row for the batch"


def test_self_hide_stays_hidden_by_user(client, db):
    author = _user(db)
    post = _post(db, author)
    post_id = post.id

    resp = client.post(
        "/pmd/action",  # no target_sqid -> acting on own posts
        json={"action": "hide", "post_ids": [post_id]},
        headers=_auth(author),
    )
    assert resp.status_code == 200, resp.text

    db.expire_all()
    p = db.query(models.Post).filter(models.Post.id == post_id).one()
    assert p.hidden_by_user is True
    assert p.hidden_by_mod is False
    # No audit row for a self-action.
    assert (
        db.query(models.AuditLog)
        .filter(
            models.AuditLog.actor_id == author.id,
            models.AuditLog.action == "pmd_batch_hide",
        )
        .count()
        == 0
    )

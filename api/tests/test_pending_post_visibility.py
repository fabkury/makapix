"""New-post UX (2026-08): a post awaiting moderation approval is visible on
the author's profile to every viewer and reachable by anyone via its direct
permalink; `public_visibility` gates discovery surfaces only (Recent feed,
search, hashtags). Approving a post and granting Trust now notify the user.
"""

import uuid

from app import models
from app.auth import create_access_token
from app.sqids_config import encode_id, encode_user_id


def _user(db, roles=("user",)):
    u = models.User(
        handle=f"p_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@e.com",
        roles=list(roles),
    )
    db.add(u)
    db.commit()
    u.public_sqid = encode_user_id(u.id)
    db.commit()
    db.refresh(u)
    return u


def _post(db, owner, **flags):
    flags.setdefault("visible", True)
    flags.setdefault("public_visibility", False)
    p = models.Post(
        owner_id=owner.id,
        title="pending-art",
        storage_key=uuid.uuid4(),
        kind="artwork",
        art_url="https://example.com/a.png",
        width=64,
        height=64,
        **flags,
    )
    db.add(p)
    db.commit()
    p.public_sqid = encode_id(p.id)
    db.commit()
    db.refresh(p)
    return p


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token(user)}"}


# --- Permalink access ---------------------------------------------------------


def test_pending_post_permalink_readable_by_anonymous(client, db):
    owner = _user(db)
    pending = _post(db, owner)
    resp = client.get(f"/p/{pending.public_sqid}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["public_visibility"] is False


def test_pending_post_permalink_readable_by_other_user(client, db):
    owner = _user(db)
    stranger = _user(db)
    pending = _post(db, owner)
    resp = client.get(f"/p/{pending.public_sqid}", headers=_auth(stranger))
    assert resp.status_code == 200, resp.text


def test_hidden_post_permalink_still_404(client, db):
    owner = _user(db)
    hidden = _post(db, owner, hidden_by_user=True)
    resp = client.get(f"/p/{hidden.public_sqid}")
    assert resp.status_code == 404, resp.text


# --- Profile listing vs discovery surfaces ------------------------------------


def test_pending_post_listed_on_profile_for_anonymous(client, db):
    owner = _user(db)
    pending = _post(db, owner)
    resp = client.get("/post", params={"owner_id": str(owner.user_key)})
    assert resp.status_code == 200, resp.text
    ids = [p["id"] for p in resp.json()["items"]]
    assert pending.id in ids


def test_pending_post_listed_on_profile_for_other_user(client, db):
    owner = _user(db)
    stranger = _user(db)
    pending = _post(db, owner)
    resp = client.get(
        "/post", params={"owner_id": str(owner.user_key)}, headers=_auth(stranger)
    )
    assert resp.status_code == 200, resp.text
    ids = [p["id"] for p in resp.json()["items"]]
    assert pending.id in ids


def test_pending_post_absent_from_global_listing(client, db):
    owner = _user(db)
    pending = _post(db, owner)
    resp = client.get("/post")
    assert resp.status_code == 200, resp.text
    ids = [p["id"] for p in resp.json()["items"]]
    assert pending.id not in ids


def test_pending_post_absent_from_recent_feed(client, db):
    owner = _user(db)
    pending = _post(db, owner)
    resp = client.get("/post/recent")
    assert resp.status_code == 200, resp.text
    ids = [p["id"] for p in resp.json()["items"]]
    assert pending.id not in ids


# --- Notifications ------------------------------------------------------------


def test_approve_public_notifies_author(client, db):
    owner = _user(db)
    mod = _user(db, roles=("user", "moderator"))
    pending = _post(db, owner)

    resp = client.post(f"/post/{pending.id}/approve-public", headers=_auth(mod))
    assert resp.status_code == 201, resp.text

    notif = (
        db.query(models.SocialNotification)
        .filter(
            models.SocialNotification.user_id == owner.id,
            models.SocialNotification.notification_type == "post_approved",
        )
        .first()
    )
    assert notif is not None
    assert notif.post_id == pending.id
    assert notif.actor_id == mod.id


def test_trust_grant_notifies_user(client, db):
    target = _user(db)
    mod = _user(db, roles=("user", "moderator"))

    resp = client.post(f"/admin/user/{target.public_sqid}/trust", headers=_auth(mod))
    assert resp.status_code == 201, resp.text

    notif = (
        db.query(models.SocialNotification)
        .filter(
            models.SocialNotification.user_id == target.id,
            models.SocialNotification.notification_type == "trust_granted",
        )
        .first()
    )
    assert notif is not None
    assert notif.actor_id == mod.id
    db.refresh(target)
    assert target.auto_public_approval is True

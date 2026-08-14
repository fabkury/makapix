"""Tests for Lineage Links (docs/artwork-provenance/PLAN.md §3.2/§4/§5, ADR 0002).

Covers: multi-parent creation (order, dedup, cap, unknown parent), publish-time
Remixable enforcement + grandfathering, self-remix bypass, replace-artwork
append-only semantics + cycle rejection, deleted/hidden parent handling
(tombstones, anonymous slots), children/me-remixes visibility filtering, the
remix notification fan-out, the mkpx Remixable gate (L11), moderator severing,
and public lineage counts.
"""

from __future__ import annotations

import io
import uuid

import pytest
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import Post, PostLineage, SocialNotification, User
from app.services.post_stats import annotate_posts_with_counts
from app.sqids_config import encode_user_id
from app.vault import MKPX_MAGIC_COMPACT

# --- helpers -----------------------------------------------------------------


def make_png_bytes(color) -> bytes:
    from PIL import Image

    img = Image.new("RGBA", (8, 8), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_user(db: Session, roles=None) -> User:
    uid = str(uuid.uuid4())[:8]
    u = User(
        handle=f"ln_{uid}",
        email=f"ln_{uid}@example.com",
        roles=roles or ["user"],
        reputation=1000,  # 64 uploads/hour — multi-upload tests stay unthrottled
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    u.public_sqid = encode_user_id(u.id)
    db.commit()
    db.refresh(u)
    return u


def _headers(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


_color_counter = iter(range(1, 10_000))


def _upload(
    client, user: User, data: dict | None = None, files_extra: dict | None = None
) -> dict:
    n = next(_color_counter)
    files = {
        "image": ("art.png", make_png_bytes((n % 255, n // 255, 42, 255)), "image/png")
    }
    if files_extra:
        files.update(files_extra)
    r = client.post(
        "/v1/post/upload",
        files=files,
        data={"title": "lineage test", **(data or {})},
        headers=_headers(user),
    )
    assert r.status_code == 201, r.text
    return r.json()["post"]


def _upload_expect_422(client, user: User, data: dict) -> dict:
    n = next(_color_counter)
    r = client.post(
        "/v1/post/upload",
        files={
            "image": (
                "art.png",
                make_png_bytes((n % 255, n // 255, 43, 255)),
                "image/png",
            )
        },
        data={"title": "lineage test", **data},
        headers=_headers(user),
    )
    assert r.status_code == 422, r.text
    return r.json()["error"]


def _links_of(db: Session, child_id: int) -> list[PostLineage]:
    return (
        db.query(PostLineage)
        .filter(PostLineage.child_post_id == child_id)
        .order_by(PostLineage.position)
        .all()
    )


def _make_public(db: Session, post_id: int) -> None:
    row = db.query(Post).filter(Post.id == post_id).first()
    row.public_visibility = True
    db.commit()


@pytest.fixture()
def vault_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


# --- link creation at upload -------------------------------------------------


def test_single_parent_link_created(client, db, vault_tmp):
    u1, u2 = _make_user(db), _make_user(db)
    parent = _upload(client, u1)
    child = _upload(client, u2, data={"remixed_from": parent["public_sqid"]})

    links = _links_of(db, child["id"])
    assert len(links) == 1
    assert links[0].parent_post_id == parent["id"]
    assert links[0].parent_sqid == parent["public_sqid"]
    assert links[0].position == 0
    assert child["parent_count"] == 1


def test_multi_parent_order_and_dedup(client, db, vault_tmp):
    u1, u2 = _make_user(db), _make_user(db)
    a = _upload(client, u1)
    b = _upload(client, u1)
    declared = f"{b['public_sqid']} , {a['public_sqid']},{b['public_sqid']}"
    child = _upload(client, u2, data={"remixed_from": declared})

    links = _links_of(db, child["id"])
    assert [l.parent_sqid for l in links] == [b["public_sqid"], a["public_sqid"]]
    assert [l.position for l in links] == [0, 1]


def test_too_many_parents_422(client, db, vault_tmp):
    u1, u2 = _make_user(db), _make_user(db)
    sqids = [_upload(client, u1)["public_sqid"] for _ in range(9)]
    err = _upload_expect_422(client, u2, {"remixed_from": ",".join(sqids)})
    assert err["code"] == "too_many_parents"


def test_unknown_parent_422(client, db, vault_tmp):
    u = _make_user(db)
    err = _upload_expect_422(client, u, {"remixed_from": "zzzzzz"})
    assert err["code"] == "parent_not_found"


# --- Remixable enforcement (publish time, ADR 0002) --------------------------


def test_non_remixable_parent_rejects_upload(client, db, vault_tmp):
    u1, u2 = _make_user(db), _make_user(db)
    parent = _upload(client, u1, data={"remixable": "false"})
    err = _upload_expect_422(client, u2, {"remixed_from": parent["public_sqid"]})
    assert err["code"] == "remix_not_allowed"
    assert err["details"]["parent"] == parent["public_sqid"]


def test_owner_may_remix_own_non_remixable_work(client, db, vault_tmp):
    u1 = _make_user(db)
    parent = _upload(client, u1, data={"remixable": "false"})
    child = _upload(client, u1, data={"remixed_from": parent["public_sqid"]})
    assert len(_links_of(db, child["id"])) == 1


def test_permission_flip_never_invalidates_links(client, db, vault_tmp):
    u1, u2 = _make_user(db), _make_user(db)
    parent = _upload(client, u1)
    child = _upload(client, u2, data={"remixed_from": parent["public_sqid"]})
    r = client.patch(
        f"/v1/post/{parent['id']}", json={"remixable": False}, headers=_headers(u1)
    )
    assert r.status_code == 200
    assert len(_links_of(db, child["id"])) == 1  # grandfathered forever


# --- replace-artwork: append-only + cycles -----------------------------------


def test_replace_appends_links_never_removes(client, db, vault_tmp):
    u1, u2 = _make_user(db), _make_user(db)
    a = _upload(client, u1)
    b = _upload(client, u1)
    child = _upload(client, u2, data={"remixed_from": a["public_sqid"]})

    n = next(_color_counter)
    r = client.post(
        f"/v1/post/{child['id']}/replace-artwork",
        files={"image": ("new.png", make_png_bytes((n % 255, 5, 5, 255)), "image/png")},
        # Re-declares a (no-op) and adds b
        data={"remixed_from": f"{a['public_sqid']},{b['public_sqid']}"},
        headers=_headers(u2),
    )
    assert r.status_code == 200, r.text
    links = _links_of(db, child["id"])
    assert [l.parent_sqid for l in links] == [a["public_sqid"], b["public_sqid"]]

    # A replace with no declaration leaves lineage untouched (L9)
    n = next(_color_counter)
    r2 = client.post(
        f"/v1/post/{child['id']}/replace-artwork",
        files={
            "image": ("new2.png", make_png_bytes((n % 255, 6, 6, 255)), "image/png")
        },
        headers=_headers(u2),
    )
    assert r2.status_code == 200, r2.text
    assert len(_links_of(db, child["id"])) == 2


def test_replace_cycle_rejected(client, db, vault_tmp):
    u1, u2 = _make_user(db), _make_user(db)
    a = _upload(client, u1)
    b = _upload(client, u2, data={"remixed_from": a["public_sqid"]})

    # a declaring its own descendant b as parent would close a cycle
    n = next(_color_counter)
    r = client.post(
        f"/v1/post/{a['id']}/replace-artwork",
        files={"image": ("new.png", make_png_bytes((n % 255, 7, 7, 255)), "image/png")},
        data={"remixed_from": b["public_sqid"]},
        headers=_headers(u1),
    )
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "lineage_cycle"

    # Self-loop is the degenerate cycle
    n = next(_color_counter)
    r2 = client.post(
        f"/v1/post/{a['id']}/replace-artwork",
        files={
            "image": ("new2.png", make_png_bytes((n % 255, 8, 8, 255)), "image/png")
        },
        data={"remixed_from": a["public_sqid"]},
        headers=_headers(u1),
    )
    assert r2.status_code == 422, r2.text
    assert r2.json()["error"]["code"] == "lineage_cycle"


# --- deleted / hidden parents (L10) ------------------------------------------


def test_soft_deleted_parent_shows_deleted_slot(client, db, vault_tmp):
    u1, u2 = _make_user(db), _make_user(db)
    parent = _upload(client, u1)
    child = _upload(client, u2, data={"remixed_from": parent["public_sqid"]})
    _make_public(db, child["id"])

    r = client.delete(f"/v1/post/{parent['id']}", headers=_headers(u1))
    assert r.status_code in (200, 204), r.text

    r2 = client.get(f"/v1/post/{child['id']}/parents", headers=_headers(u2))
    assert r2.status_code == 200, r2.text
    slots = r2.json()["items"]
    assert len(slots) == 1
    assert slots[0]["state"] == "deleted"
    assert slots[0]["post"] is None
    assert len(_links_of(db, child["id"])) == 1  # link survives


def test_hard_deleted_parent_leaves_tombstone(client, db, vault_tmp):
    u1, u2 = _make_user(db), _make_user(db)
    parent = _upload(client, u1)
    child = _upload(client, u2, data={"remixed_from": parent["public_sqid"]})
    parent_sqid = parent["public_sqid"]

    row = db.query(Post).filter(Post.id == parent["id"]).first()
    db.delete(row)
    db.commit()

    links = _links_of(db, child["id"])
    assert len(links) == 1
    assert links[0].parent_post_id is None  # FK nulled by the DB
    assert links[0].parent_sqid == parent_sqid  # snapshot survives


def test_child_hard_delete_cascades_its_links(client, db, vault_tmp):
    u1, u2 = _make_user(db), _make_user(db)
    parent = _upload(client, u1)
    child = _upload(client, u2, data={"remixed_from": parent["public_sqid"]})

    row = db.query(Post).filter(Post.id == child["id"]).first()
    db.delete(row)
    db.commit()
    assert _links_of(db, child["id"]) == []


def test_hidden_parent_yields_anonymous_slot(client, db, vault_tmp):
    u1, u2, viewer = _make_user(db), _make_user(db), _make_user(db)
    parent = _upload(client, u1)
    child = _upload(client, u2, data={"remixed_from": parent["public_sqid"]})
    _make_public(db, child["id"])

    row = db.query(Post).filter(Post.id == parent["id"]).first()
    row.hidden_by_user = True
    db.commit()

    r = client.get(f"/v1/post/{child['id']}/parents", headers=_headers(viewer))
    assert r.status_code == 200, r.text
    slots = r.json()["items"]
    assert slots[0]["state"] == "unavailable"
    assert slots[0]["post"] is None  # no identity leaked

    # The parent's owner still sees their own post in the slot
    r2 = client.get(f"/v1/post/{child['id']}/parents", headers=_headers(u1))
    assert r2.json()["items"][0]["state"] == "available"


# --- children & aggregate listings -------------------------------------------


def test_children_visibility_filtering(client, db, vault_tmp):
    u1, u2, viewer = _make_user(db), _make_user(db), _make_user(db)
    parent = _upload(client, u1)
    _make_public(db, parent["id"])
    visible_child = _upload(client, u2, data={"remixed_from": parent["public_sqid"]})
    hidden_child = _upload(client, u2, data={"remixed_from": parent["public_sqid"]})
    _make_public(db, visible_child["id"])
    row = db.query(Post).filter(Post.id == hidden_child["id"]).first()
    row.hidden_by_user = True
    db.commit()

    r = client.get(f"/v1/post/{parent['id']}/children", headers=_headers(viewer))
    assert r.status_code == 200, r.text
    ids = [p["id"] for p in r.json()["items"]]
    assert visible_child["id"] in ids
    assert hidden_child["id"] not in ids  # hidden children never leak

    # The remixer sees their own hidden child in the list
    r2 = client.get(f"/v1/post/{parent['id']}/children", headers=_headers(u2))
    ids2 = [p["id"] for p in r2.json()["items"]]
    assert hidden_child["id"] in ids2


def test_me_remixes_aggregate(client, db, vault_tmp):
    u1, u2 = _make_user(db), _make_user(db)
    a = _upload(client, u1)
    b = _upload(client, u1)
    child = _upload(
        client, u2, data={"remixed_from": f"{a['public_sqid']},{b['public_sqid']}"}
    )
    _make_public(db, child["id"])

    r = client.get("/v1/me/remixes", headers=_headers(u1))
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert len(items) == 1  # one Remix, even with two of my works as Parents
    assert items[0]["post"]["id"] == child["id"]
    assert set(items[0]["my_parent_sqids"]) == {a["public_sqid"], b["public_sqid"]}

    # Uninvolved users see nothing
    r2 = client.get("/v1/me/remixes", headers=_headers(u2))
    assert r2.json()["items"] == []


# --- notification (L12) ------------------------------------------------------


def test_remix_notification_per_distinct_owner(client, db, vault_tmp):
    u1, u2, remixer = _make_user(db), _make_user(db), _make_user(db)
    a = _upload(client, u1)
    b = _upload(client, u1)  # same owner as a
    c = _upload(client, u2)
    child = _upload(
        client,
        remixer,
        data={
            "remixed_from": ",".join(
                [a["public_sqid"], b["public_sqid"], c["public_sqid"]]
            )
        },
    )

    notes = (
        db.query(SocialNotification)
        .filter(SocialNotification.notification_type == "remix")
        .all()
    )
    # One per distinct parent owner — u1 deduped across a and b
    assert sorted(n.user_id for n in notes) == sorted([u1.id, u2.id])
    for n in notes:
        assert n.actor_id == remixer.id
        assert n.content_sqid == child["public_sqid"]  # leads to the child


def test_self_remix_no_notification(client, db, vault_tmp):
    u1 = _make_user(db)
    parent = _upload(client, u1)
    _upload(client, u1, data={"remixed_from": parent["public_sqid"]})
    notes = (
        db.query(SocialNotification)
        .filter(SocialNotification.notification_type == "remix")
        .all()
    )
    assert notes == []


# --- mkpx Remixable gate (L11) -----------------------------------------------


def test_mkpx_download_gated_by_remixable(client, db, vault_tmp):
    owner, stranger = _make_user(db), _make_user(db)
    mod = _make_user(db, roles=["user", "moderator"])
    post = _upload(
        client,
        owner,
        data={"remixable": "false"},
        files_extra={
            "mkpx": (
                "art.mkpx",
                MKPX_MAGIC_COMPACT + b"\x00" * 64,
                "application/x-mkpx",
            )
        },
    )
    _make_public(db, post["id"])
    url = f"/v1/d/{post['public_sqid']}.mkpx"

    r = client.get(url, headers=_headers(stranger))
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "not_remixable"

    assert client.get(url, headers=_headers(owner)).status_code == 200
    assert client.get(url, headers=_headers(mod)).status_code == 200

    # Flip Remixable back on → strangers may download again
    r2 = client.patch(
        f"/v1/post/{post['id']}", json={"remixable": True}, headers=_headers(owner)
    )
    assert r2.status_code == 200
    assert client.get(url, headers=_headers(stranger)).status_code == 200


# --- moderator severing (Q2 tooling) -----------------------------------------


def test_moderator_severs_link_with_audit(client, db, vault_tmp):
    u1, u2 = _make_user(db), _make_user(db)
    mod = _make_user(db, roles=["user", "moderator"])
    parent = _upload(client, u1)
    child = _upload(client, u2, data={"remixed_from": parent["public_sqid"]})
    link = _links_of(db, child["id"])[0]

    # Non-mods cannot sever
    r = client.delete(f"/v1/admin/lineage/{link.id}", headers=_headers(u2))
    assert r.status_code == 403, r.text

    r2 = client.delete(f"/v1/admin/lineage/{link.id}", headers=_headers(mod))
    assert r2.status_code == 204, r2.text
    assert _links_of(db, child["id"]) == []

    db.expire_all()
    row = db.query(Post).filter(Post.id == child["id"]).first()
    severed = row.source_details["_server"]["severed"]
    assert len(severed) == 1
    assert severed[0]["parent_sqid"] == parent["public_sqid"]
    assert severed[0]["by_user_id"] == mod.id


# --- public counts (L8) ------------------------------------------------------


def test_lineage_counts_annotation(client, db, vault_tmp):
    u1, u2 = _make_user(db), _make_user(db)
    parent = _upload(client, u1)
    child = _upload(client, u2, data={"remixed_from": parent["public_sqid"]})

    rows = db.query(Post).filter(Post.id.in_([parent["id"], child["id"]])).all()
    annotate_posts_with_counts(db, rows, None)
    by_id = {p.id: p for p in rows}
    # parent_count counts all links (the badge fact)
    assert by_id[child["id"]].parent_count == 1
    assert by_id[parent["id"]].parent_count == 0
    # child_count counts publicly-visible children only
    assert by_id[parent["id"]].child_count == 0
    _make_public(db, child["id"])
    annotate_posts_with_counts(db, rows, None)
    assert by_id[parent["id"]].child_count == 1

"""Tests for artwork provenance fields (docs/artwork-provenance/PLAN.md §3–§5).

Covers: declared/undeclared provenance, invalid declarations → 422, _server
zone stripping/assembly, mkpx inference, replace-artwork snapshot + reset
(D5), Remixable defaults + ND license coupling (L4/L5), public-schema
boundaries (channel/method/details stay internal), and backfill idempotence.
Lineage-link behavior lives in test_artwork_lineage.py.
"""

from __future__ import annotations

import io
import json
import uuid

import pytest
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import License, Post, User
from app.sqids_config import encode_user_id
from app.vault import MKPX_MAGIC_COMPACT

# --- helpers -----------------------------------------------------------------


def make_png_bytes(color=(200, 30, 90, 255)) -> bytes:
    from PIL import Image

    img = Image.new("RGBA", (8, 8), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_mkpx_bytes(payload: bytes = b"\x00" * 64) -> bytes:
    return MKPX_MAGIC_COMPACT + payload


def _make_user(db: Session, roles=None) -> User:
    uid = str(uuid.uuid4())[:8]
    u = User(
        handle=f"pv_{uid}",
        email=f"pv_{uid}@example.com",
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
):
    n = next(_color_counter)
    files = {
        "image": ("art.png", make_png_bytes((n % 255, n // 255, 7, 255)), "image/png")
    }
    if files_extra:
        files.update(files_extra)
    return client.post(
        "/v1/post/upload",
        files=files,
        data={"title": "provenance test", **(data or {})},
        headers=_headers(user),
    )


def _get_license(db: Session, identifier: str) -> License:
    # Get-or-create: the db fixture truncates seed data between tests.
    lic = db.query(License).filter(License.identifier == identifier).first()
    if lic is None:
        lic = License(
            identifier=identifier,
            title=identifier,
            canonical_url=f"https://creativecommons.org/licenses/{identifier}",
            badge_path=f"/licenses/{identifier}.svg",
        )
        db.add(lic)
        db.commit()
        db.refresh(lic)
    return lic


@pytest.fixture()
def vault_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("VAULT_LOCATION", str(tmp_path))
    return tmp_path


# --- declarations ------------------------------------------------------------


def test_undeclared_upload_records_unknown(client, db, vault_tmp):
    user = _make_user(db)
    r = _upload(client, user)
    assert r.status_code == 201, r.text
    row = db.query(Post).filter(Post.id == r.json()["post"]["id"]).first()
    assert row.upload_channel is None
    assert row.creation_method is None
    # _server observation zone still recorded (D2)
    assert row.source_details["_server"]["declared_client"] is None
    assert row.source_details["_server"]["mkpx_at_upload"] is False
    assert row.remixable is True  # default allow (L4)


def test_declared_provenance_recorded(client, db, vault_tmp):
    user = _make_user(db)
    r = _upload(
        client,
        user,
        data={
            "client": "app/1.0.14",
            "creation_method": "editor_hand_drawn",
            "source_details": json.dumps(
                {
                    "editor_version": "1.0.14",
                    "editor_platform": "android",
                    "device_type": "tablet",
                    "unknown_key": "dropped silently",
                    "_server": {"spoof": True},
                }
            ),
        },
    )
    assert r.status_code == 201, r.text
    row = db.query(Post).filter(Post.id == r.json()["post"]["id"]).first()
    assert row.upload_channel == "app"
    assert row.creation_method == "editor_hand_drawn"
    assert row.source_details["editor_version"] == "1.0.14"
    assert row.source_details["editor_platform"] == "android"
    assert row.source_details["device_type"] == "tablet"
    assert "unknown_key" not in row.source_details
    # Client can never write the server zone; server rebuilt it
    assert "spoof" not in row.source_details["_server"]
    assert row.source_details["_server"]["declared_client"] == "app/1.0.14"


def test_unrecognized_client_prefix_maps_to_null_channel(client, db, vault_tmp):
    user = _make_user(db)
    r = _upload(client, user, data={"client": "weird-script/2.0"})
    assert r.status_code == 201, r.text
    row = db.query(Post).filter(Post.id == r.json()["post"]["id"]).first()
    assert row.upload_channel is None  # absence/unknown is never coerced
    assert row.source_details["_server"]["declared_client"] == "weird-script/2.0"


def test_invalid_creation_method_422(client, db, vault_tmp):
    user = _make_user(db)
    for bad in ("editor", "ai_generated", "EDITOR_IMPORT"):
        r = _upload(client, user, data={"creation_method": bad})
        assert r.status_code == 422, r.text
        assert r.json()["error"]["code"] == "invalid_creation_method"


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        json.dumps(["a", "list"]),
        json.dumps({"device_type": "laptop"}),  # no laptop: not observable (L7)
        json.dumps({"editor_platform": "windows"}),
        json.dumps({"editor_version": "x" * 65}),
        json.dumps({"pad": "x" * 3000}),  # > 2048 bytes
    ],
)
def test_invalid_source_details_422(client, db, vault_tmp, raw):
    user = _make_user(db)
    r = _upload(client, user, data={"source_details": raw})
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "invalid_source_details"


def test_mkpx_inference_editor(client, db, vault_tmp):
    user = _make_user(db)
    r = _upload(
        client,
        user,
        files_extra={"mkpx": ("art.mkpx", make_mkpx_bytes(), "application/x-mkpx")},
    )
    assert r.status_code == 201, r.text
    row = db.query(Post).filter(Post.id == r.json()["post"]["id"]).first()
    assert row.creation_method == "editor"
    assert row.source_details["_server"]["inferred"] == {"creation_method": "editor"}
    assert row.source_details["_server"]["mkpx_at_upload"] is True


def test_declared_method_wins_over_inference(client, db, vault_tmp):
    user = _make_user(db)
    r = _upload(
        client,
        user,
        data={"creation_method": "editor_import"},
        files_extra={"mkpx": ("art.mkpx", make_mkpx_bytes(), "application/x-mkpx")},
    )
    assert r.status_code == 201, r.text
    row = db.query(Post).filter(Post.id == r.json()["post"]["id"]).first()
    assert row.creation_method == "editor_import"
    assert "inferred" not in row.source_details["_server"]


# --- replace-artwork (D5) ----------------------------------------------------


def test_replace_snapshots_and_resets_provenance(client, db, vault_tmp):
    user = _make_user(db)
    r = _upload(
        client,
        user,
        data={
            "client": "app/1.0.14",
            "creation_method": "editor_hand_drawn",
            "source_details": json.dumps({"editor_version": "1.0.14"}),
        },
    )
    post_id = r.json()["post"]["id"]

    r2 = client.post(
        f"/v1/post/{post_id}/replace-artwork",
        files={"image": ("new.png", make_png_bytes((123, 45, 67, 255)), "image/png")},
        headers=_headers(user),
    )
    assert r2.status_code == 200, r2.text

    db.expire_all()
    row = db.query(Post).filter(Post.id == post_id).first()
    # Undeclared on replace → honest unknown, no carry-over
    assert row.upload_channel is None
    assert row.creation_method is None
    replaced = row.source_details["_server"]["replaced"]
    assert len(replaced) == 1
    assert replaced[0]["upload_channel"] == "app"
    assert replaced[0]["creation_method"] == "editor_hand_drawn"
    assert replaced[0]["declared"] == {"editor_version": "1.0.14"}


def test_replace_applies_new_declaration(client, db, vault_tmp):
    user = _make_user(db)
    r = _upload(client, user, data={"creation_method": "external_file"})
    post_id = r.json()["post"]["id"]

    r2 = client.post(
        f"/v1/post/{post_id}/replace-artwork",
        files={"image": ("new.png", make_png_bytes((10, 200, 30, 255)), "image/png")},
        data={"client": "app/1.1.0", "creation_method": "editor_import"},
        headers=_headers(user),
    )
    assert r2.status_code == 200, r2.text
    db.expire_all()
    row = db.query(Post).filter(Post.id == post_id).first()
    assert row.upload_channel == "app"
    assert row.creation_method == "editor_import"
    assert row.source_details["_server"]["replaced"][0]["creation_method"] == (
        "external_file"
    )


# --- Remixable × licenses (L4/L5) -------------------------------------------


def test_nd_license_defaults_not_remixable(client, db, vault_tmp):
    user = _make_user(db)
    nd = _get_license(db, "CC-BY-ND-4.0")
    r = _upload(client, user, data={"license_id": str(nd.id)})
    assert r.status_code == 201, r.text
    assert r.json()["post"]["remixable"] is False


def test_nd_license_explicit_remixable_conflicts(client, db, vault_tmp):
    user = _make_user(db)
    nd = _get_license(db, "CC-BY-NC-ND-4.0")
    r = _upload(client, user, data={"license_id": str(nd.id), "remixable": "true"})
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "remixable_conflicts_with_license"


def test_explicit_opt_out_at_upload(client, db, vault_tmp):
    user = _make_user(db)
    r = _upload(client, user, data={"remixable": "false"})
    assert r.status_code == 201, r.text
    assert r.json()["post"]["remixable"] is False


def test_patch_remixable_toggle_and_nd_rule(client, db, vault_tmp):
    user = _make_user(db)
    r = _upload(client, user)
    post_id = r.json()["post"]["id"]

    r2 = client.patch(
        f"/v1/post/{post_id}", json={"remixable": False}, headers=_headers(user)
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["remixable"] is False

    # ND-licensed post can never be flipped to Remixable
    nd = _get_license(db, "CC-BY-ND-4.0")
    row = db.query(Post).filter(Post.id == post_id).first()
    row.license_id = nd.id
    db.commit()
    r3 = client.patch(
        f"/v1/post/{post_id}", json={"remixable": True}, headers=_headers(user)
    )
    assert r3.status_code == 422, r3.text
    assert r3.json()["error"]["code"] == "remixable_conflicts_with_license"


def test_moderator_can_force_disallow(client, db, vault_tmp):
    artist = _make_user(db)
    mod = _make_user(db, roles=["user", "moderator"])
    r = _upload(client, artist)
    post_id = r.json()["post"]["id"]

    r2 = client.patch(
        f"/v1/post/{post_id}", json={"remixable": False}, headers=_headers(mod)
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["remixable"] is False


# --- public schema boundaries (D3 remnant) ----------------------------------


def test_public_schema_has_lineage_fields_not_provenance(client, db, vault_tmp):
    user = _make_user(db)
    r = _upload(client, user, data={"client": "app/1.0.14"})
    post = r.json()["post"]
    assert "remixable" in post
    assert "parent_count" in post
    assert "child_count" in post
    assert "upload_channel" not in post
    assert "creation_method" not in post
    assert "source_details" not in post


# --- backfill (D4) -----------------------------------------------------------


def _load_backfill_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "backfill_provenance", "/workspace/api/scripts/backfill_provenance.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_backfill_targets_only_mkpx_null_rows(client, db, vault_tmp, monkeypatch):
    user = _make_user(db)
    # A legacy-style mkpx post (provenance NULL), a declared post, a plain post
    r_mkpx = _upload(
        client,
        user,
        files_extra={"mkpx": ("art.mkpx", make_mkpx_bytes(), "application/x-mkpx")},
    )
    mkpx_id = r_mkpx.json()["post"]["id"]
    row = db.query(Post).filter(Post.id == mkpx_id).first()
    # Simulate a legacy row: strip what the endpoint recorded
    row.upload_channel = None
    row.creation_method = None
    row.source_details = None
    r_plain = _upload(client, user)
    plain_id = r_plain.json()["post"]["id"]
    plain = db.query(Post).filter(Post.id == plain_id).first()
    plain.upload_channel = None
    plain.creation_method = None
    plain.source_details = None
    db.commit()

    mod = _load_backfill_module()
    monkeypatch.setattr(mod, "SessionLocal", lambda: db)
    monkeypatch.setattr("sys.argv", ["backfill_provenance.py"])
    assert mod.main() == 0

    db.expire_all()
    row = db.query(Post).filter(Post.id == mkpx_id).first()
    assert row.upload_channel == "app"
    assert row.creation_method == "editor"
    assert row.source_details["_server"]["backfilled_at"]
    assert row.source_details["_server"]["inferred"]["creation_method"] == "editor"
    # Non-mkpx rows stay unknown
    plain = db.query(Post).filter(Post.id == plain_id).first()
    assert plain.upload_channel is None
    assert plain.creation_method is None

    # Idempotence: second run matches nothing
    monkeypatch.setattr(mod, "SessionLocal", lambda: db)
    assert mod.main() == 0
    db.expire_all()
    row = db.query(Post).filter(Post.id == mkpx_id).first()
    replaced_marker = row.source_details["_server"]["backfilled_at"]
    assert row.creation_method == "editor"
    assert row.source_details["_server"]["backfilled_at"] == replaced_marker

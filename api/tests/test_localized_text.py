"""Server side of the app's localization (docs/localized-text/): stable codes
the app translates, `code` beside `detail` off /v1, and the email locale."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.auth import create_access_token
from app.models import Comment, User
from app.services import email as email_service
from app.services import email_copy
from tests.test_comment_mod_deletion import _make_post, _make_user


def _auth(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


# --- Email copy -------------------------------------------------------------


def test_copy_lookup_exact_then_base_then_english(monkeypatch):
    fake = {
        "en": {"bdr_button": "Download", "bdr_ready": "Ready."},
        "pt-br": {"bdr_button": "Baixar"},
        "de": {"bdr_button": "Herunterladen"},
    }
    monkeypatch.setattr(email_copy, "_all_copy", lambda: fake)
    assert email_copy.copy_for("pt-BR")["bdr_button"] == "Baixar"
    assert email_copy.copy_for("de-AT")["bdr_button"] == "Herunterladen"
    assert email_copy.copy_for("zh-Hant")["bdr_button"] == "Download"
    assert email_copy.copy_for(None)["bdr_button"] == "Download"
    # A key the translation lacks falls back to English.
    assert email_copy.copy_for("pt-BR")["bdr_ready"] == "Ready."


def test_otp_email_escapes_handle_in_html():
    subject, html, text = email_service._otp_message(
        None, "<b>x</b>", "123456", "verify"
    )
    assert subject == "Your Makapix Club verification code"
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html
    assert "123456" in html and "123456" in text


# --- Stored locale ----------------------------------------------------------


def test_register_stores_locale(client, db):
    email = f"loc_{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/v1/auth/register",
        json={"email": email, "password": "goodpass123", "locale": "pt-BR"},
    )
    assert r.status_code in (200, 201), r.text
    user = db.query(User).filter(User.email == email).one()
    assert user.locale == "pt-BR"


def test_register_rejects_malformed_locale(client):
    r = client.post(
        "/v1/auth/register",
        json={"email": "x@example.com", "password": "goodpass123", "locale": "!!"},
    )
    assert r.status_code == 422


def test_patch_sets_and_clears_locale_and_me_returns_it(client, db):
    user = _make_user(db, handle_prefix="loc", roles=["user"])
    r = client.patch(
        f"/v1/user/{user.user_key}", headers=_auth(user), json={"locale": "ja"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["locale"] == "ja"
    me = client.get("/v1/auth/me", headers=_auth(user))
    assert me.json()["user"]["locale"] == "ja"

    # Omitting the field leaves it alone; explicit null clears it.
    client.patch(f"/v1/user/{user.user_key}", headers=_auth(user), json={"bio": "b"})
    db.refresh(user)
    assert user.locale == "ja"
    client.patch(
        f"/v1/user/{user.user_key}", headers=_auth(user), json={"locale": None}
    )
    db.refresh(user)
    assert user.locale is None


def test_otp_request_locale_overrides_stored(client, db, monkeypatch):
    sent = []
    monkeypatch.setattr(
        email_service,
        "send_password_reset_otp_email",
        lambda to, code, handle=None, locale=None: sent.append(locale),
    )
    user = _make_user(db, handle_prefix="loc", roles=["user"])
    user.locale = "de"
    db.commit()
    client.post("/v1/auth/password-otp/request", json={"email": user.email})
    client.post(
        "/v1/auth/password-otp/request", json={"email": user.email, "locale": "fr"}
    )
    assert sent == ["de", "fr"]


# --- Codes ------------------------------------------------------------------


def test_legacy_path_carries_code_beside_detail(client):
    r = client.get(f"/user/{uuid.uuid4()}")
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == "user_not_found"
    assert isinstance(body["detail"], str)


def test_v1_specific_not_found_code(client):
    r = client.get(f"/v1/user/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "user_not_found"


def test_banned_user_gets_403_account_banned(client, db):
    user = _make_user(db, handle_prefix="ban", roles=["user"])
    token_headers = _auth(user)
    user.banned_until = datetime.now(timezone.utc) + timedelta(days=2)
    db.commit()
    r = client.get("/v1/auth/me", headers=token_headers)
    assert r.status_code == 403
    err = r.json()["error"]
    assert err["code"] == "account_banned"
    assert err["details"]["permanent"] is False


def test_admin_ban_accepts_sqid_and_uuid(client, db):
    """App 0002 §7.1: the sqid route was shadowed by the UUID one (422)."""
    mod = _make_user(db, handle_prefix="mod", roles=["user", "moderator"])
    target = _make_user(db, handle_prefix="tgt", roles=["user"])
    r = client.post(
        f"/admin/user/{target.public_sqid}/ban?duration_days=3", headers=_auth(mod)
    )
    assert r.status_code == 201, r.text
    assert r.json()["until"] is not None
    r = client.delete(f"/admin/user/{target.public_sqid}/ban", headers=_auth(mod))
    assert r.status_code == 204
    r = client.post(
        f"/v1/admin/user/{target.user_key}/ban",
        headers=_auth(mod),
        json={"duration_days": None},
    )
    assert r.status_code == 201, r.text
    assert r.json()["until"].startswith("9999-")  # PERMANENT_BAN_UNTIL


def test_forbidden_role_details(client, db):
    user = _make_user(db, handle_prefix="plain", roles=["user"])
    target = _make_user(db, handle_prefix="tgt", roles=["user"])
    r = client.delete(f"/v1/admin/user/{target.user_key}/ban", headers=_auth(user))
    assert r.status_code == 403
    err = r.json()["error"]
    assert err["code"] == "forbidden_role"
    assert err["details"] == {"required": "moderator"}


def test_comment_edit_runs_profanity_filter(client, db):
    author = _make_user(db, handle_prefix="cm", roles=["user"])
    post = _make_post(db, owner=author, title="profanity-edit")
    comment = Comment(post_id=post.id, author_id=author.id, body="nice art")
    db.add(comment)
    db.commit()
    r = client.patch(
        f"/v1/post/comments/{comment.id}",
        headers=_auth(author),
        json={"body": "this is shit"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "comment_profanity"


def test_handle_availability_reason(client, db):
    taken = _make_user(db, handle_prefix="hav", roles=["user"])
    r = client.post("/v1/auth/check-handle-availability", json={"handle": taken.handle})
    assert r.json()["available"] is False
    assert r.json()["reason"] == "taken"
    r = client.post("/v1/auth/check-handle-availability", json={"handle": "ab"})
    assert r.json()["reason"] == "too_short"

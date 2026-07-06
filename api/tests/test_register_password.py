"""Tests for `POST /auth/register` with an optional chosen password (CR A2).

Covers the four acceptance criteria from the change request:
  - chosen-password path → single OTP email → verify → sign in with that password
  - resume sign-up on an existing *unverified* account (200, password updated)
  - no-password (website) path unchanged → verification link token
  - weak password rejected with a typed `weak_password` 400; 409/precedence intact

Email delivery is disabled in tests, so we read the OTP from the DB (the OTP path
stores it on EmailVerificationToken.otp_code; the link path leaves otp_code NULL).
"""

from __future__ import annotations

import uuid

from app.models import EmailVerificationToken, User
from app.sqids_config import encode_user_id


def _email() -> str:
    return f"reg_{uuid.uuid4().hex[:8]}@example.com"


def _latest_otp(db, user_id) -> str:
    row = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.otp_code.isnot(None),
        )
        .order_by(EmailVerificationToken.created_at.desc())
        .first()
    )
    assert row is not None and row.otp_code and len(row.otp_code) == 6
    return row.otp_code


def test_register_with_chosen_password_otp_flow(client, db):
    email = _email()
    r = client.post(
        "/v1/auth/register", json={"email": email, "password": "hunter2pix"}
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["verification_method"] == "otp"
    assert body["email"] == email
    assert body["handle"]
    user_id = body["user_id"]

    # Exactly one verification token, and it's an OTP (no link/temp-password email).
    tokens = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == user_id)
        .all()
    )
    assert len(tokens) == 1
    assert tokens[0].otp_code is not None

    # Verify with the emailed code, then sign in with the SAME chosen password.
    code = _latest_otp(db, user_id)
    v = client.post("/v1/auth/email-otp/verify", json={"email": email, "code": code})
    assert v.status_code == 200, v.text
    assert v.json()["verified"] is True

    tok = client.post(
        "/v1/auth/token",
        json={"grant_type": "password", "email": email, "password": "hunter2pix"},
    )
    assert tok.status_code == 200, tok.text
    assert tok.json()["access_token"]


def test_register_without_password_is_unchanged_link_flow(client, db):
    email = _email()
    r = client.post("/v1/auth/register", json={"email": email})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["verification_method"] == "link"
    assert body["message"] == "Please check your email to verify your account"

    # Website path mints a link token (otp_code NULL), not an OTP.
    tokens = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == body["user_id"])
        .all()
    )
    assert len(tokens) == 1
    assert tokens[0].otp_code is None


def test_register_resume_signup_updates_password(client, db):
    email = _email()
    # First attempt creates an unverified account with one password.
    first = client.post(
        "/v1/auth/register", json={"email": email, "password": "first-pass1"}
    )
    assert first.status_code == 201, first.text
    user_id = first.json()["user_id"]

    # Second attempt on the still-unverified account RESUMES: 200 + password updated.
    second = client.post(
        "/v1/auth/register", json={"email": email, "password": "second-pass2"}
    )
    assert second.status_code == 200, second.text
    assert second.json()["verification_method"] == "otp"
    assert second.json()["user_id"] == user_id  # same account, not a new one

    # Verify with the freshest OTP, then the SECOND password is the one that works.
    code = _latest_otp(db, user_id)
    v = client.post("/v1/auth/email-otp/verify", json={"email": email, "code": code})
    assert v.status_code == 200, v.text

    good = client.post(
        "/v1/auth/token",
        json={"grant_type": "password", "email": email, "password": "second-pass2"},
    )
    assert good.status_code == 200, good.text
    stale = client.post(
        "/v1/auth/token",
        json={"grant_type": "password", "email": email, "password": "first-pass1"},
    )
    assert stale.status_code == 401


def test_register_weak_password_returns_typed_400(client, db):
    email = _email()
    r = client.post("/v1/auth/register", json={"email": email, "password": "short"})
    assert r.status_code == 400, r.text
    err = r.json()["error"]
    assert err["code"] == "weak_password"
    assert err["details"]["field"] == "password"
    # Nothing was created.
    assert db.query(User).filter(User.email == email).first() is None


def test_register_verified_email_still_conflicts_even_with_password(client, db):
    email = _email()
    user = User(handle=f"reg_{uuid.uuid4().hex[:8]}", email=email, email_verified=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    user.public_sqid = encode_user_id(user.id)
    db.commit()

    r = client.post(
        "/v1/auth/register", json={"email": email, "password": "hunter2pix"}
    )
    assert r.status_code == 409, r.text
    assert r.json()["error"]["message"] == "An account with this email already exists"


def test_register_unverified_no_password_keeps_409(client, db):
    email = _email()
    # Create an unverified account via the chosen-password path.
    client.post("/v1/auth/register", json={"email": email, "password": "hunter2pix"})
    # A subsequent no-password (website) register keeps the unchanged 409 string.
    r = client.post("/v1/auth/register", json={"email": email})
    assert r.status_code == 409, r.text
    assert r.json()["error"]["message"] == "pending_verification"


def test_register_stamps_terms_version(client, db):
    """D26: self-signup records acceptance of the current ToS version."""
    from app.constants import TERMS_VERSION
    from app.models import User

    email = "terms-stamp@example.com"
    r = client.post(
        "/v1/auth/register", json={"email": email, "password": "hunter2pix"}
    )
    assert r.status_code in (200, 201), r.text

    user = db.query(User).filter(User.email == email).first()
    assert user is not None
    assert user.terms_version_accepted == TERMS_VERSION

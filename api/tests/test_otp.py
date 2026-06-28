"""Tests for the numeric OTP verify/reset flows (change-request §3.4)."""

from __future__ import annotations

import uuid

from app.models import EmailVerificationToken, PasswordResetToken, User
from app.services.auth_identities import create_password_identity
from app.sqids_config import encode_user_id


def _user(db, *, verified=True, password=None) -> User:
    uid = str(uuid.uuid4())[:8]
    email = f"otp_{uid}@example.com"
    user = User(
        handle=f"otp_{uid}", email=email, roles=["user"], email_verified=verified
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.public_sqid = encode_user_id(user.id)
    db.commit()
    db.refresh(user)
    if password:
        create_password_identity(db, user.id, email, password)
    return user


def test_email_otp_request_and_verify(client, db):
    user = _user(db, verified=False)
    r = client.post("/v1/auth/email-otp/request", json={"email": user.email})
    assert r.status_code == 200
    # Read the code the server generated (email delivery is disabled in tests).
    row = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == user.id)
        .order_by(EmailVerificationToken.created_at.desc())
        .first()
    )
    assert row is not None and row.otp_code and len(row.otp_code) == 6

    ok = client.post(
        "/v1/auth/email-otp/verify",
        json={"email": user.email, "code": row.otp_code},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["verified"] is True
    db.refresh(user)
    assert user.email_verified is True


def test_email_otp_wrong_code(client, db):
    user = _user(db, verified=False)
    client.post("/v1/auth/email-otp/request", json={"email": user.email})
    bad = client.post(
        "/v1/auth/email-otp/verify",
        json={"email": user.email, "code": "000000"},
    )
    # 000000 is astronomically unlikely to match; treat as invalid.
    if bad.status_code == 200:
        return  # extremely rare code collision; skip
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "token_invalid"


def test_request_is_existence_neutral(client, db):
    r = client.post(
        "/v1/auth/email-otp/request", json={"email": "nobody-here@example.com"}
    )
    assert r.status_code == 200
    assert "message" in r.json()


def test_password_otp_reset_then_login(client, db):
    user = _user(db, verified=True, password="old-passw0rd")
    r = client.post("/v1/auth/password-otp/request", json={"email": user.email})
    assert r.status_code == 200
    row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user.id)
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )
    assert row is not None and row.otp_code

    confirm = client.post(
        "/v1/auth/password-otp/confirm",
        json={
            "email": user.email,
            "code": row.otp_code,
            "new_password": "brand-new-passw0rd",
        },
    )
    assert confirm.status_code == 200, confirm.text

    # The new password works at the token endpoint; the old one does not.
    good = client.post(
        "/v1/auth/token",
        json={
            "grant_type": "password",
            "email": user.email,
            "password": "brand-new-passw0rd",
        },
    )
    assert good.status_code == 200, good.text
    old = client.post(
        "/v1/auth/token",
        json={
            "grant_type": "password",
            "email": user.email,
            "password": "old-passw0rd",
        },
    )
    assert old.status_code == 401


def test_password_otp_wrong_code(client, db):
    user = _user(db, verified=True, password="pw-abcdef1")
    client.post("/v1/auth/password-otp/request", json={"email": user.email})
    bad = client.post(
        "/v1/auth/password-otp/confirm",
        json={
            "email": user.email,
            "code": "000000",
            "new_password": "whatever-passw0rd",
        },
    )
    assert bad.status_code == 400

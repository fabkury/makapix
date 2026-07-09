"""Tests for the Sign in with Apple grant (docs/apple-signin/API-CONTRACT.md)."""

from __future__ import annotations

import hashlib
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.models import AuthIdentity, User
from app.services import apple_signin
from app.sqids_config import encode_user_id

# One keypair for the whole module; tests patch the JWKS lookup to return it.
_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()

RAW_NONCE = "test-raw-nonce-123"


@pytest.fixture(autouse=True)
def _patch_apple_jwks(monkeypatch):
    monkeypatch.setattr(apple_signin, "_get_signing_key", lambda token: _PUBLIC_KEY)


def _hashed_nonce(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _identity_token(
    sub: str = "apple-sub-000001",
    email: str | None = None,
    email_verified="true",
    is_private_email=None,
    nonce: str | None = None,
    aud: str = apple_signin.APPLE_AUDIENCE,
    iss: str = apple_signin.APPLE_ISSUER,
    exp_delta: int = 600,
) -> str:
    now = int(time.time())
    claims = {
        "iss": iss,
        "aud": aud,
        "sub": sub,
        "iat": now,
        "exp": now + exp_delta,
        "nonce": nonce if nonce is not None else _hashed_nonce(RAW_NONCE),
    }
    if email is not None:
        claims["email"] = email
        claims["email_verified"] = email_verified
    if is_private_email is not None:
        claims["is_private_email"] = is_private_email
    return jwt.encode(
        claims, _PRIVATE_KEY, algorithm="RS256", headers={"kid": "test-kid"}
    )


def _post_grant(client, identity_token: str, **overrides):
    body = {
        "grant_type": "apple_identity_token",
        "identity_token": identity_token,
        "nonce": RAW_NONCE,
    }
    body.update(overrides)
    return client.post("/v1/auth/token", json=body)


def _unique_sub() -> str:
    return f"apple-sub-{uuid.uuid4().hex[:12]}"


def test_first_sign_in_creates_account_and_persists_profile(client, db):
    sub = _unique_sub()
    email = f"ada_{uuid.uuid4().hex[:8]}@example.com"
    r = _post_grant(
        client,
        _identity_token(sub=sub, email=email),
        given_name="Ada",
        family_name="Lovelace",
        email=email,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["expires_in"] == 3600

    identity = (
        db.query(AuthIdentity)
        .filter(AuthIdentity.provider == "apple", AuthIdentity.provider_user_id == sub)
        .first()
    )
    assert identity is not None
    assert identity.email == email
    # Apple never resends the name — it must be persisted from the first request.
    assert identity.provider_metadata["given_name"] == "Ada"
    assert identity.provider_metadata["family_name"] == "Lovelace"

    user = db.query(User).filter(User.id == identity.user_id).first()
    assert user.email == email
    assert user.email_verified is True

    # The issued access token actually authenticates.
    me = client.get(
        "/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200


def test_second_sign_in_without_email_finds_same_user(client, db):
    sub = _unique_sub()
    email = f"ret_{uuid.uuid4().hex[:8]}@example.com"
    first = _post_grant(client, _identity_token(sub=sub, email=email), email=email)
    assert first.status_code == 200, first.text
    first_user_id = first.json()["user"]["id"]

    # Second sign-in: Apple sends neither name nor email.
    second = _post_grant(client, _identity_token(sub=sub))
    assert second.status_code == 200, second.text
    assert second.json()["user"]["id"] == first_user_id
    assert db.query(User).filter(User.email == email).count() == 1


def test_nonce_mismatch_rejected(client, db):
    token = _identity_token(sub=_unique_sub(), nonce=_hashed_nonce("other-nonce"))
    r = _post_grant(client, token)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "apple_token_invalid"


def test_wrong_audience_rejected(client, db):
    token = _identity_token(sub=_unique_sub(), aud="com.example.other")
    r = _post_grant(client, token)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "apple_token_invalid"


def test_wrong_issuer_rejected(client, db):
    token = _identity_token(sub=_unique_sub(), iss="https://evil.example.com")
    r = _post_grant(client, token)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "apple_token_invalid"


def test_expired_token_rejected(client, db):
    token = _identity_token(sub=_unique_sub(), exp_delta=-60)
    r = _post_grant(client, token)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "apple_token_invalid"


def test_bad_signature_rejected(client, db):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": apple_signin.APPLE_ISSUER,
            "aud": apple_signin.APPLE_AUDIENCE,
            "sub": _unique_sub(),
            "iat": now,
            "exp": now + 600,
            "nonce": _hashed_nonce(RAW_NONCE),
        },
        other_key,
        algorithm="RS256",
    )
    r = _post_grant(client, token)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "apple_token_invalid"


def test_missing_fields_rejected(client, db):
    r = client.post(
        "/v1/auth/token",
        json={"grant_type": "apple_identity_token", "identity_token": "x"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "validation_error"


def test_verified_email_links_to_existing_account(client, db):
    email = f"link_{uuid.uuid4().hex[:8]}@example.com"
    user = User(
        handle=f"link_{uuid.uuid4().hex[:8]}",
        email=email,
        roles=["user"],
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.public_sqid = encode_user_id(user.id)
    db.commit()

    sub = _unique_sub()
    r = _post_grant(client, _identity_token(sub=sub, email=email), email=email)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["id"] == user.id
    identity = (
        db.query(AuthIdentity)
        .filter(AuthIdentity.provider == "apple", AuthIdentity.provider_user_id == sub)
        .first()
    )
    assert identity is not None and identity.user_id == user.id


def test_private_relay_email_never_links(client, db):
    # An existing account whose email happens to be a relay address must NOT be
    # linkable via Apple — the collision is rejected instead (0001 Q1).
    email = f"relay_{uuid.uuid4().hex[:8]}@privaterelay.appleid.com"
    user = User(
        handle=f"relay_{uuid.uuid4().hex[:8]}",
        email=email,
        roles=["user"],
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user.public_sqid = encode_user_id(user.id)
    db.commit()

    r = _post_grant(client, _identity_token(sub=_unique_sub(), email=email))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "conflict"


def test_relay_email_creates_fresh_account(client, db):
    email = f"fresh_{uuid.uuid4().hex[:8]}@privaterelay.appleid.com"
    sub = _unique_sub()
    r = _post_grant(
        client, _identity_token(sub=sub, email=email, is_private_email="true")
    )
    assert r.status_code == 200, r.text
    user = db.query(User).filter(User.email == email).first()
    assert user is not None and user.email_verified is True


def test_new_user_without_any_email_rejected(client, db):
    r = _post_grant(client, _identity_token(sub=_unique_sub()))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_request"

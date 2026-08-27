"""Tests for restore credentials / WebAuthn (docs/zero-tap-signin/PLAN.md).

Round-trips use soft-webauthn (a software authenticator) against the real
endpoints: create leg (options + register, authenticated) and get leg
(challenge + the restore_credential grant, unauthenticated and userless).
The test origin is https://<WEBAUTHN_RP_ID> — conftest pins the RP ID.
"""

from __future__ import annotations

import base64
import json
import uuid

import pytest
from soft_webauthn import SoftWebauthnDevice
from sqlalchemy.orm import Session

from app.auth import create_access_token
from app.models import User, WebAuthnCredential

ORIGIN = "https://test.makapix.club"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


@pytest.fixture()
def user(db: Session) -> User:
    unique = str(uuid.uuid4())[:8]
    u = User(
        handle=f"restore_{unique}",
        email=f"restore_{unique}@example.com",
        email_verified=True,
        roles=["user"],
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _creation_options_for_device(options_json: dict) -> dict:
    """Server options JSON (b64url strings) -> soft-webauthn format (bytes)."""
    pk = dict(options_json)
    pk["challenge"] = _b64url_decode(pk["challenge"])
    pk["user"] = dict(pk["user"], id=_b64url_decode(pk["user"]["id"]))
    return {"publicKey": pk}


def _request_options_for_device(options_json: dict) -> dict:
    pk = dict(options_json)
    pk["challenge"] = _b64url_decode(pk["challenge"])
    return {"publicKey": pk}


def _attestation_to_wire(attestation: dict) -> dict:
    """soft-webauthn output (bytes) -> WebAuthn wire JSON (b64url strings)."""
    return {
        "id": _b64url(attestation["rawId"]),
        "rawId": _b64url(attestation["rawId"]),
        "response": {
            "clientDataJSON": _b64url(attestation["response"]["clientDataJSON"]),
            "attestationObject": _b64url(attestation["response"]["attestationObject"]),
        },
        "type": "public-key",
        "clientExtensionResults": {},
    }


def _assertion_to_wire(assertion: dict) -> dict:
    return {
        "id": _b64url(assertion["rawId"]),
        "rawId": _b64url(assertion["rawId"]),
        "response": {
            "authenticatorData": _b64url(assertion["response"]["authenticatorData"]),
            "clientDataJSON": _b64url(assertion["response"]["clientDataJSON"]),
            "signature": _b64url(assertion["response"]["signature"]),
            "userHandle": _b64url(assertion["response"]["userHandle"]),
        },
        "type": "public-key",
        "clientExtensionResults": {},
    }


def _register_device(client, auth_headers) -> SoftWebauthnDevice:
    """Run the create leg; returns the device holding the credential."""
    resp = client.post("/v1/auth/restore/options", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    options = resp.json()
    device = SoftWebauthnDevice()
    attestation = device.create(_creation_options_for_device(options), ORIGIN)
    resp = client.post(
        "/v1/auth/restore/register",
        headers=auth_headers,
        json={"response": _attestation_to_wire(attestation)},
    )
    assert resp.status_code == 204, resp.text
    return device


def _assert_device(client, device: SoftWebauthnDevice):
    """Run the get leg; returns the /auth/token response."""
    resp = client.post("/v1/auth/restore/challenge")
    assert resp.status_code == 200, resp.text
    assertion = device.get(_request_options_for_device(resp.json()), ORIGIN)
    return client.post(
        "/v1/auth/token",
        json={
            "grant_type": "restore_credential",
            "assertion": _assertion_to_wire(assertion),
        },
    )


def test_creation_options_shape(client, auth_headers):
    resp = client.post("/v1/auth/restore/options", headers=auth_headers)
    assert resp.status_code == 200
    options = resp.json()
    assert options["rp"]["id"] == "test.makapix.club"
    assert options["authenticatorSelection"]["residentKey"] == "required"
    # Silent create/get — UV must not be demanded (messages/0003 §2a).
    assert options["authenticatorSelection"]["userVerification"] == "discouraged"
    assert options["attestation"] == "none"
    # The userHandle: 32 bytes, and stable across calls.
    handle = _b64url_decode(options["user"]["id"])
    assert len(handle) == 32
    again = client.post("/v1/auth/restore/options", headers=auth_headers).json()
    assert again["user"]["id"] == options["user"]["id"]


def test_options_require_auth(client):
    assert client.post("/v1/auth/restore/options").status_code in (401, 403)
    assert client.post(
        "/v1/auth/restore/register", json={"response": {}}
    ).status_code in (
        401,
        403,
    )


def test_challenge_is_userless(client):
    resp = client.post("/v1/auth/restore/challenge")
    assert resp.status_code == 200
    options = resp.json()
    assert options["rpId"] == "test.makapix.club"
    # Discoverable-credential flow: the server must not name credentials.
    assert options.get("allowCredentials", []) == []
    assert options["userVerification"] == "discouraged"


def test_register_and_assert_roundtrip(client, db, user, auth_headers):
    device = _register_device(client, auth_headers)

    stored = (
        db.query(WebAuthnCredential).filter(WebAuthnCredential.user_id == user.id).all()
    )
    assert len(stored) == 1
    assert stored[0].credential_id == device.credential_id

    resp = _assert_device(client, device)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["handle"] == user.handle
    assert body["access_token"] and body["refresh_token"]

    db.expire_all()
    assert stored[0].last_used_at is not None
    assert stored[0].sign_count == 1


def test_multiple_registrations_coexist(client, db, user, auth_headers):
    # One credential per device is normal; a retried/second registration must
    # not clobber the first. Both should be able to sign the user in.
    first = _register_device(client, auth_headers)
    second = _register_device(client, auth_headers)
    assert first.credential_id != second.credential_id
    assert (
        db.query(WebAuthnCredential)
        .filter(WebAuthnCredential.user_id == user.id)
        .count()
        == 2
    )
    assert _assert_device(client, first).status_code == 200
    assert _assert_device(client, second).status_code == 200


def test_assertion_challenge_is_single_use(client, user, auth_headers):
    device = _register_device(client, auth_headers)

    resp = client.post("/v1/auth/restore/challenge")
    options = resp.json()
    assertion = _assertion_to_wire(
        device.get(_request_options_for_device(options), ORIGIN)
    )
    first = client.post(
        "/v1/auth/token",
        json={"grant_type": "restore_credential", "assertion": assertion},
    )
    assert first.status_code == 200
    replay = client.post(
        "/v1/auth/token",
        json={"grant_type": "restore_credential", "assertion": assertion},
    )
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "restore_credential_invalid"


def test_unknown_credential(client, db, user, auth_headers):
    device = _register_device(client, auth_headers)
    # Simulate "credential was revoked elsewhere": drop the stored row.
    db.query(WebAuthnCredential).filter(WebAuthnCredential.user_id == user.id).delete()
    db.commit()

    resp = _assert_device(client, device)
    assert resp.status_code == 401
    # The app treats this as an ordinary signed-out start.
    assert resp.json()["error"]["code"] == "restore_credential_unknown"


def test_sign_count_regression_is_allowed(client, db, user, auth_headers):
    # Restore credentials legitimately assert from cloned backups — a counter
    # regression is logged, never rejected (PLAN.md decision).
    device = _register_device(client, auth_headers)
    db.query(WebAuthnCredential).filter(WebAuthnCredential.user_id == user.id).update(
        {"sign_count": 1000}
    )
    db.commit()

    resp = _assert_device(client, device)
    assert resp.status_code == 200, resp.text


def test_wrong_origin_rejected(client, user, auth_headers):
    device = _register_device(client, auth_headers)
    resp = client.post("/v1/auth/restore/challenge")
    assertion = device.get(
        _request_options_for_device(resp.json()), "https://evil.example"
    )
    resp = client.post(
        "/v1/auth/token",
        json={
            "grant_type": "restore_credential",
            "assertion": _assertion_to_wire(assertion),
        },
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "restore_credential_invalid"


def test_list_and_delete(client, db, user, auth_headers):
    device = _register_device(client, auth_headers)

    resp = client.get("/v1/auth/restore/credentials", headers=auth_headers)
    assert resp.status_code == 200
    creds = resp.json()["credentials"]
    assert len(creds) == 1
    cred_id = creds[0]["credential_id"]
    assert _b64url_decode(cred_id) == device.credential_id

    resp = client.delete(
        f"/v1/auth/restore/credentials/{cred_id}", headers=auth_headers
    )
    assert resp.status_code == 204
    assert (
        client.get("/v1/auth/restore/credentials", headers=auth_headers).json()[
            "credentials"
        ]
        == []
    )
    # Deleting again: gone.
    resp = client.delete(
        f"/v1/auth/restore/credentials/{cred_id}", headers=auth_headers
    )
    assert resp.status_code == 404

    # And the credential no longer signs anyone in.
    resp = _assert_device(client, device)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "restore_credential_unknown"


def test_account_deletion_cascades(client, db, user, auth_headers):
    _register_device(client, auth_headers)
    assert db.query(WebAuthnCredential).count() == 1
    db.delete(db.get(User, user.id))
    db.commit()
    assert db.query(WebAuthnCredential).count() == 0

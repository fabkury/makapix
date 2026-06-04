"""Tests for device-initiated certificate renewal (POST /player/renew-cert).

Authenticated by the device bearer token, so renewal works even after the
client certificate has expired. Mints a fresh cert+key (same player_key) within
the renewal window or past expiry, without revoking the old cert.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Player, User
from app.services import player_tokens

# Reuse the CA-on-disk helper from the deletion test suite.
from tests.test_player_deletion import _make_test_ca


@pytest.fixture
def owner(db: Session) -> User:
    uid = uuid.uuid4().hex[:8]
    user = User(handle=f"owner_{uid}", email=f"owner_{uid}@example.com", roles=["user"])
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_player(db: Session, owner: User, *, expires_at) -> Player:
    p = Player(
        player_key=uuid.uuid4(),
        owner_id=owner.id,
        device_model="TestDevice",
        firmware_version="1.0.0",
        registration_status="registered",
        name="Test Player",
        cert_serial_number="111111",
        cert_expires_at=expires_at,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _ca_env(tmp_path):
    ca_cert_path, ca_key_path, _crl = _make_test_ca(str(tmp_path))
    return {"MQTT_CA_FILE": ca_cert_path, "MQTT_CA_KEY_FILE": ca_key_path}


@pytest.fixture(autouse=True)
def _bypass_rate_limit():
    """These exercise renewal logic, not rate limiting. Keep them independent of
    the shared per-IP renewal counter, which lives in Redis with a TTL that is
    refreshed on every call and so leaks across test runs from a fixed client IP."""
    with patch("app.routers.player.check_rate_limit", return_value=(True, 999)):
        yield


def test_self_renew_requires_token(client: TestClient):
    """No / invalid bearer token is rejected."""
    assert client.post("/player/renew-cert").status_code == 401
    resp = client.post(
        "/player/renew-cert",
        headers={"Authorization": "Bearer mpx_live_does_not_exist"},
    )
    assert resp.status_code == 401


def test_self_renew_when_expired_succeeds(
    client: TestClient, db: Session, owner: User, tmp_path
):
    """A device whose cert already expired can still renew (token, not cert, auths)."""
    past = datetime.now(timezone.utc) - timedelta(days=5)
    player = _make_player(db, owner, expires_at=past)
    token = player_tokens.issue_token(db, player)
    old_serial = player.cert_serial_number

    with patch.dict(os.environ, _ca_env(tmp_path)):
        resp = client.post(
            "/player/renew-cert", headers={"Authorization": f"Bearer {token}"}
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["cert_pem"].startswith("-----BEGIN CERTIFICATE-----")
    assert body["key_pem"].startswith("-----BEGIN PRIVATE KEY-----")
    assert body["ca_pem"].startswith("-----BEGIN CERTIFICATE-----")

    # New cert: CN == player_key, ~3-year validity, chains to the CA.
    leaf = x509.load_pem_x509_certificate(body["cert_pem"].encode())
    cn = leaf.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
    assert cn == str(player.player_key)
    validity_days = (leaf.not_valid_after_utc - leaf.not_valid_before_utc).days
    assert validity_days > 1000  # CERT_VALIDITY_DAYS = 1095

    ca = x509.load_pem_x509_certificate(body["ca_pem"].encode())
    # Signature verification: leaf was signed by the CA key (raises on mismatch).
    ca.public_key().verify(
        leaf.signature,
        leaf.tbs_certificate_bytes,
        padding.PKCS1v15(),
        leaf.signature_hash_algorithm,
    )

    # Serial rotated and expiry pushed out; old serial NOT revoked (no CRL touched).
    db.refresh(player)
    assert player.cert_serial_number != old_serial
    assert player.cert_expires_at > datetime.now(timezone.utc) + timedelta(days=1000)


def test_self_renew_within_window_succeeds(
    client: TestClient, db: Session, owner: User, tmp_path
):
    """Renewal allowed when inside the 90-day window."""
    soon = datetime.now(timezone.utc) + timedelta(days=30)
    player = _make_player(db, owner, expires_at=soon)
    token = player_tokens.issue_token(db, player)
    # Pin the renewal window: CERT_RENEWAL_THRESHOLD_DAYS is read at import time,
    # so patching the env wouldn't take effect and an ambient override (e.g. dev's
    # CERT_RENEWAL_THRESHOLD_DAYS=100000) would otherwise decide these tests.
    with (
        patch.dict(os.environ, _ca_env(tmp_path)),
        patch("app.routers.player.CERT_RENEWAL_THRESHOLD_DAYS", 90),
    ):
        resp = client.post(
            "/player/renew-cert", headers={"Authorization": f"Bearer {token}"}
        )
    assert resp.status_code == 200, resp.text


def test_self_renew_too_early_is_rejected(
    client: TestClient, db: Session, owner: User, tmp_path
):
    """Renewal refused when the cert is comfortably valid (outside the window)."""
    far = datetime.now(timezone.utc) + timedelta(days=200)
    player = _make_player(db, owner, expires_at=far)
    token = player_tokens.issue_token(db, player)
    # Pin the renewal window (see note in test_self_renew_within_window_succeeds):
    # without this, an ambient CERT_RENEWAL_THRESHOLD_DAYS > 200 lets the renewal
    # through and masks this rejection path.
    with (
        patch.dict(os.environ, _ca_env(tmp_path)),
        patch("app.routers.player.CERT_RENEWAL_THRESHOLD_DAYS", 90),
    ):
        resp = client.post(
            "/player/renew-cert", headers={"Authorization": f"Bearer {token}"}
        )
    assert resp.status_code == 400
    assert "still valid" in resp.json()["detail"]


def test_self_renew_no_expiry_succeeds(
    client: TestClient, db: Session, owner: User, tmp_path
):
    """A player without a recorded expiry (no cert yet) can renew."""
    player = _make_player(db, owner, expires_at=None)
    player.cert_serial_number = None
    db.commit()
    token = player_tokens.issue_token(db, player)
    with patch.dict(os.environ, _ca_env(tmp_path)):
        resp = client.post(
            "/player/renew-cert", headers={"Authorization": f"Bearer {token}"}
        )
    assert resp.status_code == 200, resp.text

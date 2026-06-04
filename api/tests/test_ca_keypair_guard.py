"""Guard: refuse to sign player certs when ca.key doesn't match ca.crt.

Regression test for the 2026-06 incident where prod's ``ca.key`` was replaced
with a key that did not correspond to ``ca.crt``, so every newly-issued player
certificate was rejected by the broker at the TLS handshake.
"""

import os
import uuid
from unittest.mock import patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization

from app.mqtt.cert_generator import (
    CAKeypairMismatchError,
    ca_keypair_matches,
    check_ca_keypair,
    generate_client_certificate,
)
from tests.test_player_deletion import _make_test_ca


def _load(ca_cert_path: str, ca_key_path: str):
    with open(ca_cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    with open(ca_key_path, "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)
    return cert, key


def test_matched_pair_signs_ok(tmp_path):
    ca_cert, ca_key, _ = _make_test_ca(str(tmp_path))

    cert, key = _load(ca_cert, ca_key)
    assert ca_keypair_matches(cert, key) is True

    cert_pem, key_pem, serial = generate_client_certificate(
        player_key=uuid.uuid4(),
        ca_cert_path=ca_cert,
        ca_key_path=ca_key,
    )
    assert "BEGIN CERTIFICATE" in cert_pem
    assert "BEGIN PRIVATE KEY" in key_pem
    assert serial

    with patch.dict(os.environ, {"MQTT_CA_FILE": ca_cert, "MQTT_CA_KEY_FILE": ca_key}):
        assert check_ca_keypair() is True


def test_mismatched_pair_refuses_to_sign(tmp_path):
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    dir_b = tmp_path / "b"
    dir_b.mkdir()

    ca_a_cert, _ca_a_key, _ = _make_test_ca(str(dir_a))
    _ca_b_cert, ca_b_key, _ = _make_test_ca(str(dir_b))

    # ca.crt from CA "A" paired with ca.key from CA "B" — the incident's failure.
    cert_a, key_b = _load(ca_a_cert, ca_b_key)
    assert ca_keypair_matches(cert_a, key_b) is False

    with pytest.raises(CAKeypairMismatchError):
        generate_client_certificate(
            player_key=uuid.uuid4(),
            ca_cert_path=ca_a_cert,
            ca_key_path=ca_b_key,
        )

    with patch.dict(
        os.environ, {"MQTT_CA_FILE": ca_a_cert, "MQTT_CA_KEY_FILE": ca_b_key}
    ):
        assert check_ca_keypair() is False

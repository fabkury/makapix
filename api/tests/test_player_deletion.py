"""Test player deletion and certificate revocation."""

import os
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Player, User


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user."""
    user = User(
        handle="testuser",
        email="test@example.com",
        roles=["user"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_player_with_cert(test_user: User, db: Session) -> Player:
    """Create a test player with certificate."""
    player_key = uuid.uuid4()
    player = Player(
        player_key=player_key,
        owner_id=test_user.id,
        device_model="TestDevice",
        firmware_version="1.0.0",
        registration_status="registered",
        name="Test Player",
        cert_serial_number="123456789",
        cert_pem="-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----",
        key_pem="-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


@pytest.mark.parametrize(
    "has_certificate,should_revoke",
    [
        (True, True),  # Player with certificate should have it revoked
        (False, False),  # Player without certificate should skip revocation
    ],
)
def test_player_deletion_revokes_certificate(
    client: TestClient,
    test_user: User,
    test_player_with_cert: Player,
    db: Session,
    has_certificate: bool,
    should_revoke: bool,
):
    """Test that deleting a player revokes its certificate."""
    # Setup player
    player = test_player_with_cert
    if not has_certificate:
        player.cert_serial_number = None
        db.commit()
    
    # Mock authentication
    with patch("app.routers.player.get_current_user", return_value=test_user):
        # Mock certificate revocation
        with patch("app.routers.player.revoke_certificate") as mock_revoke:
            mock_revoke.return_value = True
            
            # Mock mosquitto_passwd
            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.return_value = MagicMock(returncode=0)
                
                # Mock disconnect_mqtt_client
                with patch("app.routers.player.disconnect_mqtt_client") as mock_disconnect:
                    mock_disconnect.return_value = True
                    
                    # Delete the player
                    response = client.delete(
                        f"/u/{test_user.public_sqid}/player/{player.id}"
                    )
                    
                    # Assert response
                    assert response.status_code == 204
                    
                    # Verify player was deleted from database
                    deleted_player = db.query(Player).filter(Player.id == player.id).first()
                    assert deleted_player is None
                    
                    # Verify certificate revocation was called if player had certificate
                    if should_revoke:
                        mock_revoke.assert_called_once()
                        call_args = mock_revoke.call_args
                        assert call_args[1]["serial_number"] == "123456789"
                        assert "ca_cert_path" in call_args[1]
                        assert "ca_key_path" in call_args[1]
                        assert "crl_path" in call_args[1]
                    else:
                        mock_revoke.assert_not_called()
                    
                    # Verify disconnect was called
                    mock_disconnect.assert_called_once_with(player.player_key)
                    
                    # Verify mosquitto_passwd was called to remove password
                    mock_subprocess.assert_called_once()
                    args = mock_subprocess.call_args[0][0]
                    assert "mosquitto_passwd" in args
                    assert "-D" in args


def test_player_deletion_continues_on_revocation_failure(
    client: TestClient,
    test_user: User,
    test_player_with_cert: Player,
    db: Session,
):
    """Test that player deletion continues even if certificate revocation fails."""
    player = test_player_with_cert
    
    # Mock authentication
    with patch("app.routers.player.get_current_user", return_value=test_user):
        # Mock certificate revocation to fail
        with patch("app.routers.player.revoke_certificate") as mock_revoke:
            mock_revoke.return_value = False  # Revocation fails
            
            # Mock mosquitto_passwd
            with patch("subprocess.run") as mock_subprocess:
                mock_subprocess.return_value = MagicMock(returncode=0)
                
                # Mock disconnect_mqtt_client
                with patch("app.routers.player.disconnect_mqtt_client"):
                    # Delete the player - should succeed despite revocation failure
                    response = client.delete(
                        f"/u/{test_user.public_sqid}/player/{player.id}"
                    )
                    
                    # Assert response is still success
                    assert response.status_code == 204
                    
                    # Verify player was deleted from database
                    deleted_player = db.query(Player).filter(Player.id == player.id).first()
                    assert deleted_player is None


def test_certificate_revocation_function():
    """Test the certificate revocation function directly."""
    from app.mqtt.cert_generator import revoke_certificate
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from datetime import datetime, timedelta, timezone
    import tempfile
    
    # Create temporary directory for test files
    with tempfile.TemporaryDirectory() as tmpdir:
        ca_cert_path = os.path.join(tmpdir, "ca.crt")
        ca_key_path = os.path.join(tmpdir, "ca.key")
        crl_path = os.path.join(tmpdir, "crl.pem")
        
        # Generate test CA certificate and key
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test CA"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Test CA"),
        ])
        
        now = datetime.now(timezone.utc)
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=365))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
            .sign(ca_key, hashes.SHA256())
        )
        
        # Write CA cert and key
        with open(ca_cert_path, "wb") as f:
            f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
        
        with open(ca_key_path, "wb") as f:
            f.write(
                ca_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
        
        # Test revoking a certificate
        serial_number = "123456789"
        result = revoke_certificate(
            serial_number=serial_number,
            ca_cert_path=ca_cert_path,
            ca_key_path=ca_key_path,
            crl_path=crl_path,
        )
        
        # Verify revocation succeeded
        assert result is True
        
        # Verify CRL file was created
        assert os.path.exists(crl_path)
        
        # Load and verify CRL
        with open(crl_path, "rb") as f:
            crl = x509.load_pem_x509_crl(f.read())
        
        # Verify the certificate is in the CRL
        revoked_certs = list(crl)
        assert len(revoked_certs) == 1
        assert revoked_certs[0].serial_number == int(serial_number)
        
        # Test revoking the same certificate again (should be idempotent)
        result = revoke_certificate(
            serial_number=serial_number,
            ca_cert_path=ca_cert_path,
            ca_key_path=ca_key_path,
            crl_path=crl_path,
        )
        
        assert result is True
        
        # Verify CRL still has only one entry
        with open(crl_path, "rb") as f:
            crl = x509.load_pem_x509_crl(f.read())
        
        revoked_certs = list(crl)
        assert len(revoked_certs) == 1


def test_crl_initialization():
    """Test CRL initialization function."""
    from app.mqtt.crl_init import initialize_empty_crl
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from datetime import datetime, timedelta, timezone
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        ca_cert_path = os.path.join(tmpdir, "ca.crt")
        ca_key_path = os.path.join(tmpdir, "ca.key")
        crl_path = os.path.join(tmpdir, "crl.pem")
        
        # Generate test CA certificate and key
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test CA"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Test CA"),
        ])
        
        now = datetime.now(timezone.utc)
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=365))
            .add_extension(
                x509.BasicConstraints(ca=True, path_length=None),
                critical=True,
            )
            .sign(ca_key, hashes.SHA256())
        )
        
        # Write CA cert and key
        with open(ca_cert_path, "wb") as f:
            f.write(ca_cert.public_bytes(serialization.Encoding.PEM))
        
        with open(ca_key_path, "wb") as f:
            f.write(
                ca_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
        
        # Initialize empty CRL
        result = initialize_empty_crl(
            ca_cert_path=ca_cert_path,
            ca_key_path=ca_key_path,
            crl_path=crl_path,
        )
        
        # Verify initialization succeeded
        assert result is True
        
        # Verify CRL file was created
        assert os.path.exists(crl_path)
        
        # Load and verify CRL is empty
        with open(crl_path, "rb") as f:
            crl = x509.load_pem_x509_crl(f.read())
        
        revoked_certs = list(crl)
        assert len(revoked_certs) == 0
        
        # Test that calling again returns True (already exists)
        result = initialize_empty_crl(
            ca_cert_path=ca_cert_path,
            ca_key_path=ca_key_path,
            crl_path=crl_path,
        )
        assert result is True

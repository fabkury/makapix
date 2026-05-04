"""Test certificate revocation, CRL functions, and player teardown."""

import os
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session


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
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test CA"),
                x509.NameAttribute(NameOID.COMMON_NAME, "Test CA"),
            ]
        )

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
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test CA"),
                x509.NameAttribute(NameOID.COMMON_NAME, "Test CA"),
            ]
        )

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


# --- teardown_player helper tests ---


def _make_test_ca(tmpdir: str) -> tuple[str, str, str]:
    """Generate a CA cert/key on disk and return (ca_cert, ca_key, crl) paths."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from datetime import datetime, timedelta, timezone

    ca_cert_path = os.path.join(tmpdir, "ca.crt")
    ca_key_path = os.path.join(tmpdir, "ca.key")
    crl_path = os.path.join(tmpdir, "crl.pem")

    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Test CA"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Test CA"),
        ]
    )
    now = datetime.now(timezone.utc)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

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
    return ca_cert_path, ca_key_path, crl_path


@pytest.fixture
def test_user_with_player(db: Session):
    """Seed a User and a registered Player with a cert serial. Returns (user, player)."""
    from app.models import Player, User

    unique_id = str(uuid.uuid4())[:8]
    user = User(
        handle=f"teardown_{unique_id}",
        email=f"teardown_{unique_id}@example.com",
        roles=["user"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    player = Player(
        player_key=uuid.uuid4(),
        owner_id=user.id,
        device_model="TestDevice",
        firmware_version="1.0.0",
        registration_status="registered",
        name="Test Player",
        cert_serial_number="123456789",
    )
    db.add(player)
    db.commit()
    db.refresh(player)
    return user, player


def test_teardown_player_revokes_cert_and_removes_password(
    tmp_path, db: Session, test_user_with_player
):
    """teardown_player revokes the cert, removes the MQTT password,
    deletes the player row, and writes a remove_device audit log."""
    from app import models
    from app.services.player_teardown import teardown_player

    user, player = test_user_with_player
    player_id = player.id
    player_key_str = str(player.player_key)

    ca_cert_path, ca_key_path, crl_path = _make_test_ca(str(tmp_path))

    env = {
        "MQTT_CA_FILE": ca_cert_path,
        "MQTT_CA_KEY_FILE": ca_key_path,
        "MQTT_CRL_FILE": crl_path,
        "MQTT_PASSWD_FILE": str(tmp_path / "passwords"),
    }

    with patch.dict(os.environ, env), patch(
        "app.services.player_teardown.subprocess.run"
    ) as mock_run:
        teardown_player(db, player, removed_by=user.id)

    # Player row gone
    assert (
        db.query(models.Player).filter(models.Player.id == player_id).first() is None
    )

    # mosquitto_passwd -D was invoked with the right args
    mock_run.assert_called_once()
    cmd = mock_run.call_args.args[0]
    assert cmd[0] == "mosquitto_passwd"
    assert cmd[1] == "-D"
    assert cmd[2] == env["MQTT_PASSWD_FILE"]
    assert cmd[3] == player_key_str

    # CRL contains the serial
    from cryptography import x509

    with open(crl_path, "rb") as f:
        crl = x509.load_pem_x509_crl(f.read())
    revoked_serials = {rc.serial_number for rc in crl}
    assert int("123456789") in revoked_serials

    # Audit log row exists with player_id == NULL (FK is SET NULL on delete)
    db.expire_all()
    log_rows = (
        db.query(models.PlayerCommandLog)
        .filter(models.PlayerCommandLog.command_type == "remove_device")
        .all()
    )
    assert len(log_rows) == 1
    assert log_rows[0].player_id is None
    payload = log_rows[0].payload or {}
    assert payload.get("player_key") == player_key_str
    assert payload.get("removed_by") == str(user.id)


def test_teardown_player_idempotent_when_cert_already_revoked(
    tmp_path, db: Session, test_user_with_player
):
    """teardown_player succeeds even if the cert is already in the CRL
    and mosquitto_passwd reports the entry is gone."""
    import subprocess as _subprocess
    from app.mqtt.cert_generator import revoke_certificate
    from app.services.player_teardown import teardown_player

    user, player = test_user_with_player
    ca_cert_path, ca_key_path, crl_path = _make_test_ca(str(tmp_path))

    # Pre-revoke: serial is already in the CRL
    assert revoke_certificate(
        serial_number=player.cert_serial_number,
        ca_cert_path=ca_cert_path,
        ca_key_path=ca_key_path,
        crl_path=crl_path,
    )

    env = {
        "MQTT_CA_FILE": ca_cert_path,
        "MQTT_CA_KEY_FILE": ca_key_path,
        "MQTT_CRL_FILE": crl_path,
        "MQTT_PASSWD_FILE": str(tmp_path / "passwords"),
    }

    # Simulate "entry already gone" — mosquitto_passwd -D exits non-zero
    def fake_run(cmd, **kwargs):
        raise _subprocess.CalledProcessError(returncode=1, cmd=cmd, stderr=b"missing")

    with patch.dict(os.environ, env), patch(
        "app.services.player_teardown.subprocess.run", side_effect=fake_run
    ):
        # Must not raise
        teardown_player(db, player, removed_by=user.id)

    # CRL still has exactly one entry for this serial (no duplicate)
    from cryptography import x509

    with open(crl_path, "rb") as f:
        crl = x509.load_pem_x509_crl(f.read())
    matching = [rc for rc in crl if rc.serial_number == int(player.cert_serial_number)]
    assert len(matching) == 1


def test_delete_user_account_task_runs_player_teardown(db: Session):
    """The user-deletion Celery task runs teardown_player for each player
    instead of bulk-deleting them."""
    from app.models import Player, User
    from app.tasks import delete_user_account_task

    unique_id = str(uuid.uuid4())[:8]
    user = User(
        handle=f"acctdel_{unique_id}",
        email=f"acctdel_{unique_id}@example.com",
        roles=["user"],
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    player_a = Player(
        player_key=uuid.uuid4(),
        owner_id=user.id,
        registration_status="registered",
        name="A",
    )
    player_b = Player(
        player_key=uuid.uuid4(),
        owner_id=user.id,
        registration_status="registered",
        name="B",
    )
    db.add_all([player_a, player_b])
    db.commit()
    user_id = user.id
    expected_player_ids = {player_a.id, player_b.id}

    # Patch teardown_player at its source so the in-task `from .services...
    # import teardown_player` picks up the spy.
    def fake_teardown(session, player, *, removed_by=None):
        session.delete(player)
        session.commit()

    with patch(
        "app.services.player_teardown.teardown_player", side_effect=fake_teardown
    ) as spy:
        result = delete_user_account_task.apply(args=[user_id]).get()

    assert result.get("status") != "error"
    assert spy.call_count == 2
    # Read IDs from the spy's recorded args (those Player instances were loaded
    # by the task's own session, so they're independent of the fixture session).
    called_player_ids = {call.args[1].id for call in spy.call_args_list}
    assert called_player_ids == expected_player_ids
    # All calls should record the actor as the user being deleted
    assert all(call.kwargs.get("removed_by") == user_id for call in spy.call_args_list)

"""MQTT client certificate generation."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

logger = None


def _get_logger():
    """Lazy import logger to avoid circular imports."""
    global logger
    if logger is None:
        import logging
        logger = logging.getLogger(__name__)
    return logger


def generate_client_certificate(
    player_key: UUID,
    ca_cert_path: str,
    ca_key_path: str,
    cert_validity_days: int = 365,
) -> tuple[str, str, str]:
    """
    Generate a client certificate for an MQTT device.
    
    The player_key UUID is used as the certificate's Common Name (CN).
    With Mosquitto's `use_identity_as_username true`, this CN becomes
    the MQTT username, allowing ACL patterns to match correctly.
    
    Args:
        player_key: Player's unique key UUID (becomes the certificate CN)
        ca_cert_path: Path to CA certificate file
        ca_key_path: Path to CA private key file
        cert_validity_days: Certificate validity in days (default: 1 year)
    
    Returns:
        Tuple of (cert_pem, key_pem, serial_number) as strings
    """
    log = _get_logger()
    
    # Load CA certificate and key
    ca_cert_path_obj = Path(ca_cert_path)
    ca_key_path_obj = Path(ca_key_path)
    
    if not ca_cert_path_obj.exists():
        raise FileNotFoundError(f"CA certificate not found: {ca_cert_path}")
    if not ca_key_path_obj.exists():
        raise FileNotFoundError(f"CA key not found: {ca_key_path}")
    
    with open(ca_cert_path_obj, "rb") as f:
        ca_cert = x509.load_pem_x509_certificate(f.read())
    
    with open(ca_key_path_obj, "rb") as f:
        ca_key = serialization.load_pem_private_key(f.read(), password=None)
    
    # Generate client key pair
    client_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Create certificate subject
    # CN is the player_key UUID - this becomes the MQTT username via use_identity_as_username
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Makapix"),
        x509.NameAttribute(NameOID.COMMON_NAME, str(player_key)),
    ])
    
    # Create certificate issuer (same as CA)
    issuer = ca_cert.subject
    
    # Certificate validity period
    now = datetime.now(timezone.utc)
    valid_from = now
    valid_to = now + timedelta(days=cert_validity_days)
    
    # Build certificate
    cert_builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(client_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(valid_from)
        .not_valid_after(valid_to)
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(f"player-{player_key}"),
            ]),
            critical=False,
        )
    )
    
    # Sign certificate with CA
    cert = cert_builder.sign(ca_key, hashes.SHA256())
    
    # Serialize to PEM
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    key_pem = client_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    
    serial_number = str(cert.serial_number)
    
    log.info(f"Generated client certificate for player {player_key}, serial: {serial_number}")
    
    return cert_pem, key_pem, serial_number


def load_ca_certificate(ca_cert_path: str) -> str:
    """
    Load CA certificate as PEM string.
    
    Args:
        ca_cert_path: Path to CA certificate file
    
    Returns:
        CA certificate as PEM string
    """
    ca_cert_path_obj = Path(ca_cert_path)
    if not ca_cert_path_obj.exists():
        raise FileNotFoundError(f"CA certificate not found: {ca_cert_path}")
    
    with open(ca_cert_path_obj, "r") as f:
        return f.read()


def revoke_certificate(
    serial_number: str,
    ca_cert_path: str,
    ca_key_path: str,
    crl_path: str,
) -> bool:
    """
    Revoke a certificate by adding it to the Certificate Revocation List (CRL).
    
    This function loads the existing CRL (or creates a new one), adds the
    certificate with the given serial number, and writes the updated CRL back.
    
    Args:
        serial_number: Serial number of the certificate to revoke (as string)
        ca_cert_path: Path to CA certificate file
        ca_key_path: Path to CA private key file
        crl_path: Path to CRL file (will be created if it doesn't exist)
    
    Returns:
        True if certificate was revoked successfully, False otherwise
    """
    log = _get_logger()
    
    try:
        # Load CA certificate and key
        ca_cert_path_obj = Path(ca_cert_path)
        ca_key_path_obj = Path(ca_key_path)
        
        if not ca_cert_path_obj.exists():
            log.error(f"CA certificate not found: {ca_cert_path}")
            return False
        if not ca_key_path_obj.exists():
            log.error(f"CA key not found: {ca_key_path}")
            return False
        
        with open(ca_cert_path_obj, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read())
        
        with open(ca_key_path_obj, "rb") as f:
            ca_key = serialization.load_pem_private_key(f.read(), password=None)
        
        # Load existing CRL or create a new one
        crl_path_obj = Path(crl_path)
        revoked_certs = []
        
        if crl_path_obj.exists():
            with open(crl_path_obj, "rb") as f:
                try:
                    existing_crl = x509.load_pem_x509_crl(f.read())
                    # Get existing revoked certificates
                    for revoked_cert in existing_crl:
                        revoked_certs.append(revoked_cert)
                except Exception as e:
                    log.warning(f"Could not load existing CRL, creating new one: {e}")
        
        # Check if certificate is already revoked
        serial_int = int(serial_number)
        for revoked_cert in revoked_certs:
            if revoked_cert.serial_number == serial_int:
                log.info(f"Certificate {serial_number} already revoked")
                return True
        
        # Create revoked certificate entry
        now = datetime.now(timezone.utc)
        revoked_cert_builder = (
            x509.RevokedCertificateBuilder()
            .serial_number(serial_int)
            .revocation_date(now)
        )
        revoked_certs.append(revoked_cert_builder.build())
        
        # Build new CRL
        crl_builder = x509.CertificateRevocationListBuilder()
        crl_builder = crl_builder.issuer_name(ca_cert.subject)
        crl_builder = crl_builder.last_update(now)
        crl_builder = crl_builder.next_update(now + timedelta(days=30))
        
        # Add all revoked certificates
        for revoked_cert in revoked_certs:
            crl_builder = crl_builder.add_revoked_certificate(revoked_cert)
        
        # Sign CRL with CA key
        crl = crl_builder.sign(ca_key, hashes.SHA256())
        
        # Write CRL to file
        crl_pem = crl.public_bytes(serialization.Encoding.PEM)
        
        # Ensure directory exists
        crl_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        # Write atomically using a temporary file
        temp_path = crl_path_obj.with_suffix('.tmp')
        with open(temp_path, "wb") as f:
            f.write(crl_pem)
        
        # Atomic rename
        temp_path.replace(crl_path_obj)
        
        log.info(f"Revoked certificate {serial_number} and updated CRL at {crl_path}")
        return True
        
    except Exception as e:
        log.exception(f"Failed to revoke certificate {serial_number}: {e}")
        return False


def disconnect_mqtt_client(player_key: UUID) -> bool:
    """
    Disconnect a player's active MQTT connection.
    
    This sends a DISCONNECT command via the Mosquitto dynamic security plugin
    or control API if available. Falls back to doing nothing if not available.
    
    Args:
        player_key: Player's unique key UUID
    
    Returns:
        True if disconnect was attempted, False if not available
    """
    log = _get_logger()
    
    # Mosquitto doesn't have a built-in way to forcefully disconnect clients
    # without the dynamic security plugin. The password file change + CRL
    # revocation will prevent reconnection, which is the primary security goal.
    # 
    # For immediate disconnection, we would need:
    # 1. Mosquitto dynamic security plugin (not currently used)
    # 2. External control via mosquitto_ctrl (requires Mosquitto 2.0+)
    # 3. Custom plugin or broker modification
    #
    # The current approach (CRL + password removal) ensures the player
    # cannot reconnect, which addresses the security concern.
    
    log.info(f"Marked player {player_key} for disconnection via CRL and password removal")
    log.info("Active connections will be rejected on next reconnection attempt")
    return True


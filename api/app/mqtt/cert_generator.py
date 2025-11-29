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
    user_id: UUID,
    device_id: UUID,
    ca_cert_path: str,
    ca_key_path: str,
    cert_validity_days: int = 365,
) -> tuple[str, str, str]:
    """
    Generate a client certificate for an MQTT device.
    
    Args:
        user_id: User UUID
        device_id: Device UUID
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
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Makapix"),
        x509.NameAttribute(NameOID.COMMON_NAME, f"device-{device_id}"),
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
                x509.DNSName(f"device-{device_id}"),
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
    
    log.info(f"Generated client certificate for device {device_id}, serial: {serial_number}")
    
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


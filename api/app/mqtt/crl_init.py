"""Initialize empty Certificate Revocation List (CRL) for MQTT."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization

logger = logging.getLogger(__name__)


def initialize_empty_crl(
    ca_cert_path: str,
    ca_key_path: str,
    crl_path: str,
    crl_validity_days: int = 30,
) -> bool:
    """
    Initialize an empty Certificate Revocation List (CRL) if it doesn't exist.
    
    This function creates an empty CRL signed by the CA certificate.
    The CRL is required for Mosquitto to start when crlfile is configured.
    
    Args:
        ca_cert_path: Path to CA certificate file
        ca_key_path: Path to CA private key file
        crl_path: Path where CRL should be created
        crl_validity_days: Number of days the CRL is valid (default: 30)
    
    Returns:
        True if CRL was initialized or already exists, False on error
    """
    try:
        crl_path_obj = Path(crl_path)
        
        # Check if CRL already exists
        if crl_path_obj.exists():
            logger.info(f"CRL already exists at {crl_path}")
            return True
        
        # Load CA certificate and key
        ca_cert_path_obj = Path(ca_cert_path)
        ca_key_path_obj = Path(ca_key_path)
        
        if not ca_cert_path_obj.exists():
            logger.error(f"CA certificate not found: {ca_cert_path}")
            return False
        if not ca_key_path_obj.exists():
            logger.error(f"CA key not found: {ca_key_path}")
            return False
        
        with open(ca_cert_path_obj, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read())
        
        with open(ca_key_path_obj, "rb") as f:
            ca_key = serialization.load_pem_private_key(f.read(), password=None)
        
        # Create empty CRL
        now = datetime.now(timezone.utc)
        crl_builder = x509.CertificateRevocationListBuilder()
        crl_builder = crl_builder.issuer_name(ca_cert.subject)
        crl_builder = crl_builder.last_update(now)
        crl_builder = crl_builder.next_update(now + timedelta(days=crl_validity_days))
        
        # Sign CRL with CA key
        crl = crl_builder.sign(ca_key, hashes.SHA256())
        
        # Write CRL to file
        crl_pem = crl.public_bytes(serialization.Encoding.PEM)
        
        # Ensure directory exists
        crl_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        with open(crl_path_obj, "wb") as f:
            f.write(crl_pem)
        
        logger.info(f"Initialized empty CRL at {crl_path}")
        return True
        
    except Exception as e:
        logger.exception(f"Failed to initialize CRL: {e}")
        return False


def ensure_crl_exists() -> bool:
    """
    Ensure CRL file exists, creating it if necessary.
    
    Uses environment variables for configuration:
    - MQTT_CA_FILE: Path to CA certificate (default: /certs/ca.crt)
    - MQTT_CA_KEY_FILE: Path to CA key (default: /certs/ca.key)
    - MQTT_CRL_FILE: Path to CRL (default: /certs/crl.pem)
    
    Returns:
        True if CRL exists or was created successfully, False otherwise
    """
    ca_cert_path = os.getenv("MQTT_CA_FILE", "/certs/ca.crt")
    ca_key_path = os.getenv("MQTT_CA_KEY_FILE", "/certs/ca.key")
    crl_path = os.getenv("MQTT_CRL_FILE", "/certs/crl.pem")
    
    return initialize_empty_crl(ca_cert_path, ca_key_path, crl_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = ensure_crl_exists()
    exit(0 if success else 1)

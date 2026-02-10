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


def ensure_crl_exists(renewal_threshold_days: int = 7) -> bool:
    """
    Ensure CRL file exists and is not expired or near expiry.

    If the CRL file does not exist, creates a new empty one. If it exists but
    is expired or within ``renewal_threshold_days`` of expiry, renews it.
    This runs at API startup so that every deploy produces a fresh CRL
    (the broker restart in the same deploy will pick it up).

    Uses environment variables for configuration:
    - MQTT_CA_FILE: Path to CA certificate (default: /certs/ca.crt)
    - MQTT_CA_KEY_FILE: Path to CA key (default: /certs/ca.key)
    - MQTT_CRL_FILE: Path to CRL (default: /certs/crl.pem)

    Returns:
        True if CRL exists and is valid (or was successfully created/renewed),
        False otherwise.
    """
    ca_cert_path = os.getenv("MQTT_CA_FILE", "/certs/ca.crt")
    ca_key_path = os.getenv("MQTT_CA_KEY_FILE", "/certs/ca.key")
    crl_path = os.getenv("MQTT_CRL_FILE", "/certs/crl.pem")

    crl_path_obj = Path(crl_path)

    if not crl_path_obj.exists():
        return initialize_empty_crl(ca_cert_path, ca_key_path, crl_path)

    # CRL file exists — check if it needs renewal
    expiration = get_crl_expiration(crl_path)
    if expiration is None:
        logger.warning("CRL exists but is unreadable, renewing")
        result = renew_crl(ca_cert_path, ca_key_path, crl_path)
        return result is not None

    now = datetime.now(timezone.utc)
    days_until_expiry = (expiration - now).total_seconds() / 86400

    if days_until_expiry <= renewal_threshold_days:
        logger.info(
            f"CRL expires in {days_until_expiry:.1f} days "
            f"(<= {renewal_threshold_days}), renewing at startup"
        )
        result = renew_crl(ca_cert_path, ca_key_path, crl_path)
        return result is not None

    logger.info(
        f"CRL is valid for {days_until_expiry:.0f} more days, no renewal needed"
    )
    return True


def get_crl_expiration(crl_path: str | None = None) -> datetime | None:
    """
    Get the expiration date (next_update) of the CRL.

    Args:
        crl_path: Path to CRL file (default: from MQTT_CRL_FILE env var)

    Returns:
        The next_update datetime if CRL exists and is valid, None otherwise
    """
    if crl_path is None:
        crl_path = os.getenv("MQTT_CRL_FILE", "/certs/crl.pem")

    try:
        crl_path_obj = Path(crl_path)
        if not crl_path_obj.exists():
            return None

        with open(crl_path_obj, "rb") as f:
            crl = x509.load_pem_x509_crl(f.read())

        return crl.next_update_utc
    except Exception as e:
        logger.warning(f"Failed to read CRL expiration: {e}")
        return None


def renew_crl(
    ca_cert_path: str | None = None,
    ca_key_path: str | None = None,
    crl_path: str | None = None,
    crl_validity_days: int = 30,
) -> datetime | None:
    """
    Renew the CRL by re-signing with fresh timestamps while preserving revoked certificates.

    This function loads the existing CRL, preserves all revoked certificate entries,
    and creates a new CRL with updated last_update and next_update timestamps.

    Args:
        ca_cert_path: Path to CA certificate file (default: from MQTT_CA_FILE env var)
        ca_key_path: Path to CA private key file (default: from MQTT_CA_KEY_FILE env var)
        crl_path: Path to CRL file (default: from MQTT_CRL_FILE env var)
        crl_validity_days: Number of days the renewed CRL is valid (default: 30)

    Returns:
        The new next_update datetime if renewal succeeded, None on error
    """
    # Use environment variables for defaults
    if ca_cert_path is None:
        ca_cert_path = os.getenv("MQTT_CA_FILE", "/certs/ca.crt")
    if ca_key_path is None:
        ca_key_path = os.getenv("MQTT_CA_KEY_FILE", "/certs/ca.key")
    if crl_path is None:
        crl_path = os.getenv("MQTT_CRL_FILE", "/certs/crl.pem")

    try:
        ca_cert_path_obj = Path(ca_cert_path)
        ca_key_path_obj = Path(ca_key_path)
        crl_path_obj = Path(crl_path)

        # Validate paths
        if not ca_cert_path_obj.exists():
            logger.error(f"CA certificate not found: {ca_cert_path}")
            return None
        if not ca_key_path_obj.exists():
            logger.error(f"CA key not found: {ca_key_path}")
            return None

        # Load CA certificate and key
        with open(ca_cert_path_obj, "rb") as f:
            ca_cert = x509.load_pem_x509_certificate(f.read())

        with open(ca_key_path_obj, "rb") as f:
            ca_key = serialization.load_pem_private_key(f.read(), password=None)

        # Load existing CRL to preserve revoked certificates
        revoked_certs = []
        if crl_path_obj.exists():
            try:
                with open(crl_path_obj, "rb") as f:
                    existing_crl = x509.load_pem_x509_crl(f.read())
                # Preserve all revoked certificates
                for revoked_cert in existing_crl:
                    revoked_certs.append(revoked_cert)
                logger.info(
                    f"Preserving {len(revoked_certs)} revoked certificate(s) during CRL renewal"
                )
            except Exception as e:
                logger.warning(f"Could not load existing CRL, creating fresh one: {e}")

        # Build new CRL with fresh timestamps
        now = datetime.now(timezone.utc)
        next_update = now + timedelta(days=crl_validity_days)

        crl_builder = x509.CertificateRevocationListBuilder()
        crl_builder = crl_builder.issuer_name(ca_cert.subject)
        crl_builder = crl_builder.last_update(now)
        crl_builder = crl_builder.next_update(next_update)

        # Add all preserved revoked certificates
        for revoked_cert in revoked_certs:
            crl_builder = crl_builder.add_revoked_certificate(revoked_cert)

        # Sign CRL with CA key
        crl = crl_builder.sign(ca_key, hashes.SHA256())

        # Write CRL atomically using temp file + rename
        crl_pem = crl.public_bytes(serialization.Encoding.PEM)
        temp_path = crl_path_obj.with_suffix(".tmp")

        with open(temp_path, "wb") as f:
            f.write(crl_pem)

        # Atomic rename
        temp_path.replace(crl_path_obj)

        logger.info(f"CRL renewed successfully, valid until {next_update.isoformat()}")
        return next_update

    except Exception as e:
        logger.exception(f"Failed to renew CRL: {e}")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = ensure_crl_exists()
    exit(0 if success else 1)

"""Test certificate revocation and CRL functions."""

import os


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

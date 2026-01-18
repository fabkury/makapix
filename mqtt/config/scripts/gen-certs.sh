#!/usr/bin/env bash
set -euo pipefail

CERT_DIR=${CERT_DIR:-/mosquitto/certs}
mkdir -p "${CERT_DIR}"

CA_KEY="${CERT_DIR}/ca.key"
CA_CRT="${CERT_DIR}/ca.crt"
SRV_KEY="${CERT_DIR}/server.key"
SRV_CSR="${CERT_DIR}/server.csr"
SRV_CRT="${CERT_DIR}/server.crt"

if [[ ! -f "${CA_CRT}" || ! -f "${CA_KEY}" ]]; then
  openssl req -x509 -nodes -days 365 \
    -subj "/CN=Makapix Dev CA" \
    -newkey rsa:4096 \
    -keyout "${CA_KEY}" \
    -out "${CA_CRT}" \
    -sha256
fi

if [[ ! -f "${SRV_CRT}" || ! -f "${SRV_KEY}" ]]; then
  # Create OpenSSL config with SANs for server certificate
  cat > "${CERT_DIR}/server_san.cnf" << 'SANEOF'
[req]
default_bits = 4096
prompt = no
default_md = sha256
distinguished_name = dn
req_extensions = req_ext

[dn]
CN = makapix.club

[req_ext]
subjectAltName = @alt_names

[alt_names]
DNS.1 = makapix.club
DNS.2 = www.makapix.club
DNS.3 = mqtt
DNS.4 = localhost
IP.1 = 127.0.0.1
SANEOF

  openssl genrsa -out "${SRV_KEY}" 4096
  openssl req -new -key "${SRV_KEY}" -out "${SRV_CSR}" -config "${CERT_DIR}/server_san.cnf"
  openssl x509 -req -in "${SRV_CSR}" \
    -CA "${CA_CRT}" -CAkey "${CA_KEY}" -CAcreateserial \
    -out "${SRV_CRT}" -days 365 -sha256 \
    -extfile "${CERT_DIR}/server_san.cnf" -extensions req_ext
  rm -f "${SRV_CSR}" "${CERT_DIR}/server_san.cnf"
fi

chmod 644 "${CERT_DIR}/server.key" "${CERT_DIR}/server.crt" "${CERT_DIR}/ca.crt"
chmod 600 "${CERT_DIR}/ca.key"
chmod 644 "${CERT_DIR}/ca.srl" 2>/dev/null || true

# Generate empty CRL if it doesn't exist
CRL_FILE="${CERT_DIR}/crl.pem"
if [[ ! -f "${CRL_FILE}" ]]; then
  echo "Generating empty Certificate Revocation List (CRL)..."
  
  # Create minimal database files if they don't exist
  touch /tmp/index.txt
  echo 01 > /tmp/crlnumber
  
  # Create empty CRL using openssl
  openssl ca -gencrl -keyfile "${CA_KEY}" -cert "${CA_CRT}" \
    -out "${CRL_FILE}" -config /dev/stdin << 'CRLEOF'
[ ca ]
default_ca = CA_default

[ CA_default ]
database = /tmp/index.txt
crlnumber = /tmp/crlnumber
default_crl_days = 30
default_md = sha256

[ crl_ext ]
authorityKeyIdentifier=keyid:always
CRLEOF
  
  chmod 644 "${CRL_FILE}"
  echo "Empty CRL created at ${CRL_FILE}"
fi

# Generate password file if it doesn't exist
/mosquitto/config/scripts/gen-passwd.sh

exec mosquitto -c /mosquitto/config/mosquitto.conf

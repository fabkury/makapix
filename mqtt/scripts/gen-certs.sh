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
  openssl req -nodes -days 365 \
    -subj "/CN=mqtt" \
    -newkey rsa:4096 \
    -keyout "${SRV_KEY}" \
    -out "${SRV_CSR}" \
    -sha256
  openssl x509 -req -in "${SRV_CSR}" \
    -CA "${CA_CRT}" -CAkey "${CA_KEY}" -CAcreateserial \
    -out "${SRV_CRT}" -days 365 -sha256
  rm -f "${SRV_CSR}"
fi

chmod 644 "${CERT_DIR}/server.key" "${CERT_DIR}/server.crt" "${CERT_DIR}/ca.crt"
chmod 600 "${CERT_DIR}/ca.key"
chmod 644 "${CERT_DIR}/ca.srl" 2>/dev/null || true

exec mosquitto -c /mosquitto/config/mosquitto.conf

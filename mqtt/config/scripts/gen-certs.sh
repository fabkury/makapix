#!/usr/bin/env bash
set -euo pipefail

CERT_DIR=${CERT_DIR:-/mosquitto/certs}
mkdir -p "${CERT_DIR}"

CA_KEY="${CERT_DIR}/ca.key"
CA_CRT="${CERT_DIR}/ca.crt"
SRV_KEY="${CERT_DIR}/server.key"
SRV_CSR="${CERT_DIR}/server.csr"
SRV_CRT="${CERT_DIR}/server.crt"

# CA bootstrap / integrity guard.
#   both present -> verify they are a matched pair (warn loudly if not)
#   neither      -> fresh environment: generate a new CA
#   exactly one  -> REFUSE: regenerating would mint a NEW key and invalidate
#                   every existing player certificate (2026-06 incident guard).
if [[ -f "${CA_CRT}" ]]; then ca_present=1; else ca_present=0; fi
if [[ -f "${CA_KEY}" ]]; then key_present=1; else key_present=0; fi

if [[ "${ca_present}" -eq 1 && "${key_present}" -eq 1 ]]; then
  crt_mod="$(openssl x509 -in "${CA_CRT}" -noout -modulus 2>/dev/null || true)"
  key_mod="$(openssl rsa  -in "${CA_KEY}" -noout -modulus 2>/dev/null || true)"
  if [[ -n "${crt_mod}" && "${crt_mod}" == "${key_mod}" ]]; then
    echo "gen-certs: CA cert/key pair verified (modulus match)."
  else
    echo "===================================================================" >&2
    echo "gen-certs: WARNING - CA cert/key MISMATCH in ${CERT_DIR}" >&2
    echo "  ca.crt and ca.key do NOT share a modulus." >&2
    echo "  The broker still verifies existing players against ca.crt, but the" >&2
    echo "  API will sign NEW player certs that the broker REJECTS." >&2
    echo "  Restore the ca.key that matches ca.crt - do NOT regenerate the CA." >&2
    echo "===================================================================" >&2
  fi
elif [[ "${ca_present}" -eq 0 && "${key_present}" -eq 0 ]]; then
  echo "gen-certs: no CA present - generating a fresh CA (new environment)."
  openssl req -x509 -nodes -days 3650 \
    -subj "/CN=Makapix Dev CA" \
    -newkey rsa:4096 \
    -keyout "${CA_KEY}" \
    -out "${CA_CRT}" \
    -sha256
else
  echo "===================================================================" >&2
  echo "gen-certs: FATAL - exactly one of ca.crt / ca.key exists in ${CERT_DIR}" >&2
  echo "  ca.crt present=${ca_present}  ca.key present=${key_present}" >&2
  echo "  Refusing to regenerate the CA: that would mint a NEW key and" >&2
  echo "  invalidate every existing player certificate." >&2
  echo "  Restore the missing file from backup, then restart." >&2
  echo "===================================================================" >&2
  exit 1
fi

if [[ ! -f "${SRV_CRT}" || ! -f "${SRV_KEY}" ]]; then
  # SAN list for the broker cert. Hostname-verifying clients (mbedTLS on the
  # players) reject a connect hostname absent from the SANs, so the list must
  # cover BOTH environments' public MQTT hostnames (a superset is harmless —
  # the 2026-07-08 dev incident was this cert missing development.makapix.club)
  # plus MQTT_PUBLIC_HOST when the container provides one.
  SAN_DNS=(makapix.club www.makapix.club development.makapix.club mqtt localhost)
  if [[ -n "${MQTT_PUBLIC_HOST:-}" ]]; then
    dup=0
    for d in "${SAN_DNS[@]}"; do [[ "${d}" == "${MQTT_PUBLIC_HOST}" ]] && dup=1; done
    [[ "${dup}" -eq 0 ]] && SAN_DNS+=("${MQTT_PUBLIC_HOST}")
  fi

  # Create OpenSSL config with SANs for server certificate
  {
    cat << 'SANEOF'
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
SANEOF
    i=1
    for d in "${SAN_DNS[@]}"; do
      echo "DNS.${i} = ${d}"
      i=$((i + 1))
    done
    echo "IP.1 = 127.0.0.1"
  } > "${CERT_DIR}/server_san.cnf"

  openssl genrsa -out "${SRV_KEY}" 4096
  openssl req -new -key "${SRV_KEY}" -out "${SRV_CSR}" -config "${CERT_DIR}/server_san.cnf"
  openssl x509 -req -in "${SRV_CSR}" \
    -CA "${CA_CRT}" -CAkey "${CA_KEY}" -CAcreateserial \
    -out "${SRV_CRT}" -days 3650 -sha256 \
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

# Reload the broker whenever the CRL is rewritten (nightly renewal from the
# api container, or a revocation). Backgrounded so mosquitto stays PID 1.
/mosquitto/config/scripts/watch-crl.sh &

exec mosquitto -c /mosquitto/config/mosquitto.conf

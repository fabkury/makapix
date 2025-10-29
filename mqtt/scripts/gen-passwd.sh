#!/usr/bin/env bash
# Generate password file for Mosquitto WebSocket authentication
# This creates a password file for web clients and API server

set -euo pipefail

PASSWD_FILE=${PASSWD_FILE:-/mosquitto/config/passwd}
PASSWD_DIR=$(dirname "${PASSWD_FILE}")
mkdir -p "${PASSWD_DIR}"

# Create password file if it doesn't exist
if [[ ! -f "${PASSWD_FILE}" ]]; then
    # Generate password file with mosquitto_passwd
    # Default password for web clients: webclient
    # Default password for API server: api-server (from env or default)
    mosquitto_passwd -c -b "${PASSWD_FILE}" webclient webclient || true
    mosquitto_passwd -b "${PASSWD_FILE}" api-server "${MQTT_PASSWORD:-api-server}" || true
    
    chmod 600 "${PASSWD_FILE}"
    chown mosquitto:mosquitto "${PASSWD_FILE}" 2>/dev/null || true
    echo "Password file created at ${PASSWD_FILE}"
else
    echo "Password file already exists at ${PASSWD_FILE}"
fi




#!/usr/bin/env bash
# Generate password file for Mosquitto authentication
# Creates password file for backend and player users

set -euo pipefail

PASSWD_FILE=${PASSWD_FILE:-/mosquitto/config/passwords}
PASSWD_DIR=$(dirname "${PASSWD_FILE}")
mkdir -p "${PASSWD_DIR}"

# Generate strong passwords if not provided via environment
BACKEND_PASSWORD=${BACKEND_PASSWORD:-$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)}
PLAYER_PASSWORD=${PLAYER_PASSWORD:-$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)}

# Create password file (create new or update existing)
if [[ ! -f "${PASSWD_FILE}" ]]; then
    # Create new password file
    mosquitto_passwd -c -b "${PASSWD_FILE}" api-server "${BACKEND_PASSWORD}" || true
    echo "Password file created at ${PASSWD_FILE}"
else
    # Update existing users if they don't exist, or create new file if needed
    if ! mosquitto_passwd -b "${PASSWD_FILE}" api-server "${BACKEND_PASSWORD}" 2>/dev/null; then
        # User doesn't exist, add it
        mosquitto_passwd -b "${PASSWD_FILE}" api-server "${BACKEND_PASSWORD}" || true
    fi
    echo "Password file updated at ${PASSWD_FILE}"
fi

chmod 600 "${PASSWD_FILE}"
chown mosquitto:mosquitto "${PASSWD_FILE}" 2>/dev/null || true

# Output passwords for reference (these will be needed for the Python scripts)
echo "Backend password: ${BACKEND_PASSWORD}"
echo "Player password: ${PLAYER_PASSWORD}"




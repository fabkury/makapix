#!/usr/bin/env bash
# watch-crl.sh — SIGHUP Mosquitto whenever the CRL file changes.
#
# Mosquitto loads `crlfile` only at startup / SIGHUP. Two writers rewrite
# crl.pem from OUTSIDE this container via the shared /mosquitto/certs bind
# mount, and neither reaches a long-running broker without a reload:
#   - the nightly renew_crl_if_needed Celery task (api/app/tasks.py), which
#     refreshes the CRL's 30-day validity — without a reload, a broker with
#     >30 days of uptime starts failing EVERY player handshake with
#     CRL_HAS_EXPIRED once its in-memory copy lapses;
#   - cert_generator.revoke_certificate(), whose revocations otherwise take
#     effect only on the next broker restart.
#
# Launched in the background by gen-certs.sh (the container entrypoint), so
# mosquitto itself stays PID 1 and receives the HUP.
#
# NOTE: mqtt/config is bind-mounted over /mosquitto/config at runtime,
# shadowing the copy baked into the image — the HOST copy of this script must
# keep its executable bit.

set -u

CERT_DIR=${CERT_DIR:-/mosquitto/certs}

echo "watch-crl: watching ${CERT_DIR}/crl.pem (SIGHUP to PID 1 on change)"

while true; do
  # Watch the directory, not the file: atomic writers (temp file + rename)
  # would orphan a file-level watch. Filter to crl.pem ourselves — no
  # dependency on inotifywait's --include flag.
  changed="$(inotifywait -q -e close_write -e moved_to -e create \
    --format '%f' "${CERT_DIR}" 2>/dev/null)" || {
    echo "watch-crl: inotifywait exited abnormally; retrying in 10s" >&2
    sleep 10
    continue
  }
  [ "${changed}" = "crl.pem" ] || continue
  # Debounce: coalesce bursts of writes into one reload. Events landing
  # during this window are covered by the HUP that follows (mosquitto reads
  # the file's final state).
  sleep 1
  echo "watch-crl: crl.pem changed — reloading mosquitto (SIGHUP to PID 1)"
  kill -HUP 1
done

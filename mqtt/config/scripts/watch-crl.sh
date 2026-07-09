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
# Detection is belt-and-braces: inotify for sub-second reaction, plus a
# 60-second content-hash poll as a fallback — one cross-container inotify
# event was observed to go missing on dev (2026-07-08), and the nightly-
# refresh path must not depend on perfect event delivery. A missed event
# degrades to a reload within ~60 s instead of a broker that never reloads.
#
# Launched in the background by gen-certs.sh (the container entrypoint), so
# mosquitto itself stays PID 1 and receives the HUP.
#
# NOTE: mqtt/config is bind-mounted over /mosquitto/config at runtime,
# shadowing the copy baked into the image — the HOST copy of this script must
# keep its executable bit.

set -u

CERT_DIR=${CERT_DIR:-/mosquitto/certs}
CRL_FILE="${CERT_DIR}/crl.pem"

crl_sig() { sha256sum "${CRL_FILE}" 2>/dev/null | cut -d' ' -f1; }

last="$(crl_sig)"
echo "watch-crl: watching ${CRL_FILE} (inotify + 60s hash poll; SIGHUP to PID 1 on change)"

while true; do
  # Block on inotify for up to 60 s, then fall through to the hash check.
  # Watch the directory, not the file: atomic writers (temp file + rename)
  # would orphan a file-level watch. Any event on the dir just triggers a
  # cheap hash comparison, so no filename filtering is needed.
  inotifywait -q -t 60 -e close_write -e moved_to -e create \
    "${CERT_DIR}" >/dev/null 2>&1
  rc=$?
  # 0 = event, 2 = timeout (normal poll tick); anything else is an error —
  # keep going, the hash poll still provides coverage.
  if [[ "${rc}" -ne 0 && "${rc}" -ne 2 ]]; then
    echo "watch-crl: inotifywait error (rc=${rc}); polling only" >&2
    sleep 10
  fi
  # Debounce writes-in-progress, then reload only on real content change.
  sleep 1
  cur="$(crl_sig)"
  if [[ "${cur}" != "${last}" ]]; then
    last="${cur}"
    echo "watch-crl: crl.pem changed — reloading mosquitto (SIGHUP to PID 1)"
    kill -HUP 1
  fi
done

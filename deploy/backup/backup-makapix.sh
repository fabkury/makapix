#!/usr/bin/env bash
# Nightly backup of Makapix Club prod assets to Backblaze B2 via restic.
# Design + rationale: docs/backups/PLAN.md §3. Runs as root from
# /etc/cron.d/makapix-backup; credentials in /etc/makapix-backup/env.
set -Eeuo pipefail

source /etc/makapix-backup/env

hc() { curl -fsS -m 10 --retry 3 "${HC_PING_URL}${1:-}" >/dev/null 2>&1 || true; }
trap 'hc /fail' ERR

hc /start

# 1. Database dumps (transaction-consistent); keep newest 7 locally
DUMP_DIR=/var/backups/makapix/db
mkdir -p "$DUMP_DIR"
STAMP=$(date +%Y%m%d)
docker exec makapix-prod-db sh -c 'exec pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' \
  > "$DUMP_DIR/makapix-$STAMP.dump"
docker exec makapix-prod-db sh -c 'exec pg_dumpall --globals-only -U "$POSTGRES_USER"' \
  > "$DUMP_DIR/globals-$STAMP.sql"
ls -1t "$DUMP_DIR"/makapix-*.dump | tail -n +8 | xargs -r rm --
ls -1t "$DUMP_DIR"/globals-*.sql | tail -n +8 | xargs -r rm --

# 2. Offsite snapshot (client-side encrypted, deduplicated)
restic backup \
  --exclude /mnt/vault-1/lost+found \
  /mnt/vault-1 \
  /var/backups/makapix \
  /opt/makapix/mqtt/certs \
  /opt/makapix/deploy/stack/.env \
  /opt/makapix/deploy/stack/.env.prod \
  /opt/makapix-dev/deploy/stack/.env.dev \
  /home/fab/secrets \
  /etc/makapix-backup \
  /etc/cron.d/makapix-backup

# 3. Sundays: retention + integrity check (DECISIONS.md D6)
if [ "$(date +%u)" -eq 7 ]; then
  restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 12 --prune
  restic check --read-data-subset=10%
fi

hc
echo "backup OK $(date -u +%FT%TZ)"

#!/usr/bin/env bash
# Restore drill (docs/backups/PLAN.md gate B4; re-run quarterly).
# Proves the offsite backups actually restore: 3 random artwork files
# byte-compared against the live vault, and the latest DB dump restored
# into a scratch database with row-count sanity checks.
# Usage: sudo bash deploy/backup/restore-drill.sh
set -Eeuo pipefail

[ "$(id -u)" -eq 0 ] || { echo "run as root (sudo)" >&2; exit 1; }
source /etc/makapix-backup/env

WORK=$(mktemp -d /tmp/makapix-drill.XXXXXX)
cleanup() {
  rm -rf "$WORK"
  docker exec makapix-prod-db sh -c 'dropdb --if-exists -U "$POSTGRES_USER" makapix_drill' || true
}
trap cleanup EXIT

FAIL=0

echo "== 1/2 artwork files: restore from B2, byte-compare against live vault =="
mapfile -t FILES < <(find /mnt/vault-1 -type f -not -path '*/lost+found/*' | shuf -n 3)
for f in "${FILES[@]}"; do
  restic restore latest --target "$WORK/vault" --include "$f" >/dev/null
  if cmp -s "$f" "$WORK/vault$f"; then
    echo "  OK        $f"
  else
    echo "  MISMATCH  $f"
    FAIL=1
  fi
done

echo "== 2/2 database: restore latest dump into scratch db makapix_drill =="
DUMP=$(ls -1t /var/backups/makapix/db/makapix-*.dump | head -1)
echo "  dump: $DUMP (restoring the copy stored in B2, not the local file)"
restic restore latest --target "$WORK/db" --include "$DUMP" >/dev/null
docker exec makapix-prod-db sh -c 'dropdb --if-exists -U "$POSTGRES_USER" makapix_drill; createdb -U "$POSTGRES_USER" makapix_drill'
docker exec -i makapix-prod-db sh -c 'pg_restore -U "$POSTGRES_USER" -d makapix_drill --no-owner' < "$WORK/db$DUMP"

echo "  row counts (drill vs live; small drift since the dump is normal):"
for t in users posts comments; do
  d=$(docker exec -e T="$t" makapix-prod-db sh -c 'psql -tA -U "$POSTGRES_USER" -d makapix_drill -c "SELECT count(*) FROM $T;"')
  l=$(docker exec -e T="$t" makapix-prod-db sh -c 'psql -tA -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) FROM $T;"')
  printf "    %-10s drill=%-8s live=%s\n" "$t" "$d" "$l"
  [ "$d" -gt 0 ] || FAIL=1
done

echo
if [ "$FAIL" -eq 0 ]; then
  echo "DRILL PASS $(date -u +%FT%TZ) — record it in docs/backups/PROGRESS.md"
else
  echo "DRILL FAIL — investigate before trusting these backups"
  exit 1
fi

#!/usr/bin/env bash
# One-time installer for the nightly backup job (docs/backups/PLAN.md, gate B3).
# Idempotent — safe to re-run; re-running from a different checkout re-points
# the cron entry at that checkout's backup-makapix.sh (see DECISIONS.md D11).
# Usage: sudo bash deploy/backup/install-backup.sh
set -Eeuo pipefail

[ "$(id -u)" -eq 0 ] || { echo "run as root (sudo)" >&2; exit 1; }

REPO_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
SCRIPT="$REPO_DIR/deploy/backup/backup-makapix.sh"

# 1. Credentials sanity (gate B2b must be closed)
ENV_FILE=/etc/makapix-backup/env
[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE — see PLAN.md gate B2b" >&2; exit 1; }
chmod 600 "$ENV_FILE"
source "$ENV_FILE"
: "${B2_ACCOUNT_ID:?}" "${B2_ACCOUNT_KEY:?}" "${RESTIC_REPOSITORY:?}" \
  "${RESTIC_PASSWORD:?}" "${HC_PING_URL:?}"

# 2. Packages
command -v restic >/dev/null || { apt-get update -qq; apt-get install -y -qq restic; }

# 3. Repository (no-op if already initialized)
restic cat config >/dev/null 2>&1 || restic init

# 4. Root-only wrapper so drills/restores don't need manual env sourcing
cat > /usr/local/sbin/makapix-restic <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
source /etc/makapix-backup/env
exec restic "$@"
EOF
chmod 700 /usr/local/sbin/makapix-restic

# 5. Cron: 10:30 UTC nightly (DECISIONS.md D12); logs to journald
cat > /etc/cron.d/makapix-backup <<EOF
# Nightly Makapix backup — docs/backups/PLAN.md. Managed by install-backup.sh.
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
30 10 * * * root $SCRIPT 2>&1 | logger -t makapix-backup
EOF
chmod 644 /etc/cron.d/makapix-backup
chmod 755 "$SCRIPT"
echo "Install OK — cron entry: $(grep -v '^#' /etc/cron.d/makapix-backup | tail -1)"

# 6. First backup, then show the result
"$SCRIPT"
restic snapshots --compact

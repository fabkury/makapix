# Nightly backup job

Full design, decisions, and progress: **`docs/backups/`** (read PLAN.md
before changing anything here).

- `backup-makapix.sh` — the nightly job (10:30 UTC via
  `/etc/cron.d/makapix-backup`, as root). DB dump → restic → Backblaze B2,
  healthchecks.io pings, Sunday retention + integrity check.
- `install-backup.sh` — idempotent installer: packages, repo init,
  `makapix-restic` wrapper, cron entry, first backup. Re-run it from
  `/opt/makapix` after this directory reaches `main` so the cron path points
  at the prod checkout (DECISIONS.md D11).

Credentials live in `/etc/makapix-backup/env` (root:root 0600, untracked);
bootstrap copies are in the owner's password manager.

Operations:

```bash
sudo makapix-restic snapshots            # list snapshots
sudo makapix-restic restore latest --target /tmp/r --include <path>
journalctl -t makapix-backup             # job logs
```

Restore runbook: `docs/backups/RESTORE.md`.

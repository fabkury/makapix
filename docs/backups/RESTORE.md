# Restore Runbook — Backups

Status: written 2026-07-04 alongside gate B3; verified by the B4 drill (see
PROGRESS.md for drill dates). Re-verify quarterly with
`sudo bash deploy/backup/restore-drill.sh`.

## Prerequisites

Everything below needs the restic repository credentials. On the live
server they are already at `/etc/makapix-backup/env` and wrapped by
`sudo makapix-restic <cmd>`. **If the server is gone**, recreate that env
file from the password manager (restic password + B2 app key are both
there; the B2 master account can mint a new app key).

Useful commands:

```bash
sudo makapix-restic snapshots                 # list snapshots
sudo makapix-restic ls latest | less          # browse a snapshot
```

## A. Single artwork file (accidental deletion/corruption)

```bash
sudo makapix-restic restore latest --target /tmp/r \
  --include /mnt/vault-1/<a>/<b>/<artwork_id>.<ext>
sudo cp -a /tmp/r/mnt/vault-1/<a>/<b>/<file> /mnt/vault-1/<a>/<b>/<file>
```

Get the shard path from `posts.storage_shard` (opaque relative path — never
derive it; see CLAUDE.md vault section). Older snapshots: replace `latest`
with a snapshot ID from `snapshots`.

## B. Database restore

Dumps are `pg_dump -Fc` files, both local (`/var/backups/makapix/db/`,
newest 7) and inside every restic snapshot. Prefer the local copy when the
server is alive.

```bash
# 1. Stop writers
cd /opt/makapix && make down   # or: docker stop makapix-prod-api makapix-prod-worker

# 2. Restore into a fresh db, then swap (never pg_restore over the live db)
docker start makapix-prod-db
docker exec makapix-prod-db sh -c 'createdb -U "$POSTGRES_USER" makapix_restored'
docker exec -i makapix-prod-db sh -c 'pg_restore -U "$POSTGRES_USER" -d makapix_restored --no-owner' \
  < /var/backups/makapix/db/makapix-<date>.dump
docker exec makapix-prod-db sh -c 'psql -U "$POSTGRES_USER" -d postgres -c \
  "ALTER DATABASE makapix RENAME TO makapix_broken; ALTER DATABASE makapix_restored RENAME TO makapix;"'

# 3. Restart and verify, keep makapix_broken until confident, then drop it
make up
```

If the Postgres instance itself was rebuilt from scratch, restore roles
first: `psql -U "$POSTGRES_USER" -d postgres -f globals-<date>.sql`.

## C. Total server loss

1. New Ubuntu VPS (or restore the Hetzner VM image for a head start —
   remember it does NOT contain the vault). Attach a fresh volume, mount at
   `/mnt/vault-1`.
2. Install Docker + compose; clone `github.com/fabkury/makapix` to
   `/opt/makapix` (branch `main`).
3. From the password manager: recreate `/etc/makapix-backup/env`
   (root:root 0600) and restore the secrets bundle if needed.
4. `apt install restic`, then pull everything back:
   ```bash
   source /etc/makapix-backup/env
   restic restore latest --target /
   ```
   That lands the vault, `.env` files, MQTT certs, `~/secrets`, DB dumps,
   and the backup config in their original absolute paths.
5. `cd /opt/makapix && make up`, then restore the DB per section B
   (globals first — fresh instance).
6. Re-point DNS A records (makapix.club, vault.makapix.club, etc.) at the
   new IP; Caddy re-issues TLS automatically.
7. Reinstall the backup job: `sudo bash deploy/backup/install-backup.sh`.

## D. Backups themselves were deleted (compromised server)

The B2 bucket keeps hidden file versions for 30 days (lifecycle rule). From
a CLEAN machine, log into the B2 **master** account (password manager),
browse bucket `makapix-backups` → "Show hidden files" → unhide, or use
`b2 ls --versions` / `b2 undelete` via the CLI. Then rotate: new app key,
new server credentials, treat the old key as burned.

## Known caveat

DB dump and vault scan run seconds apart, so a snapshot can contain an
artwork row without its file (or vice versa) for content uploaded mid-backup.
After a full restore, expect at most a handful of dangling references from
that window — same class of skew as any live-system file backup (PLAN.md §7).

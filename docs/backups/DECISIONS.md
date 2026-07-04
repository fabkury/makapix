# Decisions — Backups

Owner decisions (D1–D4) were made by fab on 2026-07-04 after reviewing the
options comparison. Architectural decisions (D5–D12) follow from them.

## Owner decisions

**D1 — Offsite target: Backblaze B2.**
Different provider than the VPS (true 3-2-1: a Hetzner account compromise or
billing failure cannot take out server and backups together). First 10 GB
free, then $6/TB/mo → ≈$0/mo at the current ~2.5 GB. Rejected: Hetzner
Storage Box (€3.20/mo, same-account basket risk, 100× the cost at this size);
Cloudflare R2 (equivalent, but B2 has better backup ergonomics: per-bucket
application keys, mature hide-then-delete lifecycle semantics that fit
restic); dual targets (overkill at 2.5 GB — revisit trigger in PLAN.md §8).

**D2 — Hetzner server backup add-on: enabled.**
~20% of the server plan (~€1/mo) for 7 daily rotating whole-VM images with
one-click restore. Convenience layer for "server is broken" recovery — OS,
Docker, Postgres volume, configs. **Does not include attached volumes**
(confirmed: https://docs.hetzner.com/cloud/servers/backups-snapshots/overview/),
so the vault is NOT in these images. Never a substitute for D1.

**D3 — RPO: up to 24 h (nightly).**
One nightly job. Worst case loses one day of posts/comments/uploads —
acceptable at current traffic. Tightening to hourly DB dumps is a small,
documented change if traffic grows (PLAN.md §8).

**D4 — Scope: prod + secrets only.**
Prod vault, prod DB, MQTT CA/certs, `.env` files, `~/secrets`. Dev DB and dev
vault are clones of prod → recreatable → excluded. Adding `/mnt/vault-dev`
later is one line and near-free thanks to restic dedup.

## Architectural decisions

**D5 — Tool: restic, native `b2:` backend.**
Client-side encryption, dedup, incremental snapshots, first-class retention
(`forget --prune`), single static binary from Ubuntu repos. Borg rejected
(no native B2/object-storage backend); plain rclone sync rejected (no
point-in-time snapshots; a bad sync propagates deletions).

**D6 — Retention: 7 daily, 4 weekly, 12 monthly.**
`restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 12`, prune
weekly (Sunday), `restic check --read-data-subset=10%` weekly. Local pg_dump
copies: keep 7 (free instant restore for oops-level mistakes).

**D7 — Anti-self-deletion: B2 lifecycle + master creds off-server.**
The server holds only an application key scoped to the backup bucket. The
bucket keeps hidden (deleted/overwritten) file versions for 30 days
(lifecycle rule), so even if a compromised server deletes the repo, it is
recoverable from the master account — whose credentials never touch the
server.

**D8 — Bootstrap: password manager.**
The restic repo password and a one-time bundle of the tiny irreplaceable
secrets (MQTT `ca.key`/`ca.crt`, `.env.prod`, `.env.dev`, Firebase service
account JSON) live in the owner's password manager. This breaks the
circularity of "the backup config is itself only in the backup".

**D9 — Monitoring: healthchecks.io (free tier).**
The nightly job pings start + success/fail; a missed night emails the owner.
Silent failure is the #1 real-world backup killer.

**D10 — Script lives in the repo; secrets live in `/etc`.**
`deploy/backup/backup-makapix.sh` is tracked (infra as code, no secrets in
it). Runtime config/credentials in `/etc/makapix-backup/env` (root:root,
0600, untracked). Cron entry at `/etc/cron.d/makapix-backup` runs the script
as root (needs vault read + `docker exec`).

**D11 — Cron path: prod checkout after merge.**
Long-term the cron entry calls
`/opt/makapix/deploy/backup/backup-makapix.sh` so `make deploy` keeps it
updated. Until develop→main merges, it may temporarily point at the
`/opt/makapix-dev` copy — backing up PROD data from a dev-checkout script is
fine; the script has no environment-specific logic (targets are absolute
prod paths).

**D12 — Schedule: 10:30 UTC nightly.**
= 06:30 ET summer / 05:30 ET winter — always after the Celery rollup/cleanup
window (01:00–05:00 ET). `pg_dump` is transaction-consistent regardless;
running after the window just keeps daily rollups and their cleanups inside
the same snapshot.

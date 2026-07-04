# Progress Log — Backups

**Current phase: B3 nearly closed (first manual run green 2026-07-04),
B4 drill pending.**
**Next action: (a) fab runs `sudo bash deploy/backup/restore-drill.sh` →
closes B4 on PASS; (b) confirm tomorrow's 10:30 UTC cron run pings
healthchecks.io green → fully closes B3; (c) after develop→main merge,
re-run `sudo bash /opt/makapix/deploy/backup/install-backup.sh` from the
prod checkout to re-point cron (D11).**

Newest entries first in the log; the gate table mirrors PLAN.md §5.
Update this file at the end of every working session on this effort.

## Gate status

| Gate | Description | Status |
|---|---|---|
| B0 | Decisions D1–D12 recorded | ✅ 2026-07-04 |
| B1 | Secrets bundle + restic password in password manager | ✅ 2026-07-04 |
| B2a | B2 account, `makapix-backups` bucket (EU), 30-day lifecycle, scoped app key | ✅ 2026-07-04 |
| B2b | Credentials landed in `/etc/makapix-backup/env` (root:root 0600) | ✅ 2026-07-04 |
| B2c | Hetzner server backup add-on enabled | ✅ 2026-07-04 |
| B2d | healthchecks.io check created, ping URL in env file | ✅ 2026-07-04 |
| B3 | restic repo init; script + cron installed; first nightly run green end-to-end incl. healthcheck ping | ◐ first manual run green 2026-07-04; awaiting first unattended cron run (10:30 UTC) + hc green |
| B4 | Restore drill passed (artwork byte-compare + DB into scratch); RESTORE.md written | ◐ runbook + drill script written; drill run pending |
| B5 | Privacy page updated & deployed; quarterly drill reminder; first-month B2 spend ≈ $0 confirmed | ☐ |

## Log

### 2026-07-04 (later) — Implementation session (Claude + fab)

- fab closed B1 + B2: secrets bundle + restic password in password manager;
  B2 bucket `makapix-backups` (EU, 30-day hidden-version lifecycle, scoped
  app key); Hetzner backup add-on enabled; healthchecks.io check created;
  creds landed in `/etc/makapix-backup/env`.
- Wrote `deploy/backup/`: `backup-makapix.sh` (nightly job),
  `install-backup.sh` (idempotent installer), `restore-drill.sh` (B4 +
  quarterly), plus `docs/backups/RESTORE.md` runbook.
- Installer ran clean: restic 0.16.4 from apt; repo `f9c79259` initialized
  at `b2:makapix-backups:restic`; cron at `/etc/cron.d/makapix-backup`
  (10:30 UTC → journald tag `makapix-backup`); root-only wrapper
  `/usr/local/sbin/makapix-restic`.
- **First backup: snapshot `b9b5c5cd`** — 22,748 files, 1.902 GiB processed
  in 21 s; dedup collapsed the resharding twin copies to ~1 GiB unique,
  compression stored **710 MiB** in B2 (well inside the 10 GB free tier).
- Cron currently points at the `/opt/makapix-dev` checkout (D11 interim) —
  re-run the installer from `/opt/makapix` after the develop→main merge.
- Host observations (not backup-related, for the record): Caddy apt repo
  GPG key expired (EXPKEYSIG on apt update; harmless — Caddy runs from a
  Docker image, the host package repo is vestigial); pending kernel
  6.8.0-117 → -134, reboot at leisure (a reboot restarts the MQTT broker —
  see the broker-restart/publisher gotcha in memory).

### 2026-07-04 — Planning session (Claude + fab)

- Confirmed **zero automated backups**: no user/root crontabs, no backup
  systemd timers, no Hetzner backup add-on. Found ad-hoc manual DB dumps in
  `/opt/makapix/backups/` and `/opt/makapix/db_backup/` (untracked) from
  past migrations — newest is 2026-02-04, five months stale. The vault has
  never been backed up at all.
- Un-ignored `docs/backups/` in `.gitignore` (the broad `backups/` rule —
  which protects those runtime dump dirs — was swallowing this docs folder).
- Measured the estate: prod vault 2.0 GB / ~23k files on `/mnt/vault-1`
  (Hetzner attached volume), prod DB 90 MB, dev clones ~1.8 GB / 36 MB.
  Full inventory in PLAN.md §1.
- Verified in Hetzner docs that server Backups/Snapshots **exclude attached
  volumes** → the provider add-on alone would miss the vault entirely.
  This shaped the three-layer architecture.
- Owner decisions D1–D4 captured (offsite = Backblaze B2; Hetzner add-on =
  yes; RPO = 24 h nightly; scope = prod + secrets). Architectural D5–D12
  recorded in DECISIONS.md.
- Wrote README/PLAN/DECISIONS/PROGRESS; committed to `develop`.
- Owner next steps handed off (B1/B2): password-manager bundle; B2 signup
  (EU region) + private bucket `makapix-backups` + "keep prior versions
  30 days" lifecycle + bucket-scoped app key; enable Hetzner backup add-on
  (Cloud Console → server → Backups); create healthchecks.io check; place
  creds in `/etc/makapix-backup/env`.

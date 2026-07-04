# Progress Log — Backups

**Current phase: B1 + B2 (owner provisioning) — plan committed, waiting on
owner actions.**
**Next action (fab): store the secrets bundle + a freshly generated restic
password in the password manager (B1); create the B2 account/bucket/key,
enable the Hetzner backup add-on, create the healthchecks.io check (B2).
Exact click-path steps were given in the 2026-07-04 session; also summarized
below in the log entry.**

Newest entries first in the log; the gate table mirrors PLAN.md §5.
Update this file at the end of every working session on this effort.

## Gate status

| Gate | Description | Status |
|---|---|---|
| B0 | Decisions D1–D12 recorded | ✅ 2026-07-04 |
| B1 | Secrets bundle + restic password in password manager | ☐ (fab) |
| B2a | B2 account, `makapix-backups` bucket (EU), 30-day lifecycle, scoped app key | ☐ (fab) |
| B2b | Credentials landed in `/etc/makapix-backup/env` (root:root 0600) | ☐ (fab) |
| B2c | Hetzner server backup add-on enabled | ☐ (fab) |
| B2d | healthchecks.io check created, ping URL in env file | ☐ (fab) |
| B3 | restic repo init; script + cron installed; first nightly run green end-to-end incl. healthcheck ping | ☐ |
| B4 | Restore drill passed (artwork sha256 match + DB into scratch); RESTORE.md written | ☐ |
| B5 | Privacy page updated & deployed; quarterly drill reminder; first-month B2 spend ≈ $0 confirmed | ☐ |

## Log

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

# Progress Log — Backups

**Current phase: B4 CLOSED (drill PASS 2026-07-04); B3 closes after the
first unattended cron run; B5 (steady state) in progress.**
**All active work done (2026-07-04). Remaining items are passive:
(a) confirm the 2026-07-05 10:30 UTC cron run pinged healthchecks.io green
→ fully closes B3 (healthchecks emails on failure, so silence = success);
(b) B5 leftovers: quarterly restore drill (next ~2026-10-04,
`sudo bash deploy/backup/restore-drill.sh`) and first-month B2 spend check
(~2026-08-04). Privacy disclosure is LIVE on makapix.club/privacy; cron
runs from the prod checkout (D11 closed).**

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
| B3 | restic repo init; script + cron installed; first nightly run green end-to-end incl. healthcheck ping | ◐ manual run green + hc ping confirmed green by fab 2026-07-04; awaiting first unattended cron run 2026-07-05 10:30 UTC |
| B4 | Restore drill passed (artwork byte-compare + DB into scratch); RESTORE.md written | ✅ 2026-07-04 DRILL PASS |
| B5 | Privacy page updated & deployed; quarterly drill reminder; first-month B2 spend ≈ $0 confirmed | ◐ privacy line written on develop 2026-07-04 (deploys with next merge); drill due ~2026-10-04; spend check ~2026-08-04 |

## Log

### 2026-07-04 (evening) — Prod deploy + D11 closed (Claude + fab)

- PR #213 (develop→main) merged; `make deploy` on prod clean; site 200,
  MQTT publisher healthy post-restart, privacy disclosure live.
- fab re-ran the installer from `/opt/makapix` → cron re-pointed at the
  prod checkout (**D11 closed**). Second snapshot `6319b338`: 9 changed
  files, 2.327 MiB added in 3 s — nominal incremental behavior.

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
- **Restore drill PASS (2026-07-04T20:56:58Z, closes B4):** 3 random
  artwork files restored from B2 byte-identical (spanning both legacy
  3-level and v2 2-level shard paths — twin copies verified); latest DB
  dump (B2 copy) restored into scratch `makapix_drill`; row counts matched
  live exactly (users 101, posts 2894, comments 19). fab confirmed
  healthchecks.io green. Next quarterly drill due ~2026-10-04.
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

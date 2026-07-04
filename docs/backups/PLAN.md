# Plan — Backups for Makapix Club

Status lives in `PROGRESS.md`; decisions and rationale in `DECISIONS.md`.

## 1. Asset inventory (measured 2026-07-04)

| Asset | Size | Lives at | If lost |
|---|---|---|---|
| Prod vault (artwork + `.mkpx` sources) | 2.0 GB, ~23k files | `/mnt/vault-1` (Hetzner volume `/dev/sdc`) | Irreplaceable user content, gone forever |
| Prod Postgres `makapix` | 90 MB | Docker volume `makapix_pg_data` (root disk) | All users, posts, comments, players |
| MQTT CA key + server certs | few KB | `/opt/makapix/mqtt/certs/` | Every physical player re-provisioned by hand |
| `.env.prod` / `.env` / `.env.dev` | few KB | `deploy/stack/` in both checkouts | JWT/OAuth secrets; painful reconstruction |
| Firebase service account | 2.4 KB | `/home/fab/secrets/makapix/` | Re-issuable from Firebase console |
| Code | — | GitHub (`fabkury/makapix`) | Already offsite ✓ |

Excluded by decision D4: dev vault (1.8 GB), dev DB (36 MB) — clones of prod.
Excluded as recreatable: Docker images, Caddy TLS certs (auto re-issued),
OS packages.

Total unique data ≈ 2.5 GB; slow growth (pixel art averages ~90 KB/file).

## 2. Architecture (three layers)

```
Layer 1  restic → Backblaze B2          nightly, encrypted, versioned   ≈ $0/mo
         (vault + DB dump + certs + env + secrets)                      THE backup
Layer 2  Hetzner server backup add-on   7 daily whole-VM images         ≈ €1/mo
         (root disk only — NOT the vault volumes)                       fast restore
Layer 3  Password manager               one-time secrets bundle +       $0
         restic repo password                                           bootstrap
```

Coverage map — every asset must be green in at least one layer that
survives total server loss:

| Asset | L1 restic→B2 | L2 VM images | L3 pwd manager |
|---|---|---|---|
| Prod vault | ✅ | ❌ (attached volume) | — |
| Prod DB | ✅ (pg_dump) | ✅ (crash-consistent) | — |
| MQTT CA/certs | ✅ | ✅ | ✅ |
| `.env` files | ✅ | ✅ | ✅ |
| Firebase JSON | ✅ | ✅ (`/home` is on the root disk) | ✅ |
| restic repo password | ❌ (circular) | ✅ (in `/etc`) | ✅ ← canonical |

## 3. The nightly job (Layer 1 mechanics)

Runs as root from `/etc/cron.d/makapix-backup` at **10:30 UTC** (D12).
Script: `deploy/backup/backup-makapix.sh` (tracked; secrets sourced from
`/etc/makapix-backup/env`, root:root 0600).

1. `curl $HC_PING_URL/start`
2. `docker exec makapix-prod-db pg_dump -Fc -U $POSTGRES_USER makapix`
   → `/var/backups/makapix/db/makapix-YYYYMMDD.dump`; also
   `pg_dumpall --globals-only` → `globals-YYYYMMDD.sql`; keep newest 7 of each.
3. `restic backup` of:
   - `/mnt/vault-1` (exclude `lost+found`)
   - `/var/backups/makapix/`
   - `/opt/makapix/mqtt/certs/`
   - `/opt/makapix/deploy/stack/.env*` and `/opt/makapix-dev/deploy/stack/.env*`
   - `/home/fab/secrets/`
   - `/etc/makapix-backup/` and `/etc/cron.d/makapix-backup` (self-describing
     restore; bootstrap secret still canonical in L3)
4. Sundays only: `restic forget --keep-daily 7 --keep-weekly 4
   --keep-monthly 12 --prune`, then `restic check --read-data-subset=10%`.
5. `curl $HC_PING_URL` on success, `$HC_PING_URL/fail` on any error
   (script runs with `set -euo pipefail` + trap).

Repository: `b2:makapix-backups:restic` (native restic B2 backend; bucket in
B2 EU region — closest to hel1).

## 4. B2 bucket contract

- Bucket `makapix-backups`, **private**, EU region (chosen at account signup).
- Lifecycle rule: **keep prior versions for 30 days** ("hide → delete after
  30 days"). This is the anti-ransomware layer (D7).
- Application key **scoped to this bucket only**, read/write/delete (delete
  is needed by `prune`; the lifecycle rule makes deletions recoverable).
- Master account credentials: password manager only, never on the server.

## 5. Phases & gates

| Phase | Owner of work | Gate to close |
|---|---|---|
| **B0 — Decisions** | fab + Claude | D1–D12 recorded ✅ 2026-07-04 |
| **B1 — Secrets off-server** | fab | Bundle (ca.key/crt, .env.prod, .env.dev, Firebase JSON) + restic password stored in password manager |
| **B2 — Provisioning** | fab | (a) B2 account + bucket + lifecycle + scoped key; (b) creds landed in `/etc/makapix-backup/env`; (c) Hetzner backup add-on enabled; (d) healthchecks.io check created |
| **B3 — Automation live** | Claude (root cmds via fab) | restic repo initialized; script + cron installed; first nightly run succeeded end-to-end **and** healthchecks.io received the ping |
| **B4 — Restore proven** | Claude + fab | Drill passed: (a) random artwork file restored, byte-identical (sha256); (b) DB dump restored into a scratch database, row counts sane; `RESTORE.md` runbook written |
| **B5 — Steady state** | fab + Claude | Privacy page mentions backups (one honest line + effective-date bump, via normal develop→main deploy); quarterly restore-drill reminder exists; first month of B2 spend confirmed ≈ $0 |

No phase starts before the previous phase's gate closes, except B1 and B2
which can proceed in parallel.

## 6. Costs

| Item | Cost |
|---|---|
| Backblaze B2 (≈2.5 GB, versioned) | $0 now (≤10 GB free tier); $6/TB/mo beyond → ~$0.30/mo at 50 GB |
| Hetzner backup add-on | ~20% of server plan ≈ €1/mo |
| healthchecks.io | Free tier |
| restic | Free (Ubuntu repos) |
| **Total** | **≈ €1/month** |

## 7. Risk register

| Risk | Mitigation |
|---|---|
| Silent backup failure | healthchecks.io start/success/fail pings; missed night → email |
| restic repo password lost | Canonical copy in password manager (B1 gate); never only on server |
| Compromised server deletes B2 repo | 30-day hidden-version lifecycle + master creds off-server → recoverable from a clean machine |
| B2 account lost/suspended | Accepted residual risk at this size; L2 still covers DB/config (not vault). Revisit trigger in §8 adds a second target |
| Backups restore-rotted (never tested) | B4 gate before declaring victory; quarterly drills after |
| Git checkout breaks cron script path | Cron uses absolute path into `/opt/makapix` (updated only by `make deploy`); script is self-contained, no repo imports |
| Deleted user data lingers in backups | Retention bounds it (~13 months max via monthly snapshots); privacy page discloses (B5). Acceptable for a 13+ plain-English policy |
| pg_dump vs vault skew (backup captures DB and files at slightly different instants) | Dump runs seconds before vault scan; worst case an artwork row without its file or vice versa — same class of skew as any live-system file backup; noted in RESTORE.md |

## 8. Revisit triggers

- **Vault > 50 GB** → reconsider Hetzner Storage Box (flat €3.20/mo beats
  per-GB) or add it as a second target.
- **Traffic makes 24 h loss unacceptable** → add hourly `pg_dump` +
  `restic backup` of the dump dir only (D3 note).
- **Dev gets unique content** → add `/mnt/vault-dev` + dev DB dump to §3
  (one line each; dedup makes the vault addition near-free).
- **Second irreplaceable secret appears** → add to §3 list AND to the L3
  bundle.

## 9. Explicit non-goals

- No continuous replication / point-in-time WAL archiving (overkill at this
  scale; D3).
- No backup of dev environment (D4), Docker images, or Caddy TLS material.
- No GUI/managed backup service — one auditable shell script.

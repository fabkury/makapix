# Backups — Makapix Club

Effort started 2026-07-04. Goal: get every irreplaceable MPX asset covered by
automated, tested, offsite backups. Before this effort, **nothing** was backed
up (no cron, no timers, no provider backups).

**Read `PLAN.md` before doing any backup-related work. Update `PROGRESS.md`
at the end of every working session on this effort.**

## Files

| File | Purpose |
|---|---|
| `PLAN.md` | The complete plan: inventory, architecture, phases, costs, risks |
| `DECISIONS.md` | Owner + architectural decisions (D1–D12), with rationale |
| `PROGRESS.md` | Gate status + session log (newest first) |
| `RESTORE.md` | Restore runbook — written in Phase 4, kept current after |

## One-paragraph summary

Nightly `restic` backup of the prod vault, a fresh `pg_dump` of the prod
database, MQTT CA material, `.env` files, and `~/secrets` to a Backblaze B2
bucket (different provider than the VPS; client-side encrypted; ~$0/mo at
current size). Hetzner's server backup add-on (~€1/mo) adds 7 daily whole-VM
images for fast full-server restore — note it does **not** cover the vault
volumes. A one-time copy of the tiny irreplaceable secrets lives in the
owner's password manager, which also bootstraps the restic repo password.
Success is pinged to healthchecks.io so silent failure alerts by email.
Quarterly restore drills keep the backups honest.

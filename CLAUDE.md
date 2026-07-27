# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environments

This repo is checked out twice on the VPS — once for production, once for development — driven by per-environment compose overlays (`docker-compose.prod.yml`, `docker-compose.dev.yml`):

| | Production | Development |
|---|---|---|
| Directory | `/opt/makapix` | `/opt/makapix-dev` |
| Branch | `main` | `develop` |
| URL | https://makapix.club | https://development.makapix.club |
| Compose project | `makapix-prod` | `makapix-dev` |
| Container names | `makapix-prod-*` | `makapix-dev-*` |
| Database volume | `pg_data_prod` | `pg_data_dev` |
| Database host port | 5432 (loopback) | 5433 (loopback) |
| Vault | `/mnt/vault-1` | `/mnt/vault-dev` |
| Vault subdomain | `vault.makapix.club` | `vault-dev.makapix.club` |
| MQTT host ports | 1883 (plain), 8883 (mTLS) | 1884 (plain), 8884 (mTLS) |

> Develop new features in `/opt/makapix-dev` on `develop`, test at development.makapix.club, then PR `develop` → `main` and deploy to prod — full steps (including the pre-merge gate) in Deployment Workflow below.

## Project Overview

Makapix Club (MPX) is a lightweight pixel art social network designed to run on a single VPS. It consists of a FastAPI backend, Next.js frontend, MQTT broker for real-time notifications, and a local vault for image storage.

## Development Commands

All commands run from repository root. The Makefile auto-detects the environment from the checkout directory and supplies the compose overlay, env file, and project name. **Do not run `npm run build` or similar directly** — use the Makefile or read `deploy/stack/README.stack.md` for deployment operations.

> **Plain `docker compose` in `deploy/stack/` does NOT work** — the running containers belong to a compose project (overlay files, `--env-file`, `-p`) that only the Makefile supplies; a bare `docker compose exec api ...` fails with "service is not running". Use `make` targets, or address containers directly: `docker exec makapix-dev-<service> ...` (substitute `makapix-prod-*` when working in `/opt/makapix`).

```bash
# Testing
make test                                                # Full API suite (chunked runner — see note below)
docker exec makapix-dev-api pytest tests/test_file.py    # Single file
docker exec makapix-dev-api pytest -k "test_name"        # By name
make e2e             # Playwright end-to-end tests (runs on host from web/, reads web/.env.e2e)
make e2e-report      # Open the Playwright report

# Contract & format gate — this repo has NO cloud CI; these are the CI
make check           # Regenerate api/openapi.json + fail on drift, black --check (the pre-push hook runs this)
make check-full      # make check + full test suite — run before merging to main / deploying to prod
make openapi         # Regenerate the committed OpenAPI contract after API changes
make install-hooks   # Symlink deploy/hooks/pre-push into .git/hooks (runs make check on every push)

# Database
make shell-db        # PostgreSQL interactive shell
docker exec makapix-dev-api alembic revision --autogenerate -m "description"
docker exec makapix-dev-api alembic upgrade head
docker exec makapix-dev-api alembic downgrade -1

# Destructive
make clean           # Removes containers AND volumes (10-second grace period)
```

`make test` runs `scripts/run_tests.py`, which splits the ~300-test suite into sequential pytest chunks (a fresh process per chunk) because the full suite OOMs as a single pytest process under the container's memory limit. It forwards extra pytest args: `docker exec makapix-dev-api python scripts/run_tests.py -k auth`.

## Architecture Overview

- `worker/` is a container shell only (Dockerfile + entrypoint); the Celery task code lives in `api/app/tasks.py`.

**Caddy is shared and prod-owned.** Only one instance runs, under the `makapix-prod` project (the dev overlay disables its own via a compose profile). Caddy config changes (compose labels, `Caddyfile.global`) take effect only after merging to `main`, pulling in `/opt/makapix`, and restarting the `caddy` container.

## Event Tables & Retention Policies

| Table | Retention | Aggregation Target | Notes |
|-------|-----------|-------------------|-------|
| site_events | 7 days | site_stats_daily | Page views, signups, uploads, errors |
| view_events | 7 days | site_stats_daily | Player artwork views |
| site_stats_daily | Permanent | — | Daily rollups with auth breakdowns |

**Rollup Schedule:** The daily Celery-beat rollups/cleanups run at fixed US Eastern times (beat `timezone="America/New_York"`), staggered across the 01:00–05:00 ET window. `rollup_view_events` 01:00 → `rollup_site_events` 02:00 → `cleanup_old_view_events` 02:30 (order is load-bearing: cleanup must follow the rollups). See `beat_schedule` in `api/app/tasks.py` for the full list.

## Device Type Enum

Source of truth: `api/app/utils/view_tracking.py:DeviceType`
- `desktop`, `mobile`, `tablet`, `player`

Frontend must mirror in `DEVICE_LABELS` constant (`web/src/components/SiteMetricsPanel.tsx`).

## Vault Storage System

Images are stored in a hash-based folder structure (2-level, 4,096 shards; see `api/app/vault.py:compute_storage_shard_v2`):
- `posts.storage_shard` stores the shard as an opaque relative path — never derive paths from the key; always pass the stored shard
- Legacy 3-level paths (`{h1}/{h2}/{h3}`, first 6 hex chars of the hash) remain served from twin copies during the resharding dual window, and permanently via a miss-only serving-layer remap (D16: Caddy `legacy_shard_remap` snippet in `Caddyfile.global`) — **read `docs/vault-resharding/` before any vault work**
- Served exclusively by Caddy on the env-specific vault subdomain (HTTPS for browsers/apps, plain HTTP for physical players) — see Environments table. The legacy `/api/vault/` FastAPI mount was removed 2026-07-22 (`docs/remove-api-vault/`); `VAULT_PUBLIC_BASE_URL` is a required setting (API fails fast without it)
- Format/size/dimension rules: `api/app/vault.py:validate_image_dimensions` (size cap configurable via `MAKAPIX_ARTWORK_SIZE_LIMIT`)

Avatars use a separate sub-vault (`avatar/`) under the same root — different size cap (5 MB hardcoded) and no dimension validation. See `api/app/avatar_vault.py`.

## MQTT Topics

Source of truth: `docs/MQTT_PROTOCOL.md` (index into `docs/mqtt-protocol/01-architecture.md`, `02-player-protocol.md`, `03-notifications.md`).

## Documentation Map

- `docs/README.md` — index; see also `docs/architecture.md`, `docs/deployment.md`, `docs/development.md`
- Feature efforts live in `docs/<feature>/` (e.g. `vault-resharding/`, `mkpx-upload/`, `mod-hashtags/`, `backups/`) — **read the PLAN.md / README.md there before working on that area, and update its PROGRESS.md afterward.** Some contain a `message/` exchange protocol with external teams.
- `docs/MQTT_PROTOCOL.md` — MQTT protocol reference (see MQTT Topics above)

## Deployment Workflow

1. Develop features in `/opt/makapix-dev` on `develop` branch
2. Test with `make rebuild` and verify at development.makapix.club
3. Run `make check-full` (OpenAPI drift + Black + full test suite) — there is no cloud CI; this is the gate
4. Push changes: `git push origin develop` (the pre-push hook runs `make check`)
5. Create PR on GitHub: `develop` → `main`, and merge it
6. Deploy to production: `cd /opt/makapix && make deploy`

For manual prod deployment commands (e.g. when `make deploy` is unavailable), see `deploy/stack/README.stack.md`.

## User Interaction Style

Clarifying questions are always welcome and appreciated.

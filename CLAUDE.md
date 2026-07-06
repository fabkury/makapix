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
# Service management
make up              # Start all services
make down            # Stop all services
make restart         # Restart all services
make rebuild         # Rebuild containers and restart
make deploy          # Pull latest + rebuild
make ps              # Container status
make help            # Full target list

# Logs
make logs            # All services (also: logs-api, logs-web, logs-db)

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

# Code formatting
make fmt             # Format Python code (Black)

# Container shells
make shell-api       # bash in the API container
docker exec -it makapix-dev-web sh

# Destructive
make clean           # Removes containers AND volumes (10-second grace period)
```

`make test` runs `scripts/run_tests.py`, which splits the ~300-test suite into sequential pytest chunks (a fresh process per chunk) because the full suite OOMs as a single pytest process under the container's memory limit. It forwards extra pytest args: `docker exec makapix-dev-api python scripts/run_tests.py -k auth`.

## Architecture Overview

**Monorepo structure:**
- `api/` — FastAPI backend (Python 3.12+, SQLAlchemy 2.0+)
- `web/` — Next.js 14 frontend (TypeScript, React 18)
- `worker/` — Celery worker container (Dockerfile + entrypoint only; the task code lives in `api/app/tasks.py`)
- `apps/` — auxiliary web apps served as separate containers (Piskel editor, CTA)
- `mqtt/` — Mosquitto broker config
- `deploy/stack/` — Docker Compose stack

### Backend Architecture (api/)

**Entry point:** `api/app/main.py` — initializes FastAPI, CORS, security middleware, automatic migrations, and MQTT subscriber.

**Key modules:**
- `models.py` — SQLAlchemy models (users, posts, comments, reactions, playlists, badges, players, reports, blog posts, …)
- `schemas.py` — Pydantic request/response schemas
- `auth.py` — JWT authentication + GitHub OAuth
- `vault.py` — Hash-based image storage operations
- `tasks.py` — Celery background tasks (notifications, asset processing, rollups) + `beat_schedule`
- `routers/` — API endpoint modules, one per area (auth, users, posts, artwork, player, admin, search, blog_posts, …)
- `services/` — business-logic services (rate_limit, storage_quota, social_notifications, email, …)
- `mqtt/` — MQTT pub/sub integration for real-time notifications and physical player commands

### Frontend (web/)

- `src/pages/` — Next.js pages (pages router)
- `src/components/` — React components
- `src/lib/` — API client, utilities
- `src/hooks/` — Custom React hooks

```bash
# Run inside web container or during build
npm run typecheck    # TypeScript check
npm run lint         # ESLint
npm run format       # Prettier
```

### Services (deploy/stack/docker-compose.yml)

In-container ports listed below; host port mappings differ per environment — see the Environments table.

| Service | Purpose | In-container port(s) |
|---------|---------|----------------------|
| db | PostgreSQL 17 | 5432 |
| cache | Redis 7 (API cache, Celery broker) | 6379 (internal net) |
| redis | Redis 7, separate instance on `caddy_net` (edge use) | 6379 |
| mqtt | Mosquitto (plain + mTLS, WebSocket via Caddy at `/mqtt`) | 1883, 8883 |
| api | FastAPI | 8000 |
| worker | Celery background worker | — |
| web | Next.js | 3000 |
| caddy | Shared reverse proxy with auto-TLS (caddy-docker-proxy; config via per-service compose labels) | 80, 443 |
| vault | HTTP file server for physical players | — |
| piskel | Piskel editor (built from `apps/piskel`), served on its own subdomain | 80 |
| pixelc | Pixelc editor (built from `/opt/Pixelc` in prod, `/opt/Pixelc-dev` in dev — outside this repo), own subdomain | 80 |
| www-redirect | www → apex redirect (prod only; disabled in dev) | — |

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

Images stored in hash-based folder structure:
- Path format: `/vault/{a}/{b}/{artwork_id}.{ext}` (2-level, 4,096 shards)
- `a`/`b` = low 6 bits of the first two bytes of SHA-256(artwork ID), hex-rendered (`00`–`3f`); see `api/app/vault.py:compute_storage_shard_v2`
- `posts.storage_shard` stores the shard as an opaque relative path — never derive paths from the key; always pass the stored shard
- Legacy 3-level paths (`{h1}/{h2}/{h3}`, first 6 hex chars of the hash) remain served from twin copies during the resharding dual window, and permanently via a miss-only serving-layer remap (D16: Caddy `legacy_shard_remap` snippet + `api/app/vault_serving.py`) — **read `docs/vault-resharding/` before any vault work**
- Served via `/api/vault/` (HTTPS) and the env-specific vault subdomain (HTTP for physical players) — see Environments table
- Supported formats: PNG, GIF, WebP, BMP (max 5 MiB by default, configurable via `MAKAPIX_ARTWORK_SIZE_LIMIT`)
- Dimension rules (`api/app/vault.py:validate_image_dimensions`):
  - 128×128 through 256×256 (inclusive): any size, square or rectangular
  - Under 128×128: only a whitelist of sizes (with 90° rotations): 8×8, 8×16, 8×32, 16×16, 16×32, 32×32, 32×64, 64×64, 64×128
  - Either dimension > 256: rejected

Avatars use a separate sub-vault (`avatar/`) under the same root — different size cap (5 MB hardcoded) and no dimension validation. See `api/app/avatar_vault.py`.

## MQTT Topics

Source of truth: `docs/MQTT_PROTOCOL.md` (index into `docs/mqtt-protocol/01-architecture.md`, `02-player-protocol.md`, `03-notifications.md`).

```
makapix/post/new/{post_id}                     # New-post notifications (variants: .../user/{user_id}/{post_id}, .../category/{category}/{post_id})
makapix/social-notifications/user/{user_id}    # Social notifications (one topic per user, all types)
makapix/player/{key}/request/{id}              # Client → player RPC (responses on .../response/{id})
makapix/player/{key}/command                   # Server → player commands
makapix/player/{key}/status                    # Player → server status updates
makapix/player/{key}/view                      # Fire-and-forget artwork views (ack on .../view/ack)
makapix/player/{key}/capabilities, .../state   # Retained player self-reports
```

> Known mismatch (documented in `03-notifications.md`): the web client subscribes to `makapix/posts/new/...` (plural) while the backend publishes to `makapix/post/new/...` (singular), so web clients do not currently receive new-post notifications via MQTT.

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

## Code Style

- **Python:** Black (line-length 88), Ruff linter (rules: E, F, I, B)
- **TypeScript:** ESLint (next/core-web-vitals) + Prettier
- Tests in `api/tests/` use pytest with fixtures in `conftest.py`

## User Interaction Style

Clarifying questions are always welcome and appreciated.

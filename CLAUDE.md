# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environments

This repo is checked out twice on the VPS — once for production, once for development — driven by per-environment compose overlays (`docker-compose.prod.yml`, `docker-compose.dev.yml`):

| | Production | Development |
|---|---|---|
| Directory | `/opt/makapix` | `/opt/makapix-dev` |
| Branch | `main` | `develop` |
| URL | https://makapix.club | https://development.makapix.club |
| Database volume | `pg_data_prod` | `pg_data_dev` |
| Database host port | 5432 (loopback) | 5433 (loopback) |
| Vault | `/mnt/vault-1` | `/mnt/vault-dev` |
| Vault subdomain | `vault.makapix.club` | `vault-dev.makapix.club` |
| MQTT host ports | 1883 (plain), 8883 (mTLS) | 1884 (plain), 8884 (mTLS) |
| Compose project | `makapix-prod` | `makapix-dev` |

> Develop new features in `/opt/makapix-dev` on `develop`, test at development.makapix.club, then PR `develop` → `main` and deploy to prod via `cd /opt/makapix && make deploy`.

## Project Overview

Makapix Club (MPX) is a lightweight pixel art social network designed to run on a single VPS. It consists of a FastAPI backend, Next.js frontend, MQTT broker for real-time notifications, and a local vault for image storage.

## Development Commands

All commands run from repository root. **Do not run `npm run build` or similar directly** — use the Makefile or read `deploy/stack/README.stack.md` for deployment operations.

```bash
# Service management
make up              # Start all services
make down            # Stop all services
make rebuild         # Rebuild containers and restart
make deploy          # Pull latest + rebuild

# Logs
make logs            # All services
make logs-api        # API only
make logs-web        # Web only
make logs-db         # Database only

# Testing
make test                                                      # Run all API tests
cd deploy/stack && docker compose exec api pytest tests/test_file.py    # Single file
cd deploy/stack && docker compose exec api pytest -k "test_name"        # By name
cd deploy/stack && docker compose exec api pytest -v --cov=app          # With coverage

# Database
make db.shell        # PostgreSQL interactive shell
cd deploy/stack && docker compose exec api alembic revision --autogenerate -m "description"
cd deploy/stack && docker compose exec api alembic upgrade head
cd deploy/stack && docker compose exec api alembic downgrade -1

# Code formatting
make fmt             # Format Python code (Black)

# Container shells
cd deploy/stack && docker compose exec api bash
cd deploy/stack && docker compose exec web sh
```

## Architecture Overview

**Monorepo structure:**
- `api/` — FastAPI backend (Python 3.12+, SQLAlchemy 2.0+)
- `web/` — Next.js 14 frontend (TypeScript, React 18)
- `worker/` — Celery background tasks
- `mqtt/` — Mosquitto broker config
- `deploy/stack/` — Docker Compose stack

### Backend Architecture (api/)

**Entry point:** `api/app/main.py` — initializes FastAPI, CORS, security middleware, automatic migrations, and MQTT subscriber.

**Key modules:**
- `models.py` — SQLAlchemy models (users, posts, comments, reactions, playlists, badges, devices, reports)
- `schemas.py` — Pydantic request/response schemas
- `auth.py` — JWT authentication + GitHub OAuth
- `vault.py` — Hash-based image storage operations
- `tasks.py` — Celery background tasks (notifications, asset processing)
- `routers/` — 26 API endpoint modules (auth, users, posts, artwork, comments, reactions, playlists, player, admin, search, reports, badges, stats, mqtt, etc.)
- `services/` — 18 business logic services (auth_identities, email, artist_dashboard, social_notifications, rate_limit, storage_quota, etc.)
- `mqtt/` — MQTT pub/sub integration for real-time notifications and physical player commands

### Frontend (web/)

- `src/pages/` — Next.js pages
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
| caddy | Reverse proxy with auto-TLS | 80, 443 |
| vault | HTTP file server for physical players | — |

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
- Legacy 3-level paths (`{h1}/{h2}/{h3}`, first 6 hex chars of the hash) remain served from twin copies during the resharding dual window — **read `docs/vault-resharding/` before any vault work**
- Served via `/api/vault/` (HTTPS) and the env-specific vault subdomain (HTTP for physical players) — see Environments table
- Supported formats: PNG, GIF, WebP, BMP (max 5 MB by default, configurable via `MAKAPIX_ARTWORK_SIZE_LIMIT`)
- Dimension rules (`api/app/vault.py:validate_image_dimensions`):
  - 128×128 through 256×256 (inclusive): any size, square or rectangular
  - Under 128×128: only a whitelist of sizes (with 90° rotations): 8×8, 8×16, 8×32, 16×16, 16×32, 32×32, 32×64, 64×64, 64×128
  - Either dimension > 256: rejected

Avatars use a separate sub-vault (`avatar/`) under the same root — different size cap (5 MB hardcoded) and no dimension validation. See `api/app/avatar_vault.py`.

## MQTT Topics

```
makapix/posts/new              # New post notifications
makapix/posts/promoted         # Promoted post notifications
makapix/player/{key}/command   # Server → Player commands
makapix/player/{key}/status    # Player → Server status
```

## Deployment Workflow

1. Develop features in `/opt/makapix-dev` on `develop` branch
2. Test with `make rebuild` and verify at development.makapix.club
3. Push changes: `git push origin develop`
4. Create PR on GitHub: `develop` → `main`
5. Merge PR
6. Deploy to production: `cd /opt/makapix && make deploy`

For manual prod deployment commands (e.g. when `make deploy` is unavailable), see `deploy/stack/README.stack.md`.

## Code Style

- **Python:** Black (line-length 88), Ruff linter (rules: E, F, I, B)
- **TypeScript:** ESLint (next/core-web-vitals) + Prettier
- Tests in `api/tests/` use pytest with fixtures in `conftest.py`

## User Interaction Style

Clarifying questions are always welcome and appreciated.

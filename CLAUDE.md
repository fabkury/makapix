# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Meta-guidance

Feel free to ask clarifying questions, they are welcome.

## Project Overview

Makapix Club (MPX) is a lightweight pixel art social network designed to run on a single VPS. It consists of a FastAPI backend, Next.js frontend, MQTT broker for real-time notifications, and a local vault for image storage.

## Development Commands

All commands are run from the repository root. The stack is defined in `deploy/stack/docker-compose.yml`.

```bash
# Start all services
make up

# Stop all services
make down

# View logs
make logs
make logs-api      # API only
make logs-web      # Web only
make logs-db       # Database only

# Rebuild containers
make rebuild

# Database
make db.shell      # PostgreSQL shell

# Run API tests
make test
cd deploy/stack && docker compose exec api pytest tests/test_file.py  # Single test file
cd deploy/stack && docker compose exec api pytest -k "test_name"       # Test by name

# Format Python code
make fmt

# Enter container shells
cd deploy/stack && docker compose exec api bash
cd deploy/stack && docker compose exec web sh

# Deploy (pull + rebuild)
make deploy
```

## Architecture

**Monorepo structure:**
- `api/` - FastAPI backend (Python 3.12+)
- `web/` - Next.js 14 frontend (TypeScript/React 18)
- `worker/` - Celery background tasks
- `mqtt/` - Mosquitto broker configuration
- `apps/cta/` - Marketing site (archived)
- `deploy/stack/` - Docker Compose stack (all services)

**Key services (deploy/stack/docker-compose.yml):**
- `db` - PostgreSQL 17
- `cache` - Redis 7 (API cache, Celery broker)
- `mqtt` - Mosquitto (ports 1883, 8883)
- `api` - FastAPI on port 8000
- `worker` - Celery background worker
- `web` - Next.js on port 3000
- `caddy` - Reverse proxy with auto-TLS
- `cta` - Marketing site (disabled)
- `vault` - HTTP file server for physical players
- `redis` - Edge rate limiting

## Backend (api/)

**Entry point:** `api/app/main.py`

**Key modules:**
- `models.py` - SQLAlchemy models
- `schemas.py` - Pydantic request/response schemas
- `auth.py` - JWT authentication, GitHub OAuth
- `vault.py` - Hash-based image storage system
- `routers/` - API endpoint handlers (posts, users, auth, player, etc.)
- `services/` - Business logic services
- `tasks.py` - Celery background tasks

**Database migrations:**
```bash
cd deploy/stack && docker compose exec api alembic revision --autogenerate -m "description"
cd deploy/stack && docker compose exec api alembic upgrade head
cd deploy/stack && docker compose exec api alembic downgrade -1
```

## Frontend (web/)

**Key directories:**
- `src/pages/` - Next.js pages
- `src/components/` - React components
- `src/lib/` - API client, utilities
- `src/hooks/` - Custom React hooks

**Scripts (run inside web container or during build):**
```bash
npm run build      # Production build
npm run typecheck  # TypeScript check
npm run lint       # ESLint
npm run format     # Prettier
```

## Vault Storage

Images are stored locally in a hash-based folder structure:
- Path format: `/vault/{h1}/{h2}/{h3}/{artwork_id}.{ext}`
- Hash derived from first 6 chars of SHA-256 of artwork ID
- Served via `/api/vault/` endpoint (HTTPS) and `vault.makapix.club` (HTTP for players)

## MQTT Topics

```
makapix/posts/new           # New post notifications
makapix/posts/promoted      # Promoted post notifications
makapix/player/{key}/command # Physical player commands
makapix/player/{key}/status  # Player status reports
```

## Deployment

This repository uses a dual-environment setup with `main` and `develop` branches:

| Environment | Directory | Branch | URL |
|-------------|-----------|--------|-----|
| Production | `/opt/makapix` | `main` | makapix.club |
| Development | `/opt/makapix-dev` | `develop` | development.makapix.club |

### Development Workflow

1. **Develop features** in `/opt/makapix-dev` on the `develop` branch
2. **Test locally** with `make rebuild` and verify at development.makapix.club
3. **Push changes**: `git push origin develop`
4. **Create PR** on GitHub: `develop` → `main`
5. **Merge PR** on GitHub
6. **Deploy to production**: `cd /opt/makapix && make deploy`

### Development Commands

```bash
make up        # Start development services
make rebuild   # Rebuild and restart
make sync      # Sync with remote develop branch
make deploy-to-prod  # Instructions for production deployment
```

### Production Commands (in /opt/makapix)

```bash
make deploy    # Pulls latest main and rebuilds services
```

### Manual Deployment

```bash
# Development
git pull origin develop
cd deploy/stack && docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev down
cd deploy/stack && docker compose -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.dev up -d --build

# Production
git pull origin main
cd deploy/stack && docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod down
cd deploy/stack && docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

## Code Style

- **Python:** Black formatter (line-length 88), Ruff linter
- **TypeScript:** ESLint + Prettier
- Tests in `api/tests/` use pytest

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Makapix Club (MPX) is a lightweight pixel art social network designed to run on a single VPS. It consists of a FastAPI backend, Next.js frontend, MQTT broker for real-time notifications, and a local vault for image storage.

## Development Commands

```bash
# Start all services
make up

# Stop all services
make down

# View logs
make logs
make logs-api      # API only
make logs-web      # Web only

# Rebuild containers
make rebuild

# Switch environments
make local         # localhost development
make remote        # dev.makapix.club

# Database
make db.shell      # PostgreSQL shell

# Run API tests
make test
docker compose exec api pytest tests/test_file.py  # Single test file
docker compose exec api pytest -k "test_name"       # Test by name

# Format Python code
make fmt

# Enter container shells
docker compose exec api bash
docker compose exec web sh
```

## Architecture

**Monorepo structure:**
- `api/` - FastAPI backend (Python 3.12+)
- `web/` - Next.js 14 frontend (TypeScript/React 18)
- `worker/` - Celery background tasks
- `mqtt/` - Mosquitto broker configuration
- `apps/cta/` - Marketing site (makapix.club)
- `deploy/stack/` - VPS production deployment

**Key services (docker-compose.yml):**
- `db` - PostgreSQL 17
- `cache` - Redis 7.2
- `mqtt` - Mosquitto (ports 1883, 8883, 9001)
- `api` - FastAPI on port 8000
- `web` - Next.js on port 3000
- `proxy` - Caddy reverse proxy

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
docker compose exec api alembic revision --autogenerate -m "description"
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1
```

## Frontend (web/)

**Key directories:**
- `src/pages/` - Next.js pages
- `src/components/` - React components
- `src/lib/` - API client, utilities
- `src/hooks/` - Custom React hooks

**Scripts:**
```bash
npm run dev        # Development with hot reload
npm run build      # Production build
npm run typecheck  # TypeScript check
npm run lint       # ESLint
npm run format     # Prettier
```

## Vault Storage

Images are stored locally in a hash-based folder structure:
- Path format: `/vault/{h1}/{h2}/{h3}/{artwork_id}.{ext}`
- Hash derived from first 6 chars of SHA-256 of artwork ID
- Served via `/api/vault/` endpoint

## MQTT Topics

```
makapix/posts/new           # New post notifications
makapix/posts/promoted      # Promoted post notifications
makapix/player/{key}/command # Physical player commands
makapix/player/{key}/status  # Player status reports
```

## Deployment Notes

**VPS deployment uses `deploy/stack/`** - see `deploy/stack/README.stack.md` for details.

Do NOT run `npm run build` or similar build commands directly. The deployment stack handles builds in production mode.

**Critical:** On VPS, use production mode (`deploy/stack/docker-compose.yml`) not the root docker-compose.yml, which is for local dev with hot reload.

## Code Style

- **Python:** Black formatter (line-length 88), Ruff linter
- **TypeScript:** ESLint + Prettier
- Tests in `api/tests/` use pytest

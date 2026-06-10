# Current Architecture Overview

This document summarizes the existing Makapix infrastructure as context for the dual-environment proposal.

## Service Architecture

The Makapix stack runs entirely from `deploy/stack/docker-compose.yml` with the following services:

| Service | Container Name | Role | Networks |
|---------|---------------|------|----------|
| **db** | makapix-db | PostgreSQL 17 | internal |
| **cache** | makapix-cache | Redis (Celery broker + API cache) | internal |
| **mqtt** | makapix-mqtt | Mosquitto broker (mTLS, WebSocket) | internal, caddy_net |
| **api** | makapix-api | FastAPI backend | internal, caddy_net |
| **worker** | makapix-worker | Celery background tasks | internal |
| **web** | makapix-web | Next.js frontend | caddy_net |
| **caddy** | caddy | Reverse proxy with auto-TLS | caddy_net |
| **vault** | makapix-vault | Static file server for artwork | caddy_net |
| **redis** | makapix-redis | Rate limiting Redis | caddy_net |

## Network Topology

```
                    Internet
                        │
                   ┌────▼────┐
                   │  Caddy  │  Ports 80, 443
                   │  (TLS)  │  Auto-certificates via ACME
                   └────┬────┘
                        │
         ┌──────────────┼──────────────┐
         │              │              │
    ┌────▼───┐    ┌────▼───┐    ┌────▼────┐
    │  web   │    │  api   │    │  vault  │
    │ :3000  │    │ :8000  │    │ (files) │
    └────────┘    └────┬───┘    └─────────┘
                       │
              ┌────────┼────────┐
              │        │        │
         ┌────▼───┐ ┌──▼──┐ ┌──▼───┐
         │ cache  │ │ db  │ │ mqtt │
         │ :6379  │ │:5432│ │:1883 │
         └────────┘ └─────┘ └──────┘
                           (internal)
```

## Database Structure

**PostgreSQL 17** with 43 tables organized into:

- **Core entities**: users, auth_identities, refresh_tokens, password_reset_tokens
- **Content**: posts, playlist_posts, playlist_items, comments, reactions, blog_posts
- **Social**: follow, category_follows, social_notifications, user_highlights
- **Statistics**: view_events, post_stats_daily, site_events, site_stats_daily
- **Players**: players, player_command_logs (hardware/virtual player devices)
- **Moderation**: reports, violations, badge_definitions, badge_grants

Key relationship: Users cascade-delete to posts, which cascade to comments, reactions, and view events.

## Vault Storage

Artwork files are stored locally using hash-based sharding:

```
/mnt/vault-1/{a}/{b}/{storage_key}.{format}

Example: /mnt/vault-1/8c/4f/2a/a1b2c3d4-e5f6-7890.png
```

- `{a}`/`{b}` = low 6 bits of the first two SHA-256(storage_key) bytes, hex `00`-`3f` (legacy 3-level paths still served during the resharding window)
- Served via HTTPS at `/api/vault/` (through Caddy)
- Served via HTTP at `http://vault.makapix.club/` (for IoT players)

## Configuration

All configuration via `.env` file in `deploy/stack/`:

```
# Domain
ROOT_DOMAIN=makapix.club
BASE_URL=https://makapix.club
NEXT_PUBLIC_API_BASE_URL=https://makapix.club

# Database
DB_DATABASE=makapix
DB_ADMIN_USER=owner
DB_API_WORKER_USER=api_worker

# Vault
VAULT_HOST_PATH=/mnt/vault-1
VAULT_DOMAIN=vault.makapix.club

# MQTT
MQTT_PUBLIC_HOST=makapix.club
MQTT_PUBLIC_PORT=8883

# Authentication
JWT_SECRET_KEY=...
GITHUB_OAUTH_CLIENT_ID=...
GITHUB_OAUTH_CLIENT_SECRET=...
GITHUB_REDIRECT_URI=https://makapix.club/api/auth/github/callback
```

## External Volumes

Persistent Docker volumes (survive `docker compose down`):

- `makapix_pg_data` - PostgreSQL data
- `makapix-stack_caddy_data` - TLS certificates
- `makapix-stack_caddy_config` - Caddy state

## Hardcoded Elements

The following are currently hardcoded and would need parameterization:

1. Container names: `makapix-{service}` prefix
2. Network names: `internal`, `caddy_net`
3. Volume names: `makapix_pg_data`
4. Database name: `makapix`
5. MQTT topics: `makapix/` prefix
6. Caddy labels reference `makapix.club` domain directly

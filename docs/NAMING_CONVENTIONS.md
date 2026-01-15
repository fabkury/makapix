# Naming Conventions (Websites, Compose Files, Services)

This repo is intentionally deployed as **exactly two public websites**:

1) **CTA (static marketing site)**: `https://makapix.club/`
2) **Web (live preview of the full app)**: `https://dev.makapix.club/`

There are no other “environments” intended to be publicly reachable.

## Docker Compose

All services are defined in a single file:

- `deploy/stack/docker-compose.yml`
  - **Purpose**: Complete stack for the VPS (all services)
  - Reverse proxy: `caddy-docker-proxy` (reads container labels)
  - Includes: db, cache, mqtt, api, worker, web, cta, vault, piskel, pixelc

## VPS stack service names (deploy/stack)

- `cta`
  - **What**: static site content from `apps/cta/`
  - **Public URL**: `https://makapix.club/`
  - **Container**: `makapix-cta`

- `web`
  - **What**: Next.js app from `web/`
  - **Public URL**: `https://dev.makapix.club/`
  - **Container**: `makapix-web`

## VPS env var naming (deploy/stack/.env)

We use:

- `ROOT_DOMAIN`: the CTA domain (example: `makapix.club`)
- `WEB_DOMAIN`: the live preview domain (example: `dev.makapix.club`)
- `WEB_APP_PORT`: the internal port the preview web server listens on (example: `3000`)

Legacy variables are still supported in the compose file for older deployments:

- `DEV_DOMAIN` (fallback for `WEB_DOMAIN`)
- `DEV_APP_PORT` (fallback for `WEB_APP_PORT`)

## Operational commands (VPS stack)

Run these from `deploy/stack/`:

- Rebuild/restart **only** the web preview:
  - `docker compose build web && docker compose up -d web`
- Logs:
  - `docker logs -f makapix-web`
  - `docker logs -f makapix-cta`



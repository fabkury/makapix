# Makapix Stack (Containerized)

This directory contains the Docker Compose configuration for deploying the Makapix stack on a VPS.

## Architecture

- **CTA (static)**: https://makapix.club (content: `apps/cta/`)
- **Dev (live preview)**: https://dev.makapix.club (builds from `web/`)
- **Reverse Proxy**: lucaslorentz/caddy-docker-proxy
- **Compose dir**: `deploy/stack/` (run commands from here)

## Development Workflow

1. **Local Development**: Work on `localhost` using the main `docker-compose.yml` in the repo root
2. **Staging Deployment**: Deploy to `dev.makapix.club` for testing (this stack)
3. **Production**: When ready, "flip the switch" to serve the full app at `makapix.club`

## Setup

1. Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

2. Ensure the `caddy_net` network exists:
   ```bash
   docker network create caddy_net
   ```

3. Start the stack:
   ```bash
   docker compose up -d
   ```

## Common Commands

- Rebuild and restart dev: `docker compose build dev && docker compose up -d dev`
- Update Caddy: change tags in `.env`, then `docker compose pull caddy && docker compose up -d caddy`
- Enable basic auth for dev: uncomment `caddy.basicauth./` label in compose, set a bcrypt hash, then rebuild and up.
- Logs:
  - Edge: `docker logs -f caddy`
  - CTA: `docker logs -f makapix-cta`
  - Dev: `docker logs -f makapix-dev`

## Monitoring

- Monitor CTA stats: `./monitor-cta-stats.sh`
- Stats are saved to `cta-stats.csv` (gitignored)

## Notes

- CTA site content is in `apps/cta/` (version controlled)
- Dev site builds from `web/` directory (version controlled)
- Certificates are stored in the `caddy_data` Docker volume
- All paths are relative to the monorepo root (`/opt/makapix` on VPS)

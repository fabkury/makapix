# Makapix - Pixel Art Social Network

A lightweight social network centered on pixel art, designed to run efficiently on a single VPS.

## Repository Structure

This is a monorepo containing:

- **`apps/cta/`** - Static CTA/marketing website (currently live at https://makapix.club)
- **`web/`** - Next.js frontend application (development/staging)
- **`api/`** - FastAPI backend service
- **`worker/`** - Background worker services
- **`db/`** - Database schema and migrations
- **`mqtt/`** - MQTT broker configuration
- **`deploy/stack/`** - VPS deployment orchestration (Docker Compose)

## Development Workflow

### Local Development

Work on `localhost` using the main `docker-compose.yml`:

```bash
# Switch to local environment
make local

# Start all services
make up

# View logs
make logs
```

### Staging Deployment

Deploy to `dev.makapix.club` for testing:

```bash
cd deploy/stack
cp .env.example .env
# Edit .env with your configuration
docker compose up -d
```

### Production

The CTA site is currently live at https://makapix.club. When ready to go live with the full application:

1. Update `deploy/stack/docker-compose.yml` to serve the main app at `makapix.club`
2. Keep the CTA site available at a different path or archive it

## Current Deployment Status

- **CTA Site**: https://makapix.club (static site from `apps/cta/`)
- **Dev Preview**: https://dev.makapix.club (Next.js app from `web/`)
- **VPS Stack**: Managed via `deploy/stack/docker-compose.yml`

## Key Features

- Pixel art focused social network
- GitHub Pages integration for artwork hosting
- MQTT real-time notifications
- Lightweight, cost-effective VPS deployment
- See `makapix_full_project_spec.md` for complete specification

## Getting Started

See `deploy/stack/README.stack.md` for VPS deployment instructions.

For local development, see the `Makefile` and environment templates:
- `env.local.template` - Local development configuration
- `env.remote.template` - Remote/staging configuration


# Makapix Stack (Containerized)

This directory contains the Docker Compose configuration for deploying the Makapix stack on a VPS.

## Architecture

- **CTA (static)**: https://makapix.club (content: `apps/cta/`)
- **Web (staging)**: https://dev.makapix.club (builds from `web/`)
- **Reverse Proxy**: lucaslorentz/caddy-docker-proxy
- **Compose dir**: `deploy/stack/` (run commands from here)

## ⚠️ IMPORTANT: Production vs Local Development

This stack runs the web application in **PRODUCTION MODE** (optimized build).
This is different from local development which uses **DEV MODE** (hot reload).

| Environment | Compose File | Web Mode | Container Name | Notes |
|------------|--------------|----------|----------------|-------|
| **VPS (this stack)** | `deploy/stack/docker-compose.yml` | Production | `makapix-web` | Uses `npm run build` + standalone server |
| **Local development** | Root `docker-compose.yml` | Development | `makapix-web-1` | Uses `npm run dev` with hot reload |

### Why Production Mode on dev.makapix.club?

1. **Mobile compatibility**: Next.js dev mode can cause styled-jsx runtime errors on mobile browsers
2. **Performance**: Production builds are ~5x smaller and start in ~100ms vs ~1s+
3. **Reliability**: Pre-compiled assets avoid webpack race conditions
4. **Testing**: Catch production-only issues before going live

### Common Pitfalls to Avoid

- ❌ **Do NOT run multiple web containers** with the same Caddy label (`caddy: dev.makapix.club`)
- ❌ **Do NOT mix dev/prod containers** on the same network — Caddy will route unpredictably
- ❌ **Do NOT start containers from root docker-compose.yml** when this stack is running
- ✅ **Always check** `docker ps | grep makapix` before deployments
- ✅ **Always rebuild** after Dockerfile changes: `docker compose build --no-cache web`

## Development Workflow

1. **Local Development**: Work on `localhost` using the main `docker-compose.yml` in the repo root
2. **Staging Deployment**: Deploy to `dev.makapix.club` for testing (this stack)
3. **Production**: When ready, "flip the switch" to serve the full app at `makapix.club`

## Setup

1. Copy `env.example` to `.env` and configure:
   ```bash
   cp env.example .env
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

```bash
# Rebuild and restart web (with cache)
docker compose build web && docker compose up -d web

# Rebuild web WITHOUT cache (after Dockerfile changes)
docker compose down web && docker compose build --no-cache web && docker compose up -d web

# Check what's running (always do this before deployments)
docker ps | grep makapix

# Remove orphan containers (if you see warnings)
docker compose up -d --remove-orphans

# Update Caddy
docker compose pull caddy && docker compose up -d caddy
```

## Logs

```bash
# Edge proxy (Caddy)
docker logs -f caddy

# CTA static site
docker logs -f makapix-cta

# Web application
docker logs -f makapix-web
```

## Monitoring

- Monitor CTA stats: `./monitor-cta-stats.sh`
- Stats are saved to `cta-stats.csv` (gitignored)

## Troubleshooting

### "styled-jsx: Cannot read properties of undefined"
This error occurs when running in dev mode on mobile. Solution: Ensure the stack is using
production mode (`NODE_ENV=production` and `web/Dockerfile` with `npm run build`).

### Static files returning 404
Check for conflicting containers: `docker ps | grep makapix-web`. If you see multiple
web containers, stop and remove all except the one from this stack:
```bash
docker stop <old-container-id> && docker rm <old-container-id>
docker compose restart caddy
```

### Page loads but content is empty
The JavaScript failed to hydrate. Check browser console and network tab for 404 errors
on `.js` files. Usually caused by stale HTML referencing old chunk hashes.
Solution: Hard refresh (Ctrl+Shift+R) or clear browser cache.

## Notes

- CTA site content is in `apps/cta/` (version controlled)
- Web builds from `web/` directory using multi-stage Dockerfile
- Certificates are stored in the `caddy_data` Docker volume
- All paths are relative to the monorepo root (`/opt/makapix` on VPS)
- The web image uses Next.js standalone output (~165MB vs ~877MB for dev)

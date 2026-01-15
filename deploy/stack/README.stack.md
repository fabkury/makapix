# Makapix Stack (Containerized)

This directory contains the Docker Compose configuration for deploying the Makapix stack on a VPS.

## Architecture

- **CTA (static)**: https://makapix.club (content: `apps/cta/`)
- **Web (staging)**: https://dev.makapix.club (builds from `web/`)
- **Vault (HTTP)**: http://vault.makapix.club (artwork files for physical players)
- **Reverse Proxy**: lucaslorentz/caddy-docker-proxy
- **Compose dir**: `deploy/stack/` (run commands from here)

## Production Mode

This stack runs all services including the web application in **PRODUCTION MODE** (optimized build).

### Why Production Mode?

1. **Mobile compatibility**: Next.js dev mode can cause styled-jsx runtime errors on mobile browsers
2. **Performance**: Production builds are ~5x smaller and start in ~100ms vs ~1s+
3. **Reliability**: Pre-compiled assets avoid webpack race conditions
4. **Testing**: Catch production-only issues before going live

### Best Practices

- ✅ **Always check** `docker ps | grep makapix` before deployments
- ✅ **Always rebuild** after Dockerfile changes: `docker compose build --no-cache web`
- ✅ Use `make` commands from repo root for convenience

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

# Vault HTTP server
docker logs -f makapix-vault
```

## Monitoring

- Monitor CTA stats: `./monitor-cta-stats.sh`
- Stats are saved to `cta-stats.csv` (gitignored)

## Vault HTTP Server

The vault provides **HTTP-only** access to artwork files for physical players (IoT devices).
This reduces TLS handshake overhead for resource-constrained devices.

### Architecture

The vault is served directly by the main **Caddy proxy container**, not a separate container:
- The `makapix-vault` container only provides Docker labels for caddy-docker-proxy
- Actual file serving is done by Caddy using its `/srv/vault` mount
- This is more efficient than proxying through another container

### URL Pattern

```
http://vault.makapix.club/{hash1}/{hash2}/{hash3}/{storage_key}.{ext}

Example:
http://vault.makapix.club/a1/b2/c3/550e8400-e29b-41d4-a716-446655440000.png
```

### Features

- **No TLS overhead**: HTTP-only for IoT efficiency
- **Direct file serving**: Caddy serves files directly (no Python)
- **CORS enabled**: `Access-Control-Allow-Origin: *`
- **Compression**: gzip enabled
- **Security headers**: `X-Content-Type-Options: nosniff`

### Security Considerations

⚠️ **Important**: The vault serves files **without authentication**. This is intentional and matches
the security model of the HTTPS vault (`/api/vault/...`). Access control for hidden/deleted
artworks relies on URL obscurity (UUIDs are not guessable).

### Managing the Vault

```bash
# Start/restart vault (restarts caddy to apply label changes)
docker compose up -d vault && docker compose restart caddy

# Verify vault is working
curl -I http://vault.makapix.club/path/to/file.png

# View vault access logs
docker exec caddy tail -f /var/log/caddy/vault-access.log
```

---

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

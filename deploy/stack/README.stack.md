# Makapix Stack (Containerized)

This directory contains the Docker Compose configuration for deploying the Makapix stack on a VPS.

## Architecture

- **Web (production)**: https://makapix.club (builds from `web/`)
- **Vault (HTTP)**: http://vault.makapix.club (artwork files for physical players)
- **Piskel Editor**: https://piskel.makapix.club
- **PixelC Editor**: https://pixelc.makapix.club
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

# Web application
docker logs -f makapix-web

# Vault HTTP server
docker logs -f makapix-vault
```

## Monitoring

- Monitor CTA stats: `./monitor-cta-stats.sh`
- Stats are saved to `cta-stats.csv` (gitignored)

## Vault HTTP Server

The vault provides direct access to artwork files for both physical players (HTTP)
and the website (HTTPS). Both protocols bind the same hostname so existing players
keep working unchanged while browsers fetch over TLS.

### Architecture

The vault is served directly by the main **Caddy proxy container** via manual
site blocks in `caddy/Caddyfile.global` (not via docker labels). Caddy already
mounts the vault directories read-only:

- `/mnt/vault-1   -> /srv/vault-prod` (prod artwork)
- `/mnt/vault-dev -> /srv/vault-dev`  (dev artwork)

The `makapix-vault` / `makapix-dev-vault` containers are no-op placeholders; no
HTTP server runs inside them.

### URL patterns

Posts, avatars, and blog images now live on the vault subdomain when
`VAULT_PUBLIC_BASE_URL` is set in `.env`:

```
https://vault.makapix.club/{a}/{b}/{storage_key}.{ext}        # artwork
https://vault.makapix.club/avatar/{a}/{b}/{uuid}.{ext}        # avatars
https://vault.makapix.club/blog_image/{a}/{b}/{uuid}.{ext}    # blog
```

Shards are 2-level (`{a}`/`{b}` = low 6 bits of the first two SHA-256 bytes,
hex `00`-`3f`). Legacy 3-level URLs (`{h1}/{h2}/{h3}/...`) keep serving from
twin copies during the resharding dual window (see docs/vault-resharding/).

The legacy `/api/vault/...` path (served by FastAPI StaticFiles) remains live
indefinitely as a backward-compatibility fallback for existing players.

### Features

- **HTTPS + HTTP, no auto-redirect**: browsers use HTTPS, players keep HTTP
- **Direct file serving**: Caddy `file_server`, no Python in the hot path
- **CORS**: `Access-Control-Allow-Origin: *`
- **CORP**: `Cross-Origin-Resource-Policy: cross-origin` (so the divoom-import
  page, which sets COEP `require-corp`, can load these images)
- **Immutable cache**: `Cache-Control: public, max-age=31536000, immutable`
  (filenames are UUID-keyed and content-addressed)
- **Compression**: gzip
- **Security headers**: `X-Content-Type-Options: nosniff`, `X-Robots-Tag: noindex`

### Security considerations

⚠️ **Important**: The vault serves files **without authentication**. This is
intentional and matches the security model of the legacy `/api/vault/...`
mount. Access control for hidden/deleted artworks relies on URL obscurity
(UUIDs are not guessable).

### Access logs

Each vault subdomain writes its own JSON-formatted access log with rotation:

| Subdomain | Log file | Rotation |
|---|---|---|
| `vault.makapix.club` | `/var/log/caddy/vault-access.log` | `roll_size 50mb`, `roll_keep 10`, `roll_keep_for 90d` |
| `vault-dev.makapix.club` | `/var/log/caddy/vault-dev-access.log` | same |

These logs are the canonical record of image downloads. A future PR can build
a daily download-counter rollup on top of them, following the pattern in
`api/app/tasks.py` (`rollup_site_events` reading `view_events` into
`site_stats_daily`).

### Managing the vault

```bash
# Apply site-block changes (after editing caddy/Caddyfile.global)
docker compose restart caddy

# Verify vault is working over both protocols
curl -I https://vault.makapix.club/<shard>/<uuid>.png
curl -I http://vault.makapix.club/<shard>/<uuid>.png   # must NOT redirect

# Tail the vault access log
docker run --rm -v /var/log/caddy:/logs:ro alpine tail -f /logs/vault-access.log
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

- Web builds from `web/` directory using multi-stage Dockerfile
- Certificates are stored in the `caddy_data` Docker volume
- All paths are relative to the monorepo root (`/opt/makapix` on VPS)
- The web image uses Next.js standalone output (~165MB vs ~877MB for dev)

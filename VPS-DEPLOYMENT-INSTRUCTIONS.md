# VPS Deployment Instructions

## Current Architecture

Your VPS is now configured to host **two domains**:

1. **https://makapix.club/** → Static CTA page (makapix-cta container)
2. **https://dev.makapix.club/** → Full dev environment (new makapix stack)

The `caddy-docker-proxy` container manages routing for both domains.

## Step 1: Update Code on VPS

Run these commands on your VPS:

```bash
cd /opt/makapix
git pull origin main
```

## Step 2: Review Current State

Before making changes, let's see what's running:

```bash
# Check running containers
docker ps

# Check if caddy-docker-proxy is running
docker ps | grep caddy
```

Expected containers:
- `caddy` (lucaslorentz/caddy-docker-proxy) - Main reverse proxy ✅ Keep this
- `makapix-cta` - Static CTA site for makapix.club ✅ Keep this
- `makapix-dev` - Old dev site ❌ Will be replaced

## Step 3: Stop Old Dev Container

```bash
# Stop and remove the old dev container
docker stop makapix-dev
docker rm makapix-dev
```

## Step 4: Switch to Remote Environment

```bash
cd /opt/makapix
make remote
```

This command:
- Copies `.env.remote` → `.env`
- Copies `docker-compose.override.remote.yml` → `docker-compose.override.yml`
- Generates Caddy configuration

## Step 5: Verify Environment Configuration

```bash
# Confirm environment is set to remote
cat .env | grep ENVIRONMENT
# Should show: ENVIRONMENT=remote

# Check that GitHub credentials are set
cat .env | grep GITHUB_
```

If GitHub credentials are missing, edit `.env.remote` first, then run `make remote` again.

## Step 6: Start Services

```bash
# Remove old volumes to ensure clean database
docker compose down -v

# Start all services
docker compose up -d

# Check service health
docker compose ps
```

Expected output - all services should show "(healthy)" or "Up":
- makapix-db-1
- makapix-cache-1
- makapix-mqtt-1
- makapix-api-1
- makapix-worker-1
- makapix-web-1

**Note:** The `proxy` service will NOT appear - it's disabled for remote environments.

## Step 7: Verify Routing

```bash
# Check that services are connected to caddy_net
docker network inspect caddy_net | grep -A 3 "makapix"

# View Caddy labels on the web service
docker inspect makapix-web-1 | grep -A 10 Labels
```

Expected labels on `web`:
```
"caddy": "dev.makapix.club"
"caddy.reverse_proxy": "{{upstreams 3000}}"
```

## Step 8: Test the Site

Visit https://dev.makapix.club/ in your browser. You should see the dev environment.

## Step 9: Monitor Logs (if needed)

```bash
# View all logs
docker compose logs -f

# View specific service
docker compose logs -f web
docker compose logs -f api
```

## Troubleshooting

### Issue: Port 80 already in use

**Cause:** Multiple Caddy instances trying to bind to port 80.

**Solution:** The new setup disables the standalone proxy on remote. Verify:

```bash
docker compose ps proxy
# Should show: "disabled" or not appear at all
```

### Issue: Services can't connect to database

**Cause:** Old database volumes with wrong credentials.

**Solution:**
```bash
docker compose down -v  # Remove volumes
docker compose up -d    # Recreate with fresh DB
```

### Issue: 502 Bad Gateway on dev.makapix.club

**Cause:** Caddy can't reach the services.

**Solution:** Verify services are on caddy_net:
```bash
docker network inspect caddy_net
docker compose restart api web
docker restart caddy  # Restart caddy-docker-proxy
```

### Issue: GitHub OAuth/App not working

**Cause:** GitHub App URLs might still be pointing to old endpoints.

**Solution:** Update your GitHub Apps at https://github.com/settings/apps:
1. **Remote GitHub OAuth App:**
   - Homepage URL: `https://dev.makapix.club`
   - Callback URL: `https://dev.makapix.club/auth/github/callback`

2. **Remote GitHub App:**
   - Homepage URL: `https://dev.makapix.club`
   - User authorization callback URL: `https://dev.makapix.club/auth/github/callback`
   - Setup URL: `https://dev.makapix.club/update-installation`

## Architecture Diagram

```
        Internet (ports 80/443)
                 │
                 ▼
        ┌─────────────────┐
        │ caddy-docker-   │
        │     proxy       │
        │ (port routing)  │
        └─────────────────┘
              │     │
              │     └────────────────┐
              │                      │
              ▼                      ▼
    ┌──────────────────┐   ┌─────────────────┐
    │  makapix-cta     │   │ makapix-web-1   │
    │  (static site)   │   │ (Next.js)       │
    └──────────────────┘   └─────────────────┘
      makapix.club              │
                                ▼
                      ┌─────────────────┐
                      │ makapix-api-1   │
                      │ (FastAPI)       │
                      └─────────────────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
              ┌────────┐  ┌────────┐  ┌────────┐
              │   db   │  │ cache  │  │  mqtt  │
              └────────┘  └────────┘  └────────┘
                                │
                                ▼
                          ┌──────────┐
                          │  worker  │
                          └──────────┘
```

## Maintenance Commands

```bash
# View all services
docker compose ps

# Restart a specific service
docker compose restart api

# View service logs
docker compose logs -f api

# Update code and restart
git pull origin main
make remote
docker compose up -d --build

# Clean restart (removes volumes)
docker compose down -v
docker compose up -d
```

## Next Steps

Once dev.makapix.club is working:
1. Test artwork publishing
2. Verify GitHub App integration
3. Monitor logs for any errors
4. Consider setting up monitoring/alerts

## Backup Commands (Emergency)

If something goes wrong and you need to revert:

```bash
# Stop new stack
cd /opt/makapix
docker compose down

# Restart old dev container
docker start makapix-dev

# If old container was removed, check backup
docker ps -a | grep makapix
```


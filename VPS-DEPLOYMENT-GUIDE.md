# VPS Deployment Guide - Using docker-compose.override.remote.yml

This guide explains how Docker Compose override files work and how to deploy your code to the VPS.

## Understanding Docker Compose Override Files

### How It Works

Docker Compose reads multiple files in this order:

1. **docker-compose.yml** (base configuration - always loaded)
2. **docker-compose.override.yml** (environment-specific overrides)

The override file **merges with** and **overrides** settings from the base file.

### Your Setup

```
docker-compose.yml                      # Base config (shared by both environments)
├── docker-compose.override.local.yml   # Local-specific settings
└── docker-compose.override.remote.yml  # VPS-specific settings
```

### What Gets Overridden

**In docker-compose.override.remote.yml:**

```yaml
services:
  api:
    networks:              # OVERRIDES base networks
      - internal
      - caddy_net         # Adds external caddy network
    labels:               # ADDS Caddy routing labels
      caddy: dev.makapix.club
    ports: []             # REMOVES port bindings (accessed via caddy-docker-proxy)

  web:
    networks:              # OVERRIDES base networks
      - internal
      - caddy_net
    labels:               # ADDS Caddy routing labels
      caddy: dev.makapix.club
    ports: []             # REMOVES port bindings

  proxy:
    profiles:
      - disabled          # DISABLES standalone Caddy (not needed on VPS)

networks:
  caddy_net:
    external: true        # ADDS reference to external caddy-docker-proxy network
```

**Key differences:**
- **Local:** Services bind directly to ports 80, 443, 3000, 8000
- **Remote:** Services connect to `caddy_net` and are routed by caddy-docker-proxy

## Prerequisites on VPS

Before deploying, ensure your VPS has:

1. **caddy-docker-proxy running:**
   ```bash
   docker ps | grep caddy
   ```
   Should show: `lucaslorentz/caddy-docker-proxy`

2. **caddy_net network exists:**
   ```bash
   docker network ls | grep caddy_net
   ```

3. **DNS configured:**
   - `dev.makapix.club` points to your VPS IP

4. **Ports 80 and 443 open:**
   ```bash
   sudo ufw status
   ```

## Deployment Steps

### 1. SSH into Your VPS

```bash
ssh user@your-vps-ip
cd /opt/makapix  # or wherever your repo is
```

### 2. Pull Latest Code

```bash
git pull origin main
```

This pulls:
- Code changes
- Updated `docker-compose.yml`
- Updated `docker-compose.override.remote.yml`
- Updated environment templates

### 3. Verify Environment Files

**Check that `.env.remote` exists and is configured:**
```bash
cat .env.remote | head -20
```

Should show:
- `ENVIRONMENT=remote`
- `BASE_URL=https://dev.makapix.club`
- GitHub App credentials (remote)
- Database credentials

**If `.env.remote` doesn't exist or needs updates:**
```bash
# Create from template
cp env.remote.template .env.remote

# Edit with your credentials
nano .env.remote
```

### 4. Switch to Remote Environment

```bash
# Using Makefile (Linux/Mac)
make remote

# Or manually
./scripts/switch-env.sh remote
```

This command:
1. Copies `.env.remote` → `.env`
2. Copies `docker-compose.override.remote.yml` → `docker-compose.override.yml`
3. Generates `proxy/Caddyfile` with remote domain

### 5. Verify the Override File

```bash
cat docker-compose.override.yml | head -30
```

Should show:
- `caddy_net` network connections
- Caddy labels with `dev.makapix.club`
- Empty `ports: []` arrays
- `proxy` service with `profiles: [disabled]`

### 6. Restart Services

```bash
# Stop current services
docker compose down

# Start with new configuration
docker compose up -d

# Watch startup logs
docker compose logs -f
```

Press `Ctrl+C` to stop following logs.

### 7. Verify Deployment

**Check service health:**
```bash
docker compose ps
```

Expected output:
```
NAME              STATUS
repo-api-1        Up X seconds (healthy)
repo-web-1        Up X seconds (healthy)
repo-worker-1     Up X seconds
repo-db-1         Up X seconds (healthy)
repo-cache-1      Up X seconds (healthy)
repo-mqtt-1       Up X seconds (healthy)
```

**Note:** `proxy` service should NOT appear (it's disabled on remote).

**Verify services are on caddy_net:**
```bash
docker network inspect caddy_net --format '{{range .Containers}}{{.Name}} {{end}}'
```

Should include: `repo-api-1` and `repo-web-1`

**Test the site:**
```bash
# From VPS
curl -I https://dev.makapix.club
curl -I https://dev.makapix.club/publish
curl -I https://dev.makapix.club/api/health
```

All should return `200 OK` or `405 Method Not Allowed` (for POST endpoints).

### 8. Visit in Browser

Open in your browser:
- https://dev.makapix.club
- https://dev.makapix.club/publish

Should see your app with valid SSL certificate.

## Common Deployment Issues

### Issue 1: Services Not Accessible (502 Bad Gateway)

**Cause:** Services not connected to `caddy_net`

**Solution:**
```bash
# Verify override file is active
cat docker-compose.override.yml | grep caddy_net

# Should show:
#   - caddy_net

# If not, run:
make remote  # or ./scripts/switch-env.sh remote
docker compose down
docker compose up -d
```

### Issue 2: Port 80 Already in Use

**Cause:** Standalone proxy service is running

**Solution:**
```bash
# Verify proxy is disabled
docker compose ps proxy
# Should show nothing or "disabled"

# If it's running:
cat docker-compose.override.yml | grep -A 3 "proxy:"
# Should show:
#   proxy:
#     profiles:
#       - disabled

# If not:
make remote
docker compose down
docker compose up -d
```

### Issue 3: Wrong Domain in Logs

**Cause:** `.env` file has wrong domain

**Solution:**
```bash
# Check current domain
cat .env | grep BASE_URL
# Should show: BASE_URL=https://dev.makapix.club

# If showing localhost:
make remote  # or ./scripts/switch-env.sh remote
docker compose restart
```

### Issue 4: GitHub OAuth Not Working

**Cause:** GitHub App callback URLs not updated for remote

**Solution:**
1. Go to https://github.com/settings/apps
2. Find your **remote** GitHub App
3. Update URLs:
   - Homepage: `https://dev.makapix.club`
   - Callback: `https://dev.makapix.club/auth/github/callback`
   - Webhook: `https://dev.makapix.club/api/webhooks/github`

### Issue 5: Database Connection Errors

**Cause:** Old database volumes with wrong credentials

**Solution:**
```bash
# Clean restart (removes all volumes)
docker compose down -v
docker compose up -d

# Watch for database initialization
docker compose logs -f db
```

## Daily Deployment Workflow

### Deploying Code Changes

**On your local machine:**
```bash
# Make changes, test locally
git add .
git commit -m "Your changes"
git push origin main
```

**On your VPS:**
```bash
cd /opt/makapix
git pull origin main
make remote              # Ensure remote environment is active
docker compose up -d     # Restart services with new code
```

### Deploying Environment Changes

If you update `.env.remote` or `docker-compose.override.remote.yml`:

```bash
# On VPS
git pull origin main
make remote              # Re-generate .env and override files
docker compose down      # Full restart required
docker compose up -d
```

## Understanding the Network Architecture

### Local Setup (docker-compose.override.local.yml)

```
Browser → localhost:80 → Standalone Caddy → Services
                                          ├─ web:3000
                                          └─ api:8000
```

Services are on `internal` and `proxy` networks (created by docker-compose.yml).

### Remote Setup (docker-compose.override.remote.yml)

```
Browser → dev.makapix.club:443 → caddy-docker-proxy → Services
                                                     ├─ web:3000
                                                     └─ api:8000
```

Services are on `internal` (created by docker-compose.yml) and `caddy_net` (external network).

The `proxy` service is disabled because caddy-docker-proxy handles routing.

## Monitoring and Logs

### View All Logs
```bash
docker compose logs -f
```

### View Specific Service
```bash
docker compose logs -f web
docker compose logs -f api
docker compose logs -f worker
```

### Check Resource Usage
```bash
docker stats
```

### Check Service Health
```bash
docker compose ps
```

## Rollback Procedure

If deployment fails and you need to revert:

### Quick Rollback
```bash
# Go back to previous commit
git log --oneline -5  # Find previous commit hash
git reset --hard <commit-hash>

# Restart services
make remote
docker compose down
docker compose up -d
```

### Emergency Rollback
```bash
# Stop everything
docker compose down

# Go back to last known good state
git reset --hard HEAD~1

# Restart
make remote
docker compose up -d
```

## Advanced: Manual Override File Activation

If you want to manually activate the remote override without using the switch script:

```bash
# Copy override file
cp docker-compose.override.remote.yml docker-compose.override.yml

# Copy environment file
cp .env.remote .env

# Regenerate Caddyfile (if needed)
# The template uses DOMAIN environment variable
envsubst < proxy/Caddyfile.template > proxy/Caddyfile

# Restart services
docker compose down
docker compose up -d
```

**Not recommended:** Use `make remote` instead.

## Security Notes

1. **Never commit `.env` files** - They contain secrets
2. **Use strong database passwords** in `.env.remote`
3. **Rotate JWT secrets** regularly
4. **Keep GitHub App private keys secure**
5. **Monitor logs** for suspicious activity

## Checklist for Successful Deployment

Before deploying:
- [ ] Code changes committed and pushed to Git
- [ ] `.env.remote` configured on VPS
- [ ] caddy-docker-proxy is running on VPS
- [ ] `caddy_net` network exists on VPS
- [ ] DNS points to VPS IP

After deploying:
- [ ] Ran `git pull` on VPS
- [ ] Ran `make remote` on VPS
- [ ] Ran `docker compose up -d` on VPS
- [ ] All services show "(healthy)" in `docker compose ps`
- [ ] Services visible in `docker network inspect caddy_net`
- [ ] Site accessible at https://dev.makapix.club
- [ ] No errors in `docker compose logs`

## Summary

**Key takeaway:** Docker Compose override files allow you to have one base configuration and environment-specific customizations. The remote override connects services to `caddy_net` and adds Caddy routing labels, while the local override keeps services on direct port bindings with a standalone Caddy proxy.

The switch scripts automate this process, ensuring the correct override file and environment variables are active before starting services.

# Deployment Guide

This document covers the deployment of Piskel as part of the Makapix stack.

## Prerequisites

- [x] DNS A record for `piskel.makapix.club` pointing to VPS IP
- [ ] Docker and Docker Compose installed
- [ ] Caddy network exists (`caddy_net`)

## Directory Structure

```
/opt/makapix/
├── apps/
│   └── piskel/              # Customized Piskel source
│       ├── src/
│       ├── Dockerfile
│       ├── package.json
│       └── Gruntfile.js
├── deploy/
│   └── stack/
│       └── docker-compose.yml
└── reference/
    └── piskel/              # Original Piskel source (read-only reference)
```

---

## Step 1: Prepare Piskel Source

```bash
# Copy Piskel source to apps directory
cp -r /opt/makapix/reference/piskel /opt/makapix/apps/piskel

# Navigate to the directory
cd /opt/makapix/apps/piskel

# Install dependencies
npm ci

# Test build locally
npx grunt build

# Verify build output exists
ls -la dest/prod/
```

---

## Step 2: Create Dockerfile

Create `/opt/makapix/apps/piskel/Dockerfile`:

```dockerfile
# =============================================================================
# Piskel Editor - Makapix Integration Build
# =============================================================================
# This Dockerfile builds the Piskel pixel art editor with Makapix-specific
# customizations and serves it via Caddy.
# =============================================================================

# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Install grunt-cli globally for build
RUN npm install -g grunt-cli

# Copy package files first for layer caching
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build production version
RUN grunt build

# Verify build succeeded
RUN test -f dest/prod/index.html || (echo "Build failed: index.html not found" && exit 1)

# =============================================================================
# Production stage - lightweight static file server
# =============================================================================
FROM caddy:2-alpine

# Copy built files from builder
COPY --from=builder /app/dest/prod /srv

# Simple Caddy config for static files
# Note: When using caddy-docker-proxy, this Caddyfile is NOT used.
# The proxy generates config from container labels.
# This is only here for standalone/local testing.
RUN echo ':80 {\n\
    root * /srv\n\
    encode gzip\n\
    file_server\n\
    header X-Content-Type-Options nosniff\n\
}' > /etc/caddy/Caddyfile

EXPOSE 80
```

---

## Step 3: Add to Docker Compose

Add the following service to `/opt/makapix/deploy/stack/docker-compose.yml`:

```yaml
  # ---------------------------------------------------------------------------
  # Piskel Editor - Pixel art editor at piskel.makapix.club
  # ---------------------------------------------------------------------------
  piskel:
    build:
      context: ../../apps/piskel
      dockerfile: Dockerfile
    container_name: makapix-piskel
    restart: unless-stopped
    labels:
      # Caddy auto-routing via label
      caddy: piskel.makapix.club
      caddy.encode: "gzip zstd"
      # Security headers
      caddy.header.X-Content-Type-Options: "nosniff"
      caddy.header.X-Frame-Options: "ALLOW-FROM https://makapix.club"
      caddy.header.Content-Security-Policy: "frame-ancestors 'self' https://makapix.club"
      # Reverse proxy to container's Caddy
      caddy.reverse_proxy: "{{upstreams 80}}"
    networks:
      - caddy_net
```

---

## Step 4: Build and Deploy

```bash
# Navigate to stack directory
cd /opt/makapix/deploy/stack

# Build the Piskel container
docker compose build piskel

# Start the service
docker compose up -d piskel

# Verify it's running
docker ps | grep piskel

# Check logs for any errors
docker logs -f makapix-piskel
```

---

## Step 5: Verify Deployment

### Check Container Health

```bash
# Container should be running
docker ps --filter name=makapix-piskel

# Check Caddy received the config
docker exec caddy caddy list-modules

# View Caddy's generated config
docker exec caddy cat /config/caddy/autosave.json | jq '.apps.http.servers'
```

### Test Endpoints

```bash
# Test direct container access (from VPS)
curl -I http://localhost:$(docker port makapix-piskel 80 | cut -d: -f2)/

# Test via Caddy proxy
curl -I https://piskel.makapix.club/

# Verify index.html loads
curl -s https://piskel.makapix.club/ | head -20
```

### Browser Test

1. Navigate to `https://piskel.makapix.club`
2. Verify SSL certificate is valid
3. Verify Piskel editor loads
4. Check browser console for errors

---

## Step 6: Configure X-Frame-Options

For iframe embedding to work, Piskel must allow being framed by Makapix:

The Caddy label already sets:
```
caddy.header.X-Frame-Options: "ALLOW-FROM https://makapix.club"
caddy.header.Content-Security-Policy: "frame-ancestors 'self' https://makapix.club"
```

**Note**: `X-Frame-Options: ALLOW-FROM` is deprecated in modern browsers. `Content-Security-Policy: frame-ancestors` is the modern replacement and should work.

---

## Updating Piskel

When you need to update Piskel with new customizations:

```bash
cd /opt/makapix/deploy/stack

# Rebuild the container
docker compose build --no-cache piskel

# Restart with new image
docker compose up -d piskel

# Verify the update
docker logs -f makapix-piskel
```

---

## Rollback Procedure

If something goes wrong:

```bash
# Stop Piskel container
docker compose stop piskel

# Remove the container
docker compose rm -f piskel

# Revert code changes in apps/piskel
cd /opt/makapix/apps/piskel
git checkout .  # If tracked by git
# Or restore from reference:
# rm -rf /opt/makapix/apps/piskel
# cp -r /opt/makapix/reference/piskel /opt/makapix/apps/piskel

# Rebuild and restart
docker compose build piskel
docker compose up -d piskel
```

---

## Monitoring

### Logs

```bash
# Follow Piskel container logs
docker logs -f makapix-piskel

# View Caddy access logs for Piskel
docker exec caddy tail -f /var/log/caddy/access.log | grep piskel
```

### Resource Usage

```bash
# Check container stats
docker stats makapix-piskel

# Check disk usage
docker system df
```

---

## SSL Certificate

Caddy automatically provisions SSL certificates for `piskel.makapix.club` via Let's Encrypt:

- Certificates stored in `caddy_data` volume
- Auto-renewal handled by Caddy
- No manual intervention required

If certificate issues occur:

```bash
# Check Caddy logs for ACME errors
docker logs caddy | grep -i acme

# Force certificate renewal
docker exec caddy caddy reload
```

---

## Environment Variables

Currently, Piskel doesn't require environment variables. If needed in the future, add to docker-compose.yml:

```yaml
  piskel:
    environment:
      - MAKAPIX_API_URL=https://makapix.club
```

---

## Production Checklist

Before going live:

- [ ] DNS A record propagated (verify with `dig piskel.makapix.club`)
- [ ] Container builds successfully
- [ ] SSL certificate provisioned
- [ ] Piskel loads in browser
- [ ] X-Frame-Options allows embedding from makapix.club
- [ ] postMessage communication works
- [ ] Makapix /editor page loads iframe correctly
- [ ] Export flow works end-to-end
- [ ] Edit flow works end-to-end

---

## Troubleshooting

### Piskel won't load in iframe

1. Check browser console for X-Frame-Options errors
2. Verify Content-Security-Policy header is set
3. Ensure origin matches exactly (`https://makapix.club`)

### postMessage not working

1. Check both origins are HTTPS
2. Verify origin validation in message handlers
3. Check browser console for blocked messages

### Build fails

```bash
# Check Node.js version
node --version  # Should be 18.x

# Clear npm cache
npm cache clean --force

# Reinstall dependencies
rm -rf node_modules
npm ci

# Try building again
npx grunt build
```

### Container won't start

```bash
# Check logs
docker logs makapix-piskel

# Verify Dockerfile
docker build -t piskel-test ../../apps/piskel

# Run interactively to debug
docker run -it --rm piskel-test sh
```


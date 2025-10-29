# Makapix Production Architecture

This document explains how the Makapix services are organized across domains.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│          caddy-docker-proxy (ports 80/443)             │
│  Manages SSL and routes traffic to all services        │
└─────────────────────────────────────────────────────────┘
           │                              │
           │                              │
           ▼                              ▼
    ┌──────────────┐            ┌─────────────────────┐
    │ makapix-cta  │            │  Makapix Dev Stack  │
    │ Static Site  │            │  (Full Application) │
    └──────────────┘            └─────────────────────┘
           │                              │
           │                              │
  makapix.club                   dev.makapix.club
```

## Domain Configuration

### 1. https://makapix.club/ 
**Purpose:** Static call-to-action page with Discord link

**Services:**
- Container: `makapix-cta`
- Type: Static site (Caddy serving static files)

### 2. https://dev.makapix.club/
**Purpose:** Full development environment for testing new features

**Services (from docker-compose.yml):**
- `api` - FastAPI backend (routed via `/api/*`)
- `web` - Next.js frontend (routed to `/`)
- `worker` - Celery background tasks
- `db` - PostgreSQL database
- `cache` - Redis cache
- `mqtt` - MQTT broker for real-time updates

**Routing:** Handled by caddy-docker-proxy using Docker labels

### 3. http://localhost/
**Purpose:** Local development version of dev.makapix.club

**Services:** Same as dev.makapix.club
**Routing:** Uses standalone Caddy proxy (makapix-proxy-1)
**Note:** HTTP only, no SSL certificates

## Network Configuration

### Remote (VPS)
- Uses `caddy-docker-proxy` container for routing
- Services connected to `caddy_net` external network
- No direct port bindings on api/web services
- SSL certificates managed automatically by Caddy

### Local (Laptop)
- Uses standalone `proxy` service (Caddy)
- Binds to port 80 only (HTTP)
- All services expose ports directly for debugging
- No SSL certificates

## Environment Switching

Use these commands to switch environments:

### Linux/Mac:
```bash
make local    # Switch to localhost
make remote   # Switch to dev.makapix.club
make up       # Start services
```

### Windows (PowerShell):
```powershell
.\dev.ps1 local    # Switch to localhost
.\dev.ps1 remote   # Switch to dev.makapix.club
.\dev.ps1 up       # Start services
```

## Deployment Steps

### Initial VPS Setup
1. Ensure `caddy-docker-proxy` is running:
   ```bash
   docker ps | grep caddy-docker-proxy
   ```

2. Clone the repository:
   ```bash
   cd /opt
   git clone <repository-url> makapix
   cd makapix
   ```

3. Switch to remote environment:
   ```bash
   make remote
   ```

4. Configure environment variables:
   - Edit `.env` and add GitHub credentials
   - Update GitHub OAuth App URLs
   - Update GitHub App URLs

5. Start services:
   ```bash
   docker compose up -d
   ```

### Updating Remote Environment
```bash
cd /opt/makapix
git pull origin main
make remote  # Ensure remote config is active
docker compose up -d --build
```

## GitHub App Configuration

You need TWO GitHub Apps:

### Remote GitHub App (dev.makapix.club)
- Homepage URL: `https://dev.makapix.club`
- User authorization callback URL: `https://dev.makapix.club/auth/github/callback`
- Setup URL: `https://dev.makapix.club/update-installation`

### Local GitHub App (localhost)
- Homepage URL: `http://localhost`
- User authorization callback URL: `http://localhost/auth/github/callback`  
- Setup URL: `http://localhost/update-installation`

## Troubleshooting

### Port 80 already in use
```bash
# Check what's using port 80
sudo lsof -i :80

# If it's old containers:
docker ps -a
docker stop <container-name>
docker rm <container-name>
```

### Database authentication failed
```bash
# Remove volumes and restart
docker compose down -v
docker compose up -d
```

### Services can't connect
```bash
# Check network connectivity
docker network ls
docker network inspect caddy_net

# Restart caddy-docker-proxy
docker restart caddy
```

### Check Caddy configuration
```bash
# View Caddy configuration
docker exec caddy caddy fmt --overwrite /config/caddy/Caddyfile
docker exec caddy cat /config/caddy/Caddyfile
```


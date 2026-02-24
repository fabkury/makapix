# Deployment and Operations

Production deployment, dual-environment setup, backups, monitoring, and troubleshooting.

## Prerequisites

| Requirement | Minimum |
|-------------|---------|
| VPS | 2 vCPU, 2--4 GB RAM, 50+ GB SSD |
| OS | Ubuntu 22.04+ or Debian 12+ |
| Docker | Docker Engine 24+ with Compose V2 |
| DNS | A records for all subdomains (see below) |

### Required DNS Records

| Record | Points To | Used By |
|--------|-----------|---------|
| `makapix.club` | VPS IP | Web app (prod) |
| `www.makapix.club` | VPS IP | Redirect to apex |
| `development.makapix.club` | VPS IP | Web app (dev) |
| `vault.makapix.club` | VPS IP | Artwork serving for players (prod, HTTP) |
| `vault-dev.makapix.club` | VPS IP | Artwork serving for players (dev, HTTP) |
| `piskel.makapix.club` | VPS IP | Piskel editor (prod) |
| `piskel-dev.makapix.club` | VPS IP | Piskel editor (dev) |
| `pixelc.makapix.club` | VPS IP | Pixelc editor (prod) |
| `pixelc-dev.makapix.club` | VPS IP | Pixelc editor (dev) |

---

## Initial Setup

```bash
# Clone the repository
git clone https://github.com/fabkury/makapix.git /opt/makapix
cd /opt/makapix

# Create external Docker resources (shared between environments)
docker network create caddy_net
docker volume create makapix-stack_caddy_data
docker volume create makapix-stack_caddy_config

# Create production database volume
docker volume create makapix_pg_data

# Configure environment
cd deploy/stack
cp .env.example .env.prod
# Edit .env.prod with production secrets (see Environment Configuration below)

# Start all services
cd /opt/makapix
make up
```

For development, clone a second copy:

```bash
git clone -b develop https://github.com/fabkury/makapix.git /opt/makapix-dev
cd /opt/makapix-dev/deploy/stack
cp .env.example .env.dev
# Edit .env.dev with development secrets

# Create dev database volume
docker volume create makapix-dev_pg_data

cd /opt/makapix-dev
make up
```

---

## Environment Configuration

Key environment variables in `deploy/stack/.env.prod` (or `.env.dev`):

| Category | Variable | Description |
|----------|----------|-------------|
| Database | `DB_ADMIN_USER` | PostgreSQL admin username |
| Database | `DB_ADMIN_PASSWORD` | PostgreSQL admin password |
| Database | `DB_API_WORKER_USER` | Application-level DB username |
| Database | `DB_API_WORKER_PASSWORD` | Application-level DB password |
| Database | `DB_DATABASE` | Database name (`makapix`) |
| Auth | `JWT_SECRET_KEY` | JWT signing secret (32+ chars) |
| Auth | `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL (default: 60) |
| Auth | `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL (default: 30) |
| MQTT | `MQTT_PASSWORD` | Backend service MQTT password |
| MQTT | `MQTT_WEBCLIENT_PASSWORD` | Web client MQTT password |
| OAuth | `GITHUB_OAUTH_CLIENT_ID` | GitHub OAuth app client ID |
| OAuth | `GITHUB_OAUTH_CLIENT_SECRET` | GitHub OAuth app client secret |
| GitHub App | `GITHUB_APP_ID` | GitHub App numeric ID |
| GitHub App | `GITHUB_APP_PRIVATE_KEY` | GitHub App private key (PEM) |
| Email | `RESEND_API_KEY` | Resend transactional email key |
| Email | `RESEND_FROM_EMAIL` | Sender address |
| Admin | `MAKAPIX_ADMIN_USER` | Site owner account handle |
| Admin | `MAKAPIX_ADMIN_PASSWORD` | Site owner account password |
| Vault | `VAULT_LOCATION` | Container-internal vault path |
| Vault | `VAULT_HOST_PATH` | Host vault path (e.g. `/mnt/vault-1`) |
| Caddy | `ACME_EMAIL` | Let's Encrypt ACME email |
| IDs | `SQIDS_ALPHABET` | Sqids alphabet (**never change after go-live**) |

See [security/operations.md](security/operations.md) for the full secret inventory and rotation procedures.

---

## Service Architecture

All services are defined in `deploy/stack/docker-compose.yml` with environment-specific overrides.

| Service | Image / Build | Purpose | Networks |
|---------|---------------|---------|----------|
| db | `postgres:17-alpine` | Primary database | internal |
| cache | `redis:7-alpine` | API cache, Celery broker | internal |
| mqtt | `mqtt/Dockerfile` | Mosquitto broker (MQTT + WebSocket) | internal, caddy_net |
| api | `api/Dockerfile` | FastAPI backend | internal, caddy_net |
| worker | `worker/Dockerfile` | Celery background tasks | internal |
| web | `web/Dockerfile` | Next.js frontend | caddy_net |
| caddy | `lucaslorentz/caddy-docker-proxy` | Reverse proxy, auto-TLS | caddy_net |
| vault | `alpine:latest` | Dummy container for Caddy file_server labels | caddy_net |
| www-redirect | `alpine:latest` | www -> apex redirect (prod only) | caddy_net |
| piskel | `apps/piskel/Dockerfile` | Piskel pixel art editor | caddy_net |
| pixelc | `/opt/Pixelc/Dockerfile` | Pixelc pixel art editor | caddy_net |
| redis | `redis:7-alpine` | Edge rate limiting | caddy_net |

### Networks

- **internal** -- Backend services only (db, cache, api, worker, mqtt). Not externally reachable.
- **caddy_net** -- External network shared between all environments. Caddy discovers containers via Docker labels.

### Ports

| Port | Service | Environment |
|------|---------|-------------|
| 80, 443 | Caddy | Shared (both envs) |
| 1883, 8883 | MQTT | Production |
| 1884, 8884 | MQTT | Development |
| 5433 | PostgreSQL | Development (localhost only) |

---

## Dual-Environment Setup

Both environments run on the same VPS, sharing the Caddy reverse proxy and `caddy_net` network. Everything else is isolated.

| Resource | Production | Development |
|----------|-----------|-------------|
| Directory | `/opt/makapix` | `/opt/makapix-dev` |
| Branch | `main` | `develop` |
| Domain | `makapix.club` | `development.makapix.club` |
| DB Volume | `makapix_pg_data` | `makapix-dev_pg_data` |
| Vault | `/mnt/vault-1` | `/mnt/vault-dev` |
| Env file | `.env.prod` | `.env.dev` |
| MQTT mTLS | Port 8883 | Port 8884 |
| Compose project | `makapix-prod` | `makapix-dev` |

### Makefile Auto-Detection

The `Makefile` auto-detects the environment based on the working directory:

- `/opt/makapix` -> production compose command with `-f docker-compose.prod.yml --env-file .env.prod -p makapix-prod`
- Anything else -> development compose command with `-f docker-compose.dev.yml --env-file .env.dev -p makapix-dev`

### Caddy Sharing

Caddy runs only in the production compose stack. The dev override disables it via a `disabled` profile. Both stacks connect to the shared `caddy_net` external network, so Caddy discovers containers from both environments via Docker labels.

The dev web frontend adds HTTP Basic Auth for most pages (except auth-related routes) and sets `X-Robots-Tag: noindex, nofollow` to prevent indexing.

---

## TLS / Certificates

### HTTPS (Caddy)

Caddy obtains and auto-renews TLS certificates via Let's Encrypt. Routing is configured entirely through Docker labels on service containers -- there is no separate Caddyfile to manage. The global config lives at `deploy/stack/caddy/Caddyfile.global`.

### MQTT mTLS

Player devices authenticate via mTLS client certificates. The CA and server certificates are generated by `mqtt/config/scripts/gen-certs.sh`. Certificates are stored in `mqtt/certs/`:

- `ca.key` / `ca.crt` -- Certificate Authority
- `server.key` / `server.crt` -- MQTT broker
- `crl.pem` -- Certificate Revocation List (auto-renewed by Celery task)

Individual player certificates are issued via the API when a device registers, and stored in the database.

---

## Backups

There are no automated backup scripts in the repository. Set up manual or cron-based backups.

### Database Backup

```bash
# Dump the database
cd /opt/makapix/deploy/stack
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file .env.prod -p makapix-prod \
  exec db pg_dump -U postgres_admin -d makapix --format=custom \
  > /backups/makapix-$(date +%Y%m%d_%H%M%S).dump

# Or using the Makefile shorthand (from /opt/makapix)
cd deploy/stack && docker compose exec db pg_dump -U owner -d makapix -Fc > /backups/db.dump
```

### Database Restore

```bash
cd /opt/makapix/deploy/stack
docker compose exec db pg_restore -U postgres_admin -d makapix --clean --if-exists \
  < /backups/makapix-YYYYMMDD.dump
```

### Vault Backup

```bash
# rsync the vault directory
rsync -av /mnt/vault-1/ /backups/vault-1/

# Or tar it
tar -czf /backups/vault-$(date +%Y%m%d).tar.gz -C /mnt vault-1
```

### Crontab Example

```cron
# Daily DB backup at 4 AM UTC
0 4 * * * cd /opt/makapix/deploy/stack && docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.prod -p makapix-prod exec -T db pg_dump -U postgres_admin -d makapix -Fc > /backups/makapix-$(date +\%Y\%m\%d).dump 2>&1 | logger -t makapix-backup

# Weekly vault backup on Sundays at 5 AM UTC
0 5 * * 0 tar -czf /backups/vault-$(date +\%Y\%m\%d).tar.gz -C /mnt vault-1 2>&1 | logger -t makapix-vault-backup

# Delete backups older than 30 days
0 6 * * * find /backups -name "makapix-*.dump" -mtime +30 -delete
```

---

## Updates and Rollback

### Standard Update

From the appropriate directory:

```bash
# Production
cd /opt/makapix
make deploy   # git pull origin main && rebuild

# Development
cd /opt/makapix-dev
make deploy   # git pull origin develop && rebuild
```

`make deploy` pulls the latest code, stops containers, rebuilds images, starts containers, and prunes the Docker build cache.

### Manual Rollback

```bash
cd /opt/makapix
git log --oneline -10          # Find the commit to roll back to
git checkout <commit-hash>     # Check out that commit
make rebuild                   # Rebuild from that commit
```

---

## Monitoring

### Service Health

```bash
make ps                          # Container status
docker compose logs -f           # Live logs (all services)
docker compose logs -f api       # API logs only
curl https://makapix.club/api/health   # API health endpoint
```

### Disk Space

```bash
df -h                            # Filesystem usage
du -sh /mnt/vault-1              # Vault size
docker system df                 # Docker disk usage
```

### Database

```bash
# Database size
docker compose exec db psql -U owner -d makapix -c \
  "SELECT pg_size_pretty(pg_database_size('makapix'));"

# Table sizes
docker compose exec db psql -U owner -d makapix -c \
  "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;"

# Active connections
docker compose exec db psql -U owner -d makapix -c \
  "SELECT count(*) FROM pg_stat_activity;"
```

### Redis

```bash
docker compose exec cache redis-cli INFO memory | grep used_memory_human
docker compose exec cache redis-cli DBSIZE
```

### MQTT

```bash
docker compose logs mqtt --tail=50
# Check connected clients (from within mqtt container)
docker compose exec mqtt mosquitto_sub -h localhost -t '$SYS/broker/clients/connected' -C 1 \
  -u svc_backend -P "$MQTT_PASSWORD"
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check container status and exit codes
make ps
docker compose logs <service> --tail=100

# Common causes:
# - Missing .env file or missing variables
# - Port conflicts (another process using the port)
# - Volume mount failures (directory doesn't exist)
# - Image build failures (check Dockerfile changes)
```

### Database Connection Errors

```bash
# Verify DB is running and healthy
docker compose exec db pg_isready

# Check credentials match .env
docker compose exec db psql -U $DB_API_WORKER_USER -d $DB_DATABASE -c "SELECT 1;"

# Check for connection exhaustion
docker compose exec db psql -U owner -d makapix -c \
  "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"
```

### Disk Space Full

```bash
# Check what's using space
du -sh /mnt/vault-1 /var/lib/docker

# Prune Docker resources
docker system prune -af --volumes
docker builder prune -af

# Check for large log files
du -sh /var/log/caddy/*
```

### SSL Certificate Issues

Caddy auto-renews certificates. If certificates fail:

```bash
# Check Caddy logs for ACME errors
docker compose logs caddy | grep -i "acme\|tls\|certificate"

# Verify DNS resolves correctly
dig makapix.club +short

# Force certificate reload
docker compose restart caddy
```

### High Memory Usage

```bash
# Check per-container memory
docker stats --no-stream

# The dev compose override sets resource limits; prod does not.
# If memory is an issue in prod, add resource limits to docker-compose.prod.yml.
```

### MQTT Connection Issues

```bash
# Check MQTT broker logs
docker compose logs mqtt --tail=50

# Test internal connectivity
docker compose exec api python3 -c "
import paho.mqtt.client as mqtt
c = mqtt.Client()
c.username_pw_set('svc_backend', '$MQTT_PASSWORD')
c.connect('mqtt', 1883, 60)
print('Connected')
c.disconnect()
"
```

---

## Useful Commands Reference

| Command | Description |
|---------|-------------|
| `make up` | Start all services |
| `make down` | Stop all services |
| `make rebuild` | Rebuild and restart |
| `make deploy` | Pull latest + rebuild |
| `make logs` | Tail all logs |
| `make logs-api` | Tail API logs |
| `make logs-web` | Tail web logs |
| `make logs-db` | Tail database logs |
| `make ps` | Show container status |
| `make test` | Run API tests |
| `make shell-api` | Shell into API container |
| `make shell-db` / `make db.shell` | PostgreSQL interactive shell |
| `make fmt` | Format Python code (Black) |
| `make clean` | Remove all containers and volumes (destructive) |

See also: [development.md](development.md) for day-to-day development workflow.

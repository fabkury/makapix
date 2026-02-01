# Finalized Dual-Environment Migration Plan

This document contains the complete, finalized plan for migrating Makapix to a dual-environment architecture. All architectural decisions have been made and no open questions remain.

---

## 1. Goals

| Goal | Description |
|------|-------------|
| **EA (Production)** | Serves live website at `https://makapix.club/` |
| **EB (Development)** | Serves development website at `https://development.makapix.club/` |
| **Access Control** | Only developers can access EB (HTTP Basic Auth) |
| **Complete Isolation** | Separate databases, vault storage, MQTT brokers, Redis instances |
| **Atomic Deployment** | Changes tested on EB can be deployed to EA with minimal downtime |

---

## 2. Final Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  Single VPS                                      │
├────────────────────────────────────┬────────────────────────────────────────────┤
│       EA (Production)              │           EB (Development)                  │
│       makapix.club                 │       development.makapix.club              │
├────────────────────────────────────┼────────────────────────────────────────────┤
│  makapix-prod-db      (PostgreSQL) │  makapix-dev-db      (PostgreSQL)           │
│  makapix-prod-cache   (Redis)      │  makapix-dev-cache   (Redis)                │
│  makapix-prod-api     (FastAPI)    │  makapix-dev-api     (FastAPI)              │
│  makapix-prod-worker  (Celery)     │  makapix-dev-worker  (Celery)               │
│  makapix-prod-web     (Next.js)    │  makapix-dev-web     (Next.js)              │
│  makapix-prod-mqtt    (Mosquitto)  │  makapix-dev-mqtt    (Mosquitto)            │
│  makapix-prod-vault   (HTTP files) │  makapix-dev-vault   (HTTP files)           │
│  /mnt/vault-1/                     │  /mnt/vault-dev/                            │
│  Port 8883 (MQTT mTLS)             │  Port 8884 (MQTT mTLS)                      │
├────────────────────────────────────┴────────────────────────────────────────────┤
│                         Shared: Caddy (reverse proxy, TLS)                       │
│                         Network: caddy_net (external)                            │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Architectural Decisions (Finalized)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Docker Compose Structure** | Overrides (base + .prod.yml + .dev.yml) | Less duplication, easier to maintain consistency |
| **Database Isolation** | Separate PostgreSQL containers | Complete isolation, independent backups, no shared connection pool |
| **MQTT Isolation** | Separate Mosquitto brokers | EA on port 8883, EB on port 8884; no risk of cross-environment messages |
| **Developer Access to EB** | HTTP Basic Auth | Simple, effective; Caddy handles auth before requests reach app |
| **Data Sampling** | On-demand script | Manual control over when to refresh EB data from EA |
| **GitHub OAuth** | Separate OAuth app for EB | Proper isolation; requires registering new app on GitHub |
| **Resource Limits** | Medium (40% of VPS for EB) | Max 2 CPU cores, 2GB RAM total for EB; protects EA performance |
| **Development Vault** | vault-dev.makapix.club | Separate subdomain for HTTP access by physical player devices |

---

## 4. DNS Requirements

The following DNS records must exist (A records pointing to VPS IP):

| Subdomain | Purpose | Status |
|-----------|---------|--------|
| `makapix.club` | Production website | Exists |
| `vault.makapix.club` | Production vault (HTTP for players) | Exists |
| `development.makapix.club` | Development website | **Exists** |
| `vault-dev.makapix.club` | Development vault (HTTP for players) | **To be created** |

---

## 5. File Structure After Migration

```
/opt/makapix/
├── deploy/
│   └── stack/
│       ├── docker-compose.yml           # Base configuration (shared)
│       ├── docker-compose.prod.yml      # Production overrides
│       ├── docker-compose.dev.yml       # Development overrides
│       ├── .env.prod                    # Production environment variables
│       ├── .env.dev                     # Development environment variables
│       └── Caddyfile                    # Caddy configuration (if not using labels)
├── scripts/
│   ├── sample-data-to-dev.py           # On-demand data sampling script
│   ├── sync-vault-to-dev.sh            # Vault file synchronization
│   ├── deploy-to-prod.sh               # "Flip the switch" deployment script
│   └── backup-prod.sh                  # Production backup script
└── ...
```

---

## 6. Migration Phases

### Phase 1: Prepare Docker Compose Structure

**Goal**: Refactor existing docker-compose.yml to support parameterization.

**Tasks**:
1. Parameterize container names using `${COMPOSE_PROJECT_NAME:-makapix}` pattern
2. Parameterize volume names
3. Parameterize environment-specific values (domains, database names)
4. Create `docker-compose.prod.yml` with production-specific overrides
5. Create `docker-compose.dev.yml` with development-specific overrides and resource limits
6. Create `.env.prod` (copy of current `.env` with explicit production values)
7. Create `.env.dev` with development-specific values

**Deliverables**:
- Modified `docker-compose.yml`
- New `docker-compose.prod.yml`
- New `docker-compose.dev.yml`
- New `.env.prod`
- New `.env.dev`

---

### Phase 2: Configure Caddy for Dual Routing

**Goal**: Single Caddy instance routes traffic to correct environment based on domain.

**Tasks**:
1. Update Caddy labels/configuration to handle both domains
2. Add HTTP Basic Auth for `development.makapix.club`
3. Add `X-Robots-Tag: noindex, nofollow` header for development
4. Configure `vault-dev.makapix.club` routing
5. Generate HTTP Basic Auth credentials file

**Caddy Configuration Requirements**:

```
makapix.club {
    # Production routing (existing)
}

development.makapix.club {
    basic_auth {
        # Developer credentials (hashed)
    }
    header X-Robots-Tag "noindex, nofollow"
    # Development routing
}

vault.makapix.club {
    # Production vault (HTTP, no TLS for IoT devices)
}

vault-dev.makapix.club {
    basic_auth {
        # Same developer credentials
    }
    # Development vault (HTTP)
}
```

**Deliverables**:
- Updated Caddy configuration
- `.htpasswd` or equivalent credentials file
- Documentation for adding/removing developer access

---

### Phase 3: Create Development Environment

**Goal**: EB stack running alongside EA.

**Tasks**:
1. Create DNS record for `vault-dev.makapix.club`
2. Create `/mnt/vault-dev/` directory
3. Start EB stack with `docker compose -p makapix-dev`
4. Verify EB services are running
5. Verify Caddy routes correctly to EB
6. Test HTTP Basic Auth is working

**Commands**:
```bash
# Create vault directory
sudo mkdir -p /mnt/vault-dev
sudo chown 1000:1000 /mnt/vault-dev

# Start development environment
cd /opt/makapix/deploy/stack
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  --env-file .env.dev -p makapix-dev up -d

# Verify
docker compose -p makapix-dev ps
curl -u developer:password https://development.makapix.club/api/health
```

**Deliverables**:
- Running EB stack
- Verified routing and auth

---

### Phase 4: Migrate Production to New Structure

**Goal**: EA runs using the new parameterized compose structure.

**Tasks**:
1. Create production database backup
2. Stop current production stack
3. Start EA with new compose structure
4. Verify EA is working correctly
5. Monitor for issues

**Commands**:
```bash
# Backup
docker compose exec db pg_dump -U owner makapix > /backups/makapix-$(date +%Y%m%d-%H%M%S).sql

# Stop old stack
cd /opt/makapix/deploy/stack
docker compose down

# Start with new structure
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file .env.prod -p makapix-prod up -d

# Verify
docker compose -p makapix-prod ps
curl https://makapix.club/api/health
```

**Deliverables**:
- EA running with new structure
- Verified functionality

---

### Phase 5: Data Sampling Tooling

**Goal**: Script to populate EB database with sample of EA data.

**Tasks**:
1. Create `scripts/sample-data-to-dev.py` script
2. Create `scripts/sync-vault-to-dev.sh` script
3. Test sampling with small percentage first
4. Document usage

**Sampling Script Requirements**:
- Select 10% of users randomly (configurable)
- Copy all posts by sampled users
- Copy comments/reactions on those posts
- Copy follows within sampled user set
- Anonymize emails: `user{id}@dev.makapix.local`
- Regenerate/invalidate auth tokens
- Preserve user handles and content for realistic testing
- Handle foreign key dependencies correctly

**Vault Sync Requirements**:
- Only copy files for posts that exist in EB database
- Copy both original and upscaled variants
- Preserve directory structure

**Deliverables**:
- `scripts/sample-data-to-dev.py`
- `scripts/sync-vault-to-dev.sh`
- Usage documentation

---

### Phase 6: MQTT Configuration

**Goal**: Separate MQTT brokers for EA and EB.

**Tasks**:
1. Configure EA MQTT on port 8883 (existing)
2. Configure EB MQTT on port 8884
3. Generate separate certificates for EB MQTT (if using mTLS)
4. Update firewall to allow port 8884
5. Test player device connectivity to EB MQTT

**Deliverables**:
- EB MQTT broker running on port 8884
- Firewall rules updated
- Player connectivity verified

---

### Phase 7: GitHub OAuth for Development

**Goal**: Separate OAuth app for EB.

**Manual Steps** (user must do):
1. Go to GitHub Developer Settings > OAuth Apps > New OAuth App
2. Application name: `Makapix Development`
3. Homepage URL: `https://development.makapix.club`
4. Authorization callback URL: `https://development.makapix.club/api/auth/github/callback`
5. Copy Client ID and Client Secret to `.env.dev`

**Deliverables**:
- New GitHub OAuth app registered
- `.env.dev` updated with credentials

---

### Phase 8: Operational Scripts

**Goal**: Scripts for common operations.

**Scripts to Create**:

1. **`scripts/deploy-to-prod.sh`** - Deploy tested changes from EB to EA
   - Runs tests on EB
   - Creates EA backup
   - Pulls latest code
   - Rebuilds EA containers
   - Runs migrations
   - Verifies health
   - Provides rollback instructions

2. **`scripts/backup-prod.sh`** - Backup production database
   - Creates timestamped SQL dump
   - Rotates old backups (keep last 7)

3. **Makefile updates** - Add new targets:
   - `make up-prod` / `make up-dev`
   - `make down-prod` / `make down-dev`
   - `make logs-prod` / `make logs-dev`
   - `make sample-data` (run sampling script)
   - `make deploy-prod` (run deploy script)

**Deliverables**:
- All scripts created
- Makefile updated
- Documentation

---

## 7. Configuration Details

### 7.1 Environment Variables (.env.dev)

```bash
# Project
COMPOSE_PROJECT_NAME=makapix-dev

# Domain
ROOT_DOMAIN=development.makapix.club
WEB_DOMAIN=development.makapix.club
BASE_URL=https://development.makapix.club
NEXT_PUBLIC_API_BASE_URL=https://development.makapix.club

# Database
DB_HOST=makapix-dev-db
DB_DATABASE=makapix
DB_ADMIN_USER=owner
DB_API_WORKER_USER=api_worker
# (passwords should differ from production)

# Redis
REDIS_HOST=makapix-dev-cache

# Vault
VAULT_HOST_PATH=/mnt/vault-dev
VAULT_DOMAIN=vault-dev.makapix.club

# MQTT
MQTT_HOST=makapix-dev-mqtt
MQTT_PUBLIC_HOST=development.makapix.club
MQTT_PUBLIC_PORT=8884

# JWT (different from production for security)
JWT_SECRET_KEY=dev-secret-key-not-for-production

# GitHub OAuth (separate app)
GITHUB_OAUTH_CLIENT_ID=<dev-client-id>
GITHUB_OAUTH_CLIENT_SECRET=<dev-client-secret>
GITHUB_REDIRECT_URI=https://development.makapix.club/api/auth/github/callback

# Email (use dev sender or disable)
RESEND_FROM_EMAIL=noreply@dev.makapix.club

# Environment flag
ENVIRONMENT=development
```

### 7.2 Resource Limits (docker-compose.dev.yml)

```yaml
services:
  db:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 768M

  cache:
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 128M

  api:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 384M

  worker:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M

  web:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M

  mqtt:
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 64M

  vault:
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 64M

# Total EB limits: ~2 CPU cores, ~1.9GB RAM (within 40% target)
```

### 7.3 HTTP Basic Auth Credentials

Generate credentials using `caddy hash-password`:

```bash
# Generate password hash
docker run --rm caddy:2-alpine caddy hash-password --plaintext 'your-secure-password'

# Store in Caddyfile or environment
# Format: username hashed_password
```

Recommended: Create a shared `.htpasswd` file for all developers, or use Caddy's `basicauth` directive with hashed passwords.

---

## 8. Deployment Workflow

### 8.1 Developer Workflow

1. Make code changes locally
2. Push to feature branch
3. SSH to VPS, checkout branch in `/opt/makapix`
4. Rebuild EB: `make rebuild-dev`
5. Test at `https://development.makapix.club/`
6. If database changes needed, run migrations on EB first
7. Connect player devices to EB MQTT (port 8884) for testing
8. When satisfied, merge to main branch
9. Run `make deploy-prod` to deploy to EA

### 8.2 Deploy to Production (Flip the Switch)

```bash
#!/bin/bash
# scripts/deploy-to-prod.sh

set -e

echo "=== Deploying to Production ==="

# 1. Run tests on development
echo "Running tests on EB..."
docker compose -p makapix-dev exec api pytest
if [ $? -ne 0 ]; then
    echo "Tests failed! Aborting deployment."
    exit 1
fi

# 2. Backup production
echo "Creating production backup..."
./scripts/backup-prod.sh

# 3. Pull latest code
echo "Pulling latest code..."
git pull origin main

# 4. Rebuild production
echo "Rebuilding production containers..."
cd /opt/makapix/deploy/stack
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file .env.prod -p makapix-prod up -d --build

# 5. Run migrations
echo "Running migrations..."
docker compose -p makapix-prod exec api alembic upgrade head

# 6. Verify health
echo "Verifying health..."
sleep 5
curl -f https://makapix.club/api/health || {
    echo "Health check failed! Consider rollback."
    exit 1
}

echo "=== Deployment Complete ==="
```

### 8.3 Rollback Procedure

```bash
# 1. Stop production
docker compose -p makapix-prod down

# 2. Revert code
git checkout HEAD~1

# 3. Restore database if needed
cat /backups/makapix-YYYYMMDD-HHMMSS.sql | \
  docker compose -p makapix-prod exec -T db psql -U owner makapix

# 4. Start with previous code
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file .env.prod -p makapix-prod up -d --build
```

---

## 9. Security Considerations

| Concern | Mitigation |
|---------|------------|
| Production data in EB | Emails anonymized, auth tokens invalidated during sampling |
| EB accessible to public | HTTP Basic Auth required for all EB endpoints |
| Search engine indexing | `X-Robots-Tag: noindex` header + robots.txt |
| Shared VPS resources | Resource limits prevent EB from impacting EA |
| Different JWT secrets | EB tokens won't work on EA and vice versa |
| MQTT isolation | Separate brokers, separate ports, separate credentials |

---

## 10. Monitoring Recommendations

After migration, monitor:

| Metric | Alert Threshold |
|--------|-----------------|
| EA API latency P99 | > 500ms |
| EA database connections | > 80% of pool |
| EA disk usage | > 80% |
| EB container resource usage | Exceeding limits |
| Certificate expiration | < 14 days |

---

## 11. Checklist Summary

### Pre-Migration
- [ ] DNS record for `vault-dev.makapix.club` created
- [ ] GitHub OAuth app for development registered
- [ ] HTTP Basic Auth credentials generated
- [ ] Backup strategy confirmed

### Phase 1: Docker Compose
- [ ] `docker-compose.yml` parameterized
- [ ] `docker-compose.prod.yml` created
- [ ] `docker-compose.dev.yml` created
- [ ] `.env.prod` created
- [ ] `.env.dev` created

### Phase 2: Caddy
- [ ] Caddy configuration updated for dual routing
- [ ] HTTP Basic Auth configured
- [ ] X-Robots-Tag header added
- [ ] vault-dev routing configured

### Phase 3: Start EB
- [ ] `/mnt/vault-dev/` created
- [ ] EB stack started
- [ ] Routing verified
- [ ] Basic Auth working

### Phase 4: Migrate EA
- [ ] Production backup created
- [ ] EA restarted with new structure
- [ ] Functionality verified

### Phase 5: Data Sampling
- [ ] `sample-data-to-dev.py` created
- [ ] `sync-vault-to-dev.sh` created
- [ ] Initial data sampling completed

### Phase 6: MQTT
- [ ] EB MQTT on port 8884
- [ ] Firewall rule added
- [ ] Player connectivity tested

### Phase 7: OAuth
- [ ] GitHub OAuth app registered
- [ ] `.env.dev` updated

### Phase 8: Operations
- [ ] `deploy-to-prod.sh` created
- [ ] `backup-prod.sh` created
- [ ] Makefile updated
- [ ] Documentation complete

---

## 12. Estimated Disk Space

| Component | EA (Current) | EB (New) |
|-----------|--------------|----------|
| PostgreSQL data | ~2GB | ~200MB (10% sample) |
| Vault files | ~50GB | ~5GB (10% sample) |
| Container images | Shared | Shared |
| Logs | ~1GB | ~200MB |

**Additional space needed for EB**: ~6GB

---

## 13. Post-Migration Verification

After all phases complete:

1. **EA Smoke Test**
   - Browse https://makapix.club/
   - Login with existing account
   - Create a post
   - Check MQTT notifications working

2. **EB Smoke Test**
   - Browse https://development.makapix.club/ (with Basic Auth)
   - Login with GitHub (new OAuth app)
   - Create a post
   - Connect player device to port 8884
   - Verify vault files accessible at vault-dev.makapix.club

3. **Deployment Test**
   - Make trivial change on EB
   - Run deploy-to-prod.sh
   - Verify change appears on EA

---

*Document finalized: Ready for implementation*

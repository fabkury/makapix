# Technical Implementation Considerations

This document details the technical challenges and approaches for implementing the dual-environment architecture.

---

## 1. Docker Compose Structure

### Option A: Separate Compose Files

```
deploy/
├── stack/
│   ├── docker-compose.yml          (production)
│   └── .env
└── stack-dev/
    ├── docker-compose.yml          (development)
    └── .env
```

**Pros**: Complete isolation, independent management
**Cons**: Duplication, configuration drift

### Option B: Compose Overrides (Recommended)

```
deploy/stack/
├── docker-compose.yml              (base config)
├── docker-compose.prod.yml         (production overrides)
├── docker-compose.dev.yml          (development overrides)
├── .env.prod
└── .env.dev
```

**Usage:**
```bash
# Production
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file .env.prod -p makapix-prod up -d

# Development
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
  --env-file .env.dev -p makapix-dev up -d
```

### Required Changes in docker-compose.yml

```yaml
# Container names must be parameterized
services:
  db:
    container_name: ${COMPOSE_PROJECT_NAME:-makapix}-db

  api:
    container_name: ${COMPOSE_PROJECT_NAME:-makapix}-api

# Volume names must be parameterized
volumes:
  pg_data:
    name: ${COMPOSE_PROJECT_NAME:-makapix}_pg_data
```

---

## 2. Network Isolation

### Current State

- `internal` network: Backend services (db, cache, api, worker)
- `caddy_net`: External network (must be pre-created)

### Required Changes

**Option A: Separate External Networks**

```yaml
# docker-compose.prod.yml
networks:
  caddy_net:
    external: true
    name: caddy_net_prod

# docker-compose.dev.yml
networks:
  caddy_net:
    external: true
    name: caddy_net_dev
```

This requires running **two Caddy instances** (one per environment).

**Option B: Shared Caddy (Recommended)**

Single Caddy instance routes based on subdomain:

```yaml
# In docker-compose.yml (base)
services:
  web:
    labels:
      caddy: ${WEB_DOMAIN:-makapix.club}

  api:
    labels:
      caddy: ${WEB_DOMAIN:-makapix.club}
      caddy.@api.path: /api/*
```

Both environments connect to the same `caddy_net`, but Caddy routes by domain.

---

## 3. Database Configuration

### Approach: Two PostgreSQL Containers

```yaml
# docker-compose.prod.yml
services:
  db:
    volumes:
      - pg_data_prod:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: makapix

# docker-compose.dev.yml
services:
  db:
    volumes:
      - pg_data_dev:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: makapix_dev
```

### Alternative: Single PostgreSQL, Separate Databases

```yaml
services:
  db:
    # Single container, both databases
    volumes:
      - pg_data:/var/lib/postgresql/data

# Production API connects to: makapix
# Development API connects to: makapix_dev
```

**Trade-off**: Simpler management, but shared resources and no complete isolation.

---

## 4. Data Sampling Script

### Requirements

1. Select 10% of users randomly
2. Copy all related data (posts, comments, reactions, etc.)
3. Anonymize sensitive information
4. Handle foreign key dependencies
5. Copy corresponding vault files

### Implementation Outline

```python
#!/usr/bin/env python3
"""
Sample production data to development database.
Run with: python scripts/sample_to_dev.py
"""

import random
from sqlalchemy import create_engine, text

def sample_users(prod_engine, sample_rate=0.10):
    """Select random sample of user IDs."""
    with prod_engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
        sample_size = int(total * sample_rate)

        # Get random sample
        users = conn.execute(text("""
            SELECT id FROM users
            WHERE NOT banned_until IS NOT NULL
            ORDER BY RANDOM()
            LIMIT :limit
        """), {"limit": sample_size}).fetchall()

    return [u[0] for u in users]

def copy_with_anonymization(prod_engine, dev_engine, user_ids):
    """Copy users with anonymized data."""
    with prod_engine.connect() as prod_conn:
        with dev_engine.begin() as dev_conn:
            # Disable FK constraints
            dev_conn.execute(text("SET session_replication_role = 'replica'"))

            # Copy users with anonymized emails
            dev_conn.execute(text("""
                INSERT INTO users (id, handle, email, ...)
                SELECT id, handle,
                       'user' || id || '@dev.makapix.local' as email,
                       ...
                FROM dblink('production', 'SELECT * FROM users WHERE id = ANY(:ids)')
                AS t(id int, handle text, email text, ...)
            """), {"ids": user_ids})

            # Copy related tables...

            # Re-enable FK constraints
            dev_conn.execute(text("SET session_replication_role = 'origin'"))
```

### Tables to Copy (in order)

1. **users** (root entity, anonymize email)
2. **auth_identities** (regenerate password hashes)
3. **posts** (all posts by sampled users)
4. **comments** (on sampled posts + by sampled users)
5. **reactions** (on sampled posts + by sampled users)
6. **follow** (within sampled users only)
7. **social_notifications** (within sampled users)
8. **view_events** (on sampled posts, anonymize IPs)
9. **post_stats_daily** (for sampled posts)
10. **badge_grants** (for sampled users)
11. **players** (for sampled users, regenerate certs)

### Foreign Key Strategy

```sql
-- Option 1: Include referenced users (expands sample)
WITH sampled AS (
    SELECT id FROM users ORDER BY RANDOM() LIMIT 1000
),
referenced AS (
    SELECT DISTINCT f.following_id
    FROM follow f
    WHERE f.follower_id IN (SELECT id FROM sampled)
)
SELECT * FROM sampled UNION SELECT * FROM referenced;

-- Option 2: Allow NULL references (simpler)
ALTER TABLE comments ALTER COLUMN user_id DROP NOT NULL;
-- Copy data, then restore constraint where possible
```

---

## 5. Vault File Synchronization

### Directory Structure

```
Production: /mnt/vault-1/
Development: /mnt/vault-dev/
```

### Sync Script

```bash
#!/bin/bash
# sync-vault.sh - Copy artwork files for sampled posts

SAMPLED_POSTS_FILE="/tmp/sampled_post_storage_keys.txt"
PROD_VAULT="/mnt/vault-1"
DEV_VAULT="/mnt/vault-dev"

# Generate list from database
psql makapix_dev -t -c "
    SELECT storage_shard || '/' || storage_key || '.' || format
    FROM posts
" > "$SAMPLED_POSTS_FILE"

# Copy each file
while read -r filepath; do
    src="$PROD_VAULT/$filepath"
    dst="$DEV_VAULT/$filepath"

    if [[ -f "$src" ]]; then
        mkdir -p "$(dirname "$dst")"
        cp "$src" "$dst"

        # Also copy upscaled variant if exists
        upscaled="${src%.*}_upscaled.webp"
        if [[ -f "$upscaled" ]]; then
            cp "$upscaled" "${dst%.*}_upscaled.webp"
        fi
    fi
done < "$SAMPLED_POSTS_FILE"
```

### Storage Estimation

- If production vault is 50GB and 10% of posts are sampled
- Development vault needs ~5GB
- Plan for 2x safety margin: 10GB

---

## 6. Caddy Configuration

### Subdomain Routing

```yaml
# Production containers
services:
  web-prod:
    labels:
      caddy: makapix.club
      caddy.reverse_proxy: "{{upstreams 3000}}"

  api-prod:
    labels:
      caddy: makapix.club
      caddy.@api.path: /api/*
      caddy.handle_0.handle_path.reverse_proxy: "{{upstreams 8000}}"

# Development containers
services:
  web-dev:
    labels:
      caddy: development.makapix.club
      caddy.reverse_proxy: "{{upstreams 3000}}"

  api-dev:
    labels:
      caddy: development.makapix.club
      caddy.@api.path: /api/*
      caddy.handle_0.handle_path.reverse_proxy: "{{upstreams 8000}}"
```

### Crawler Blocking (Development)

```yaml
services:
  web-dev:
    labels:
      caddy: development.makapix.club
      # Block crawlers via robots.txt
      caddy.@robots.path: /robots.txt
      caddy.handle_0.respond: |
        User-agent: *
        Disallow: /
      # Add noindex header
      caddy.header.X-Robots-Tag: "noindex, nofollow"
```

---

## 7. MQTT Configuration

### Option A: Separate MQTT Containers (Recommended)

```yaml
services:
  mqtt-prod:
    ports:
      - "8883:8883"    # Production mTLS
    environment:
      - MQTT_TOPIC_PREFIX=makapix

  mqtt-dev:
    ports:
      - "8884:8883"    # Development mTLS (different port)
    environment:
      - MQTT_TOPIC_PREFIX=makapix-dev
```

### Option B: Shared MQTT with Topic Namespacing

```python
# In api/app/mqtt/publisher.py
TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "makapix")

def publish_new_post(post_id):
    topic = f"{TOPIC_PREFIX}/posts/new"
    # ...
```

**Risk**: Misconfiguration could cause cross-environment message leakage.

---

## 8. OAuth Configuration

### GitHub OAuth Apps

Each environment needs its own GitHub OAuth app:

| Environment | Client ID | Callback URL |
|-------------|-----------|--------------|
| Production | `Ov23li...` | `https://makapix.club/api/auth/github/callback` |
| Development | `Ov23xx...` | `https://development.makapix.club/api/auth/github/callback` |

### Environment Variables

```bash
# .env.prod
GITHUB_OAUTH_CLIENT_ID=Ov23likuVKQD2QXX82bE
GITHUB_REDIRECT_URI=https://makapix.club/api/auth/github/callback

# .env.dev
GITHUB_OAUTH_CLIENT_ID=Ov23xxDEVELOPMENT
GITHUB_REDIRECT_URI=https://development.makapix.club/api/auth/github/callback
```

---

## 9. Environment-Specific Settings

### .env.dev Differences

```bash
# Domain
ROOT_DOMAIN=development.makapix.club
WEB_DOMAIN=development.makapix.club
BASE_URL=https://development.makapix.club
NEXT_PUBLIC_API_BASE_URL=https://development.makapix.club

# Database (different name)
DB_DATABASE=makapix_dev

# Vault (different path)
VAULT_HOST_PATH=/mnt/vault-dev
VAULT_DOMAIN=vault-dev.makapix.club

# MQTT (different port or prefix)
MQTT_PUBLIC_PORT=8884
MQTT_TOPIC_PREFIX=makapix-dev

# JWT (should differ for security)
JWT_SECRET_KEY=dev-only-secret-key-different-from-prod

# Email (use test mode or different sender)
RESEND_FROM_EMAIL=noreply@dev-notification.makapix.club

# Environment flag
ENVIRONMENT=development
```

---

## 10. "Flip the Switch" Deployment Process

### Step 1: Ensure EB is Stable

```bash
# Run tests on development
docker compose -p makapix-dev exec api pytest

# Check for migration issues
docker compose -p makapix-dev exec api alembic check
```

### Step 2: Backup Production

```bash
# Database backup
docker compose -p makapix-prod exec db \
  pg_dump -U owner makapix > backup-$(date +%Y%m%d).sql

# Note current image digests
docker compose -p makapix-prod images --format json > images-before.json
```

### Step 3: Apply to Production

```bash
# Pull latest code (same repo, different project name)
git pull origin main

# Rebuild production
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file .env.prod -p makapix-prod up -d --build

# Run migrations
docker compose -p makapix-prod exec api alembic upgrade head

# Verify
docker compose -p makapix-prod ps
```

### Step 4: Rollback if Needed

```bash
# Restore database
cat backup-20240115.sql | docker compose -p makapix-prod exec -T db \
  psql -U owner makapix

# Revert to previous images
docker compose -p makapix-prod down
git checkout HEAD~1
docker compose -p makapix-prod up -d --build
```

---

## 11. Resource Limits

### Docker Compose Resource Constraints

```yaml
# docker-compose.dev.yml
services:
  api-dev:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          memory: 256M

  db-dev:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G

  web-dev:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
```

### PostgreSQL Tuning

```yaml
# Lower resource usage for dev database
services:
  db-dev:
    command:
      - postgres
      - -c
      - shared_buffers=128MB
      - -c
      - work_mem=4MB
      - -c
      - max_connections=50
```

---

## 12. Monitoring Recommendations

### Metrics to Track

| Metric | Purpose |
|--------|---------|
| Container CPU/Memory | Detect resource contention |
| Database connections | Ensure pool limits respected |
| Disk usage per vault | Monitor storage growth |
| Request latency (prod) | Detect dev impact on prod |
| Error rates | Catch environment-specific issues |

### Alerting Thresholds

- Production API latency P99 > 500ms
- Production database connections > 80% of pool
- Disk usage > 80% on either vault
- Development containers using > allocated limits

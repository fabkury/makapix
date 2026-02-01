# Infrastructure & Deployment Security Audit

## Overview

Makapix Club is deployed as a containerized application stack using Docker Compose with Caddy as a reverse proxy, PostgreSQL for data storage, and Redis for caching.

---

## Positive Security Controls ✅

### 1. Database Access Control
**Status:** ✅ Good

**Location:** `db/init-users.sh`

```sql
-- Create separate API worker role with limited privileges
CREATE ROLE "$DB_API_WORKER_USER" WITH LOGIN PASSWORD '$DB_API_WORKER_PASSWORD';
GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO "$DB_API_WORKER_USER";
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "$DB_API_WORKER_USER";
```

**Findings:**
- Separate admin and worker database users
- Worker user has minimal required privileges (no DROP, CREATE, etc.)
- No superuser access for application

### 2. Network Isolation
**Status:** ✅ Good

**Location:** `docker-compose.yml`

```yaml
networks:
  internal:
    driver: bridge
  proxy:
    driver: bridge
  caddy_net:
    external: true
```

**Findings:**
- Services separated into internal and proxy networks
- Database and cache only accessible from internal network
- Public access only through reverse proxy

### 3. HTTPS Configuration
**Status:** ✅ Good

**Location:** `deploy/stack/docker-compose.yml`

```yaml
caddy:
  image: lucaslorentz/caddy-docker-proxy
  environment:
    - ACME_AGREE=true
```

**Findings:**
- Automatic HTTPS via Let's Encrypt
- HSTS headers configured (max-age=31536000)
- HTTP automatically redirected to HTTPS

### 4. Container Security
**Status:** ✅ Good

**Findings:**
- Using official Alpine-based images (smaller attack surface)
- No privileged containers
- Read-only mounts where appropriate (`:ro` suffix)
- Health checks configured for all services

### 5. Logging Configuration
**Status:** ✅ Good

**Location:** `deploy/stack/docker-compose.yml:43-50`

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "50m"
    max-file: "10"
```

**Findings:**
- Log rotation configured
- Size limits prevent disk exhaustion
- JSON format for structured logging

---

## Issues Identified

### [H3] Vault HTTP Subdomain Serves Files Without Authentication
**Severity:** 🟠 HIGH

**Location:** `deploy/stack/docker-compose.yml:79-118`

**Issue:** The vault subdomain (http://vault.makapix.club) serves artwork files over plain HTTP without authentication. While intended for IoT devices with limited TLS capabilities, this creates security considerations.

**Current Configuration:**
```yaml
vault:
  labels:
    # HTTP-only subdomain for vault files (http:// prefix = no HTTPS)
    caddy: http://${VAULT_DOMAIN:-vault.makapix.club}
    caddy.file_server: "*"
    caddy.root: "* /srv/vault"
    caddy.header.Access-Control-Allow-Origin: "*"
```

**Security Implications:**
1. Files transmitted without encryption (can be intercepted)
2. No authentication required (relies on URL obscurity)
3. Hidden/deleted artworks still accessible via direct URL
4. CORS allows any origin

**Mitigation Options:**
1. **Signed URLs:** Generate time-limited signed URLs for vault access
2. **Player-specific tokens:** Require bearer token in request header
3. **IP allowlisting:** If players have static IPs, restrict access
4. **Monitoring:** Log and alert on unusual access patterns

**Current Risk Level:** The URL structure uses hashed paths (`/a1/b2/c3/{uuid}.png`) which provides some obscurity, but this is not security.

---

### Environment Variable Security

**Location:** `.env.example`

**Review Required:**

| Variable | Status | Notes |
|----------|--------|-------|
| `POSTGRES_PASSWORD` | ⚠️ | Ensure strong password in production |
| `JWT_SECRET_KEY` | ⚠️ | Must be cryptographically random |
| `DB_API_WORKER_PASSWORD` | ⚠️ | Ensure different from admin password |
| `GITHUB_APP_PRIVATE_KEY` | ⚠️ | Securely store RSA private key |

**Recommendation:** Use a secrets manager (Docker Secrets, HashiCorp Vault, or cloud provider secrets) for production deployments.

---

### Service Exposure

**Port Mapping Analysis:**

| Port | Service | Exposure | Recommendation |
|------|---------|----------|----------------|
| 80, 443 | Caddy | Public | ✅ Required |
| 8883 | MQTT (mTLS) | Public | ✅ Required for devices |
| 5432 | PostgreSQL | Internal only | ✅ Good - not exposed |
| 6379 | Redis | Internal only | ✅ Good - not exposed |
| 8000 | API | Internal only | ✅ Proxied via Caddy |
| 3000 | Web | Internal only | ✅ Proxied via Caddy |
| 1883 | MQTT (no TLS) | Docker network | ⚠️ Internal API use only |

**Note:** Port 1883 (MQTT without TLS) is for internal API communication within the Docker network. Verify it's not exposed to host.

---

## Production Deployment Checklist

### Pre-Launch Verification

- [ ] **Secrets Management**
  - [ ] JWT_SECRET_KEY is cryptographically random (32+ bytes)
  - [ ] Database passwords are strong and unique
  - [ ] GitHub App private key is securely stored
  - [ ] Secrets not committed to version control

- [ ] **Network Configuration**
  - [ ] Only required ports exposed to internet (80, 443, 8883)
  - [ ] Database not accessible from outside Docker network
  - [ ] Redis not accessible from outside Docker network

- [ ] **HTTPS/TLS**
  - [ ] Let's Encrypt certificates auto-renewing
  - [ ] HSTS header configured
  - [ ] TLS 1.2 minimum enforced

- [ ] **Monitoring & Logging**
  - [ ] Log aggregation configured
  - [ ] Alerting for service failures
  - [ ] Disk space monitoring
  - [ ] Certificate expiry monitoring

### Backup & Recovery

- [ ] **Database Backups**
  - [ ] Automated daily backups configured
  - [ ] Backups stored off-server
  - [ ] Restore procedure tested

- [ ] **Vault Backups**
  - [ ] Artwork files backed up
  - [ ] Backup retention policy defined

---

## Container Image Security

### Base Image Analysis

| Service | Base Image | Recommendation |
|---------|------------|----------------|
| API | Python (custom) | Consider distroless |
| Web | Node (custom) | Consider distroless |
| Database | postgres:17-alpine | ✅ Official, minimal |
| Cache | redis:7.2-alpine | ✅ Official, minimal |
| Proxy | caddy:2 | ✅ Official |
| MQTT | Eclipse Mosquitto | ✅ Official |

### Recommendations

1. **Image Scanning:** Add vulnerability scanning to CI/CD pipeline
2. **Version Pinning:** Pin specific image versions (not just tags)
3. **Non-root Users:** Verify containers run as non-root where possible

---

## Recommendations Summary

| Priority | Action |
|----------|--------|
| Pre-Launch | Review all production secrets |
| Pre-Launch | Verify network isolation (database not exposed) |
| Pre-Launch | Consider vault access controls |
| Post-Launch | Implement secrets rotation |
| Post-Launch | Add container vulnerability scanning |
| Post-Launch | Set up log aggregation and alerting |

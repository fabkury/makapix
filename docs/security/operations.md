# Security Operations

Secret management, rotation procedures, hardening, and maintenance checklists.

## Secret Inventory

### Environment Variables (`deploy/stack/.env.prod` or `.env.dev`)

| Variable | Purpose | Rotation |
|----------|---------|----------|
| `JWT_SECRET_KEY` | JWT access token signing | 90 days |
| `DB_ADMIN_PASSWORD` | PostgreSQL admin user | 90 days |
| `DB_API_WORKER_PASSWORD` | PostgreSQL application user | 90 days |
| `MQTT_PASSWORD` | MQTT backend service auth | 90 days |
| `MQTT_WEBCLIENT_PASSWORD` | MQTT web client auth | 90 days |
| `MAKAPIX_ADMIN_PASSWORD` | Site owner account | 90 days |
| `GITHUB_OAUTH_CLIENT_SECRET` | GitHub OAuth login | 180 days |
| `GITHUB_APP_PRIVATE_KEY` | GitHub App integration | 365 days |
| `RESEND_API_KEY` | Transactional email (Resend) | 180 days |

### File-Based Secrets

| File | Purpose | Rotation |
|------|---------|----------|
| `mqtt/config/passwords` | Mosquitto password file (bcrypt hashed) | Updated when MQTT passwords rotate |
| `mqtt/certs/ca.key` | MQTT CA private key | Only on compromise |
| `mqtt/certs/ca.crt` | MQTT CA certificate | Only on compromise |
| `mqtt/certs/server.key` | MQTT server private key | 365 days |
| `mqtt/certs/server.crt` | MQTT server certificate | 365 days |
| `mqtt/certs/crl.pem` | Certificate revocation list | Auto-renewed within 7 days of expiry |

### Hardcoded Values (Require Code Change)

| Location | What | Notes |
|----------|------|-------|
| `web/src/lib/mqtt-client.ts` | MQTT webclient credentials | Open finding H1 -- should migrate to per-session tokens |

### Critical: DO NOT ROTATE

**`SQIDS_ALPHABET`** -- Defined in `.env`. Changing this value breaks ALL existing canonical URLs for posts and users. This is not a secret; it must remain stable after go-live.

---

## Rotation Procedures

### JWT Secret Key

Rotating invalidates all access tokens. Refresh tokens (opaque, not JWT) remain valid.

```bash
cd /opt/makapix/deploy/stack
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

NEW_JWT=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
sed -i "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$NEW_JWT/" .env

docker compose restart api worker
docker compose ps
curl https://makapix.club/api/health
```

Users auto-refresh on next request. Access tokens expire within 60 minutes.

### Database Credentials

Rotate admin and worker passwords separately.

**Admin password:**

```bash
cd /opt/makapix/deploy/stack
source .env

NEW_PASS=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
docker compose exec db psql -U "$DB_ADMIN_USER" -d "$DB_DATABASE" -c \
  "ALTER USER $DB_ADMIN_USER WITH PASSWORD '$NEW_PASS';"
sed -i "s/DB_ADMIN_PASSWORD=.*/DB_ADMIN_PASSWORD=$NEW_PASS/" .env
```

**Worker password:**

```bash
NEW_PASS=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
docker compose exec db psql -U "$DB_ADMIN_USER" -d "$DB_DATABASE" -c \
  "ALTER USER $DB_API_WORKER_USER WITH PASSWORD '$NEW_PASS';"
sed -i "s/DB_API_WORKER_PASSWORD=.*/DB_API_WORKER_PASSWORD=$NEW_PASS/" .env

docker compose restart api worker
```

### MQTT Backend Password

```bash
cd /opt/makapix/deploy/stack
source .env

NEW_MQTT=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
mosquitto_passwd -b /opt/makapix/mqtt/config/passwords svc_backend "$NEW_MQTT"
sed -i "s/MQTT_PASSWORD=.*/MQTT_PASSWORD=$NEW_MQTT/" .env

docker compose restart mqtt api worker
```

### MQTT Webclient Password

Requires code change and frontend rebuild:

```bash
NEW_WC=$(openssl rand -base64 16 | tr -d "=+/" | cut -c1-16)

# 1. Update password file
mosquitto_passwd -b /opt/makapix/mqtt/config/passwords webclient "$NEW_WC"

# 2. Update env var (used by Next.js at build time)
sed -i "s/MQTT_WEBCLIENT_PASSWORD=.*/MQTT_WEBCLIENT_PASSWORD=$NEW_WC/" .env

# 3. Rebuild web service and restart
cd /opt/makapix/deploy/stack
docker compose build --no-cache web
docker compose restart web mqtt
```

### OAuth Client Secret (GitHub)

1. Go to GitHub > Settings > Developer settings > OAuth Apps
2. Generate a new client secret (keep old one active during transition)
3. Update `.env`:
   ```bash
   sed -i "s/GITHUB_OAUTH_CLIENT_SECRET=.*/GITHUB_OAUTH_CLIENT_SECRET=$NEW_SECRET/" .env
   docker compose restart api
   ```
4. Test OAuth login, then delete old secret from GitHub

### Admin Account Password

```bash
NEW_ADMIN=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)

# Update via API (if logged in)
curl -X POST https://makapix.club/api/auth/change-password \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"current_password":"OLD","new_password":"'"$NEW_ADMIN"'"}'

# Update seed value in .env
sed -i "s/MAKAPIX_ADMIN_PASSWORD=.*/MAKAPIX_ADMIN_PASSWORD=$NEW_ADMIN/" .env
```

### TLS Certificates

**HTTPS (Caddy):** Auto-renewed via Let's Encrypt. No manual action needed.

**MQTT CA rotation (destructive -- only on compromise):**

```bash
cd /opt/makapix/mqtt/certs
cp ca.key ca.key.backup.$(date +%Y%m%d)
cp ca.crt ca.crt.backup.$(date +%Y%m%d)

openssl req -x509 -nodes -days 365 \
  -subj "/CN=Makapix CA $(date +%Y)" \
  -newkey rsa:4096 -keyout ca.key -out ca.crt -sha256

docker compose exec mqtt /mosquitto/config/scripts/gen-certs.sh
docker compose restart mqtt
```

This invalidates ALL player certificates. All devices must re-register.

### Resend API Key

1. Create new key at https://resend.com/api-keys
2. Update `.env`:
   ```bash
   sed -i "s/RESEND_API_KEY=.*/RESEND_API_KEY=$NEW_KEY/" .env
   docker compose restart api
   ```
3. Test email delivery, then delete old key from Resend dashboard

---

## Emergency Rotation

### Priority Order

| Priority | Secrets | Deadline |
|----------|---------|----------|
| Critical | DB credentials, JWT secret, admin password | Within 1 hour |
| High | MQTT backend password, OAuth client secret | Within 4 hours |
| Medium | GitHub App key, TLS certificates | Within 24 hours |

### Session Revocation

Force all users to re-authenticate:

```bash
docker compose exec db psql -U $DB_ADMIN_USER -d $DB_DATABASE -c \
  "UPDATE refresh_tokens SET revoked = true WHERE revoked = false;"
```

### Incident Response Steps

1. Rotate the compromised credential using procedures above
2. Revoke all active sessions (SQL above)
3. Review access logs: `docker compose logs api --since 24h | grep -i "401\|403\|500"`
4. Document: what was exposed, when, how, actions taken
5. Notify affected users if personal data was at risk

---

## Open Security Findings

Unresolved findings from the January 2026 security audit:

| ID | Severity | Finding | Status | Remediation |
|----|----------|---------|--------|-------------|
| H1 | High | Shared webclient MQTT credentials | Open | Implement per-session MQTT tokens via Redis |
| M1 | Medium | JWT refresh tokens 30-day expiry | Open | Consider reducing to 7-14 days |
| M2 | Medium | MQTT certs 365-day validity | Open | Consider reducing to 180 days |
| M3 | Medium | Player cert private keys stored in DB | Open | Consider filesystem or HSM storage |
| M5 | Medium | CSP allows `unsafe-inline` for OAuth | Open | Implement nonce-based CSP |
| L1 | Low | No account lockout after failed attempts | Open | Add Redis-backed lockout |
| L2 | Low | No automated monitoring for failed auth | Open | Add alerting on auth failure spikes |
| L3 | Low | No automated security scanning in CI | Open | Add `pip-audit` / `npm audit` to CI |

### Webclient Privacy Concern

The `webclient` MQTT account can subscribe to `makapix/social-notifications/#`, which covers ALL users' social notifications. The ACL restricts webclient to read-only, but the wildcard scope is broader than necessary. Per-session tokens (H1 fix) would also resolve this by scoping subscriptions per user.

---

## MQTT Hardening

The following Mosquitto settings are recommended but **not yet applied** to `mqtt/config/mosquitto.conf`:

```
max_connections 2000
max_inflight_messages 20
max_queued_messages 100
max_queued_bytes 1048576
max_packet_size 65536
persistent_client_expiration 1d
```

These mitigate connection flooding, message queue exhaustion, and resource abuse. See `_docs/dos-attack/RECOMMENDATIONS.md` for full analysis.

### Port Exposure

In the dev compose override, port 1883 (internal MQTT) is mapped to host port 1884 for debugging. In production, this port should NOT be exposed to the host -- it should only be accessible within the Docker internal network.

---

## Security Headers

Implemented in `api/app/middleware.py` (`SecurityHeadersMiddleware`):

| Header | Value |
|--------|-------|
| X-Content-Type-Options | `nosniff` |
| X-Frame-Options | `DENY` |
| X-XSS-Protection | `1; mode=block` |
| Referrer-Policy | `strict-origin-when-cross-origin` |
| Permissions-Policy | `geolocation=(), microphone=(), camera=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()` |
| Strict-Transport-Security | `max-age=31536000; includeSubDomains; preload` (HTTPS only) |
| Content-Security-Policy | `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'` |

The `RequestIdMiddleware` adds an `X-Request-Id` header (8-char UUID) to every response for audit trail correlation.

---

## Scheduled Maintenance

### Quarterly (Every 90 Days)

- [ ] Rotate JWT secret
- [ ] Rotate database passwords (admin + worker)
- [ ] Rotate MQTT backend password
- [ ] Rotate admin account password
- [ ] Review access logs for anomalies
- [ ] Update dependencies (`pip-audit`, `npm audit`)
- [ ] Document in rotation audit log

### Monthly

- [ ] Check certificate expiration: `docker compose logs caddy | grep cert`
- [ ] Review failed auth attempts: `docker compose logs api | grep "401\|403" | tail -100`
- [ ] Check disk space: `df -h`
- [ ] Review service health: `docker compose ps`

### Weekly

- [ ] Check for service errors: `docker compose logs --since 168h | grep -i "error\|fatal"`
- [ ] Verify backups exist and are recent
- [ ] Check MQTT broker status: `docker compose logs mqtt --tail=50`

---

## Verification Commands

Quick checks after any rotation:

```bash
# Service health
docker compose ps

# API health
curl https://makapix.club/api/health

# Log errors
docker compose logs --tail=100 | grep -i "error\|fail\|denied"

# Test authentication
curl -X POST https://makapix.club/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass"}'

# MQTT backend connectivity
docker compose logs api --tail=20 | grep -i "mqtt.*connect"

# Database connectivity
docker compose exec db psql -U $DB_API_WORKER_USER -d $DB_DATABASE -c "SELECT 1;"

# Redis connectivity
docker compose exec cache redis-cli PING
```

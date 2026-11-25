# Security Operations

Secret management, rotation procedures, hardening, and maintenance checklists.

Commands below target production. Define this helper once; its absolute paths keep the selected stack stable even when a procedure changes directories:

```bash
mpxprod() {
  docker compose --project-directory /opt/makapix/deploy/stack \
    -f /opt/makapix/deploy/stack/docker-compose.yml \
    -f /opt/makapix/deploy/stack/docker-compose.prod.yml \
    --env-file /opt/makapix/deploy/stack/.env.prod -p makapix-prod "$@"
}
```

Environment substitutions come from `.env.prod`; some services also read `.env`. Reconcile both sources for the setting you change, as described in [Deployment](../deployment.md#environment-configuration). Changing an environment file requires container recreation; `restart` alone does not reload container environment variables.

## Secret Inventory

### Environment Variables (`deploy/stack/.env.prod` or `.env.dev`)

| Variable | Purpose | Rotation |
|----------|---------|----------|
| `JWT_SECRET_KEY` | JWT access token signing | 90 days |
| `DB_ADMIN_PASSWORD` | PostgreSQL admin user | 90 days |
| `DB_API_WORKER_PASSWORD` | PostgreSQL application user | 90 days |
| `MQTT_PASSWORD` | MQTT backend service auth | 90 days |
| `MAKAPIX_ADMIN_PASSWORD` | Site owner account | 90 days |
| `GITHUB_OAUTH_CLIENT_SECRET` | GitHub OAuth login | 180 days |
| `RESEND_API_KEY` | Transactional email (Resend) | 180 days |

### File-Based Secrets

| File | Purpose | Rotation |
|------|---------|----------|
| `mqtt/config/passwords` | Mosquitto password file (bcrypt hashed) | Updated when MQTT passwords rotate |
| `mqtt/certs/ca.key` | MQTT CA private key | Only on compromise |
| `mqtt/certs/ca.crt` | MQTT CA certificate | Renew before expiry; coordinate device trust updates |
| `mqtt/certs/server.key` | MQTT server private key | 365 days |
| `mqtt/certs/server.crt` | MQTT server certificate | 365 days |
| `mqtt/certs/crl.pem` | Certificate revocation list | Auto-renewed within 7 days of expiry |

### Critical: DO NOT ROTATE

**`SQIDS_ALPHABET`** -- Defined in `.env`. Changing this value breaks ALL existing canonical URLs for posts and users. This is not a secret; it must remain stable after go-live.

---

## Rotation Procedures

### JWT Secret Key

Rotating the signing key invalidates existing access tokens. Opaque refresh tokens remain valid unless separately revoked.

1. Back up the relevant environment files securely.
2. Generate a fresh random signing secret and update `JWT_SECRET_KEY` in every environment source used by the production API.
3. Recreate the services so they receive the new environment:

```bash
mpxprod up -d --force-recreate api worker
mpxprod ps
curl https://makapix.club/api/health
```

Verify login and refresh. The default access-token lifetime is 60 minutes; the server can override it.

### Database Credentials

Rotate the admin and application roles separately. Changing an environment variable does not change the password of an existing PostgreSQL role.

1. Open an authorized database session and change the intended role's password (for example, with psql's interactive `\password` command).
2. Update the corresponding `DB_ADMIN_PASSWORD` or `DB_API_WORKER_PASSWORD` in the environment sources used by Compose and the services.
3. Recreate affected clients and verify database connectivity before rotating the next role:

```bash
mpxprod up -d --force-recreate api worker
```

Keep the role names and database name from your installation's configuration; do not assume the example usernames apply to every host.

### MQTT Backend Password

Update the `svc_backend` entry in the broker password file and the `MQTT_PASSWORD` used by its clients together. Use the installed Mosquitto password tooling, preserving the file's permissions. Then recreate the broker and clients:

```bash
mpxprod up -d --force-recreate mqtt api worker
```

Verify both broker authentication and player request/response traffic.

### MQTT Webclient Password

**Removed 2026-08:** the browser MQTT path was retired
(docs/notification-architecture/): the `webclient` broker account, the
WebSocket listener, and the bundled `NEXT_PUBLIC_MQTT_WEBCLIENT_PASSWORD`
were all deleted; the web consumes the bearer-authenticated SSE stream
instead. The old shared password is worthless (the account no longer
exists), so no rotation is required. This closes finding H1 by deletion.

### OAuth Client Secret (GitHub)

1. Go to GitHub > Settings > Developer settings > OAuth Apps
2. Generate a new client secret (keep old one active during transition)
3. Update `GITHUB_OAUTH_CLIENT_SECRET` in the API's environment sources, then run `mpxprod up -d --force-recreate api`.
4. Test OAuth login, then delete old secret from GitHub

### Admin Account Password

```bash
NEW_ADMIN=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)

# Update via API (if logged in)
curl -X POST https://makapix.club/api/v1/auth/change-password \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"current_password":"OLD","new_password":"'"$NEW_ADMIN"'"}'

# Update seed value in .env
sed -i "s/MAKAPIX_ADMIN_PASSWORD=.*/MAKAPIX_ADMIN_PASSWORD=$NEW_ADMIN/" .env
```

### TLS Certificates

**HTTPS (Caddy):** Auto-renewed via Let's Encrypt. No manual action needed.

**MQTT certificates:** Check certificate expiry and distinguish renewing a certificate with the existing CA key from replacing that key. Replacing the CA trust anchor affects every device and requires a coordinated recovery plan. Preserve backups of the existing CA material; do not run a CA-generation command as a routine renewal step. For device client certificates, use the [player renewal endpoints](../player/registration.md#certificate-renewal).

### Resend API Key

1. Create new key at https://resend.com/api-keys
2. Update `RESEND_API_KEY` in the API's environment sources, then run `mpxprod up -d --force-recreate api`.
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

Revoke refresh sessions using an authorized database session. Load `DB_ADMIN_USER` and `DB_DATABASE` from the intended installation before using this example. Already-issued access tokens remain valid until expiry unless you also rotate the signing key:

```bash
mpxprod exec db psql -U $DB_ADMIN_USER -d $DB_DATABASE -c \
  "UPDATE refresh_tokens SET revoked = true WHERE revoked = false;"
```

### Incident Response Steps

1. Rotate the compromised credential using procedures above
2. Revoke all active sessions (SQL above)
3. Review access logs: `mpxprod logs api --since 24h | grep -i "401\|403\|500"`
4. Document: what was exposed, when, how, actions taken
5. Notify affected users if personal data was at risk

---

## Historical Security Findings

Historical findings from the January 2026 audit follow. Their original Open labels are not a fresh assessment of the current deployment. Revalidate them against current code and configuration before planning remediation.

| ID | Severity | Finding | Status | Remediation |
|----|----------|---------|--------|-------------|
| H1 | High | Shared webclient MQTT credentials | **Resolved 2026-08** | Browser MQTT path deleted; web on bearer-auth SSE (docs/notification-architecture/) |
| M1 | Medium | JWT refresh tokens 30-day expiry | Open | Consider reducing to 7-14 days |
| M2 | Medium | Certificate lifetime policy | Requires reassessment | Current client certificates last 1095 days; renewal is available within 90 days of expiry |
| M3 | Medium | Player cert private keys stored in DB | Open | Consider filesystem or HSM storage |
| M5 | Medium | CSP allows `unsafe-inline` for OAuth | Open | Implement nonce-based CSP |
| L1 | Low | No account lockout after failed attempts | Open | Add Redis-backed lockout |
| L2 | Low | No automated monitoring for failed auth | Open | Add alerting on auth failure spikes |
| L3 | Low | No automated security scanning in CI | Open | Add `pip-audit` / `npm audit` to CI |

### Webclient Privacy Concern

**Resolved 2026-08 by deletion**: the `webclient` account and the
`makapix/social-notifications/*` topics no longer exist. Social notifications
are delivered per-user over the bearer-authenticated SSE stream
(`docs/http-api/notifications.md`).

---

## MQTT Hardening

The values below are historical tuning suggestions, not a configuration to paste unchanged. In particular, a 65,536-byte packet cap is smaller than the current 128 KiB player response cap; coordinate broker limits with device and API limits before applying them.

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

Plain MQTT is bound to loopback: `127.0.0.1:1883` in production and `127.0.0.1:1884` in development. Public player access uses mTLS on 8883 and 8884 respectively. Preserve these bind addresses when editing the overlays.

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

- [ ] Check certificate expiration: `mpxprod logs caddy | grep cert`
- [ ] Review failed auth attempts: `mpxprod logs api | grep "401\|403" | tail -100`
- [ ] Check disk space: `df -h`
- [ ] Review service health: `mpxprod ps`

### Weekly

- [ ] Check for service errors: `mpxprod logs --since 168h | grep -i "error\|fatal"`
- [ ] Verify backups exist and are recent
- [ ] Check MQTT broker status: `mpxprod logs mqtt --tail=50`

---

## Verification Commands

Quick checks after any rotation:

```bash
# Service health
mpxprod ps

# API health
curl https://makapix.club/api/health

# Log errors
mpxprod logs --tail=100 | grep -i "error\|fail\|denied"

# Test authentication
curl -X POST https://makapix.club/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass"}'

# MQTT backend connectivity
mpxprod logs api --tail=20 | grep -i "mqtt.*connect"

# Database connectivity
mpxprod exec db psql -U $DB_API_WORKER_USER -d $DB_DATABASE -c "SELECT 1;"

# Redis connectivity
mpxprod exec cache redis-cli PING
```

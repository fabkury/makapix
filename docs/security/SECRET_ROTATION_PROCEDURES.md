# Secret Rotation Procedures - Makapix Club

**Document Version:** 1.0  
**Last Updated:** January 16, 2026  
**Purpose:** Comprehensive procedures for rotating all secrets used in Makapix Club platform

## Table of Contents

1. [Overview](#overview)
2. [Rotation Schedule](#rotation-schedule)
3. [Secret Inventory](#secret-inventory)
4. [Rotation Procedures](#rotation-procedures)
   - [JWT Secret Key](#1-jwt-secret-key)
   - [Database Credentials](#2-database-credentials)
   - [MQTT Passwords](#3-mqtt-passwords)
   - [TLS Certificates](#4-tls-certificates)
   - [OAuth Credentials](#5-oauth-credentials)
   - [GitHub App Credentials](#6-github-app-credentials)
   - [Admin Account Password](#7-admin-account-password)
   - [Redis Password](#8-redis-password-optional)
   - [Caddy Admin API](#9-caddy-admin-api-optional)
5. [Emergency Rotation](#emergency-rotation)
6. [Post-Rotation Verification](#post-rotation-verification)
7. [Audit Trail](#audit-trail)

---

## Overview

Secret rotation is a critical security practice that limits the exposure window if credentials are compromised. This document provides step-by-step procedures for rotating all secrets used in the Makapix Club platform.

### Prerequisites

- SSH access to the VPS
- Root or sudo privileges
- Access to GitHub repository settings (for OAuth/App credentials)
- Backup of current `.env` file
- Understanding of Docker Compose operations

### General Principles

1. **Zero Downtime:** Most rotations can be performed without service interruption
2. **Backup First:** Always backup current secrets before rotation
3. **Verify After:** Test service functionality after rotation
4. **Document:** Record rotation in audit log
5. **Coordinate:** Schedule rotations during low-traffic periods when possible

---

## Rotation Schedule

### Recommended Rotation Frequencies

| Secret Type | Rotation Frequency | Priority | Automation Status |
|-------------|-------------------|----------|-------------------|
| JWT Secret Key | 90 days | High | ⚠️ Manual |
| Database Admin Password | 90 days | High | ⚠️ Manual |
| Database Worker Password | 90 days | High | ⚠️ Manual |
| MQTT Backend Password | 90 days | High | ⚠️ Manual |
| MQTT Player Passwords | Per-device lifecycle | Medium | ✅ Automatic |
| TLS Certificates | 365 days (auto-renewal at 30 days) | High | ✅ Automatic |
| OAuth Client Secret | 180 days | Medium | ⚠️ Manual |
| GitHub App Private Key | 365 days | Medium | ⚠️ Manual |
| Admin Account Password | 90 days | Critical | ⚠️ Manual |

### Calendar

Create calendar reminders for:
- **Quarterly (every 90 days):** JWT, Database, MQTT, Admin passwords
- **Bi-annually (every 180 days):** OAuth credentials
- **Annually (every 365 days):** GitHub App key, review all secrets

---

## Secret Inventory

### Environment Variables (`.env` file in `deploy/stack/`)

```bash
# Database credentials
DB_ADMIN_USER=postgres_admin
DB_ADMIN_PASSWORD=<SECRET>
DB_API_WORKER_USER=api_worker
DB_API_WORKER_PASSWORD=<SECRET>
DB_DATABASE=makapix

# JWT authentication
JWT_SECRET_KEY=<SECRET>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# MQTT broker
MQTT_PASSWORD=<SECRET>

# OAuth (GitHub)
GITHUB_OAUTH_CLIENT_ID=<PUBLIC>
GITHUB_OAUTH_CLIENT_SECRET=<SECRET>
GITHUB_REDIRECT_URI=https://dev.makapix.club/auth/github/callback

# GitHub App
GITHUB_APP_ID=<PUBLIC>
GITHUB_APP_CLIENT_ID=<PUBLIC>
GITHUB_APP_SLUG=makapix-club
GITHUB_APP_PRIVATE_KEY=<SECRET>

# Admin account
MAKAPIX_ADMIN_USER=admin
MAKAPIX_ADMIN_PASSWORD=<SECRET>
```

### File-Based Secrets

- **MQTT Password File:** `/opt/makapix/mqtt/config/passwords`
- **TLS Certificates:** `/opt/makapix/mqtt/certs/` (ca.key, ca.crt, server.key, server.crt)
- **CRL File:** `/opt/makapix/mqtt/certs/crl.pem`

---

## Rotation Procedures

### 1. JWT Secret Key

The JWT secret key signs and verifies access tokens. Rotating it will invalidate all existing access tokens (but NOT refresh tokens).

#### Impact Analysis
- **Downtime:** None (gradual rollover)
- **User Impact:** Users will need to refresh tokens on next request
- **Duration:** ~5 minutes

#### Procedure

```bash
# 1. Generate new secret (32+ characters, high entropy)
NEW_JWT_SECRET=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
echo "New JWT secret: $NEW_JWT_SECRET"

# 2. Backup current secret
cd /opt/makapix/deploy/stack
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# 3. Update .env file
sed -i.bak "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$NEW_JWT_SECRET/" .env

# 4. Restart API and worker services
docker compose restart api worker

# 5. Verify services are healthy
docker compose ps
docker compose logs -f api --tail=50

# 6. Test authentication
curl -X POST https://dev.makapix.club/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass"}'
```

#### Rollback

```bash
# If issues occur, restore from backup
cd /opt/makapix/deploy/stack
cp .env.backup.YYYYMMDD_HHMMSS .env
docker compose restart api worker
```

#### Notes
- Existing refresh tokens remain valid (they're opaque, not JWT)
- Access tokens expire within 60 minutes (default)
- Users will automatically get new access tokens on refresh

---

### 2. Database Credentials

Rotating database credentials requires coordinating PostgreSQL user changes with application configuration.

#### Impact Analysis
- **Downtime:** ~2-5 minutes (during restart)
- **User Impact:** Site briefly unavailable during restart
- **Duration:** ~10 minutes

#### Procedure - Admin Password

```bash
# 1. Generate new password
NEW_ADMIN_PASS=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
echo "New admin password: $NEW_ADMIN_PASS"

# 2. Update PostgreSQL password
docker compose exec db psql -U postgres_admin -d makapix -c \
  "ALTER USER postgres_admin WITH PASSWORD '$NEW_ADMIN_PASS';"

# 3. Update .env file
cd /opt/makapix/deploy/stack
sed -i "s/DB_ADMIN_PASSWORD=.*/DB_ADMIN_PASSWORD=$NEW_ADMIN_PASS/" .env

# 4. Test connection
docker compose exec db psql -U postgres_admin -d makapix -c "SELECT 1;"
```

#### Procedure - Worker Password

```bash
# 1. Generate new password
NEW_WORKER_PASS=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
echo "New worker password: $NEW_WORKER_PASS"

# 2. Update PostgreSQL password
docker compose exec db psql -U postgres_admin -d makapix -c \
  "ALTER USER api_worker WITH PASSWORD '$NEW_WORKER_PASS';"

# 3. Update .env file
cd /opt/makapix/deploy/stack
sed -i "s/DB_API_WORKER_PASSWORD=.*/DB_API_WORKER_PASSWORD=$NEW_WORKER_PASS/" .env

# 4. Restart services that use database
docker compose restart api worker

# 5. Verify database connectivity
docker compose logs -f api --tail=50
docker compose exec api python -c "from app.database import engine; print(engine.connect())"
```

#### Notes
- Database users must exist before rotating passwords
- Always rotate worker password separately from admin password
- Coordinate rotation to avoid authentication failures

---

### 3. MQTT Passwords

MQTT has three types of passwords: backend service, player clients, and web clients.

#### Impact Analysis
- **Downtime:** ~2 minutes (during MQTT broker restart)
- **User Impact:** Brief MQTT disconnection (auto-reconnect)
- **Duration:** ~5 minutes

#### Procedure - Backend Service Password

```bash
# 1. Generate new password
NEW_MQTT_PASS=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
echo "New MQTT backend password: $NEW_MQTT_PASS"

# 2. Update password file
cd /opt/makapix/mqtt/config
mosquitto_passwd -b passwords svc_backend "$NEW_MQTT_PASS"

# 3. Update .env file
cd /opt/makapix/deploy/stack
sed -i "s/MQTT_PASSWORD=.*/MQTT_PASSWORD=$NEW_MQTT_PASS/" .env

# 4. Restart MQTT broker and services
docker compose restart mqtt api worker

# 5. Verify MQTT connectivity
docker compose logs -f mqtt --tail=50
docker compose logs -f api --tail=20 | grep -i mqtt
```

#### Procedure - Web Client Password

```bash
# 1. Generate new password (or keep hardcoded for simplicity)
NEW_WEBCLIENT_PASS=$(openssl rand -base64 16 | tr -d "=+/" | cut -c1-16)
echo "New webclient password: $NEW_WEBCLIENT_PASS"

# 2. Update password file
cd /opt/makapix/mqtt/config
mosquitto_passwd -b passwords webclient "$NEW_WEBCLIENT_PASS"

# 3. Update web application configuration
# Edit web/src/contexts/MqttContext.tsx or equivalent
# Update the MQTT connection credentials

# 4. Rebuild and restart web service
cd /opt/makapix/deploy/stack
docker compose build --no-cache web
docker compose restart web mqtt

# 5. Test web MQTT connection
# Open browser, connect to https://dev.makapix.club
# Check browser console for MQTT connection status
```

#### Notes
- **Web client password rotation requires code changes** (currently hardcoded)
- Player passwords rotate automatically on device registration
- Backend password is most critical - rotate quarterly

---

### 4. TLS Certificates

TLS certificates are used for HTTPS (via Caddy) and MQTT (mTLS for players).

#### Impact Analysis
- **Downtime:** None (Caddy auto-renews HTTPS certificates)
- **User Impact:** Players need new certificates on rotation
- **Duration:** Variable (depends on number of players)

#### Procedure - HTTPS Certificates (Caddy)

```bash
# Caddy automatically renews Let's Encrypt certificates
# No manual intervention needed

# To force renewal (if needed):
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile

# Verify certificate status
docker compose exec caddy caddy list-certificates
```

#### Procedure - MQTT CA Certificate (Major Rotation)

**⚠️ WARNING: This invalidates ALL player certificates. Only perform if CA is compromised.**

```bash
# 1. Backup existing CA
cd /opt/makapix/mqtt/certs
cp ca.key ca.key.backup.$(date +%Y%m%d)
cp ca.crt ca.crt.backup.$(date +%Y%m%d)

# 2. Generate new CA
openssl req -x509 -nodes -days 365 \
  -subj "/CN=Makapix CA $(date +%Y)" \
  -newkey rsa:4096 \
  -keyout ca.key \
  -out ca.crt \
  -sha256

# 3. Revoke all existing player certificates
cd /opt/makapix
python3 -c "
from api.app.database import SessionLocal
from api.app.models import Player
from api.app.cert_generator import revoke_certificate

db = SessionLocal()
players = db.query(Player).filter(Player.cert_serial.isnot(None)).all()
for player in players:
    if player.cert_serial:
        revoke_certificate(player.cert_serial)
db.close()
"

# 4. Generate new server certificate
docker compose exec mqtt /mosquitto/config/scripts/gen-certs.sh

# 5. Restart MQTT broker
docker compose restart mqtt

# 6. Notify all player owners to re-register devices
# Send email or in-app notification about certificate rotation

# 7. Players will need to:
#    - Request new registration code
#    - Re-register device with new code
#    - Download new certificates
```

#### Procedure - Individual Player Certificate Rotation

```bash
# Use the API endpoint to rotate individual player certificates
# This is done automatically on device re-registration

# To manually rotate via API:
curl -X POST https://dev.makapix.club/api/player/{player_key}/credentials/rotate \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# Or via database:
cd /opt/makapix
python3 -c "
from api.app.database import SessionLocal
from api.app.cert_generator import issue_player_certificate
from api.app.models import Player

db = SessionLocal()
player = db.query(Player).filter_by(player_key='$PLAYER_KEY').first()
cert_pem, key_pem, serial = issue_player_certificate(player.player_key)
player.cert_pem = cert_pem
player.cert_key = key_pem
player.cert_serial = serial
db.commit()
print(f'Rotated certificate for player {player.player_key}')
db.close()
"
```

#### Notes
- HTTPS certificates auto-renew at 30 days before expiry
- MQTT CA rotation is **destructive** - only for compromises
- Individual player certificates rotate automatically on re-registration
- Consider 180-day validity for production CA certificates

---

### 5. OAuth Credentials

GitHub OAuth credentials allow users to sign in with GitHub accounts.

#### Impact Analysis
- **Downtime:** None (graceful switchover)
- **User Impact:** OAuth login temporarily unavailable during update
- **Duration:** ~5 minutes

#### Procedure

```bash
# 1. Generate new client secret in GitHub
# Go to: https://github.com/settings/developers
# Click on your OAuth App > "Generate a new client secret"
# Copy the new secret immediately (shown only once)

NEW_OAUTH_SECRET="<paste_new_secret_here>"

# 2. Update .env file (keep old secret temporarily)
cd /opt/makapix/deploy/stack
sed -i "s/GITHUB_OAUTH_CLIENT_SECRET=.*/GITHUB_OAUTH_CLIENT_SECRET=$NEW_OAUTH_SECRET/" .env

# 3. Restart API service
docker compose restart api

# 4. Test OAuth login
# Open browser: https://dev.makapix.club/auth/github/login
# Verify successful authentication

# 5. Delete old client secret from GitHub (after verification)
# Go back to GitHub OAuth App settings
# Click "Delete" on the old secret
```

#### Rollback

```bash
# If new secret doesn't work:
cd /opt/makapix/deploy/stack
sed -i "s/GITHUB_OAUTH_CLIENT_SECRET=.*/GITHUB_OAUTH_CLIENT_SECRET=$OLD_SECRET/" .env
docker compose restart api
```

#### Notes
- You can have multiple active client secrets during rotation
- Test thoroughly before deleting old secret
- Update redirect URIs if domain changes

---

### 6. GitHub App Credentials

GitHub App private key is used for installation authentication.

#### Impact Analysis
- **Downtime:** None (graceful switchover)
- **User Impact:** GitHub App features temporarily unavailable
- **Duration:** ~10 minutes

#### Procedure

```bash
# 1. Generate new private key in GitHub
# Go to: https://github.com/settings/apps/your-app-name
# Scroll to "Private keys" section
# Click "Generate a new private key"
# Download the .pem file

# 2. Convert private key to single-line format
NEW_PRIVATE_KEY=$(cat ~/Downloads/your-app.YYYY-MM-DD.private-key.pem | awk '{printf "%s\\n", $0}')

# 3. Update .env file
cd /opt/makapix/deploy/stack
# Manually edit .env file (sed is tricky with multi-line values)
nano .env
# Update: GITHUB_APP_PRIVATE_KEY="$NEW_PRIVATE_KEY"

# 4. Restart API service
docker compose restart api

# 5. Test GitHub App functionality
curl -X GET https://dev.makapix.club/api/auth/github/installations \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# 6. Revoke old private key in GitHub
# Go back to GitHub App settings
# Click "Delete" on the old key
```

#### Notes
- Keep old key active during testing
- GitHub Apps can have multiple active private keys
- Store backup of new key in secure location

---

### 7. Admin Account Password

The admin account has owner-level privileges in the application.

#### Impact Analysis
- **Downtime:** None
- **User Impact:** Admin must use new password
- **Duration:** ~2 minutes

#### Procedure

```bash
# 1. Generate new password
NEW_ADMIN_APP_PASS=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
echo "New admin password: $NEW_ADMIN_APP_PASS"

# 2. Update password via API (if already logged in)
curl -X POST https://dev.makapix.club/api/auth/change-password \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "OLD_PASSWORD",
    "new_password": "'"$NEW_ADMIN_APP_PASS"'"
  }'

# OR update directly in database:
docker compose exec api python3 << EOF
from app.database import SessionLocal
from app.services.auth_identities import update_password
from app.models import User, AuthIdentity

db = SessionLocal()
admin_user = db.query(User).filter_by(handle='admin').first()
identity = db.query(AuthIdentity).filter_by(
    user_id=admin_user.id,
    provider='password'
).first()

update_password(db, identity.id, '$NEW_ADMIN_APP_PASS')
db.commit()
print('Admin password updated')
db.close()
EOF

# 3. Update .env file (for seeding/initialization)
cd /opt/makapix/deploy/stack
sed -i "s/MAKAPIX_ADMIN_PASSWORD=.*/MAKAPIX_ADMIN_PASSWORD=$NEW_ADMIN_APP_PASS/" .env

# 4. Test new password
curl -X POST https://dev.makapix.club/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@makapix.club",
    "password": "'"$NEW_ADMIN_APP_PASS"'"
  }'
```

#### Notes
- Admin account used for system operations
- Store new password in secure password manager
- Consider implementing 2FA for admin account

---

### 8. Redis Password (Optional)

Currently, Redis is used without authentication on internal network. For enhanced security:

#### Impact Analysis
- **Downtime:** ~2 minutes
- **User Impact:** Brief session loss
- **Duration:** ~5 minutes

#### Procedure

```bash
# 1. Generate password
REDIS_PASSWORD=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)
echo "New Redis password: $REDIS_PASSWORD"

# 2. Update docker-compose.yml
cd /opt/makapix/deploy/stack
nano docker-compose.yml

# Add to cache service:
#   command: redis-server --requirepass $REDIS_PASSWORD

# 3. Update .env file
echo "REDIS_PASSWORD=$REDIS_PASSWORD" >> .env

# 4. Update connection strings in .env
sed -i "s|redis://cache:6379|redis://:$REDIS_PASSWORD@cache:6379|g" .env

# 5. Restart services
docker compose restart cache api worker

# 6. Verify connectivity
docker compose exec api python3 -c "
import redis
r = redis.from_url('redis://:$REDIS_PASSWORD@cache:6379/1')
r.ping()
print('Redis connection successful')
"
```

#### Notes
- Redis currently runs without auth (internal network only)
- Adding auth improves defense-in-depth
- Optional but recommended for production

---

### 9. Caddy Admin API (Optional)

Caddy's admin API is exposed on localhost only. To add authentication:

#### Procedure

```bash
# 1. Update docker-compose.yml
cd /opt/makapix/deploy/stack
nano docker-compose.yml

# Add to caddy service environment:
#   - CADDY_ADMIN_PASSWORD=<secret>

# 2. Update Caddy configuration if needed
# Caddy automatically secures admin API when password is set

# 3. Restart Caddy
docker compose restart caddy
```

#### Notes
- Admin API only exposed to localhost (127.0.0.1:2019)
- Additional auth is optional but recommended

---

## Emergency Rotation

If credentials are compromised, perform emergency rotation immediately:

### Priority Order

1. **CRITICAL - Immediate (within 1 hour)**
   - Database credentials (if exposed)
   - JWT secret key (if exposed)
   - Admin account password

2. **HIGH - Urgent (within 4 hours)**
   - MQTT backend password
   - OAuth client secret

3. **MEDIUM - Priority (within 24 hours)**
   - GitHub App private key
   - TLS certificates (if private keys exposed)

### Emergency Procedure

```bash
# 1. Immediately change exposed credential using procedure above
# 2. Review access logs for unauthorized access
docker compose logs api --since 24h | grep -i "401\|403\|500"

# 3. Revoke all active sessions
docker compose exec db psql -U postgres_admin -d makapix -c \
  "UPDATE refresh_tokens SET revoked = true WHERE revoked = false;"

# 4. Force all users to re-authenticate
# Users will need to log in again with their passwords

# 5. Notify security team and document incident
# Record: What was exposed, when, how, actions taken

# 6. Review and update security procedures
```

---

## Post-Rotation Verification

After rotating any secret, perform these verification checks:

### General Verification

```bash
# 1. Check service health
docker compose ps
# All services should show "Up" and "healthy"

# 2. Review logs for errors
docker compose logs --tail=100 | grep -i "error\|fail\|denied"

# 3. Test API health
curl https://dev.makapix.club/api/health
# Expected: {"status": "healthy"}

# 4. Test user authentication
curl -X POST https://dev.makapix.club/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass"}'
# Expected: JWT tokens returned

# 5. Test MQTT connectivity (if MQTT rotated)
docker compose exec mqtt mosquitto_sub -h localhost -t '$SYS/#' -C 1 \
  -u svc_backend -P $MQTT_PASSWORD
# Expected: System message received
```

### Specific Verification

**Database:**
```bash
docker compose exec api python3 -c "
from app.database import engine
with engine.connect() as conn:
    result = conn.execute('SELECT 1')
    print('Database connection: OK')
"
```

**MQTT:**
```bash
# Test backend connection
docker compose logs api --tail=20 | grep -i "mqtt.*connect"
# Should see successful connection

# Test player certificate
openssl s_client -connect dev.makapix.club:8883 \
  -CAfile /opt/makapix/mqtt/certs/ca.crt \
  -cert /path/to/player/cert.pem \
  -key /path/to/player/key.pem
```

**OAuth:**
```bash
# Test OAuth login flow
# 1. Open https://dev.makapix.club/auth/github/login
# 2. Complete GitHub authorization
# 3. Verify successful redirect and login
```

---

## Audit Trail

Document all secret rotations in a secure audit log:

### Rotation Log Template

```markdown
## Secret Rotation - [DATE]

**Performed by:** [Name/Email]
**Date/Time:** [YYYY-MM-DD HH:MM:SS UTC]
**Type:** [Scheduled/Emergency]

### Secrets Rotated
- [ ] JWT Secret Key
- [ ] Database Admin Password
- [ ] Database Worker Password
- [ ] MQTT Backend Password
- [ ] OAuth Client Secret
- [ ] GitHub App Private Key
- [ ] Admin Account Password
- [ ] Other: [specify]

### Reason
[Scheduled rotation / Security incident / Other]

### Procedure Followed
[Which procedure from this document]

### Downtime
[Duration, if any]

### Issues Encountered
[None / List issues]

### Verification Status
- [ ] Services healthy
- [ ] Authentication working
- [ ] MQTT connectivity OK
- [ ] No error logs
- [ ] User testing completed

### Notes
[Any additional notes or observations]

**Verified by:** [Name/Email]
**Sign-off:** [Initials]
```

### Audit Log Location

Store rotation logs in:
- **Secure location:** `/opt/makapix/security/rotation-log.md` (not in git)
- **Backup:** Cloud secure storage (encrypted)
- **Access:** Limited to security team only

---

## Summary Checklist

Use this checklist for routine rotation:

```markdown
### Quarterly Rotation Checklist (Every 90 Days)

- [ ] Backup current .env file
- [ ] Generate new JWT secret
- [ ] Rotate database admin password
- [ ] Rotate database worker password
- [ ] Rotate MQTT backend password
- [ ] Rotate admin account password
- [ ] Update .env file with new secrets
- [ ] Restart affected services
- [ ] Verify service health
- [ ] Test user authentication
- [ ] Test MQTT connectivity
- [ ] Document in audit log
- [ ] Store backup securely
- [ ] Update password manager
```

---

## Additional Resources

- [Security Audit Report](./SECURITY_AUDIT_2026.md)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL Password Management](https://www.postgresql.org/docs/current/sql-alterrole.html)
- [Mosquitto Password File](https://mosquitto.org/man/mosquitto_passwd-1.html)
- [GitHub OAuth Apps](https://docs.github.com/en/developers/apps/building-oauth-apps)
- [Let's Encrypt Certificate Renewal](https://letsencrypt.org/docs/integration-guide/)

---

## Support

For questions or issues with secret rotation:
- **Security Team:** security@makapix.club
- **Documentation:** https://github.com/fabkury/makapix/docs/security/
- **Emergency Contact:** [Emergency contact info]

---

*This document should be treated as CONFIDENTIAL and stored securely. Access should be limited to personnel authorized to perform secret rotation operations.*

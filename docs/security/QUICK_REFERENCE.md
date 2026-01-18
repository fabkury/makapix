# Security Quick Reference Card

**For:** Operations Team & System Administrators  
**Updated:** January 16, 2026

## Emergency Contacts

- **Security Team:** security@makapix.club
- **On-Call:** [Emergency contact]
- **Documentation:** `/opt/makapix/docs/security/`

## Critical Secrets Location

| Secret | Location | Rotation |
|--------|----------|----------|
| JWT Key | `/opt/makapix/deploy/stack/.env` | 90 days |
| DB Passwords | `/opt/makapix/deploy/stack/.env` | 90 days |
| MQTT Backend | `/opt/makapix/deploy/stack/.env` + `/opt/makapix/mqtt/config/passwords` | 90 days |
| MQTT Webclient | `/opt/makapix/mqtt/config/passwords` + `web/src/lib/mqtt-client.ts` | 90 days |
| Admin Password | `/opt/makapix/deploy/stack/.env` | 90 days |
| OAuth Secrets | `/opt/makapix/deploy/stack/.env` | 180 days |
| GitHub App Key | `/opt/makapix/deploy/stack/.env` | 365 days |
| Resend API Key | `/opt/makapix/deploy/stack/.env` | 180 days |

## Quick Commands

### Health Check
```bash
cd /opt/makapix/deploy/stack
docker compose ps
docker compose logs --tail=50 | grep -i "error\|fail"
curl https://makapix.club/api/health
```

### View Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f mqtt
docker compose logs -f web
```

### Restart Services
```bash
# All services
docker compose restart

# Specific service
docker compose restart api
docker compose restart mqtt
```

## Emergency Procedures

### If Database Credentials Compromised
```bash
# 1. Generate new password
NEW_PASS=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)

# 2. Update PostgreSQL
docker compose exec db psql -U postgres_admin -d makapix -c \
  "ALTER USER api_worker WITH PASSWORD '$NEW_PASS';"

# 3. Update .env
sed -i "s/DB_API_WORKER_PASSWORD=.*/DB_API_WORKER_PASSWORD=$NEW_PASS/" .env

# 4. Restart
docker compose restart api worker
```

### If JWT Secret Compromised
```bash
# 1. Generate new secret
NEW_JWT=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')

# 2. Update .env
sed -i "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$NEW_JWT/" .env

# 3. Restart
docker compose restart api worker

# 4. Revoke all sessions
docker compose exec db psql -U postgres_admin -d makapix -c \
  "UPDATE refresh_tokens SET revoked = true;"
```

### If MQTT Password Compromised
```bash
# 1. Generate new password
NEW_MQTT=$(openssl rand -base64 24 | tr -d "=+/" | cut -c1-24)

# 2. Update password file
mosquitto_passwd -b /opt/makapix/mqtt/config/passwords svc_backend "$NEW_MQTT"

# 3. Update .env
sed -i "s/MQTT_PASSWORD=.*/MQTT_PASSWORD=$NEW_MQTT/" .env

# 4. Restart
docker compose restart mqtt api worker
```

## Scheduled Maintenance

### Quarterly (Every 90 Days)
```bash
# Run this checklist:
# [ ] Rotate JWT secret
# [ ] Rotate database passwords
# [ ] Rotate MQTT passwords
# [ ] Rotate admin password
# [ ] Review access logs
# [ ] Update dependencies
# [ ] Run security scan
# [ ] Document in audit log
```

### Monthly
```bash
# [ ] Check certificate expiration
docker compose exec caddy caddy list-certificates

# [ ] Review failed login attempts
docker compose logs api | grep "401\|403" | tail -100

# [ ] Check disk space
df -h

# [ ] Review service health
docker compose ps
```

### Weekly
```bash
# [ ] Check for service errors
docker compose logs --since 168h | grep -i "error\|fatal"

# [ ] Verify backups
ls -lh /path/to/backups/

# [ ] Check MQTT broker status
docker compose logs mqtt --tail=50
```

## Common Issues

### Service Won't Start After Restart
```bash
# Check logs
docker compose logs api --tail=100

# Common causes:
# - Invalid environment variable
# - Database connection failed
# - Port already in use

# Solution: Check .env file for typos
```

### Authentication Failing
```bash
# Verify JWT secret is set
grep JWT_SECRET_KEY /opt/makapix/deploy/stack/.env

# Check token expiration
# Access tokens: 60 minutes
# Refresh tokens: 30 days

# Test database connection
docker compose exec api python3 -c \
  "from app.database import engine; engine.connect()"
```

### MQTT Connection Issues
```bash
# Test backend connection
docker compose exec mqtt mosquitto_sub -h localhost -t '$SYS/#' -C 1 \
  -u svc_backend -P $MQTT_PASSWORD

# Check password file
ls -la /opt/makapix/mqtt/config/passwords
# Should be: -rw------- (permissions 600)

# Verify certificate validity
openssl x509 -in /opt/makapix/mqtt/certs/server.crt -noout -dates
```

## Security Checklist (Pre-Production)

- [ ] All secrets rotated from default/development values
- [ ] JWT_SECRET_KEY is 32+ random characters
- [ ] Database uses strong passwords (24+ chars)
- [ ] MQTT backend password rotated (MQTT_PASSWORD)
- [ ] MQTT webclient password rotated (code + password file)
- [ ] Admin password is strong and unique
- [ ] GitHub OAuth client secret rotated
- [ ] GitHub App private key rotated
- [ ] Resend API key configured and rotated
- [ ] CORS_ORIGINS does not contain "*"
- [ ] HTTPS enabled with valid certificates
- [ ] All services have health checks
- [ ] Logs are being captured
- [ ] Backups are configured
- [ ] Security audit reviewed and issues addressed
- [ ] Secret rotation schedule documented
- [ ] All old secrets deleted from external services (GitHub, Resend)

## Useful Monitoring Commands

```bash
# Active connections
docker compose exec db psql -U postgres_admin -d makapix -c \
  "SELECT count(*) FROM pg_stat_activity;"

# MQTT client count
docker compose exec mqtt sh -c \
  "mosquitto_sub -h localhost -t '\$SYS/broker/clients/connected' -C 1"

# API response time (last 100 requests)
docker compose logs api --tail=100 | grep "request_duration"

# Failed authentication attempts (last hour)
docker compose logs api --since 1h | grep -i "401" | wc -l

# Database size
docker compose exec db psql -U postgres_admin -d makapix -c \
  "SELECT pg_size_pretty(pg_database_size('makapix'));"

# Redis memory usage
docker compose exec cache redis-cli INFO memory | grep used_memory_human
```

## Documentation Links

- **Full Security Audit:** `/opt/makapix/docs/security/SECURITY_AUDIT_2026.md`
- **Rotation Procedures:** `/opt/makapix/docs/security/SECRET_ROTATION_PROCEDURES.md`
- **Architecture:** `/opt/makapix/docs/ARCHITECTURE.md`
- **Deployment:** `/opt/makapix/deploy/stack/README.stack.md`

---

**Print this card and keep it accessible for emergency reference**

*Last updated: January 16, 2026*

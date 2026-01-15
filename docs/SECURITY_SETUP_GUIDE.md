# Security Setup Guide

This guide provides step-by-step instructions for securely configuring Makapix for production deployment.

## Table of Contents
1. [Pre-Deployment Security Checklist](#pre-deployment-security-checklist)
2. [Secrets Management](#secrets-management)
3. [JWT Configuration](#jwt-configuration)
4. [CORS Configuration](#cors-configuration)
5. [MQTT Security](#mqtt-security)
6. [Database Security](#database-security)
7. [HTTPS/TLS Configuration](#httpstls-configuration)
8. [Monitoring and Logging](#monitoring-and-logging)

---

## Pre-Deployment Security Checklist

Before deploying to production, ensure all these items are completed:

- [ ] **JWT_SECRET_KEY** is set with a strong, randomly generated value (minimum 32 characters)
- [ ] **CORS_ORIGINS** is configured with specific allowed domains (not "*")
- [ ] **ENVIRONMENT** is set to "production"
- [ ] All passwords use strong, unique values (no default passwords)
- [ ] HTTPS is enabled with valid TLS certificates
- [ ] Database uses strong passwords and restricted access
- [ ] MQTT uses mTLS for client authentication
- [ ] Rate limiting is enabled and configured
- [ ] All debug endpoints are disabled in production
- [ ] Logs are configured to not expose sensitive data
- [ ] Security headers are configured (CSP, HSTS, etc.)
- [ ] File upload limits are enforced
- [ ] Regular security updates are scheduled
- [ ] Backup and disaster recovery plan is in place

---

## Secrets Management

### Required Secrets

Generate strong secrets for production:

```bash
# Generate JWT secret key (required)
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'

# Generate database passwords
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'

# Generate MQTT backend password
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

### Environment Variables

**NEVER commit secrets to version control!**

Create a `.env` file (not tracked in git) with your secrets:

```bash
# Copy the example env file and customize
cd /opt/makapix/deploy/stack
cp env.example .env
# Edit .env with your secrets
```

### Production Secrets Management

For production deployments, use a secrets management service:

#### Option 1: HashiCorp Vault
```bash
# Store secrets in Vault
vault kv put secret/makapix/jwt JWT_SECRET_KEY="your-secret-here"
vault kv put secret/makapix/db DB_PASSWORD="your-db-password"
```

#### Option 2: AWS Secrets Manager
```bash
# Store secrets in AWS
aws secretsmanager create-secret --name makapix/jwt \
  --secret-string '{"JWT_SECRET_KEY":"your-secret-here"}'
```

#### Option 3: Docker Secrets (Docker Swarm)
```bash
# Create Docker secrets
echo "your-jwt-secret" | docker secret create jwt_secret -
```

---

## JWT Configuration

### Generate Secure JWT Secret

**CRITICAL:** Never use the default or a weak secret key.

```bash
# Generate a secure 256-bit key
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

### Configure in Environment

```bash
# In your .env file
JWT_SECRET_KEY=your_generated_secret_here_minimum_32_characters
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60    # 1 hour (adjust as needed)
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30       # 30 days (adjust as needed)
JWT_ALGORITHM=HS256                     # or RS256 for asymmetric keys
```

### Token Rotation Best Practices

- Access tokens: Short-lived (15-60 minutes)
- Refresh tokens: Longer-lived (7-30 days) with rotation
- Revoke all tokens on password change
- Implement token blacklist for immediate revocation

### Validation

The application will fail to start if JWT_SECRET_KEY is not set or is too short:

```python
# auth.py performs these checks on startup:
if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY environment variable is required")
if len(JWT_SECRET_KEY) < 32:
    raise RuntimeError("JWT_SECRET_KEY is too short")
```

---

## CORS Configuration

### Development vs Production

**Development:**
```bash
CORS_ORIGINS=http://localhost:3000,http://localhost
```

**Production:**
```bash
CORS_ORIGINS=https://makapix.club,https://dev.makapix.club
```

### Never Use Wildcard in Production

❌ **INSECURE:**
```bash
CORS_ORIGINS=*  # Allows requests from ANY origin with credentials
```

✅ **SECURE:**
```bash
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Multiple Domains

For multiple trusted domains, use comma-separated list:

```bash
CORS_ORIGINS=https://makapix.club,https://app.makapix.club,https://api.makapix.club
```

---

## MQTT Security

### Certificate-Based Authentication (mTLS)

The MQTT broker uses mutual TLS (mTLS) for physical player devices.

#### Generate CA and Server Certificates

Certificates are automatically generated on first run, or manually:

```bash
cd mqtt
./scripts/gen-certs.sh
```

#### Certificate Files

- `ca.crt` - Certificate Authority (distribute to clients)
- `ca.key` - CA private key (keep secret!)
- `server.crt` - Server certificate
- `server.key` - Server private key

#### Certificate Management

**Production recommendations:**
- Use a proper PKI infrastructure
- Store CA private key in HSM or vault
- Implement certificate rotation (before 365-day expiry)
- Monitor certificate expiration dates
- Revoke compromised certificates immediately

### Password Authentication

For WebSocket connections (web browsers), password auth is used:

```bash
# Set strong MQTT password
MQTT_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
```

### MQTT ACL Configuration

Edit `mqtt/config/acls` to restrict topic access:

```
# Backend service has full access
user svc_backend
topic readwrite #

# Players can only publish to their own status topic
pattern readwrite players/%u/status
pattern read posts/new/#
```

---

## Database Security

### Connection Security

**Use SSL/TLS for database connections in production:**

```bash
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db?sslmode=require
```

### Password Requirements

- Minimum 16 characters
- Use randomly generated passwords
- Different passwords for different users/roles

```bash
# Generate strong DB passwords
DB_ADMIN_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
DB_API_WORKER_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
```

### User Permissions

The application uses least-privilege principle:

- **postgres** (superuser): Database initialization only
- **api_worker**: Application access with limited permissions
  - No CREATE/DROP database
  - No superuser privileges
  - Access only to required tables

### Regular Backups

```bash
# Automated daily backups
pg_dump -h localhost -U postgres -d makapix > backup_$(date +%Y%m%d).sql

# Encrypt backups
gpg --encrypt --recipient your-key backup_$(date +%Y%m%d).sql
```

---

## HTTPS/TLS Configuration

### Caddy Configuration

Caddy automatically handles TLS certificates via Let's Encrypt.

**For production, ensure your Caddyfile includes:**

```
makapix.club {
    tls {
        protocols tls1.2 tls1.3
    }
    
    header {
        # Security headers
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        X-XSS-Protection "1; mode=block"
        Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "geolocation=(), microphone=(), camera=()"
    }
    
    reverse_proxy api:8000
}
```

### TLS Best Practices

- Use TLS 1.2 or 1.3 only (disable older versions)
- Enable HSTS with long max-age
- Use strong cipher suites
- Enable OCSP stapling
- Implement certificate pinning for API clients
- Monitor certificate expiration

### Let's Encrypt Rate Limits

- 50 certificates per domain per week
- 5 duplicate certificates per week
- Plan certificate renewals accordingly

---

## Monitoring and Logging

### Log Configuration

**Production logging best practices:**

```bash
# Set appropriate log level
LOG_LEVEL=INFO  # or WARNING for production

# Never log sensitive data
- ❌ Passwords
- ❌ Tokens
- ❌ API keys
- ❌ PII (email, names, etc.)
```

### Security Monitoring

Implement monitoring for:

1. **Failed Authentication Attempts**
   - Alert on >5 failed logins per minute
   - Block IPs with >20 failed attempts per hour

2. **Unusual API Activity**
   - Rate limit violations
   - Sudden traffic spikes
   - Geographic anomalies

3. **System Security**
   - Failed sudo attempts
   - SSH login attempts
   - File integrity monitoring

4. **Certificate Expiration**
   - Alert 30 days before expiry
   - Automated renewal monitoring

### Log Aggregation

Use centralized logging:

```bash
# Example: ELK Stack, Splunk, or CloudWatch Logs
docker-compose logs -f | grep ERROR
```

### Audit Logging

The application includes audit logging for security-sensitive operations:

- User authentication/authorization
- Password changes
- Role modifications
- Admin actions

Access audit logs:

```sql
SELECT * FROM audit_logs 
WHERE action IN ('login', 'password_change', 'role_change')
ORDER BY created_at DESC;
```

---

## Rate Limiting

### Implementation Status

⚠️ **TODO**: Rate limiting is currently a placeholder. Implement Redis-based rate limiting before production deployment.

### Recommended Limits

```python
# Per user limits
RATE_LIMIT_LOGIN = 5 per 5 minutes
RATE_LIMIT_REGISTER = 3 per hour per IP
RATE_LIMIT_API_GLOBAL = 100 per minute
RATE_LIMIT_UPLOAD = 10 per hour
RATE_LIMIT_MQTT_PUBLISH = 60 per minute
```

### Redis Configuration for Rate Limiting

```bash
REDIS_URL=redis://cache:6379/1  # Separate DB for rate limiting
```

---

## Security Incident Response

### Immediate Actions for Security Breach

1. **Isolate affected systems**
   ```bash
   docker-compose down
   ```

2. **Rotate all secrets immediately**
   - Generate new JWT secret
   - Revoke all refresh tokens
   - Change all passwords

3. **Review audit logs**
   ```sql
   SELECT * FROM audit_logs WHERE created_at > NOW() - INTERVAL '24 hours';
   ```

4. **Notify affected users**
   - Force password resets if needed
   - Send security notifications

5. **Document incident**
   - Timeline of events
   - Root cause analysis
   - Prevention measures

### Contact Information

For security issues, contact:
- Email: security@makapix.club
- PGP Key: [Link to public key]

---

## Security Checklist Summary

Use this checklist before each production deployment:

### Environment
- [ ] ENVIRONMENT=production
- [ ] All services use HTTPS/TLS
- [ ] Valid TLS certificates configured

### Secrets
- [ ] JWT_SECRET_KEY is strong and unique
- [ ] All passwords are strong and unique
- [ ] No default passwords in use
- [ ] Secrets stored securely (not in git)

### Network
- [ ] CORS limited to trusted origins only
- [ ] Rate limiting enabled and tested
- [ ] Firewall rules configured
- [ ] Only necessary ports exposed

### Authentication
- [ ] Password requirements enforced
- [ ] Account lockout after failed attempts
- [ ] Session timeout configured
- [ ] MFA available for admin accounts

### Database
- [ ] SSL/TLS enabled for connections
- [ ] Least privilege user permissions
- [ ] Regular automated backups
- [ ] Backup encryption enabled

### Monitoring
- [ ] Log aggregation configured
- [ ] Security alerts configured
- [ ] Uptime monitoring enabled
- [ ] Certificate expiration monitoring

### Code
- [ ] All dependencies updated
- [ ] Security scan completed (CodeQL)
- [ ] No known vulnerabilities
- [ ] Debug endpoints disabled

### Documentation
- [ ] Security procedures documented
- [ ] Incident response plan ready
- [ ] Team trained on security practices
- [ ] Contact information updated

---

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [Mozilla Web Security Guidelines](https://infosec.mozilla.org/guidelines/web_security)
- [FastAPI Security Documentation](https://fastapi.tiangolo.com/tutorial/security/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)

---

**Last Updated:** December 5, 2025  
**Maintained By:** Makapix Security Team  
**Review Frequency:** Quarterly or after security incidents

# Security Documentation

This directory contains comprehensive security documentation for the Makapix Club platform.

## Documents

### [SECURITY_AUDIT_2026.md](./SECURITY_AUDIT_2026.md)
**Comprehensive Security Audit Report**

A thorough security assessment covering all aspects of the Makapix platform:
- Authentication & Authorization systems
- API security controls
- Infrastructure and deployment security
- MQTT/IoT security architecture
- Data protection mechanisms
- Secrets management practices
- Dependency security analysis
- Monitoring and logging capabilities

**Last Updated:** January 16, 2026  
**Overall Security Rating:** ✅ GOOD

### [SECRET_ROTATION_PROCEDURES.md](./SECRET_ROTATION_PROCEDURES.md)
**Secret Rotation Procedures**

Step-by-step procedures for rotating all secrets used in the platform:
- JWT secret keys
- Database credentials (admin and worker)
- MQTT passwords and certificates
- TLS certificates
- OAuth credentials (GitHub)
- GitHub App private keys
- Admin account passwords
- Emergency rotation procedures
- Post-rotation verification steps

**Recommended Rotation Schedule:**
- Critical secrets: Every 90 days
- OAuth credentials: Every 180 days
- Certificates: Every 365 days (auto-renewal)

## Quick Reference

### Security Status Summary

| Category | Status | Issues |
|----------|--------|--------|
| Authentication | ✅ Excellent | 0 critical, 0 high |
| API Security | ✅ Excellent | 0 critical, 0 high |
| Infrastructure | ✅ Good | 0 critical, 0 high |
| MQTT/IoT | ✅ Good | 0 critical, 1 high |
| Data Protection | ✅ Excellent | 0 critical, 0 high |
| Secrets Management | ✅ Good | 0 critical, 0 high |

### Priority Issues to Address

1. **[H1]** Webclient MQTT password is hardcoded - Consider per-session credentials
2. **[M1]** JWT refresh tokens have 30-day expiration - Consider reducing to 14 days
3. **[M2]** MQTT certificates have 365-day validity - Consider reducing to 180 days
4. **[M5]** CSP allows unsafe-inline for OAuth - Consider nonce-based CSP

## Secret Inventory

### Environment Variables (`.env`)
- `JWT_SECRET_KEY` - JWT signing key (rotate every 90 days)
- `DB_ADMIN_PASSWORD` - PostgreSQL admin password (rotate every 90 days)
- `DB_API_WORKER_PASSWORD` - PostgreSQL worker password (rotate every 90 days)
- `MQTT_PASSWORD` - MQTT backend password (rotate every 90 days)
- `GITHUB_OAUTH_CLIENT_SECRET` - OAuth client secret (rotate every 180 days)
- `GITHUB_APP_PRIVATE_KEY` - GitHub App private key (rotate every 365 days)
- `MAKAPIX_ADMIN_PASSWORD` - Admin account password (rotate every 90 days)
- `RESEND_API_KEY` - Email service API key (rotate every 180 days)

### File-Based Secrets
- `/mqtt/config/passwords` - MQTT password file (bcrypt hashed)
- `/mqtt/certs/ca.key` - MQTT CA private key (365-day validity)
- `/mqtt/certs/server.key` - MQTT server private key (365-day validity)
- `/mqtt/certs/crl.pem` - Certificate revocation list (30-day validity)

### Hardcoded Secrets (Require Code Changes)
- `web/src/lib/mqtt-client.ts` - MQTT webclient credentials (see rotation procedures)

## Security Best Practices

### Authentication
- ✅ Use JWT for stateless authentication
- ✅ Store refresh tokens in HttpOnly cookies
- ✅ Implement token rotation with grace period
- ✅ Hash passwords with bcrypt
- ✅ Validate JWT secret entropy on startup

### API Security
- ✅ Use SQLAlchemy ORM (prevents SQL injection)
- ✅ Validate all inputs with Pydantic
- ✅ Implement rate limiting on sensitive endpoints
- ✅ Use security headers middleware
- ✅ Enable CORS only for specific origins

### Infrastructure
- ✅ Use Docker network isolation
- ✅ Enable HTTPS with automatic certificate renewal
- ✅ Use mTLS for IoT device connections
- ✅ Implement health checks for all services
- ✅ Use least-privilege database users

### Secrets Management
- ✅ Load secrets from environment variables
- ✅ Never commit secrets to version control
- ✅ Validate secret strength on startup
- ✅ Hash tokens before database storage
- ✅ Rotate secrets on schedule

## Emergency Contacts

For security incidents or questions:
- **Security Team:** security@makapix.club
- **Emergency:** [Emergency contact information]
- **GitHub Issues:** https://github.com/fabkury/makapix/issues (for non-sensitive security enhancements)

## Related Documentation

- [Architecture Documentation](../ARCHITECTURE.md)
- [Development Guide](../DEVELOPMENT.md)
- [Deployment Guide](../DEPLOYMENT.md) *(if exists)*
- [MQTT Protocol Documentation](../MQTT_PROTOCOL.md)
- [Legacy Security Audit](../legacy/go-live-security-audit/README.md)

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 2.0 | 2026-01-16 | Automated Security Review | Comprehensive audit with secret rotation procedures |
| 1.0 | 2026-01-14 | Security Team | Initial go-live security audit |

---

**⚠️ CONFIDENTIAL:** This documentation contains sensitive security information and should be treated as confidential. Access should be limited to authorized personnel only.

# Production Deployment Changes Summary

This document summarizes all changes made to prepare Makapix for production deployment at https://makapix.club.

## Files Modified

### 1. `proxy/Caddyfile`
**Purpose**: Enable automatic SSL via Let's Encrypt and configure for production domain

**Changes**:
- Removed `auto_https off` and debug settings
- Added email for Let's Encrypt certificate notifications
- Changed from `:80` to `makapix.club` domain configuration
- Caddy will now automatically obtain and renew SSL certificates

**Before**:
```caddy
{
    auto_https off
    admin 0.0.0.0:2019
    debug
}

:80 {
```

**After**:
```caddy
{
    email fabio@biokury.com
}

makapix.club {
```

### 2. `web/src/pages/publish.tsx`
**Purpose**: Replace hardcoded localhost URLs with environment-based URLs

**Changes**:
- Added `API_BASE_URL` constant that reads from `NEXT_PUBLIC_API_BASE_URL` environment variable
- Replaced all hardcoded `http://localhost` URLs with `API_BASE_URL`
- Updated OAuth login URLs to use dynamic base URL
- Upload endpoint now uses dynamic URL
- Job status polling now uses dynamic URL

**Key additions**:
```typescript
const API_BASE_URL = typeof window !== 'undefined' 
  ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
  : 'http://localhost';
```

**URLs updated**:
- Line 117: Job status polling URL
- Line 138: Alert message with auth URL
- Line 173: Upload endpoint URL
- Lines 255, 260: OAuth login URLs

### 3. `web/src/pages/update-installation.tsx`
**Purpose**: Use environment-based or relative URLs instead of hardcoded localhost

**Changes**:
- Updated API endpoint to use `NEXT_PUBLIC_API_BASE_URL` from environment
- Falls back to relative URL `/api/profiles/bind-github-app` if env var not set

**Before**:
```typescript
const response = await fetch('http://localhost/api/profiles/bind-github-app', {
```

**After**:
```typescript
const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL 
  ? `${process.env.NEXT_PUBLIC_API_BASE_URL}/profiles/bind-github-app`
  : '/api/profiles/bind-github-app';

const response = await fetch(apiUrl, {
```

### 4. `docker-compose.yml`
**Purpose**: Configure environment variables for production and expose HTTPS port

**Changes**:
- Updated `NEXT_PUBLIC_API_BASE_URL` to use environment variable with production default
- Updated `NEXT_PUBLIC_MQTT_WS_URL` to use environment variable with production default
- Added port 443 for HTTPS traffic

**Web service environment (lines 155-157)**:
```yaml
NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL:-https://makapix.club/api}
API_INTERNAL_URL: http://api:8000
NEXT_PUBLIC_MQTT_WS_URL: ${NEXT_PUBLIC_MQTT_WS_URL:-wss://makapix.club:9001}
```

**Proxy ports (lines 184-185)**:
```yaml
ports:
  - "80:80"
  - "443:443"
```

## Documentation Created

### 1. `docs/env-production-template.md`
**Purpose**: Provide a template for creating the production `.env` file

**Contents**:
- Complete list of all required environment variables
- Placeholder values for sensitive credentials
- Comments explaining each variable
- Instructions for setting permissions

### 2. `docs/production-deployment.md`
**Purpose**: Comprehensive guide for deploying to production VPS

**Contents**:
- Step-by-step GitHub OAuth App setup
- Step-by-step GitHub App setup
- VPS deployment procedure
- Testing and verification steps
- Monitoring and maintenance commands
- Troubleshooting guide
- Security checklist
- Backup recommendations

### 3. `docs/production-changes-summary.md` (this file)
**Purpose**: Document all changes made for production deployment

## Environment Variables Required

The following environment variables must be set in the production `.env` file:

### Database
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`

### API
- `API_PORT`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`
- `JWT_REFRESH_TOKEN_EXPIRE_DAYS`

### GitHub Integration
- `GITHUB_OAUTH_CLIENT_ID`
- `GITHUB_OAUTH_CLIENT_SECRET`
- `GITHUB_REDIRECT_URI`
- `GITHUB_APP_ID`
- `GITHUB_APP_PRIVATE_KEY`

### Celery
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

### Frontend
- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_MQTT_WS_URL`

## Deployment Workflow

1. **Pre-deployment** (GitHub setup):
   - Create production GitHub OAuth App
   - Create production GitHub App
   - Save credentials

2. **Code changes** (already implemented):
   - Update Caddyfile for SSL
   - Update frontend URLs to be environment-based
   - Update docker-compose for production defaults

3. **VPS deployment**:
   - Clone repository
   - Create `.env` with production credentials
   - Build and start Docker containers
   - Run database migrations
   - Verify all services

4. **Testing**:
   - Health check API
   - Test authentication flow
   - Test publishing flow
   - Verify GitHub Pages publishing

## Security Considerations

- `.env` file contains sensitive credentials and must have 600 permissions
- Never commit `.env` to git (already in `.gitignore`)
- Use strong random values for `POSTGRES_PASSWORD` and `JWT_SECRET_KEY`
- GitHub App private key must preserve newlines
- Firewall should only allow ports 80, 443, and SSH
- Regular backups of database volume

## Production vs Development

| Aspect | Development | Production |
|--------|-------------|------------|
| Domain | `localhost` | `makapix.club` |
| SSL | Disabled | Automatic (Let's Encrypt) |
| Ports | 80 | 80, 443 |
| API URL | `http://localhost/api` | `https://makapix.club/api` |
| MQTT URL | `ws://localhost:9001` | `wss://makapix.club:9001` |
| OAuth Callback | `http://localhost/auth/github/callback` | `https://makapix.club/auth/github/callback` |
| Environment | Hardcoded in code | Environment variables |

## Rollback Plan

If deployment issues occur:

```bash
docker compose down
git checkout <previous-commit>
docker compose build
docker compose up -d
```

## Next Steps After Deployment

1. Set up automated database backups
2. Configure monitoring (Prometheus, Grafana)
3. Set up log aggregation
4. Enable rate limiting
5. Configure email notifications for errors
6. Test disaster recovery procedures

## References

- GitHub OAuth setup: https://github.com/settings/developers
- GitHub App setup: https://github.com/settings/apps
- Let's Encrypt documentation: https://letsencrypt.org/docs/
- Caddy documentation: https://caddyserver.com/docs/
- Docker Compose documentation: https://docs.docker.com/compose/


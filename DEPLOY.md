# Quick Deploy to Production

This is a condensed deployment guide for Makapix production VPS. For detailed instructions, see `docs/production-deployment.md`.

## Prerequisites

- VPS with Docker & Docker Compose
- Domain `makapix.club` pointing to VPS IP
- GitHub OAuth App and GitHub App already created

## Quick Steps

### 1. Clone Repository

```bash
cd /opt
git clone https://github.com/fabkury/makapix.git
cd makapix
```

### 2. Create .env File

```bash
nano .env
```

See `docs/env-production-template.md` for the template. Use credentials from plan file.

**Critical values to update:**
- `POSTGRES_PASSWORD` - Generate secure random password
- `JWT_SECRET_KEY` - Generate secure random string
- `GITHUB_APP_PRIVATE_KEY` - Paste actual private key with newlines

```bash
chmod 600 .env
```

### 3. Deploy

```bash
# Build and start
docker compose build
docker compose up -d

# Wait for SSL certificate (1-2 minutes)
docker compose logs -f proxy

# Run migrations
docker compose exec api alembic upgrade head

# Verify
docker compose ps  # All should be "healthy"
curl https://makapix.club/api/health  # Should return {"status":"ok"}
```

### 4. Update Installation ID

1. Visit: https://makapix.club/update-installation
2. Click "Update Installation ID"
3. Restart worker: `docker compose restart worker`

### 5. Test

1. Visit: https://makapix.club
2. Log in with GitHub
3. Go to /publish
4. Upload pixel art
5. Verify artwork publishes to GitHub Pages

## Troubleshooting

```bash
# View logs
docker compose logs -f

# Restart services
docker compose restart

# Check service status
docker compose ps
```

## Credentials Reference

Located in the plan file (`milestone-2-implementation.plan.md`):
- GitHub OAuth Client ID: `Ov23likuVKQD2QXX82bE`
- GitHub OAuth Client Secret: `bcbd98607a3c47b69a2d683926b7b98184cda755`
- GitHub App ID: `2198186`
- GitHub App Installation ID: `92061343`
- Private Key: In downloaded .pem file

## Documentation

- Full deployment guide: `docs/production-deployment.md`
- Deployment checklist: `docs/deployment-checklist.md`
- Changes summary: `docs/production-changes-summary.md`
- Environment template: `docs/env-production-template.md`

## Support

If deployment fails, check:
1. DNS points to VPS: `nslookup makapix.club`
2. Ports 80/443 open: `sudo ufw status`
3. Service logs: `docker compose logs <service-name>`
4. All credentials in .env are correct


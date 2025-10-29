# Production Deployment Checklist

Use this checklist when deploying Makapix to production at https://makapix.club.

## Pre-Deployment (Complete ✅)

- [x] GitHub OAuth App created
  - Client ID: `Ov23likuVKQD2QXX82bE`
  - Client Secret: `bcbd98607a3c47b69a2d683926b7b98184cda755`
  - Callback URL: `https://makapix.club/auth/github/callback`

- [x] GitHub App created
  - App ID: `2198186`
  - Installation ID: `92061343`
  - Private key: Downloaded (makapix.2025-10-29.private-key.pem)
  - Permissions: Contents, Metadata, Administration, Pages (all Read & write)
  - Callback URL: `https://makapix.club/auth/github/callback`

- [x] Code updated for production
  - Caddyfile configured for SSL
  - Frontend URLs use environment variables
  - Docker compose configured for HTTPS
  - Documentation created

## VPS Deployment Steps

### 1. Prepare VPS Environment

```bash
# SSH into VPS
ssh user@your-vps-ip

# Verify Docker is installed
docker --version
docker compose version

# Verify DNS is pointing to VPS
nslookup makapix.club

# Ensure ports 80 and 443 are open
sudo ufw status
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

- [ ] SSH access verified
- [ ] Docker and Docker Compose installed
- [ ] DNS pointing to VPS
- [ ] Firewall configured (ports 80, 443, 22)

### 2. Clone Repository

```bash
cd /opt
sudo git clone https://github.com/fabkury/makapix.git
cd makapix
```

- [ ] Repository cloned to `/opt/makapix`

### 3. Create Production .env File

```bash
sudo nano .env
```

Paste the following (fill in the GitHub App private key):

```bash
# Database
POSTGRES_DB=makapix
POSTGRES_USER=makapix_user
POSTGRES_PASSWORD=mk_prod_db_2024_secure_random_pass

# API
DATABASE_URL=postgresql://makapix_user:mk_prod_db_2024_secure_random_pass@db:5432/makapix
API_PORT=8000

# JWT
JWT_SECRET_KEY=mk_jwt_secret_2024_ultra_secure_random_key_change_this
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# GitHub OAuth
GITHUB_OAUTH_CLIENT_ID=Ov23likuVKQD2QXX82bE
GITHUB_OAUTH_CLIENT_SECRET=bcbd98607a3c47b69a2d683926b7b98184cda755
GITHUB_REDIRECT_URI=https://makapix.club/auth/github/callback

# GitHub App
GITHUB_APP_ID=2198186
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
PASTE_YOUR_PRIVATE_KEY_CONTENT_HERE
-----END RSA PRIVATE KEY-----"

# Celery
CELERY_BROKER_URL=redis://cache:6379/0
CELERY_RESULT_BACKEND=redis://cache:6379/0

# Frontend
NEXT_PUBLIC_API_BASE_URL=https://makapix.club/api
NEXT_PUBLIC_MQTT_WS_URL=wss://makapix.club:9001
```

**Important**: Replace `POSTGRES_PASSWORD` and `JWT_SECRET_KEY` with actual secure random values, and paste the actual private key content.

```bash
# Set permissions
sudo chmod 600 .env
```

- [ ] .env file created with all credentials
- [ ] Private key pasted with preserved newlines
- [ ] Secure passwords generated
- [ ] File permissions set to 600

### 4. Build and Start Services

```bash
# Build all containers
sudo docker compose build

# Start services in detached mode
sudo docker compose up -d

# Watch logs to monitor startup
sudo docker compose logs -f
```

Wait for SSL certificate acquisition (watch proxy logs):
```bash
sudo docker compose logs -f proxy
```

Look for: "certificate obtained successfully"

- [ ] All containers built successfully
- [ ] All services started
- [ ] SSL certificate obtained (watch proxy logs)

### 5. Run Database Migrations

```bash
# Wait for API to be healthy (check with docker compose ps)
sudo docker compose ps

# Run migrations
sudo docker compose exec api alembic upgrade head
```

- [ ] Database migrations completed successfully

### 6. Verify All Services

```bash
# Check service status
sudo docker compose ps

# Should show all services as "Up" and "healthy"
```

Expected services:
- db (healthy)
- cache (healthy)
- mqtt (started)
- api (healthy)
- worker (up)
- web (healthy)
- proxy (healthy)

- [ ] All services running and healthy

## Post-Deployment Testing

### 7. Health Check

```bash
curl https://makapix.club/api/health
```

Expected: `{"status":"ok"}`

- [ ] API health check passes

### 8. Web Interface

Visit: https://makapix.club

- [ ] Website loads over HTTPS
- [ ] No SSL certificate warnings
- [ ] Homepage displays correctly

### 9. Authentication Flow

1. Visit: https://makapix.club/auth/github/login
2. Authorize the GitHub OAuth app
3. Verify redirect back to success page

- [ ] GitHub OAuth login works
- [ ] User is authenticated
- [ ] Tokens stored in browser

### 10. Update GitHub App Installation

1. Visit: https://makapix.club/update-installation
2. Click "Update Installation ID"
3. Verify success message

```bash
# Restart worker to pick up new installation
sudo docker compose restart worker
```

- [ ] Installation ID updated
- [ ] Worker restarted

### 11. Publishing Flow (End-to-End Test)

1. Visit: https://makapix.club/publish
2. Verify authentication status shows "Authenticated"
3. Select a pixel art image (e.g., 32x32 GIF or PNG)
4. Click "Publish to GitHub Pages"
5. Monitor job status (should go: queued → running → committed)
6. Check GitHub repository for committed files
7. Verify repository is now public
8. Visit GitHub Pages URL (https://fabkury.github.io/makapix-user/)

- [ ] Upload succeeds
- [ ] Job status shows "committed"
- [ ] Files committed to GitHub
- [ ] Repository made public automatically
- [ ] Artwork visible on GitHub Pages

### 12. Monitor Logs

```bash
# Check for any errors
sudo docker compose logs --tail=100

# Watch ongoing logs
sudo docker compose logs -f api
sudo docker compose logs -f worker
```

- [ ] No critical errors in logs
- [ ] All services operating normally

## Troubleshooting

If any step fails, refer to:
- `docs/production-deployment.md` - Full deployment guide
- `docs/production-changes-summary.md` - Changes made for production

Common issues:
- SSL not working → Check DNS, firewall, Caddy logs
- OAuth fails → Verify callback URLs match exactly
- Worker fails → Check GitHub App permissions and private key format
- Database errors → Check credentials in .env

## Security Post-Deployment

```bash
# Verify .env permissions
ls -la .env  # Should show -rw------- (600)

# Set up automated backups (example)
sudo crontab -e
# Add: 0 2 * * * cd /opt/makapix && docker compose exec -T db pg_dump -U makapix_user makapix > /backups/makapix_$(date +\%Y\%m\%d).sql
```

- [ ] .env has correct permissions (600)
- [ ] Backup strategy planned/implemented
- [ ] Monitoring alerts configured (optional)

## Rollback Procedure

If critical issues occur:

```bash
cd /opt/makapix
sudo docker compose down
sudo git log --oneline  # Find previous working commit
sudo git checkout <commit-hash>
sudo docker compose build
sudo docker compose up -d
```

## Success Criteria

All items must be checked:

- [ ] Website loads at https://makapix.club with valid SSL
- [ ] Users can log in with GitHub OAuth
- [ ] Users can publish pixel art
- [ ] Artwork appears on GitHub Pages
- [ ] Repository is automatically made public
- [ ] All Docker services are healthy
- [ ] No critical errors in logs

## Next Steps After Successful Deployment

- Set up automated database backups
- Configure monitoring and alerts
- Set up log aggregation
- Test disaster recovery procedures
- Document any environment-specific configurations
- Plan regular maintenance windows

---

**Deployment Date**: _____________

**Deployed By**: _____________

**Git Commit**: _____________

**Notes**: _____________________________________________


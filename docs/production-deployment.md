# Production Deployment Guide

This guide walks you through deploying Makapix to your production VPS at https://makapix.club.

## Prerequisites

- VPS with Docker and Docker Compose installed
- Domain name (makapix.club) pointing to your VPS IP
- SSL certificate management (Let's Encrypt via Caddy)
- GitHub account for OAuth and GitHub App setup

## Step 1: Create GitHub OAuth App

1. Go to https://github.com/settings/developers
2. Click "New OAuth App"
3. Configure:
   - **Application name**: `Makapix` (or `Makapix Club`)
   - **Homepage URL**: `https://makapix.club`
   - **Authorization callback URL**: `https://makapix.club/auth/github/callback`
4. Click "Register application"
5. **Save the Client ID and Client Secret** (you'll need these for `.env`)

## Step 2: Create GitHub App

Follow the instructions in `docs/github-app-setup.md` with these production-specific values:

1. Go to https://github.com/settings/apps
2. Click "New GitHub App"
3. Configure:
   - **GitHub App name**: `Makapix`
   - **Homepage URL**: `https://makapix.club`
   - **Callback URL**: `https://makapix.club/auth/github/callback`
   - **Webhook URL**: Leave blank
4. Set permissions:
   - Repository: `Contents` (Read & write), `Metadata` (Read), `Administration` (Read & write), `Pages` (Read & write)
5. Click "Create GitHub App"
6. **Generate and download the private key** (.pem file)
7. **Note the App ID**
8. Install the app to your account and **note the Installation ID** from the URL

## Step 3: Prepare Your Local Repository

1. **Commit all changes**:
   ```bash
   git add .
   git commit -m "Configure for production deployment"
   ```

2. **Push to GitHub**:
   ```bash
   git push origin main
   ```

## Step 4: Deploy to VPS

### 4.1. Clone Repository on VPS

SSH into your VPS and clone the repository:

```bash
# Choose your preferred location
cd /opt  # or /var/www, or ~/apps

# Clone the repository
git clone https://github.com/your-username/makapix.git
cd makapix
```

### 4.2. Create Production .env File

Create `.env` file with your production credentials:

```bash
nano .env
```

Use the template from `docs/env-production-template.md` and fill in:

- Database password (generate a secure random password)
- JWT secret key (generate a secure random string)
- GitHub OAuth Client ID and Secret (from Step 1)
- GitHub App ID and Private Key (from Step 2)

**Important**: Make sure to preserve the newlines in the `GITHUB_APP_PRIVATE_KEY` value.

### 4.3. Set Proper Permissions

```bash
chmod 600 .env
chown root:root .env  # or your user if not root
```

### 4.4. Build and Start Services

```bash
# Build all containers
docker compose build

# Start all services in detached mode
docker compose up -d

# Watch the logs to ensure everything starts correctly
docker compose logs -f
```

### 4.5. Wait for SSL Certificate

Caddy will automatically request an SSL certificate from Let's Encrypt. This may take 1-2 minutes. Watch the logs:

```bash
docker compose logs -f proxy
```

You should see messages about certificate acquisition.

### 4.6. Run Database Migrations

Once the API service is healthy, run the migrations:

```bash
docker compose exec api alembic upgrade head
```

### 4.7. Verify Services

Check that all services are running and healthy:

```bash
docker compose ps
```

All services should show "Up" and "healthy" status.

## Step 5: Test the Deployment

### 5.1. Health Check

```bash
curl https://makapix.club/api/health
```

Should return: `{"status":"ok"}`

### 5.2. Web Interface

Visit https://makapix.club in your browser. You should see the Makapix homepage.

### 5.3. Authentication Flow

1. Click "log in with GitHub" (or visit https://makapix.club/auth/github/login)
2. Authorize the OAuth application
3. You should be redirected back with a success message

### 5.4. Publishing Flow

1. Go to https://makapix.club/publish
2. Verify you're authenticated
3. Select a pixel art image
4. Click "Publish to GitHub Pages"
5. Monitor the job status
6. Verify the artwork appears on your GitHub Pages site

### 5.5. Update GitHub App Installation

If you need to bind a new GitHub App installation:

1. Go to https://makapix.club/update-installation
2. Click "Update Installation ID"
3. Restart the worker: `docker compose restart worker`

## Step 6: Monitoring and Maintenance

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f web
```

### Restart Services

```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart api
docker compose restart worker
```

### Update Deployment

```bash
# Pull latest changes
git pull origin main

# Rebuild and restart
docker compose build
docker compose up -d

# Run any new migrations
docker compose exec api alembic upgrade head
```

## Troubleshooting

### SSL Certificate Issues

If Caddy can't get a certificate:

1. Check that ports 80 and 443 are open in your firewall
2. Verify DNS is pointing to your VPS
3. Check Caddy logs: `docker compose logs proxy`

### Database Connection Issues

If the API can't connect to the database:

1. Check database logs: `docker compose logs db`
2. Verify `DATABASE_URL` in `.env` matches your credentials
3. Restart services: `docker compose restart`

### GitHub OAuth/App Issues

If authentication fails:

1. Verify GitHub OAuth callback URL is exactly `https://makapix.club/auth/github/callback`
2. Verify GitHub App callback URL is exactly `https://makapix.club/auth/github/callback`
3. Check that credentials in `.env` match your GitHub apps
4. Verify `GITHUB_APP_PRIVATE_KEY` preserves all newlines

### Worker Job Failures

If uploads fail:

1. Check worker logs: `docker compose logs worker`
2. Verify GitHub App has correct permissions (Contents, Administration, Pages)
3. Restart worker: `docker compose restart worker`

## Rollback Procedure

If you need to roll back to a previous version:

```bash
# Stop all services
docker compose down

# Checkout previous version
git log --oneline  # Find the commit hash
git checkout <previous-commit-hash>

# Rebuild and restart
docker compose build
docker compose up -d
```

## Security Checklist

- [ ] `.env` file has 600 permissions
- [ ] Firewall allows only ports 80, 443, and SSH
- [ ] SSH is configured with key-based authentication
- [ ] Database uses a strong random password
- [ ] JWT secret is a strong random string
- [ ] GitHub OAuth/App secrets are kept secure
- [ ] Regular backups of database volume (`pg_data`)
- [ ] Docker images are kept up to date

## Backup Recommendations

### Database Backup

```bash
# Create backup
docker compose exec -T db pg_dump -U makapix_user makapix > backup_$(date +%Y%m%d).sql

# Restore backup
docker compose exec -T db psql -U makapix_user makapix < backup_20241029.sql
```

### Volume Backup

```bash
# Backup all Docker volumes
docker run --rm -v repo_pg_data:/data -v $(pwd):/backup alpine tar czf /backup/pg_data_backup.tar.gz /data
```

## Next Steps

- Set up automated backups (cron job or backup service)
- Configure monitoring (e.g., Prometheus, Grafana)
- Set up log aggregation (e.g., Loki, ELK stack)
- Enable rate limiting and DDoS protection (Cloudflare, fail2ban)
- Configure email notifications for errors


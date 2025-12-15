# Makapix Deployment Guide

Complete guide for deploying Makapix Club to production on a VPS.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [VPS Setup](#vps-setup)
4. [Initial Deployment](#initial-deployment)
5. [Configuration](#configuration)
6. [SSL/TLS Setup](#ssltls-setup)
7. [Monitoring](#monitoring)
8. [Backups](#backups)
9. [Updates](#updates)
10. [Troubleshooting](#troubleshooting)

---

## Overview

Makapix is designed to run on a single VPS with the following characteristics:

- **Cost**: $7-$18/month
- **Specs**: 2 vCPU, 2-4 GB RAM, 50+ GB SSD
- **OS**: Ubuntu 22.04 LTS (recommended)
- **Capacity**: Supports up to 10,000 monthly active users

All services run as Docker containers orchestrated by Docker Compose.

---

## Prerequisites

### Required Services

- Domain name (e.g., `makapix.club`)
- DNS access to configure A records
- VPS provider account (DigitalOcean, Linode, Vultr, Hetzner, etc.)

### Required Knowledge

- Basic Linux command line
- SSH and basic server administration
- Docker and Docker Compose basics

---

## VPS Setup

### 1. Provision VPS

Create a VPS with the following specifications:

**Minimum Requirements:**
- 2 vCPU
- 2 GB RAM
- 50 GB SSD storage
- Ubuntu 22.04 LTS

**Recommended Providers:**
- DigitalOcean ($12/month droplet)
- Linode ($12/month Nanode)
- Vultr ($12/month instance)
- Hetzner ($7/month CX21)

### 2. Initial Server Setup

SSH into your server:

```bash
ssh root@your-server-ip
```

Update system:

```bash
apt update && apt upgrade -y
```

Create non-root user:

```bash
adduser makapix
usermod -aG sudo makapix
```

Set up SSH key authentication (recommended):

```bash
# On your local machine
ssh-copy-id makapix@your-server-ip
```

Configure firewall:

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

### 3. Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Add user to docker group
usermod -aG docker makapix

# Install Docker Compose
apt install docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

### 4. Install Additional Tools

```bash
apt install -y git make htop ncdu
```

---

## Initial Deployment

### 1. Clone Repository

```bash
# Switch to makapix user
su - makapix

# Create directory and clone
mkdir -p /opt/makapix
cd /opt/makapix
git clone https://github.com/fabkury/makapix.git .
```

### 2. Configure DNS

Point your domain to your VPS IP:

```
A     makapix.club          -> your-vps-ip
A     dev.makapix.club      -> your-vps-ip
A     *.makapix.club        -> your-vps-ip (optional)
```

Wait for DNS propagation (can take up to 48 hours, usually 5-30 minutes).

Verify:

```bash
dig makapix.club
dig dev.makapix.club
```

### 3. Set Up Environment

Navigate to deployment directory:

```bash
cd /opt/makapix/deploy/stack
```

Copy and configure environment:

```bash
cp env.example .env
nano .env
```

Update the following values:

```bash
# Domain configuration
ROOT_DOMAIN=makapix.club
WEB_DOMAIN=dev.makapix.club

# Web app port (reverse-proxied by Caddy)
WEB_APP_PORT=3000

# Database credentials (use strong passwords!)
POSTGRES_PASSWORD=your-strong-password-here
POSTGRES_USER=appuser
POSTGRES_DB=appdb

# GitHub OAuth (if using)
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# Session secrets (generate random strings)
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)

# Email configuration (optional)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-email@example.com
SMTP_PASSWORD=your-email-password
```

### 4. Create Docker Network

```bash
docker network create caddy_net
```

### 5. Start Services

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### 6. Verify Deployment

Check that services are running:

```bash
# Check containers
docker compose ps

# Check logs for errors
docker compose logs api
docker compose logs web
```

Access the application:

- CTA site: https://makapix.club
- Web (live preview): https://dev.makapix.club

---

## Configuration

### Environment Variables

Key environment variables in `/opt/makapix/deploy/stack/.env`:

#### Core Settings

```bash
# Domains
ROOT_DOMAIN=makapix.club
WEB_DOMAIN=dev.makapix.club

# Web app port
WEB_APP_PORT=3000

# Database
POSTGRES_USER=appuser
POSTGRES_PASSWORD=strong-password-here
POSTGRES_DB=appdb
DATABASE_URL=postgresql+psycopg://appuser:password@db:5432/appdb
```

#### Storage Configuration

```bash
# Vault location inside container
VAULT_LOCATION=/vault

# Vault location on host (where images are stored)
VAULT_HOST_PATH=/opt/makapix/vault
```

Create vault directory:

```bash
mkdir -p /opt/makapix/vault
chown -R 1000:1000 /opt/makapix/vault
```

#### MQTT Configuration

```bash
MQTT_HOST=mqtt
MQTT_PORT=8883
MQTT_TLS=true
MQTT_CA_FILE=/certs/ca.crt
```

#### Service Ports

```bash
API_PORT=8000
WEB_PORT=3000
DB_PORT=5432
REDIS_PORT=6379
```

### Caddy Configuration

Caddy automatically handles TLS certificates via Let's Encrypt.

The configuration is in `deploy/stack/caddy/Caddyfile.global`:

```
makapix.club {
    root * /srv/cta
    file_server
}

dev.makapix.club {
    reverse_proxy web:3000
}

api.makapix.club {
    reverse_proxy api:8000
}
```

---

## SSL/TLS Setup

### Automatic with Let's Encrypt

Caddy automatically obtains and renews SSL certificates from Let's Encrypt. No manual configuration needed!

**Requirements:**
- Valid domain pointing to your server
- Port 80 and 443 open in firewall
- Valid email in Caddy configuration

### Certificate Storage

Certificates are stored in Docker volume:

```bash
docker volume inspect stack_caddy_data
```

### Manual Certificate Renewal

Caddy handles renewals automatically, but you can force renewal:

```bash
docker compose restart caddy
```

### Verify SSL

```bash
# Check certificate
curl -vI https://makapix.club

# Online tool
# Visit: https://www.ssllabs.com/ssltest/
```

---

## Monitoring

### Service Health Checks

```bash
# Check all services
docker compose ps

# Check specific service
docker compose ps api

# View resource usage
docker stats
```

### Logs

```bash
# View all logs
docker compose logs

# Follow logs in real-time
docker compose logs -f

# Specific service
docker compose logs -f api

# Last 100 lines
docker compose logs --tail=100 api
```

### System Resources

```bash
# Disk usage
df -h
ncdu /opt/makapix/vault

# Memory usage
free -h

# CPU usage
htop
```

### Database Monitoring

```bash
# Connect to database
docker compose exec db psql -U appuser -d appdb

# Check database size
docker compose exec db psql -U appuser -d appdb -c "SELECT pg_size_pretty(pg_database_size('appdb'));"

# Check table sizes
docker compose exec db psql -U appuser -d appdb -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

### CTA Stats Monitoring

Monitor CTA site statistics:

```bash
cd /opt/makapix/deploy/stack
./monitor-cta-stats.sh
```

Stats are saved to `cta-stats.csv`.

---

## Backups

### Database Backups

#### Manual Backup

```bash
# Create backup directory
mkdir -p /opt/makapix/backups

# Backup database
docker compose exec db pg_dump -U appuser appdb > /opt/makapix/backups/backup-$(date +%Y%m%d-%H%M%S).sql

# Compress backup
gzip /opt/makapix/backups/backup-*.sql
```

#### Automated Daily Backups

Create backup script `/opt/makapix/scripts/backup-db.sh`:

```bash
#!/bin/bash
BACKUP_DIR=/opt/makapix/backups
DATE=$(date +%Y%m%d-%H%M%S)

cd /opt/makapix/deploy/stack

# Create backup
docker compose exec -T db pg_dump -U appuser appdb | gzip > $BACKUP_DIR/db-$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "db-*.sql.gz" -mtime +30 -delete

echo "Backup completed: db-$DATE.sql.gz"
```

Make executable and add to crontab:

```bash
chmod +x /opt/makapix/scripts/backup-db.sh

# Add to crontab (runs daily at 2 AM)
crontab -e
# Add line:
0 2 * * * /opt/makapix/scripts/backup-db.sh >> /var/log/makapix-backup.log 2>&1
```

#### Restore Database

```bash
# Stop services
cd /opt/makapix/deploy/stack
docker compose down

# Start only database
docker compose up -d db

# Wait for database to be ready
sleep 10

# Restore from backup
gunzip < /opt/makapix/backups/db-20250101-020000.sql.gz | \
    docker compose exec -T db psql -U appuser -d appdb

# Start all services
docker compose up -d
```

### Vault Backups

#### Manual Backup

```bash
# Backup vault to tarball
tar -czf /opt/makapix/backups/vault-$(date +%Y%m%d-%H%M%S).tar.gz /opt/makapix/vault
```

#### Automated Daily Backups

Create backup script `/opt/makapix/scripts/backup-vault.sh`:

```bash
#!/bin/bash
BACKUP_DIR=/opt/makapix/backups
DATE=$(date +%Y%m%d-%H%M%S)

# Create incremental backup using rsync
rsync -av --link-dest=$BACKUP_DIR/vault-latest \
    /opt/makapix/vault/ \
    $BACKUP_DIR/vault-$DATE/

# Update latest symlink
rm -f $BACKUP_DIR/vault-latest
ln -s $BACKUP_DIR/vault-$DATE $BACKUP_DIR/vault-latest

# Keep only last 7 daily backups
find $BACKUP_DIR -maxdepth 1 -name "vault-*" -type d -mtime +7 | \
    grep -v latest | xargs rm -rf

echo "Vault backup completed: vault-$DATE"
```

Make executable and add to crontab:

```bash
chmod +x /opt/makapix/scripts/backup-vault.sh

# Add to crontab (runs daily at 3 AM)
crontab -e
# Add line:
0 3 * * * /opt/makapix/scripts/backup-vault.sh >> /var/log/makapix-backup.log 2>&1
```

### Off-site Backups

For production, use off-site backup service:

```bash
# Using rclone (configure with your provider)
rclone sync /opt/makapix/backups remote:makapix-backups
```

---

## Updates

### Updating the Application

```bash
# Navigate to directory
cd /opt/makapix

# Pull latest changes
git pull origin main

# Navigate to stack directory
cd deploy/stack

# Rebuild and restart services
docker compose build
docker compose up -d

# Run database migrations if needed
docker compose exec api alembic upgrade head

# Check logs
docker compose logs -f
```

### Updating Dependencies

#### Update Docker Images

```bash
cd /opt/makapix/deploy/stack

# Pull latest base images
docker compose pull

# Rebuild custom images
docker compose build

# Restart services
docker compose up -d
```

#### Update System Packages

```bash
sudo apt update
sudo apt upgrade -y
sudo reboot  # If kernel updated
```

### Rollback

If an update causes issues:

```bash
# Go to repository
cd /opt/makapix

# List recent commits
git log --oneline -10

# Rollback to previous version
git checkout <commit-hash>

# Rebuild and restart
cd deploy/stack
docker compose build
docker compose up -d
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check Docker daemon
sudo systemctl status docker

# Check logs
docker compose logs

# Restart services
docker compose restart

# Full restart
docker compose down
docker compose up -d
```

### Out of Disk Space

```bash
# Check disk usage
df -h

# Check Docker disk usage
docker system df

# Clean up Docker resources
docker system prune -a

# Clean up old logs
journalctl --vacuum-time=7d

# Check vault size
du -sh /opt/makapix/vault
```

### Database Connection Errors

```bash
# Check database is running
docker compose ps db

# Check database logs
docker compose logs db

# Restart database
docker compose restart db

# Connect to database to check
docker compose exec db psql -U appuser -d appdb
```

### SSL Certificate Issues

```bash
# Check Caddy logs
docker compose logs caddy

# Verify DNS is correct
dig makapix.club

# Restart Caddy
docker compose restart caddy

# Check certificate expiry
echo | openssl s_client -servername makapix.club -connect makapix.club:443 2>/dev/null | openssl x509 -noout -dates
```

### High Memory Usage

```bash
# Check memory
free -h

# Check per-container usage
docker stats

# Restart heavy services
docker compose restart api worker
```

### Performance Issues

```bash
# Check system load
htop

# Check database performance
docker compose exec db psql -U appuser -d appdb -c "SELECT * FROM pg_stat_activity WHERE state != 'idle';"

# Check slow queries
docker compose logs api | grep -i "slow"

# Restart services
docker compose restart
```

---

## Security Checklist

- [ ] Strong passwords for database and admin accounts
- [ ] SSH key authentication enabled, password auth disabled
- [ ] Firewall configured (UFW or iptables)
- [ ] Automatic security updates enabled
- [ ] Regular backups configured and tested
- [ ] SSL/TLS certificates active and auto-renewing
- [ ] Monitoring and alerting set up
- [ ] Database not exposed to internet (only localhost)
- [ ] Rate limiting enabled in API
- [ ] Vault directory has correct permissions (owned by container user, not world-readable)

---

## Additional Resources

- **[Architecture Documentation](ARCHITECTURE.md)** - System design details
- **[Development Guide](DEVELOPMENT.md)** - Local development setup
- **[Physical Player Guide](PHYSICAL_PLAYER.md)** - Hardware integration
- **[Roadmap](ROADMAP.md)** - Project milestones

---

For production support and questions, please open an issue on GitHub.

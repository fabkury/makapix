# Quick Deployment Guide

Simple, step-by-step instructions for deploying to your VPS.

## Prerequisites

- SSH access to your VPS
- Git repository cloned at `/opt/makapix` (or your chosen path)
- `.env.remote` file configured with your credentials
- `caddy-docker-proxy` running on VPS
- DNS pointing `dev.makapix.club` to your VPS

## Deploying Changes to VPS

### Method 1: One-Command Deployment (Recommended)

SSH into your VPS and run:

```bash
cd /opt/makapix
make deploy-vps
```

This single command:
1. Pulls latest code from Git
2. Switches to remote environment
3. Stops current services
4. Rebuilds and starts services
5. Shows deployment status

**That's it!** Your changes are deployed.

---

### Method 2: Manual Step-by-Step

If you prefer to run each step manually:

```bash
# 1. SSH into VPS
ssh user@your-vps-ip

# 2. Navigate to repo
cd /opt/makapix

# 3. Pull latest code
git pull origin main

# 4. Switch to remote environment
make remote

# 5. Restart services
docker compose down
docker compose up -d

# 6. Check status
docker compose ps
```

---

## Verifying Deployment

### Quick Check

Visit in your browser:
- https://dev.makapix.club
- https://dev.makapix.club/publish

Both should load without errors.

### Detailed Verification

```bash
# Check all services are healthy
docker compose ps

# Expected output:
# NAME              STATUS
# repo-api-1        Up X seconds (healthy)
# repo-web-1        Up X seconds (healthy)
# repo-worker-1     Up X seconds
# repo-db-1         Up X seconds (healthy)
# repo-cache-1      Up X seconds (healthy)
# repo-mqtt-1       Up X seconds (healthy)

# Check services are connected to caddy_net
docker network inspect caddy_net | grep makapix

# View recent logs
make logs

# Test API endpoint
curl https://dev.makapix.club/api/health
```

---

## Common Issues & Quick Fixes

### Issue: 502 Bad Gateway

**Quick fix:**
```bash
make remote
docker compose restart
```

**If that doesn't work:**
```bash
docker compose down
docker compose up -d
docker restart caddy  # Restart caddy-docker-proxy
```

---

### Issue: Services show "unhealthy"

**Quick fix:**
```bash
# Check logs for the unhealthy service
docker compose logs api  # or web, db, etc.

# If database issues:
docker compose down -v  # Removes volumes - ⚠️ deletes data!
docker compose up -d
```

---

### Issue: Changes not appearing

**Quick fix:**
```bash
# Force rebuild without cache
docker compose down
docker compose up -d --build --force-recreate
```

---

### Issue: Wrong environment active

**Quick fix:**
```bash
# Check current environment
make status

# If showing "local" instead of "remote":
make remote
docker compose restart
```

---

## Rollback

If deployment breaks something:

```bash
# Go back to previous commit
git log --oneline -5        # Find the previous good commit
git reset --hard <commit>   # Replace <commit> with hash

# Redeploy
make deploy-vps
```

---

## Deployment Checklist

**Before deploying:**
- [ ] Code tested locally
- [ ] Changes committed and pushed to Git
- [ ] `.env.remote` is up to date on VPS

**During deployment:**
- [ ] Ran `make deploy-vps` on VPS
- [ ] No errors in deployment output
- [ ] All services show "(healthy)"

**After deployment:**
- [ ] Site loads at https://dev.makapix.club
- [ ] No errors in browser console
- [ ] API endpoints responding
- [ ] Check logs for errors: `make logs`

---

## Daily Workflow

### Typical development cycle:

**On your laptop:**
1. Make code changes
2. Test locally with `make local && make up`
3. Commit and push: `git push origin main`

**On your VPS:**
1. Deploy with: `make deploy-vps`
2. Verify deployment
3. Done!

---

## Advanced Commands

### Deploy without rebuilding images
```bash
cd /opt/makapix
git pull origin main
make remote
docker compose up -d  # Note: no --build flag
```

### Deploy and follow logs
```bash
make deploy-vps && make logs
```

### Check what changed in latest deployment
```bash
git log --oneline -5
git diff HEAD~1 HEAD
```

### Rebuild only specific service
```bash
docker compose up -d --build --no-deps web  # Rebuilds only web
```

---

## Getting Help

**View available commands:**
```bash
make help
```

**View service status:**
```bash
make status
```

**View logs:**
```bash
make logs          # All services
make logs-api      # Just API
make logs-web      # Just web
```

**Check network connections:**
```bash
docker network inspect caddy_net
```

---

## Complete Documentation

For detailed explanations:
- **Full deployment guide:** [VPS-DEPLOYMENT-GUIDE.md](VPS-DEPLOYMENT-GUIDE.md)
- **Environment workflow:** [WORKFLOW.md](WORKFLOW.md)
- **Environment configuration:** [README-DEV-ENVIRONMENTS.md](README-DEV-ENVIRONMENTS.md)

---

## TL;DR - Just Deploy Already!

```bash
ssh your-vps
cd /opt/makapix
make deploy-vps
```

Done! 🚀

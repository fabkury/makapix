# Makapix Club Go-Live Plan

**Status:** Planning
**Target Date:** TBD
**Last Updated:** 2026-01-18

---

## Overview

This document tracks the migration from `dev.makapix.club` to `makapix.club` as the primary production domain.

### What "Going Live" Means

1. All view counters reset to 0
2. All reactions and comments are deleted (posts remain)
3. The website moves from `https://dev.makapix.club/` to `https://makapix.club/`
4. The call-to-action page at `https://makapix.club/` ceases to exist

### Subdomains That Remain Unchanged

- `vault.makapix.club` — HTTP file server for physical players
- `piskel.makapix.club` — Piskel pixel art editor
- `pixelc.makapix.club` — PixelC pixel art editor
- `notification.makapix.club` — Email sending domain

---

## Pre-Migration Checklist

Complete these before starting the migration:

- [ ] **Backup database** — Full PostgreSQL dump
- [ ] **Notify users** — Announce maintenance window (if applicable)
- [ ] **Verify DNS access** — Confirm ability to modify DNS records
- [ ] **Verify GitHub access** — Confirm ability to modify OAuth app settings
- [ ] **Document current state** — Screenshot current site for reference

---

## Phase 1: External Configuration (Manual Steps)

These steps require manual action outside the codebase.

### 1.1 GitHub OAuth App Configuration

**Location:** https://github.com/settings/developers → OAuth Apps → Makapix

| Setting | Current Value | New Value |
|---------|---------------|-----------|
| Homepage URL | `https://dev.makapix.club` | `https://makapix.club` |
| Authorization callback URL | `https://dev.makapix.club/api/auth/github/callback` | `https://makapix.club/api/auth/github/callback` |

- [ ] Update Homepage URL
- [ ] Update Authorization callback URL
- [ ] Save changes

### 1.2 DNS Configuration

Ensure the following DNS records point to the VPS IP address:

| Record Type | Name | Value | Status |
|-------------|------|-------|--------|
| A | `makapix.club` | `<VPS_IP>` | [ ] Configured |
| A | `www.makapix.club` | `<VPS_IP>` | [ ] Configured |
| A | `dev.makapix.club` | `<VPS_IP>` | [ ] Keep (for redirect) |

**Note:** If `makapix.club` currently points to Squarespace for the CTA page, it must be changed to point to the VPS.

- [ ] Verify current DNS configuration
- [ ] Update DNS records if needed
- [ ] Wait for DNS propagation (check with `dig makapix.club`)

### 1.3 Verify Email Domain

Confirm `notification.makapix.club` is properly configured in Resend:

- [ ] Verify domain is verified in Resend dashboard
- [ ] Test email sending works

---

## Phase 2: Database Reset

Execute these SQL commands to reset engagement data.

### 2.1 Create Backup

```bash
# SSH into server
ssh user@dev.makapix.club

# Create full backup
cd /opt/makapix/deploy/stack
docker compose exec db pg_dump -U owner makapix > /tmp/makapix_backup_$(date +%Y%m%d_%H%M%S).sql

# Copy backup to safe location
cp /tmp/makapix_backup_*.sql /opt/backups/
```

- [ ] Backup created
- [ ] Backup verified (check file size, spot-check content)

### 2.2 Reset Engagement Data

```bash
# Connect to database
cd /opt/makapix/deploy/stack
docker compose exec db psql -U owner makapix
```

```sql
-- Start transaction
BEGIN;

-- Check current counts (for logging)
SELECT 'posts' as table_name, COUNT(*) as count FROM posts
UNION ALL SELECT 'reactions', COUNT(*) FROM reactions
UNION ALL SELECT 'comments', COUNT(*) FROM comments;

-- Reset view counters
UPDATE posts SET view_count = 0;

-- Delete all reactions
DELETE FROM reactions;

-- Delete all comments
DELETE FROM comments;

-- Verify changes
SELECT 'posts' as table_name, COUNT(*) as count, SUM(view_count) as total_views FROM posts
UNION ALL SELECT 'reactions', COUNT(*), NULL FROM reactions
UNION ALL SELECT 'comments', COUNT(*), NULL FROM comments;

-- If everything looks correct:
COMMIT;

-- If something went wrong:
-- ROLLBACK;
```

- [ ] Transaction started
- [ ] View counts reset
- [ ] Reactions deleted
- [ ] Comments deleted
- [ ] Transaction committed
- [ ] Changes verified

---

## Phase 3: Environment Configuration

### 3.1 Update `/opt/makapix/.env`

| Variable | Current Value | New Value |
|----------|---------------|-----------|
| `BASE_URL` | `https://dev.makapix.club` | `https://makapix.club` |
| `CORS_ORIGINS` | `https://dev.makapix.club,...` | `https://makapix.club,https://www.makapix.club,...` |
| `GITHUB_REDIRECT_URI` | `https://dev.makapix.club/api/auth/github/callback` | `https://makapix.club/api/auth/github/callback` |
| `MQTT_PUBLIC_HOST` | `dev.makapix.club` | `makapix.club` |
| `API_BASE_URL` | `https://dev.makapix.club/api` | `https://makapix.club/api` |
| `NEXT_PUBLIC_API_BASE_URL` | `https://dev.makapix.club` | `https://makapix.club` |
| `NEXT_PUBLIC_MQTT_WS_URL` | `wss://dev.makapix.club:9001` | `wss://makapix.club/mqtt` |

- [ ] All variables updated in `.env`

### 3.2 Update `/opt/makapix/deploy/stack/.env`

| Variable | Current Value | New Value |
|----------|---------------|-----------|
| `WEB_DOMAIN` | (uses default `dev.makapix.club`) | `makapix.club` |
| `GITHUB_REDIRECT_URI` | `https://dev.makapix.club/api/auth/github/callback` | `https://makapix.club/api/auth/github/callback` |

- [ ] Stack env updated

---

## Phase 4: Source Code Changes

### 4.1 Docker Compose Updates

**File:** `/opt/makapix/deploy/stack/docker-compose.yml`

| Line | Change |
|------|--------|
| 123 | `MQTT_PUBLIC_HOST: dev.makapix.club` → `MQTT_PUBLIC_HOST: makapix.club` |
| 269 | `NEXT_PUBLIC_API_BASE_URL=https://dev.makapix.club` → `https://makapix.club` |
| 270 | `NEXT_PUBLIC_MQTT_WS_URL=wss://dev.makapix.club/mqtt` → `wss://makapix.club/mqtt` |
| 278 | `NEXT_PUBLIC_API_BASE_URL=https://dev.makapix.club` → `https://makapix.club` |
| 279 | `NEXT_PUBLIC_MQTT_WS_URL=wss://dev.makapix.club/mqtt` → `wss://makapix.club/mqtt` |
| 281 | `caddy: ${WEB_DOMAIN:-dev.makapix.club}` → `caddy: makapix.club, www.makapix.club` |
| 315 | CSP `https://dev.makapix.club` → `https://makapix.club` |
| 335 | CSP `https://dev.makapix.club` → `https://makapix.club` |

- [ ] All docker-compose.yml changes applied

### 4.2 Remove CTA Service

**File:** `/opt/makapix/deploy/stack/docker-compose.yml`

Remove or comment out the entire CTA service block (lines ~220-238):
```yaml
# cta:
#   build: ...
#   ...
```

Also remove/comment the CTA build context if separate.

- [ ] CTA service removed from docker-compose.yml

### 4.3 API Source Code Updates

**File:** `/opt/makapix/api/app/routers/player.py`

| Line | Change |
|------|--------|
| 105 | `os.getenv("MQTT_PUBLIC_HOST", "dev.makapix.club")` → `"makapix.club"` |
| 335 | `os.getenv("MQTT_PUBLIC_HOST", "dev.makapix.club")` → `"makapix.club"` |
| 460 | `os.getenv("MQTT_PUBLIC_HOST", "dev.makapix.club")` → `"makapix.club"` |

- [ ] player.py updated

**File:** `/opt/makapix/api/app/routers/mqtt.py`

| Line | Change |
|------|--------|
| 24 | `os.getenv("MQTT_PUBLIC_HOST", "dev.makapix.club")` → `"makapix.club"` |

- [ ] mqtt.py updated

### 4.4 Frontend Source Code Updates

**File:** `/opt/makapix/apps/piskel/src/js/makapix/MakapixIntegration.js`

| Line | Change |
|------|--------|
| 9 | `var MAKAPIX_ORIGIN = 'https://dev.makapix.club';` → `'https://makapix.club'` |

- [ ] MakapixIntegration.js updated

**File:** `/opt/makapix/web/src/pages/about.tsx`

| Line | Change |
|------|--------|
| 567 | `href="https://dev.makapix.club/u/t5"` → `href="/u/t5"` (use relative URL) |

- [ ] about.tsx updated

---

## Phase 5: MQTT Certificate Regeneration (Optional)

The current certificates have SANs for both `dev.makapix.club` and `makapix.club`, so they will work. However, for cleanliness, regenerate with `makapix.club` as the primary CN.

**Decision:** [ ] Skip for now / [ ] Regenerate certificates

If regenerating:

```bash
cd /opt/makapix/deploy/stack

# Stop MQTT service
docker compose stop mqtt

# Backup existing certs
cp -r ../../mqtt/certs ../../mqtt/certs.backup.$(date +%Y%m%d)

# Remove old certs (regeneration will create new ones)
rm -f ../../mqtt/certs/*.crt ../../mqtt/certs/*.key ../../mqtt/certs/*.pem

# Update gen-certs.sh to use makapix.club as primary CN
# (Edit mqtt/scripts/gen-certs.sh line with CN=dev.makapix.club)

# Rebuild and start MQTT
docker compose up -d --build mqtt
```

- [ ] Certificate decision made
- [ ] Certificates regenerated (if applicable)

**Warning:** Regenerating certificates will require re-provisioning all physical players with new client certificates.

---

## Phase 6: Deployment

### 6.1 Stop Services

```bash
cd /opt/makapix/deploy/stack
docker compose down
```

- [ ] Services stopped

### 6.2 Pull Latest Code

```bash
cd /opt/makapix
git pull origin main
```

- [ ] Code pulled

### 6.3 Rebuild and Start Services

```bash
cd /opt/makapix/deploy/stack
docker compose up -d --build
```

- [ ] Services rebuilt and started

### 6.4 Verify Deployment

```bash
# Check all containers are running
docker compose ps

# Check API health
curl https://makapix.club/api/health

# Check web is accessible
curl -I https://makapix.club

# Check MQTT WebSocket
# (Use browser dev tools or wscat)

# Check Caddy logs for TLS certificate provisioning
docker compose logs caddy | grep -i certificate
```

- [ ] All containers running
- [ ] API health check passes
- [ ] Web accessible at makapix.club
- [ ] MQTT WebSocket working
- [ ] TLS certificates provisioned

---

## Phase 7: Post-Deployment Verification

### 7.1 Functional Testing

- [ ] Homepage loads at `https://makapix.club`
- [ ] Login with GitHub works
- [ ] Can create a new post
- [ ] Can view posts
- [ ] Real-time notifications work (MQTT)
- [ ] Piskel editor loads and can submit art
- [ ] PixelC editor loads and can submit art
- [ ] Physical player can connect (if applicable)

### 7.2 Verify Reset

- [ ] All posts show 0 views
- [ ] No reactions visible on any posts
- [ ] No comments visible on any posts

### 7.3 Redirect Setup (Optional)

Set up redirect from `dev.makapix.club` to `makapix.club`:

Add to docker-compose.yml web service labels:
```yaml
caddy_1: dev.makapix.club
caddy_1.redir: https://makapix.club{uri} permanent
```

- [ ] Redirect configured (if desired)

---

## Phase 8: Cleanup

### 8.1 Remove CTA App (Optional)

If the CTA app folder is no longer needed:

```bash
# Keep for reference or remove
rm -rf /opt/makapix/apps/cta
```

- [ ] CTA app removed or kept for reference

### 8.2 Update Documentation

Update references in documentation files:

- [ ] `README.md`
- [ ] `docs/DEVELOPMENT.md`
- [ ] `docs/MQTT_PROTOCOL.md`
- [ ] `CLAUDE.md`

### 8.3 Commit Changes

```bash
git add -A
git commit -m "Go live: migrate from dev.makapix.club to makapix.club"
git push origin main
```

- [ ] Changes committed and pushed

---

## Rollback Plan

If critical issues are discovered after go-live:

### Quick Rollback (< 1 hour after deployment)

1. Restore database from backup:
   ```bash
   docker compose exec -T db psql -U owner makapix < /opt/backups/makapix_backup_YYYYMMDD_HHMMSS.sql
   ```

2. Revert code changes:
   ```bash
   git revert HEAD
   git push origin main
   ```

3. Redeploy:
   ```bash
   docker compose down
   docker compose up -d --build
   ```

### DNS Rollback

If DNS was changed from Squarespace:
1. Revert DNS records to point to original Squarespace IP
2. Wait for propagation

### GitHub OAuth Rollback

1. Go to GitHub OAuth App settings
2. Revert Homepage URL and Callback URL to `dev.makapix.club`

---

## Timeline Estimate

| Phase | Estimated Duration |
|-------|-------------------|
| Phase 1: External Config | 15-30 minutes |
| Phase 2: Database Reset | 5-10 minutes |
| Phase 3: Environment Config | 5 minutes |
| Phase 4: Source Code Changes | 10-15 minutes |
| Phase 5: MQTT Certs (optional) | 10 minutes |
| Phase 6: Deployment | 5-10 minutes |
| Phase 7: Verification | 15-20 minutes |
| Phase 8: Cleanup | 10 minutes |

**Total:** ~1-2 hours (excluding DNS propagation time)

---

## Notes and Decisions

_Record any decisions or notes during the migration here:_

-

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Migration Lead | | | |
| Verification | | | |

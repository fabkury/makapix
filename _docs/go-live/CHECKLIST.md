# Go-Live Quick Checklist

A condensed checklist for quick reference during migration. See `PLAN.md` for full details.

**Status: COMPLETED**
**Date: 2026-01-18**

---

## Pre-Flight

- [x] Database backup created (`/opt/makapix/backups/makapix_backup_20260118_162834.sql`)
- [x] DNS access verified
- [x] GitHub OAuth access verified

---

## Phase 1: External (MANUAL)

- [x] GitHub OAuth: Update Homepage URL → `https://makapix.club`
- [x] GitHub OAuth: Update Callback → `https://makapix.club/api/auth/github/callback`
- [x] DNS: `makapix.club` → VPS IP
- [x] DNS: `www.makapix.club` → VPS IP
- [x] DNS propagation confirmed

---

## Phase 2: Database

```sql
-- Executed successfully
DELETE FROM view_events;      -- 5359 rows deleted
DELETE FROM post_stats_daily; -- 3790 rows deleted
DELETE FROM post_stats_cache; -- 0 rows deleted
DELETE FROM reactions;        -- 141 rows deleted
DELETE FROM comments;         -- 51 rows deleted
DELETE FROM social_notifications; -- 70 rows deleted
```

- [x] View events deleted (5,359 records)
- [x] Reactions deleted (141 records)
- [x] Comments deleted (51 records)
- [x] Daily stats deleted (3,790 records)
- [x] Social notifications deleted (70 records)

---

## Phase 3: Environment Files

### `/opt/makapix/.env`
- [x] `BASE_URL=https://makapix.club`
- [x] `ENVIRONMENT=production`
- [x] `CORS_ORIGINS` updated
- [x] `GITHUB_REDIRECT_URI` updated
- [x] `MQTT_PUBLIC_HOST=makapix.club`
- [x] `API_BASE_URL=https://makapix.club/api`
- [x] `NEXT_PUBLIC_API_BASE_URL=https://makapix.club`
- [x] `NEXT_PUBLIC_MQTT_WS_URL=wss://makapix.club/mqtt`

### `/opt/makapix/deploy/stack/.env`
- [x] `WEB_DOMAIN=makapix.club`
- [x] `GITHUB_REDIRECT_URI` updated

---

## Phase 4: Code Changes

### docker-compose.yml
- [x] Line 123: MQTT_PUBLIC_HOST → makapix.club
- [x] Lines 269-270: Build args → makapix.club
- [x] Lines 278-279: Runtime env → makapix.club
- [x] Line 281: Caddy domain → `makapix.club, www.makapix.club`
- [x] Lines 314, 334: CSP headers → makapix.club
- [x] CTA service block commented out

### API
- [x] `api/app/routers/player.py` (3 locations updated)
- [x] `api/app/routers/mqtt.py` (1 location updated)

### Frontend
- [x] `apps/piskel/src/js/makapix/MakapixIntegration.js`
- [x] `web/src/pages/about.tsx`

---

## Phase 5: MQTT Certs

- [x] Decision: **Skip** (existing certs have makapix.club in SANs)
- [ ] (Not needed) Certs regenerated

---

## Phase 6: Deploy

```bash
cd /opt/makapix/deploy/stack
docker compose down
docker compose up -d --build
docker stop makapix-cta && docker rm makapix-cta  # Remove old CTA container
```

- [x] Services stopped
- [x] Services rebuilt
- [x] Old CTA container removed

---

## Phase 7: Verify

- [x] `docker compose ps` — all running (11 services healthy)
- [x] `curl https://makapix.club/api/health` — `{"status":"ok"}`
- [x] `curl -I https://makapix.club` — HTTP/2 200
- [x] `curl -I https://www.makapix.club` — HTTP/2 200
- [x] `curl -I https://piskel.makapix.club` — HTTP/2 200
- [x] `curl -I https://pixelc.makapix.club` — HTTP/2 200
- [x] MQTT bootstrap returns `makapix.club`
- [x] Posts preserved (2,798 posts)
- [x] Engagement data reset (0 views, 0 reactions, 0 comments)
- [ ] Login works (manual verification needed)
- [ ] Post creation works (manual verification needed)
- [ ] MQTT notifications work (manual verification needed)

---

## Phase 8: Cleanup

- [ ] Redirect from dev.makapix.club (optional)
- [ ] Documentation updated (CLAUDE.md, README.md, etc.)
- [ ] Changes committed

---

## Emergency Rollback

```bash
# Restore DB
docker compose exec -T db psql -U owner makapix < /opt/makapix/backups/makapix_backup_20260118_162834.sql

# Revert code
git revert HEAD && git push

# Redeploy
docker compose down && docker compose up -d --build
```

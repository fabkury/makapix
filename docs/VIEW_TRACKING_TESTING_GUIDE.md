# View Tracking Implementation - Testing & Deployment Guide

## Overview

This document provides testing procedures and deployment instructions for the comprehensive view tracking implementation that addresses the issues identified in `VIEW_TRACKING_ANALYSIS_REPORT.md`.

---

## Changes Summary

### 1. Blog Post View Tracking (Complete Implementation)

#### Database
- **Migration**: `20251208000000_add_blog_post_view_tracking.py`
- **Tables Created**:
  - `blog_post_view_events` - Raw events (7-day retention)
  - `blog_post_stats_daily` - Daily aggregates (30-day retention)

#### Backend
- **Models**: `BlogPostViewEvent`, `BlogPostStatsDaily` in `api/app/models.py`
- **Tracking Functions**: 
  - `record_blog_post_view()` - Single view tracking
  - `record_blog_post_views_batch()` - Batch view tracking
- **Celery Tasks**:
  - `write_blog_post_view_event` - Async event writer
  - `rollup_blog_post_view_events` - Daily aggregation
- **Statistics Service**: `BlogPostStatsService` in `api/app/services/blog_post_stats_service.py`
- **API Endpoints**:
  - `GET /api/blog-post/{id}/stats` - Retrieve blog post statistics
  - `GET /api/blog-post/b/{public_sqid}` - Now tracks views
  - `GET /api/blog-post/{id}` - Now tracks views

#### Features
- Author view exclusion (blog post owners don't count their own views)
- Privacy-preserving IP hashing (SHA256)
- Device type, country, referrer tracking
- Separate authenticated/unauthenticated statistics
- 5-minute Redis cache for computed stats
- Async Celery processing (non-blocking)

### 2. Frontend Page View Tracking (Complete Implementation)

#### Backend API
- **New Router**: `api/app/routers/tracking.py`
- **Endpoint**: `POST /api/track/page-view`
  - Public (no auth required)
  - Accepts `{ path: string, referrer?: string }`
  - Returns 204 No Content
  - Fire-and-forget design

#### Frontend
- **Hook**: `web/src/hooks/usePageViewTracking.ts`
  - Automatic tracking on all pages
  - Tracks initial load + route changes
  - Prevents duplicate tracking
  - Silent failure (errors don't affect UX)
  
- **Integration**: Added to `web/src/pages/_app.tsx`
  - Runs globally on all pages
  - No per-page code changes needed

#### Coverage
Now tracking ALL pages:
- Home `/`
- Search `/search`
- Blog feed `/blog`
- User profiles `/u/{sqid}`
- Blog posts `/b/{sqid}`
- Post/artwork pages `/p/{sqid}`
- All other routes

---

## Deployment Steps

### 1. Database Migration

```bash
# Navigate to API directory
cd api

# Run database migrations
alembic upgrade head

# Verify migration
alembic current
# Should show: 20251208000000 (head)
```

**Expected Output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 20251204000000_add_width_height_fields -> 20251208000000, add blog post view tracking tables
```

### 2. Verify Database Tables

```sql
-- Connect to your database and verify tables exist
\dt blog_post_view_events
\dt blog_post_stats_daily

-- Check indexes
\di blog_post_view_events*
\di blog_post_stats_daily*
```

### 3. Restart Backend Services

```bash
# Restart API server
docker-compose restart api

# Restart Celery workers
docker-compose restart celery-worker

# Restart Celery beat scheduler
docker-compose restart celery-beat
```

### 4. Verify Celery Beat Schedule

```bash
# Check Celery beat is running the new task
docker-compose logs celery-beat | grep rollup-blog-post-view-events
```

**Expected Log Entry:**
```
Scheduler: Sending due task rollup-blog-post-view-events
```

### 5. Deploy Frontend

```bash
# Navigate to web directory
cd web

# Install dependencies (if needed)
npm install

# Build for production
npm run build

# Start/restart Next.js server
npm run start
# or if using PM2, Docker, etc.:
# pm2 restart makapix-web
# docker-compose restart web
```

---

## Testing Procedures

### Test 1: Blog Post View Tracking

#### 1.1 Create a Test Blog Post
```bash
# Via API or frontend
POST /api/blog-post
{
  "title": "Test Blog Post",
  "body": "Testing view tracking"
}
```

#### 1.2 View the Blog Post
```bash
# Visit the blog post URL
GET /api/blog-post/b/{public_sqid}
```

#### 1.3 Check View Event in Database
```sql
SELECT *
FROM blog_post_view_events
WHERE blog_post_id = <blog_post_id>
ORDER BY created_at DESC
LIMIT 5;
```

**Expected Result:** 
- One row per view (excluding views by the blog post owner)
- `viewer_ip_hash` populated (SHA256 hash)
- `device_type`, `country_code`, `view_type` populated
- `created_at` is recent

#### 1.4 Check Blog Post Statistics API
```bash
# As the blog post owner or moderator
GET /api/blog-post/{id}/stats
Authorization: Bearer {access_token}
```

**Expected Response:**
```json
{
  "blog_post_id": 123,
  "total_views": 1,
  "unique_viewers": 1,
  "views_by_country": {"US": 1},
  "views_by_device": {"desktop": 1},
  "daily_views": [...],
  "total_reactions": 0,
  "total_comments": 0,
  ...
}
```

### Test 2: Frontend Page View Tracking

#### 2.1 Check Browser Developer Tools
1. Open any page on the frontend
2. Open Browser DevTools (F12) → Network tab
3. Filter for "track"
4. Refresh the page

**Expected Result:**
- POST request to `/api/track/page-view`
- Status: 204 No Content
- Payload: `{"path": "/", "referrer": "..."}`

#### 2.2 Navigate Between Pages
1. Navigate from home → blog → search → etc.
2. Check Network tab for each navigation

**Expected Result:**
- One POST request per page navigation
- No duplicate requests for same page

#### 2.3 Check Site Events in Database
```sql
SELECT event_type, page_path, device_type, country_code, created_at
FROM site_events
WHERE event_type = 'page_view'
ORDER BY created_at DESC
LIMIT 10;
```

**Expected Result:**
- Multiple rows with different `page_path` values
- Paths match frontend routes (e.g., "/", "/search", "/blog")
- Recent timestamps

### Test 3: Statistics Aggregation

#### 3.1 Wait for Daily Rollup (or Trigger Manually)
```bash
# Trigger manually via Celery
docker-compose exec celery-worker celery -A app.tasks call app.tasks.rollup_blog_post_view_events

# Check logs
docker-compose logs celery-worker | grep "rollup_blog_post_view_events"
```

**Expected Log Output:**
```
Rolled up X blog post daily aggregates, deleted Y old events
```

#### 3.2 Verify Daily Aggregates Table
```sql
SELECT blog_post_id, date, total_views, unique_viewers, views_by_country
FROM blog_post_stats_daily
ORDER BY date DESC
LIMIT 5;
```

**Expected Result:**
- Rows with aggregated data
- `total_views` > 0 for recent dates
- `views_by_country` JSON populated

### Test 4: Moderator Dashboard

#### 4.1 Access Moderator Dashboard
```bash
# Login as moderator
# Navigate to /mod-dashboard
# Click "Metrics" tab
```

#### 4.2 Verify Metrics Display
**Expected:**
- "Total Page Views (30 Days)" shows non-zero count
- "Daily Page Views" chart shows activity
- "Top Pages" list includes pages you visited
- "Top Countries" shows your country

#### 4.3 Toggle Authenticated/Unauthenticated Stats
**Expected:**
- Toggle works without errors
- Numbers change when toggling
- Authenticated counts ≤ Total counts

### Test 5: Author View Exclusion

#### 5.1 View Your Own Blog Post
1. Login as user A
2. Create a blog post
3. View your own blog post
4. Check statistics

**Expected Result:**
- View count should NOT increase when you view your own post
- Statistics API should show `total_views: 0` (if no other users viewed it)

#### 5.2 View Someone Else's Blog Post
1. Still logged in as user A
2. View a blog post by user B
3. Check user B's blog post statistics

**Expected Result:**
- View count SHOULD increase
- Your view is tracked

---

## Monitoring & Verification

### Key Metrics to Monitor

#### 1. Event Tables Growth
```sql
-- Monitor event table sizes (should stay small due to 7-day retention)
SELECT 
    'blog_post_view_events' as table_name,
    COUNT(*) as row_count,
    pg_size_pretty(pg_total_relation_size('blog_post_view_events')) as total_size
FROM blog_post_view_events
UNION ALL
SELECT 
    'site_events',
    COUNT(*),
    pg_size_pretty(pg_total_relation_size('site_events'))
FROM site_events;
```

**Expected:**
- Row counts grow with traffic but don't explode (7-day rolling window)
- Table sizes remain manageable (< 100MB for small sites)

#### 2. Daily Aggregates Tables
```sql
-- Monitor daily aggregate tables (30-day retention)
SELECT 
    'blog_post_stats_daily' as table_name,
    COUNT(*) as row_count,
    MIN(date) as oldest_date,
    MAX(date) as newest_date
FROM blog_post_stats_daily
UNION ALL
SELECT 
    'site_stats_daily',
    COUNT(*),
    MIN(date),
    MAX(date)
FROM site_stats_daily;
```

**Expected:**
- ~30 days of data per blog post/site
- Oldest date ~30 days ago
- Newest date = today or yesterday

#### 3. Celery Task Success Rate
```bash
# Check Celery logs for task failures
docker-compose logs celery-worker | grep -i error | tail -20

# Check Celery beat schedule
docker-compose logs celery-beat | grep -E "rollup|cleanup" | tail -10
```

**Expected:**
- No errors in task execution
- Daily rollup tasks running successfully
- Cleanup tasks removing old data

#### 4. Redis Cache Hit Rate
```bash
# Connect to Redis
redis-cli

# Check keys for stats cache
KEYS *blog_post_stats:*
KEYS *post_stats:*
KEYS *sitewide_stats*

# Check TTLs
TTL blog_post_stats:123
```

**Expected:**
- Cache keys exist for recently accessed stats
- TTL ~ 300 seconds (5 minutes)

---

## Troubleshooting

### Issue: Blog post views not being tracked

**Symptoms:** View count stays at 0

**Checks:**
1. Check if Celery worker is running: `docker-compose ps celery-worker`
2. Check Celery logs: `docker-compose logs celery-worker`
3. Verify Redis is accessible: `docker-compose ps redis`
4. Check database connection: `docker-compose logs api | grep -i database`

**Solutions:**
- Restart Celery worker: `docker-compose restart celery-worker`
- Check Redis connectivity: `redis-cli ping`
- Verify migration ran: `alembic current`

### Issue: Frontend tracking requests failing

**Symptoms:** 400/500 errors in browser console

**Checks:**
1. Check browser console for errors
2. Check API logs: `docker-compose logs api | grep track`
3. Verify endpoint is registered: `curl http://localhost:8000/api/docs` (check for /api/track/page-view)

**Solutions:**
- Restart API server: `docker-compose restart api`
- Check CORS settings in `api/app/main.py`
- Verify tracking router is imported in `main.py`

### Issue: Statistics not updating

**Symptoms:** Stats API returns old data

**Checks:**
1. Check Redis cache: `redis-cli KEYS *blog_post_stats*`
2. Check cache TTL: `redis-cli TTL blog_post_stats:123`
3. Try invalidating cache: `redis-cli DEL blog_post_stats:123`

**Solutions:**
- Wait for cache to expire (5 minutes)
- Manually invalidate cache via Redis CLI
- Restart Redis: `docker-compose restart redis`

### Issue: Daily rollup not working

**Symptoms:** Old events not being cleaned up, daily aggregates not created

**Checks:**
1. Check Celery beat is running: `docker-compose ps celery-beat`
2. Check beat schedule: `docker-compose logs celery-beat | grep rollup-blog-post`
3. Manually trigger task: `docker-compose exec celery-worker celery -A app.tasks call app.tasks.rollup_blog_post_view_events`

**Solutions:**
- Restart Celery beat: `docker-compose restart celery-beat`
- Check beat schedule configuration in `api/app/tasks.py`
- Verify task is registered: `docker-compose exec celery-worker celery -A app.tasks inspect registered`

---

## Performance Considerations

### Database Indexes

All necessary indexes are created by the migration:
- `blog_post_view_events`: Indexes on `blog_post_id`, `created_at`, `country_code`, `device_type`, `view_type`
- `blog_post_stats_daily`: Indexes on `blog_post_id`, `date`, and composite `(blog_post_id, date)`

### Query Performance

- **Event writes**: O(1) - Single INSERT, no joins
- **Stats computation**: O(n) where n = events in last 7 days + daily aggregates in last 30 days
  - Cached for 5 minutes in Redis
  - Typically < 100ms with caching
- **Daily rollup**: O(n) where n = events older than 7 days
  - Runs once per day during low-traffic hours

### Scaling Considerations

**For high-traffic sites (>1M views/day):**

1. **Increase Celery workers:**
   ```yaml
   celery-worker:
     deploy:
       replicas: 4
   ```

2. **Shard view events by blog_post_id:**
   ```python
   # Partition table by hash(blog_post_id)
   # Requires PostgreSQL 10+
   ```

3. **Increase Redis memory:**
   ```yaml
   redis:
     command: redis-server --maxmemory 2gb
   ```

4. **Use read replicas for stats queries:**
   - Route stats API to read replica
   - Route writes to primary

---

## Rollback Procedure

If issues occur after deployment:

### 1. Rollback Database Migration
```bash
cd api
alembic downgrade -1
```

**This will:**
- Drop `blog_post_view_events` table
- Drop `blog_post_stats_daily` table

### 2. Rollback Code
```bash
git revert <commit_hash>
git push origin main
```

### 3. Remove Celery Task
```bash
# Stop Celery beat
docker-compose stop celery-beat

# Remove rollup task from beat schedule in api/app/tasks.py
# Restart services
docker-compose up -d
```

### 4. Rollback Frontend
```bash
cd web
git checkout <previous_commit>
npm run build
npm run start
```

---

## Success Criteria

✅ **Blog Post View Tracking**
- Blog post views are recorded in `blog_post_view_events` table
- Author views are excluded
- Statistics API returns accurate data
- Daily rollup creates aggregates and cleans up old events

✅ **Frontend Page View Tracking**
- All pages send tracking requests on load
- Tracking requests return 204 status
- Site events are recorded in `site_events` table
- Moderator dashboard shows accurate page view counts

✅ **Data Retention**
- Raw events cleaned up after 7 days
- Daily aggregates retained for 30 days
- Old data automatically removed by scheduled tasks

✅ **Performance**
- View tracking doesn't block request handling (< 1ms overhead)
- Stats API responses cached (< 100ms with cache hit)
- Frontend tracking doesn't slow page loads (async fire-and-forget)

✅ **Privacy**
- IP addresses never stored (SHA256 hashed)
- No personally identifiable information in analytics
- Anonymous and authenticated users tracked separately

---

## Post-Deployment Checklist

- [ ] Database migration successful
- [ ] All tables created with correct indexes
- [ ] Celery workers running and processing tasks
- [ ] Celery beat running scheduled tasks
- [ ] Frontend tracking hook active on all pages
- [ ] Test blog post views being tracked
- [ ] Test frontend page views being tracked
- [ ] Statistics API returning data
- [ ] Moderator dashboard showing metrics
- [ ] Author view exclusion working
- [ ] Daily rollup task executed successfully
- [ ] Old data being cleaned up (check after 7+ days)
- [ ] Redis cache working
- [ ] No errors in logs
- [ ] Performance acceptable (page load times unchanged)

---

## Additional Notes

### Double Tracking on Some Pages

Pages like `/p/{sqid}` (artwork) and `/b/{sqid}` (blog posts) are now tracked twice:
1. Once by the frontend `usePageViewTracking` hook (sitewide page_view event)
2. Once by the backend API endpoint (specific view event for that post/blog)

**This is intentional:**
- Sitewide events track overall traffic patterns
- Post-specific events track engagement with specific content
- Different retention and aggregation rules apply to each

### Future Enhancements

Consider implementing:
- **Bot detection and filtering** - Filter out crawler traffic
- **User session tracking** - Track session duration and bounce rate
- **Conversion funnels** - Track user journeys through the site
- **A/B testing framework** - Split traffic for feature testing
- **Real-time analytics dashboard** - WebSocket-based live metrics
- **Export to analytics platforms** - Integration with Google Analytics, Mixpanel, etc.

---

**Document Version:** 1.0
**Last Updated:** December 8, 2025
**Author:** GitHub Copilot

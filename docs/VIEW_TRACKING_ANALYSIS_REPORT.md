# View Tracking and Statistics Analysis Report
## Makapix Club - Comprehensive Review

**Date**: December 8, 2025  
**Analysis Focus**: View tracking, statistics aggregation, metrics reporting, and data cleanup

---

## Executive Summary

This report provides a comprehensive analysis of the Makapix Club view tracking and statistics system. The investigation covered:
1. **Post (artwork) views** counting and statistics
2. **Blog post views** counting and statistics  
3. **Sitewide telemetry** and page view tracking
4. **Moderator dashboard metrics** aggregation
5. **Data cleanup and rollup** processes

### Key Findings

#### ✅ **WORKING PROPERLY**
- **Post/Artwork view tracking**: Fully implemented with async Celery workers
- **Sitewide page view tracking**: Implemented for API endpoints
- **Data cleanup and rollup**: Automated daily tasks properly configured
- **Moderator dashboard metrics**: All statistics properly aggregated and displayed

#### ⚠️ **ISSUES IDENTIFIED**
- **Blog post views**: **NOT TRACKED** - No view tracking implemented
- **Frontend page views**: **INCONSISTENTLY TRACKED** - Only backend API routes track page views
- **Missing view tracking**: Several critical pages don't track visits

---

## 1. Post (Artwork) Views Tracking

### Implementation Status: ✅ **FULLY IMPLEMENTED**

#### How It Works

1. **View Recording** (`api/app/utils/view_tracking.py`)
   - Function: `record_view()` and `record_views_batch()`
   - Captures: Device type, country, IP hash, user agent, referrer, view type
   - **Author views are excluded** (users don't count views on their own posts)
   - Deferred writes via Celery for zero request-path blocking

2. **Database Tables**
   - `view_events` - Raw events (last 7 days)
   - `post_stats_daily` - Daily rollups (8-30 days)

3. **View Types Tracked**
   - `intentional` - Direct click to view artwork
   - `listing` - Appeared in feed/list
   - `search` - Appeared in search results
   - `widget` - Viewed via embedded widget

4. **Where Views Are Tracked**
   - ✅ `/api/artwork.py` - `/p/{public_sqid}` endpoint (line 94)
   - ✅ `/api/posts.py` - Individual post fetches

5. **Statistics Computation** (`api/app/services/stats.py`)
   - On-demand computation with 5-minute Redis cache
   - Aggregates both authenticated and unauthenticated views separately
   - Returns 30-day trends, country/device/type breakdowns
   - Includes reactions and comments counts

6. **API Endpoint**
   - Route: `GET /api/post/{id}/stats`
   - Authorization: Post owner or moderator
   - Response includes both "all" and "authenticated-only" stats

### Data Retention
- **Raw events**: Kept for 7 days
- **Daily aggregates**: Kept for 30 days (configurable)
- **Cleanup**: Automated via `rollup_view_events` Celery task (daily)

---

## 2. Blog Post Views Tracking

### Implementation Status: ❌ **NOT IMPLEMENTED**

#### Critical Gap Identified

**Blog posts do NOT track views at all.** There is no equivalent to the post view tracking system for blog posts.

#### What's Missing

1. **No `record_view` calls** in blog post endpoints:
   - `/api/blog-post/b/{public_sqid}` - Canonical blog post view (line 193-235)
   - `/api/blog-post/{id}` - Legacy blog post view (line 238-291)
   
2. **No blog post view tracking tables** in the database

3. **No blog post statistics endpoint** (no `/api/blog-post/{id}/stats`)

4. **Frontend doesn't track blog views** at `/b/[sqid].tsx`

#### Impact

- Blog post owners cannot see view statistics
- Moderators cannot see blog post engagement metrics
- No data for "popular blog posts" features
- Blog posts appear in moderator metrics only via reactions/comments, not views

#### Recommendation

Implement blog post view tracking system parallel to post view tracking:
- Add `blog_post_view_events` table
- Add `blog_post_stats_daily` table
- Create `record_blog_post_view()` function
- Add view tracking to blog post GET endpoints
- Create blog post stats service and API endpoint

---

## 3. Sitewide Telemetry and Page Views

### Implementation Status: ⚠️ **PARTIALLY IMPLEMENTED**

#### How It Works

1. **Event Recording** (`api/app/utils/site_tracking.py`)
   - Function: `record_site_event(request, event_type, user, event_data)`
   - Event types: `page_view`, `signup`, `upload`, `api_call`, `error`
   - Deferred writes via Celery (zero blocking)

2. **Database Tables**
   - `site_events` - Raw events (last 7 days)
   - `site_stats_daily` - Daily rollups (8-30 days)

3. **Where Page Views ARE Tracked**
   - ✅ `/api/artwork.py` - Post views via `/p/{public_sqid}` (line 91)
   - ✅ `/api/routers/auth.py` - Signup events

4. **Where Page Views ARE NOT Tracked**
   - ❌ **Blog post pages** - `/b/{sqid}` (frontend)
   - ❌ **Home page** - `/` (frontend)
   - ❌ **Search page** - `/search` (frontend)
   - ❌ **User profile pages** - `/u/{sqid}` (frontend)
   - ❌ **Blog feed** - `/blog` (frontend)
   - ❌ **Recommended page** - `/recommended` (frontend)
   - ❌ **Hashtag pages** - `/hashtags/{tag}` (frontend)
   - ❌ Most other frontend Next.js pages

#### Issue Analysis

**The current implementation only tracks page views from backend API endpoints**, not from frontend page loads. This means:

- Only artwork detail page views are counted (via API call to `/api/p/{sqid}`)
- Most other pages (home, search, profiles, blog feed, etc.) are **NOT counted** in sitewide statistics
- This leads to **significant underreporting** of actual site traffic

#### How Pages Should Track Views

Frontend Next.js pages should call a tracking API endpoint on page load, OR the backend should track all requests to Next.js page routes. Current architecture relies on API calls to track views, but most pages don't make API calls that trigger tracking.

#### Path Normalization

The system has a `normalize_page_path()` function (`api/app/services/site_stats.py` line 27-76) that groups similar routes:
- `/post/...` → `/p/[post]`
- `/user/...` → `/u/[user]`
- `/blog-post/...` → `/b/[blog]`

However, **this only helps when paths are tracked in the first place**, which they currently aren't for most pages.

---

## 4. Moderator Dashboard Metrics Panel

### Implementation Status: ✅ **FULLY IMPLEMENTED**

The moderator dashboard at `/mod-dashboard` includes a comprehensive **Metrics** tab that displays:

#### Summary Cards (30 days)
- Total page views (all + authenticated)
- Unique visitors (all + authenticated)
- New signups
- New posts
- Total API calls
- Total errors

#### Visualizations
- 📈 **Page Views (Last 30 Days)** - Daily trend chart
- ⏰ **Page Views (Last 24 Hours)** - Hourly granular chart
- 📄 **Top Pages** - Top 20 pages by view count
- 🌍 **Top Countries** - Geographic breakdown with flags
- 📱 **Devices** - Desktop/mobile/tablet breakdown
- 🔗 **Top Referrers** - External traffic sources
- ⚠️ **Errors by Type** - Error tracking

#### Toggle Feature
Users can toggle between:
- "All statistics (including unauthenticated)"
- "Authenticated-only statistics"

This allows filtering out bot traffic and anonymous visitors.

#### Data Source
- API: `GET /api/admin/sitewide-stats`
- Service: `SiteStatsService` (`api/app/services/site_stats.py`)
- Cached for 5 minutes in Redis

#### Data Accuracy Note
**Due to the incomplete page view tracking noted in Section 3**, the metrics panel will show:
- ✅ Accurate counts for: Post views, signups, API calls, errors
- ❌ Incomplete counts for: Overall page views (missing frontend page loads)

---

## 5. Statistics Computation and Aggregation

### How Statistics Are Computed

#### Post Statistics (`api/app/services/stats.py`)

1. **Data Sources**
   - Raw events: `view_events` table (last 7 days)
   - Historical data: `post_stats_daily` table (8-30 days ago)
   - Reactions: `reactions` table
   - Comments: `comments` table (excluding hidden/deleted)

2. **Aggregation**
   - Total views and unique viewers (by IP hash)
   - Views by country (top 10)
   - Views by device type (desktop, mobile, tablet, player)
   - Views by view type (intentional, listing, search, widget)
   - Daily trends for last 30 days
   - Reactions by emoji
   - Comment counts

3. **Separated Statistics**
   - All statistics (including unauthenticated)
   - Authenticated-only statistics
   - Both computed simultaneously and returned together

4. **Caching**
   - Redis cache with 5-minute TTL
   - Cache key: `post_stats:{post_id}`

#### Sitewide Statistics (`api/app/services/site_stats.py`)

1. **Data Sources**
   - Raw events: `site_events` table (last 7 days)
   - Historical data: `site_stats_daily` table (8-30 days ago)
   - User signups: Counted from `signup` events
   - Post uploads: Counted from `upload` events

2. **Aggregation**
   - Total page views and unique visitors
   - New signups, posts, API calls, errors
   - Daily trends (30 days)
   - Hourly breakdown (last 24 hours, from events)
   - Views by page, country, device
   - Top referrers
   - Errors by type

3. **Caching**
   - Redis cache with 5-minute TTL
   - Cache key: `sitewide_stats`

---

## 6. Data Cleanup and Rollup Processes

### Implementation Status: ✅ **FULLY CONFIGURED**

All cleanup and rollup tasks are properly configured in Celery Beat schedule (`api/app/tasks.py` lines 323-355).

#### Scheduled Tasks

1. **`rollup_view_events`** - Daily
   - Aggregates view events older than 7 days
   - Groups by (post_id, date)
   - Upserts into `post_stats_daily`
   - Deletes old raw events
   - Task: `app.tasks.rollup_view_events`

2. **`rollup_site_events`** - Daily at 1AM UTC
   - Aggregates site events older than 7 days
   - Groups by date
   - Upserts into `site_stats_daily`
   - Deletes old raw events
   - Task: `app.tasks.rollup_site_events`

3. **`cleanup_old_site_events`** - Daily at 2AM UTC
   - Safety net to clean up any remaining old events
   - Deletes site events older than 7 days
   - Task: `app.tasks.cleanup_old_site_events`

4. **`cleanup_expired_stats_cache`** - Hourly
   - Cleans up expired cache entries from database
   - (Redis expires automatically, this is for DB persistence)
   - Task: `app.tasks.cleanup_expired_stats_cache`

5. **`cleanup_expired_player_registrations`** - Hourly
   - Cleans up expired pending player registrations
   - Task: `app.tasks.cleanup_expired_player_registrations`

#### Data Retention Policy

| Data Type | Retention Period | Storage Location |
|-----------|------------------|------------------|
| Raw view events | 7 days | `view_events` table |
| Raw site events | 7 days | `site_events` table |
| Daily rollups | 30 days | `post_stats_daily`, `site_stats_daily` |
| Computed statistics cache | 5 minutes | Redis |

#### How Rollup Works

1. **Query** events older than 7 days
2. **Aggregate** by relevant dimensions (post_id + date, or just date)
3. **Merge** with existing daily records if present
4. **Delete** processed raw events
5. **Commit** transaction

This ensures:
- Efficient storage (aggregated data is much smaller)
- Fast queries (no need to scan millions of raw events)
- Historical data preserved (30-day window for analysis)

---

## 7. Issues and Recommendations

### Critical Issues

#### Issue 1: Blog Post Views Not Tracked ❌ CRITICAL

**Problem**: Blog posts have no view tracking whatsoever.

**Impact**: 
- No visibility into blog post performance
- Cannot identify popular blog content
- Incomplete sitewide metrics (missing blog traffic)

**Recommendation**: 
1. Create `blog_post_view_events` and `blog_post_stats_daily` tables
2. Implement `record_blog_post_view()` in `view_tracking.py`
3. Add tracking to blog post endpoints:
   - `GET /api/blog-post/b/{public_sqid}`
   - `GET /api/blog-post/{id}`
4. Create blog post stats service and API endpoint
5. Add stats panel for blog posts in frontend

#### Issue 2: Frontend Page Views Not Tracked ❌ CRITICAL

**Problem**: Most frontend pages don't trigger sitewide page view tracking.

**Impact**:
- Sitewide metrics severely undercount actual traffic
- Only post detail pages and API-driven pages are counted
- Cannot analyze user navigation patterns
- Metrics dashboard shows incomplete data

**Recommendation**:
1. **Option A** (Preferred): Add client-side tracking beacon
   - Create `/api/track/page-view` endpoint that accepts page path
   - Call from frontend `useEffect` on all pages
   - Lightweight, doesn't block page load
   
2. **Option B**: Server-side middleware tracking
   - Add Next.js middleware to track all page requests
   - Forward tracking events to backend API
   - More reliable but requires middleware setup

Example client-side implementation:
```typescript
// web/src/hooks/usePageViewTracking.ts
export function usePageViewTracking() {
  useEffect(() => {
    fetch('/api/track/page-view', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: window.location.pathname })
    }).catch(() => {}); // Silent fail
  }, []);
}
```

### Minor Issues

#### Issue 3: Blog Post Statistics Not Available to Authors ⚠️ MEDIUM

**Problem**: Blog post authors cannot see statistics for their posts (because tracking doesn't exist).

**Recommendation**: Once blog post view tracking is implemented, add:
- Stats panel in blog post view page (similar to artwork stats)
- Stats dashboard for blog authors
- API endpoint for blog post statistics

#### Issue 4: No View Tracking for Embedded Widgets ⚠️ LOW

**Problem**: While the system has a `widget` view type, it's unclear if embedded widgets actually track views.

**Recommendation**: Verify that the Makapix widget (`/makapix-widget.js`) calls the tracking API when displaying embedded artwork.

---

## 8. Implementation Priorities

### Phase 1: Critical Fixes (High Priority)

1. **Implement blog post view tracking** (Estimated: 4-6 hours)
   - Database tables
   - Tracking functions
   - API endpoints
   - Frontend integration

2. **Implement frontend page view tracking** (Estimated: 2-3 hours)
   - Create tracking endpoint
   - Add tracking hook
   - Apply to all pages
   - Test with sitewide metrics

### Phase 2: Enhancements (Medium Priority)

3. **Add blog post statistics dashboard** (Estimated: 2-3 hours)
   - Stats panel component
   - API integration
   - Display on blog post pages

4. **Verify widget tracking** (Estimated: 1 hour)
   - Test embedded widgets
   - Ensure tracking calls are made
   - Update documentation

### Phase 3: Analytics Improvements (Low Priority)

5. **Enhanced metrics**
   - User retention metrics
   - Engagement metrics (time on site)
   - Conversion funnels
   - A/B test framework

---

## 9. Technical Architecture Summary

### System Design Strengths ✅

1. **Async Processing**: Celery workers handle all writes asynchronously
2. **Zero Request Blocking**: View tracking doesn't slow down page loads
3. **Efficient Storage**: Daily rollups reduce storage requirements
4. **Privacy-Preserving**: IP addresses are hashed (SHA256)
5. **Caching**: Redis caching prevents repeated computations
6. **Scalability**: Can handle high traffic without performance issues
7. **Flexibility**: Separate auth/unauth stats allow filtering

### Data Flow

```
Request → record_view/record_site_event → Celery Queue
                                              ↓
                                        Celery Worker
                                              ↓
                                    Write to view_events
                                      or site_events table
                                              ↓
                                    (7 days retention)
                                              ↓
                               Daily Rollup Task (Celery Beat)
                                              ↓
                           Aggregate and write to *_stats_daily
                                              ↓
                                    (30 days retention)
                                              ↓
                          Statistics Service (on-demand compute)
                                              ↓
                               Cache in Redis (5 min TTL)
                                              ↓
                                    API Response to Client
```

---

## 10. Database Schema Summary

### View Tracking Tables

#### `view_events` (Raw Events - 7 days)
- `id` (UUID, PK)
- `post_id` (Integer, FK to posts)
- `viewer_user_id` (Integer, FK to users, nullable)
- `viewer_ip_hash` (String, SHA256)
- `country_code` (String, nullable)
- `device_type` (String: desktop/mobile/tablet/player)
- `view_source` (String: web/api/widget/player)
- `view_type` (String: intentional/listing/search/widget)
- `user_agent_hash` (String, SHA256, nullable)
- `referrer_domain` (String, nullable)
- `created_at` (DateTime)

#### `post_stats_daily` (Daily Rollups - 30 days)
- `id` (Integer, PK)
- `post_id` (Integer, FK to posts)
- `date` (Date)
- `total_views` (Integer)
- `unique_viewers` (Integer)
- `views_by_country` (JSON)
- `views_by_device` (JSON)
- `views_by_type` (JSON)

### Site Events Tables

#### `site_events` (Raw Events - 7 days)
- `id` (UUID, PK)
- `event_type` (String: page_view/signup/upload/api_call/error)
- `page_path` (String, nullable)
- `visitor_ip_hash` (String, SHA256)
- `user_id` (Integer, FK to users, nullable)
- `device_type` (String)
- `country_code` (String, nullable)
- `referrer_domain` (String, nullable)
- `event_data` (JSON, nullable)
- `created_at` (DateTime)

#### `site_stats_daily` (Daily Rollups - 30 days)
- `id` (Integer, PK)
- `date` (Date)
- `total_page_views` (Integer)
- `unique_visitors` (Integer)
- `new_signups` (Integer)
- `new_posts` (Integer)
- `total_api_calls` (Integer)
- `total_errors` (Integer)
- `views_by_page` (JSON)
- `views_by_country` (JSON)
- `views_by_device` (JSON)
- `errors_by_type` (JSON)
- `top_referrers` (JSON)

---

## 11. Conclusion

The Makapix Club view tracking system is **well-architected and performant** with a solid foundation for analytics. However, there are **two critical gaps** that need to be addressed:

1. **Blog post views are not tracked at all** - This is a complete missing feature
2. **Frontend page views are inconsistently tracked** - Only backend API routes count, missing most actual page loads

Once these gaps are fixed, the system will provide comprehensive analytics across all content types and pages.

### Overall Assessment

| Component | Status | Grade |
|-----------|--------|-------|
| Post/Artwork View Tracking | ✅ Fully Implemented | A |
| Blog Post View Tracking | ❌ Not Implemented | F |
| Sitewide Page View Tracking | ⚠️ Partially Implemented | C |
| Statistics Computation | ✅ Fully Implemented | A |
| Data Cleanup/Rollup | ✅ Fully Implemented | A |
| Moderator Dashboard | ✅ Fully Implemented | A |
| **Overall System** | ⚠️ **Needs Fixes** | **B-** |

---

## Appendix A: File References

### Backend Files

**View Tracking**
- `/api/app/utils/view_tracking.py` - Core view tracking utilities
- `/api/app/utils/site_tracking.py` - Sitewide event tracking

**Services**
- `/api/app/services/stats.py` - Post statistics service
- `/api/app/services/site_stats.py` - Sitewide statistics service
- `/api/app/services/post_stats.py` - Post stats helper functions
- `/api/app/services/blog_post_stats.py` - Blog post count aggregation (NOT views)

**API Routes**
- `/api/app/routers/stats.py` - Statistics API endpoints
- `/api/app/routers/artwork.py` - Artwork view endpoints
- `/api/app/routers/posts.py` - Post endpoints
- `/api/app/routers/blog_posts.py` - Blog post endpoints (NO view tracking)

**Background Tasks**
- `/api/app/tasks.py` - Celery tasks for async processing and cleanup

**Database Migrations**
- `/api/alembic/versions/20251126000000_add_view_tracking.py`
- `/api/alembic/versions/20251127000000_add_sitewide_metrics.py`
- `/api/alembic/versions/20251125181822_clear_view_tracking_data.py`

### Frontend Files

**Components**
- `/web/src/components/StatsPanel.tsx` - Post statistics display
- `/web/src/components/SiteMetricsPanel.tsx` - Sitewide metrics display

**Pages**
- `/web/src/pages/mod-dashboard.tsx` - Moderator dashboard with metrics
- `/web/src/pages/p/[sqid].tsx` - Artwork detail page (tracked via API)
- `/web/src/pages/b/[sqid].tsx` - Blog post page (NOT tracked)
- `/web/src/pages/blog/[id].tsx` - Legacy blog redirect
- Various other pages (NOT tracked)

---

**Report Generated**: December 8, 2025  
**Analyst**: GitHub Copilot  
**Repository**: fabkury/makapix

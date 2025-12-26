# Known Issues and Limitations

This document centralizes all known issues, limitations, and areas for improvement in the View Tracking System.

## Summary Table

| ID | Category | Severity | Status | Description |
|----|----------|----------|--------|-------------|
| VTS-001 | Data Loss | Medium | Open | Authenticated stats limited to 7-day window |
| VTS-002 | Accuracy | Low | Open | Unique viewer approximation across aggregated days |
| VTS-003 | Feature Gap | Low | Open | Timezone analytics not implemented |
| VTS-004 | Architecture | Low | Open | Two MQTT view patterns should be consolidated |
| VTS-005 | Cache | Low | Open | Cache invalidation relies on TTL only |
| VTS-006 | Feature Gap | Low | Open | No playlist item-level view tracking |
| VTS-007 | Feature Gap | Low | Open | No geographic data for player views |
| VTS-008 | Performance | Low | Open | Artist dashboard queries all posts synchronously |

---

## VTS-001: Authenticated Statistics Limited to 7-Day Window

### Description

The `post_stats_daily` table does not separate authenticated vs. unauthenticated views. This means authenticated-only statistics are only available for the last 7 days (from raw `view_events`), while "all" statistics span the full 30-day window.

### Impact

- Artists cannot see authenticated-only historical trends beyond 7 days
- Toggle between "all" and "authenticated" shows different time ranges
- May cause confusion in stats interpretation

### Root Cause

The daily rollup task aggregates all views together without maintaining separate counters for authenticated users.

### Affected Components

- `app/services/stats.py` — `_compute_stats()` method
- `app/tasks.py` — `rollup_view_events()` task
- `app/models.py` — `PostStatsDaily` model

### Potential Resolution

Extend `PostStatsDaily` to include authenticated-only counters:

```
# Proposed additional columns
total_views_authenticated: int
unique_viewers_authenticated: int
views_by_country_authenticated: JSON
views_by_device_authenticated: JSON
views_by_type_authenticated: JSON
```

Requires migration and rollup task update.

### Workaround

Currently, users are informed via UI that authenticated stats cover a shorter window.

---

## VTS-002: Unique Viewer Approximation

### Description

When combining raw events (last 7 days) with daily aggregates (days 8-30), the `unique_viewers` count may slightly overcount because we cannot deduplicate IP hashes across aggregated data.

### Impact

- `unique_viewers` may be inflated by ~5-15% for high-traffic artworks
- More pronounced for artworks with returning visitors across day boundaries

### Root Cause

Daily aggregates store only the count of unique viewers, not the actual IP hashes. When merging with raw events or other daily records, deduplication is impossible.

### Affected Components

- `app/services/stats.py` — `_compute_stats()` method
- `app/services/artist_dashboard.py` — `get_artist_stats()` method

### Potential Resolution

Options:
1. Store HyperLogLog sketches instead of counts (allows probabilistic union)
2. Extend retention of raw events (storage cost tradeoff)
3. Document as "approximate" in UI

### Workaround

The UI could label unique viewers as "≈" (approximate) for 30-day stats.

---

## VTS-003: Timezone Analytics Not Implemented

### Description

Player devices report `local_datetime` and `local_timezone`, but the server stores these as-is without processing. No analytics leverage this data.

### Impact

- Cannot analyze viewing patterns by local time of day
- Cannot determine peak engagement hours in viewer's timezone
- Data is captured but unused

### Root Cause

Feature marked as "future work" in initial implementation; never prioritized.

### Affected Components

- `app/models.py` — Fields exist but unused
- `app/services/stats.py` — No timezone-based aggregation
- Frontend — No timezone visualization

### Potential Resolution

1. Parse and validate timezone data on ingest
2. Add hourly buckets to stats (e.g., "views by hour of day in local time")
3. Build "peak hours" visualization

### Workaround

None; data is stored for future use.

---

## VTS-004: Dual MQTT View Patterns

### Description

Two separate MQTT patterns exist for player view reporting:
1. Request/Response via `/request/+` topic
2. Fire-and-Forget via `/view` topic

This creates maintenance overhead and potential inconsistencies.

### Impact

- Two code paths to maintain
- Slightly different processing logic
- Documentation complexity

### Root Cause

Fire-and-forget was added later for p3a efficiency without deprecating the original pattern.

### Affected Components

- `app/mqtt/player_requests.py` — `_handle_submit_view()`
- `app/mqtt/player_views.py` — `_on_view_message()`

### Potential Resolution

Consolidate into a single pattern (likely fire-and-forget with optional ack flag).

### Workaround

Both patterns work correctly; this is a code quality issue only.

---

## VTS-005: Cache Invalidation Relies on TTL

### Description

When new views are recorded, the stats cache is not explicitly invalidated. Instead, it relies on the 5-minute TTL to expire.

### Impact

- Stats may be up to 5 minutes stale
- High-traffic artworks show delayed updates
- Not a critical issue for typical use cases

### Root Cause

Design decision to minimize Redis operations on the hot path (view recording).

### Affected Components

- `app/tasks.py` — `write_view_event()` does not invalidate cache
- `app/services/stats.py` — `invalidate_cache()` exists but isn't called on new views

### Potential Resolution

Options:
1. Call `invalidate_cache()` from `write_view_event()` task
2. Reduce TTL (increases computation load)
3. Accept as acceptable staleness

### Workaround

Users can wait 5 minutes or refresh multiple times.

---

## VTS-006: No Playlist Item-Level Tracking

### Description

When a player plays a playlist, views are recorded for the individual artwork posts but there's no tracking of the playlist container itself.

### Impact

- Cannot measure playlist popularity independent of artwork views
- No way to attribute view sources to specific playlists
- Playlist creators cannot see "views via my playlist"

### Root Cause

Playlists were added after the initial VTS design; view tracking wasn't extended.

### Affected Components

- `app/mqtt/player_views.py` — No playlist context captured
- `app/models.py` — No `playlist_id` field on `ViewEvent`

### Potential Resolution

Add optional `playlist_post_id` to `ViewEvent` when view originates from playlist playback.

### Workaround

None; feature gap.

---

## VTS-007: No Geographic Data for Player Views

### Description

Player views don't include country code because players don't expose their IP address to the server.

### Impact

- Geographic breakdown excludes player views entirely
- Artists with significant player audience see incomplete country data

### Root Cause

Players connect via MQTT with client certificates; IP is the broker's, not the player's. No mechanism to report player location.

### Affected Components

- `app/mqtt/player_views.py` — Sets `country_code = None`
- `app/mqtt/player_requests.py` — Sets `country_code = None`

### Potential Resolution

Options:
1. Players could optionally report their configured timezone/location
2. Accept as privacy-preserving behavior
3. Use certificate metadata if available

### Workaround

Document that country stats exclude player views.

---

## VTS-008: Artist Dashboard Queries All Posts

### Description

The Artist Dashboard loads statistics by querying all posts for a user, then fetching stats for each. This doesn't scale well for prolific artists.

### Impact

- Slow dashboard load for artists with many posts
- Database query count proportional to post count

### Root Cause

Initial implementation prioritized correctness over performance; no batching or caching.

### Affected Components

- `app/services/artist_dashboard.py` — `get_posts_stats_list()`

### Potential Resolution

1. Pre-aggregate user-level stats in a cached table
2. Use pagination with lazy loading
3. Implement background computation with Redis caching

### Workaround

Pagination is implemented (`limit`/`offset` params) but front-end may request many posts.

---

## Future Enhancement Requests

These are not bugs but requested features:

### FE-001: Metrics Dashboard (Grafana)

Build operational dashboard for view event monitoring including:
- View event rate (messages/second)
- Duplicate rate percentage
- Rate limit hit percentage
- Processing error rate

### FE-002: Channel Analytics

Dashboard showing view patterns by channel type:
- Which channels drive most views
- Time spent in each channel
- Conversion from channel views to intentional views

### FE-003: Play Order Analytics

Analyze which play order modes (server, created, random) result in more engagement.

### FE-004: Batch Database Writes

Group multiple view events for more efficient database inserts (currently 1 insert per event).

---

## Reporting New Issues

When discovering new VTS issues:

1. Assign an ID: `VTS-NNN` (next sequential number)
2. Categorize: Data Loss, Accuracy, Feature Gap, Architecture, Performance, Security
3. Assess severity: Critical, High, Medium, Low
4. Document in this file with:
   - Description
   - Impact
   - Root cause
   - Affected components
   - Potential resolution
   - Workaround (if any)

---

*Last updated: December 2025*


# Scheduled Tasks and Data Retention

Celery Beat runs periodic tasks for data hygiene, statistics aggregation, integrity checks, and certificate maintenance.

The active schedule is defined in [`api/app/tasks.py`](../../api/app/tasks.py). Daily times below use **America/New_York** (US Eastern, with daylight-saving changes). Interval tasks are timed from the scheduler, independent of wall-clock time.

## Task Schedule

| Task | Schedule | Description |
|------|----------|-------------|
| `mark-stale-players-offline` | Every minute | Mark players offline after three minutes without a heartbeat |
| `cleanup-expired-stats-cache` | Hourly | Remove expired computed statistics |
| `cleanup-expired-player-registrations` | Hourly | Remove expired pending registrations |
| `check-post-hashes` | Every 6 hours | Verify artwork file hashes |
| `cleanup-unverified-accounts` | Every 12 hours | Remove unverified accounts older than three days |
| `check-vault-free-space` | Every 6 hours | Check vault capacity and alert on low space |
| `rollup-view-events` | Daily 01:00 ET | Aggregate completed UTC days into post and site statistics; delete only rolled events beyond retention |
| `rollup-blog-post-view-events` | Daily 01:30 ET | Aggregate blog view statistics |
| `rollup-site-events` | Daily 02:00 ET | Aggregate site events and clean up retained raw events |
| `check-view-ingestion-health` | Daily 02:30 ET | Check rejected view events and stale rollup progress |
| `rollup-download-stats` | Daily 03:00 ET | Aggregate vault download logs for the previous UTC day |
| `cleanup-deleted-posts` | Daily 03:30 ET | Permanently remove user-deleted posts older than seven days |
| `cleanup-retired-artwork` | Daily 03:45 ET | Remove replaced artwork files after their retention deadline |
| `cleanup-expired-auth-tokens` | Daily 04:00 ET | Delete expired authentication tokens with applicable grace periods |
| `cleanup-report-ips` | Daily 04:15 ET | Clear anonymous reporter IPs after 30 days |
| `cleanup-expired-bdrs` | Daily 04:30 ET | Expire batch-download archives and purge old request records |
| `cleanup-social-notifications` | Daily 04:45 ET | Remove read notifications after 90 days, all after 365 days |
| `renew-crl-if-needed` | Daily 05:00 ET | Renew the MQTT revocation list when within seven days of expiry |
| `refresh-geoip-database` | Daily 05:15 ET | Check GeoIP freshness; download when missing or older than six days |

## Data Retention Summary

| Data | Retention | Aggregation Target | Notes |
|------|-----------|-------------------|-------|
| `view_events` | At least 7 days; cleanup only after rollup | `post_stats_daily` and the player slice of `site_stats_daily` | Raw artwork view events |
| `site_events` | 7 days | `site_stats_daily` | Page views, signups, uploads, errors |
| `blog_post_view_events` | 7 days | `blog_post_stats_daily` | Blog post view events |
| `post_stats_daily` | Permanent | -- | Daily rollups per post |
| `site_stats_daily` | Permanent | -- | Daily rollups with auth breakdowns |
| `blog_post_stats_daily` | Permanent | -- | Daily rollups per blog post |
| `post_stats_cache` | Until expiry | -- | Transient computed stats |
| Unverified accounts | 3 days | -- | Accounts that never completed email verification |
| Soft-deleted posts | 7 days | -- | Posts marked `deleted_by_user = true` |
| Expired auth tokens | 24h grace (refresh), 7 days (verification/reset) | -- | Cleaned in batches |
| Expired player registrations | On expiry | -- | Pending device registrations |
| Stale player connections | 3 minutes without heartbeat | -- | Marked offline, not deleted |
| Batch download ZIPs | On expiry | -- | Temporary ZIP archives |
| MQTT CRL | Renewed within 7 days of expiry | -- | Certificate Revocation List |
| Banned user profiles | **Never** automatically deleted | -- | See [Admin API](../http-api/admin.md) |

## Rollup Pipeline

The statistics pipeline runs in three stages:

1. **Rollup:** Raw events are aggregated into daily summary tables. For site events, this includes breakdowns by authenticated/unauthenticated, device type, country, page, and referrer.
2. **Cleanup:** The view/site rollup tasks own deletion after aggregation. There are no independently scheduled `cleanup-old-view-events` or `cleanup-old-site-events` jobs; independent cutoffs could delete events before they are counted.
3. **Cache expiry:** Computed post-level stats caches are cleaned hourly.

All rollup and cleanup tasks use batched processing to handle large datasets without memory issues.

## Integrity Checks

The `check-post-hashes` task (every 6 hours) reads artwork files from the vault, computes their SHA-256 hash, and compares against the stored hash in the database. On mismatch, the post is flagged `non_conformant = true`. If a previously non-conformant post now matches, the flag is cleared.

This detects vault corruption, incomplete uploads, or unauthorized file modifications.

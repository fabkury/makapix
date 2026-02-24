# Scheduled Tasks and Data Retention

Celery Beat runs periodic tasks for data hygiene, statistics aggregation, integrity checks, and certificate maintenance.

All tasks are defined in `api/app/tasks.py` via the `beat_schedule` configuration.

## Task Schedule

| Task | Schedule | Description |
|------|----------|-------------|
| `check-post-hashes` | Every 6 hours | Verify artwork file hashes against stored values; mark non-conformant on mismatch |
| `rollup-view-events` | Daily | Aggregate raw `view_events` (7 days) into `post_stats_daily` |
| `rollup-blog-post-view-events` | Daily | Aggregate raw `blog_post_view_events` (7 days) into `blog_post_stats_daily` |
| `rollup-site-events` | Daily | Aggregate raw `site_events` (7 days) into `site_stats_daily` with auth breakdowns |
| `cleanup-old-site-events` | Daily | Delete `site_events` older than 7 days (after rollup) |
| `cleanup-old-view-events` | Daily | Delete `view_events` older than 7 days (after rollup) |
| `cleanup-expired-stats-cache` | Hourly | Remove expired entries from `post_stats_cache` |
| `cleanup-expired-player-registrations` | Hourly | Remove player registrations past their expiry time |
| `mark-stale-players-offline` | Every minute | Set `connection_status = 'offline'` for players not seen in 3 minutes |
| `cleanup-expired-auth-tokens` | Every 12 hours | Delete expired refresh tokens (24h grace), verification tokens, and password reset tokens (7 days) |
| `cleanup-unverified-accounts` | Every 12 hours | Delete unverified accounts older than 3 days (with all associated data) |
| `cleanup-deleted-posts` | Daily | Hard-delete soft-deleted posts older than 7 days (cascades to comments, reactions, stats, notifications) |
| `cleanup-expired-bdrs` | Daily | Remove expired batch download request ZIP files and records |
| `renew-crl-if-needed` | Daily | Regenerate the MQTT Certificate Revocation List if it expires within 7 days |

## Data Retention Summary

| Data | Retention | Aggregation Target | Notes |
|------|-----------|-------------------|-------|
| `view_events` | 7 days | `post_stats_daily` | Raw artwork view events |
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

1. **Rollup** -- Raw events are aggregated into daily summary tables. For site events, this includes breakdowns by authenticated/unauthenticated, device type, country, page, and referrer.
2. **Cleanup** -- After rollup, raw events older than 7 days are deleted in batches to avoid long-running transactions.
3. **Cache expiry** -- Computed post-level stats caches are cleaned hourly.

All rollup and cleanup tasks use batched processing to handle large datasets without memory issues.

## Integrity Checks

The `check-post-hashes` task (every 6 hours) reads artwork files from the vault, computes their SHA-256 hash, and compares against the stored hash in the database. On mismatch, the post is flagged `non_conformant = true`. If a previously non-conformant post now matches, the flag is cleared.

This detects vault corruption, incomplete uploads, or unauthorized file modifications.

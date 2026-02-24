# Artist Dashboard API

Analytics dashboard for artists showing views, reactions, comments, and device/country breakdowns across all their artworks.

## Endpoint

```
GET /api/user/{user_key}/artist-dashboard
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `user_key` (path) | string | Yes | User's UUID or public Sqid |
| `page` | integer | No | Page number (default: 1) |
| `page_size` | integer | No | Posts per page (default: 20) |

## Access Control

| Viewer | Access |
|--------|--------|
| The artist themselves | Full access to own dashboard |
| Moderator or Owner | Full access to any user's dashboard |
| Other users | `403 Forbidden` |

## Response

```json
{
  "artist_stats": {
    "user_id": 42,
    "user_key": "a1b2c3d4-...",
    "total_posts": 15,
    "total_views": 1200,
    "unique_viewers": 340,
    "views_by_country": {"US": 400, "BR": 200, "DE": 150, "...": "..."},
    "views_by_device": {"desktop": 600, "mobile": 350, "tablet": 50, "player": 200},
    "total_reactions": 85,
    "reactions_by_emoji": {"heart": 40, "fire": 25, "star": 20},
    "total_comments": 12,
    "total_views_authenticated": 500,
    "unique_viewers_authenticated": 120,
    "views_by_country_authenticated": {"US": 200, "BR": 100, "...": "..."},
    "views_by_device_authenticated": {"desktop": 300, "mobile": 150, "...": "..."},
    "total_reactions_authenticated": 60,
    "reactions_by_emoji_authenticated": {"heart": 30, "fire": 20, "star": 10},
    "total_comments_authenticated": 8,
    "first_post_at": "2025-11-15T10:30:00Z",
    "latest_post_at": "2026-02-20T14:45:00Z",
    "computed_at": "2026-02-24T12:00:00Z"
  },
  "posts": [
    {
      "post_id": 101,
      "public_sqid": "xK9mQ",
      "title": "Sunset Castle",
      "created_at": "2026-02-20T14:45:00Z",
      "total_views": 150,
      "unique_viewers": 80,
      "total_reactions": 12,
      "total_comments": 3,
      "total_views_authenticated": 60,
      "unique_viewers_authenticated": 30,
      "total_reactions_authenticated": 8,
      "total_comments_authenticated": 2
    }
  ],
  "total_posts": 15,
  "page": 1,
  "page_size": 20,
  "has_more": false
}
```

## Schema Reference

### ArtistStatsResponse (aggregate)

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | integer | Internal user ID |
| `user_key` | string | User UUID |
| `total_posts` | integer | Total artworks posted |
| `total_views` | integer | Lifetime views across all posts |
| `unique_viewers` | integer | Distinct viewer count |
| `views_by_country` | object | Top 10 countries by view count |
| `views_by_device` | object | Views split by `desktop`, `mobile`, `tablet`, `player` |
| `total_reactions` | integer | Total emoji reactions received |
| `reactions_by_emoji` | object | Reaction counts by emoji type |
| `total_comments` | integer | Total comments received |
| `total_views_authenticated` | integer | Views from logged-in users |
| `unique_viewers_authenticated` | integer | Distinct logged-in viewers |
| `views_by_country_authenticated` | object | Country breakdown (auth only) |
| `views_by_device_authenticated` | object | Device breakdown (auth only) |
| `total_reactions_authenticated` | integer | Reactions from logged-in users |
| `reactions_by_emoji_authenticated` | object | Emoji breakdown (auth only) |
| `total_comments_authenticated` | integer | Comments from logged-in users |
| `first_post_at` | string (ISO 8601) | Timestamp of first artwork |
| `latest_post_at` | string (ISO 8601) | Timestamp of most recent artwork |
| `computed_at` | string (ISO 8601) | When these stats were computed |

### PostStatsListItem (per-post)

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | integer | Internal post ID |
| `public_sqid` | string | Public post identifier |
| `title` | string | Artwork title |
| `created_at` | datetime | When the artwork was posted |
| `total_views` | integer | Total views |
| `unique_viewers` | integer | Distinct viewers |
| `total_reactions` | integer | Total reactions |
| `total_comments` | integer | Total comments |
| `total_views_authenticated` | integer | Views from logged-in users |
| `unique_viewers_authenticated` | integer | Distinct logged-in viewers |
| `total_reactions_authenticated` | integer | Reactions from logged-in users |
| `total_comments_authenticated` | integer | Comments from logged-in users |

## Data Sources and Limitations

Statistics are computed from multiple tables with different retention windows:

| Source | Time Range | Data |
|--------|-----------|------|
| `view_events` | Last 7 days | Raw view events with full detail |
| `post_stats_daily` | 8--30 days | Pre-aggregated daily view counts |
| `reactions` | All time | Emoji reaction records |
| `comments` | All time | Comment records |

### Authenticated-Only Stats Limitation

The `*_authenticated` fields (views, viewers, reactions, comments from logged-in users) are computed **only from the last 7 days** of raw `view_events` data. The pre-aggregated `post_stats_daily` table does not separate authenticated from unauthenticated views. This means authenticated stats reflect recent activity only, while total stats cover the full 30-day window.

## Frontend Route

The artist dashboard is accessible at `/u/[sqid]/dashboard` in the web application.

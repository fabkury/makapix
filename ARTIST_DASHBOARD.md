# Artist Dashboard Feature

## Overview

The Artist Dashboard is a comprehensive analytics and statistics feature for Makapix Club that allows artists to view detailed telemetry data about their artwork and audience engagement.

## Features

### Artist-Level Statistics (Aggregated Across All Posts)

- **Total Posts**: Total number of artworks by the artist
- **Total Views**: Sum of all views across all posts
- **Unique Viewers**: Approximate count of unique viewers (based on IP hash)
- **Total Reactions**: Sum of all reactions across all posts
- **Total Comments**: Sum of all comments across all posts

### Detailed Breakdowns

- **Views by Country**: Top 10 countries with the most views
- **Views by Device**: Breakdown by desktop, mobile, tablet, and player devices
- **Reactions by Emoji**: Top emojis used in reactions

### Post-Level Statistics (Paginated List)

For each post, the dashboard shows:
- Post title (clickable link to post)
- Creation date
- Total views
- Unique viewers
- Total reactions
- Total comments

### Authenticated-Only Filter

Users can toggle between:
- **All Statistics**: Includes both authenticated and unauthenticated users
- **Authenticated Only**: Shows only statistics from logged-in users

This helps artists understand the difference between casual viewers and engaged community members.

## Access Control

### Who Can Access the Artist Dashboard?

1. **Artists**: Can view their own dashboard
   - Access via "📊 Dashboard" button on their profile page
   
2. **Moderators and Owners**: Can view any artist's dashboard
   - Access via "📊 Dashboard" button that appears when viewing any user's profile

3. **Regular Users**: Cannot access other artists' dashboards
   - No dashboard button appears when viewing other profiles

## API Endpoint

### GET `/api/user/{user_key}/artist-dashboard`

**Parameters:**
- `user_key` (path): User's UUID or public_sqid
- `page` (query, optional): Page number (default: 1)
- `page_size` (query, optional): Number of posts per page (default: 20, max: 100)

**Response:**
```json
{
  "artist_stats": {
    "user_id": 123,
    "user_key": "uuid-string",
    "total_posts": 42,
    "total_views": 15000,
    "unique_viewers": 8500,
    "views_by_country": {
      "US": 5000,
      "BR": 3000,
      "JP": 2000
    },
    "views_by_device": {
      "desktop": 8000,
      "mobile": 6000,
      "tablet": 800,
      "player": 200
    },
    "total_reactions": 1200,
    "reactions_by_emoji": {
      "❤️": 500,
      "🔥": 300,
      "👍": 200
    },
    "total_comments": 350,
    "total_views_authenticated": 12000,
    "unique_viewers_authenticated": 7000,
    "views_by_country_authenticated": {...},
    "views_by_device_authenticated": {...},
    "total_reactions_authenticated": 1100,
    "reactions_by_emoji_authenticated": {...},
    "total_comments_authenticated": 345,
    "first_post_at": "2024-01-01T00:00:00Z",
    "latest_post_at": "2024-12-01T00:00:00Z",
    "computed_at": "2024-12-08T18:00:00Z"
  },
  "posts": [
    {
      "post_id": 1,
      "public_sqid": "abc123",
      "title": "Cool Pixel Art",
      "created_at": "2024-12-01T00:00:00Z",
      "total_views": 500,
      "unique_viewers": 300,
      "total_reactions": 50,
      "total_comments": 10,
      "total_views_authenticated": 400,
      "unique_viewers_authenticated": 250,
      "total_reactions_authenticated": 48,
      "total_comments_authenticated": 10
    }
  ],
  "total_posts": 42,
  "page": 1,
  "page_size": 20,
  "has_more": true
}
```

**Authorization:**
- Requires authentication
- User must be the artist (owner of the profile) OR a moderator/owner

**Errors:**
- `401 Unauthorized`: Not authenticated
- `403 Forbidden`: Not authorized to view this dashboard
- `404 Not Found`: User not found

## Frontend Routes

### `/u/[sqid]/dashboard`

The dashboard page displays:
1. Summary statistics cards at the top
2. Detailed breakdowns (country, device, emoji)
3. Paginated list of posts with individual statistics
4. Toggle for authenticated-only filter
5. Pagination controls

## Technical Implementation

### Backend

**Service**: `api/app/services/artist_dashboard.py`
- `ArtistDashboardService`: Main service class
- `get_artist_stats()`: Computes aggregated statistics
- `get_posts_stats_list()`: Gets paginated post statistics

**Router**: `api/app/routers/users.py`
- New endpoint: `GET /api/user/{user_key}/artist-dashboard`

**Schemas**: `api/app/schemas.py`
- `ArtistStatsResponse`: Artist-level statistics
- `PostStatsListItem`: Individual post statistics
- `ArtistDashboardResponse`: Complete dashboard response

### Frontend

**Page**: `web/src/pages/u/[sqid]/dashboard.tsx`
- React component with state management
- Responsive design for mobile/desktop
- Pagination controls
- Authenticated filter toggle

**Profile Integration**: `web/src/pages/u/[sqid].tsx`
- Added "📊 Dashboard" button for artists and moderators

## Performance Considerations

1. **Redis Caching**: Individual post statistics are cached in Redis (5-minute TTL) via the existing `PostStatsService`

2. **Pagination**: Post list is paginated to handle artists with arbitrarily large numbers of posts

3. **Efficient Aggregation**: Uses existing `PostStatsDaily` aggregates for historical data (8-30 days ago) and raw `ViewEvent` data for recent data (last 7 days)

4. **Approximate Unique Viewers**: When aggregating across days, unique viewer counts from `PostStatsDaily` are summed as an approximation, since we can't deduplicate IP hashes from pre-aggregated data

5. **Authenticated Stats Limitation**: Authenticated-only statistics are computed only from recent views (last 7 days) because `PostStatsDaily` doesn't currently separate authenticated/unauthenticated data

## Data Sources

The dashboard aggregates data from:
- `ViewEvent` table: Raw view events (last 7 days)
- `PostStatsDaily` table: Daily aggregated statistics (8-30 days ago)
- `Reaction` table: All reactions on posts
- `Comment` table: All non-hidden, non-deleted comments
- `Post` table: Post metadata

## Future Enhancements

Potential improvements for future versions:

1. **Time Range Selector**: Allow artists to view statistics for custom date ranges
2. **Trend Graphs**: Add visual charts showing views/reactions/comments over time
3. **Comparison Mode**: Compare statistics between multiple posts
4. **Export Feature**: Allow artists to export their statistics as CSV/PDF
5. **Real-Time Updates**: Add WebSocket support for real-time statistics updates
6. **Advanced Filters**: Filter posts by hashtags, date range, or performance metrics
7. **Benchmarking**: Show how artist's statistics compare to platform averages
8. **Notification Preferences**: Allow artists to set up alerts for milestone achievements

## Security Considerations

1. **Authorization Checks**: Every request validates that the user is either the artist or a moderator
2. **Privacy**: IP addresses are hashed before storage (SHA256)
3. **Data Access**: Regular users cannot access other artists' dashboards
4. **Rate Limiting**: Uses existing rate limiting infrastructure to prevent abuse
5. **Input Validation**: All parameters are validated (page, page_size, user_key)

## Testing

See `api/tests/test_artist_dashboard.py` for:
- Authorization test cases
- Pagination test scenarios
- Manual testing checklist
- Edge case documentation

## Related Documentation

- [View Tracking System](../api/app/utils/view_tracking.py)
- [Post Statistics Service](../api/app/services/stats.py)
- [Telemetry Architecture](ARCHITECTURE.md)

# Player View Reporting Implementation

## Overview

This document describes the implementation of enhanced player view reporting functionality for the Makapix Club MQTT backend service. The implementation allows player devices (such as p3a) to report artwork views with rich contextual information.

## Implementation Date

December 22, 2025

## Changes Made

### 1. MQTT Schema Updates (`api/app/mqtt/schemas.py`)

#### SubmitViewRequest
- Added support for both old (`automated`/`intentional`) and new (`channel`/`artwork`) view intent values
- Added new optional fields:
  - `local_datetime`: Player's local date and time in ISO 8601 format with timezone
  - `local_timezone`: Player's IANA timezone identifier (e.g., "America/New_York")
  - `play_order`: Play order mode (0=server, 1=created_at, 2=random)
  - `channel`: Channel being played (all, promoted, user, by_user, artwork, hashtag)
  - `channel_user_sqid`: User sqid for 'by_user' channel context
  - `channel_hashtag`: Hashtag (without #) for 'hashtag' channel context

#### SubmitViewResponse
- Added `error_code` field for structured error handling
- Added `retry_after` field to indicate seconds until next view submission allowed (used for rate limiting)

### 2. Database Model Updates (`api/app/models.py`)

#### ViewEvent Model
Added new nullable columns for player-specific context:
- `player_id`: UUID foreign key to players table
- `local_datetime`: Player's local datetime as ISO string
- `local_timezone`: Player's IANA timezone (future: proper timezone support)
- `play_order`: Play order mode (0-2)
- `channel`: Channel name (indexed)
- `channel_context`: Context for channel (user_sqid or hashtag)

### 3. Database Migration (`api/alembic/versions/20251222000000_add_player_view_context.py`)

Created Alembic migration to add the new columns to the `view_events` table with appropriate indexes:
- Index on `player_id` for efficient player-based queries
- Index on `channel` for channel-based analytics

Migration has been successfully applied to the database.

### 4. Rate Limiting (`api/app/services/rate_limit.py`)

#### New Function: `check_player_view_rate_limit()`
- Implements strict rate limiting: 1 view per 5 seconds per player (global, not per-artwork)
- Uses Redis SETEX with 5-second TTL
- Returns `(allowed: bool, retry_after: float | None)` tuple
- Fails open if Redis is unavailable (allows request)
- Returns remaining TTL when rate limited

### 5. Handler Updates (`api/app/mqtt/player_requests.py`)

#### Updated `_handle_submit_view()` Function
1. **Rate Limit Check**: First action is to check rate limit before processing
2. **Intent Mapping**: Maps both old and new view_intent values:
   - `channel` → `automated` → `ViewType.LISTING`
   - `artwork` → `intentional` → `ViewType.INTENTIONAL`
3. **Channel Context**: Builds `channel_context` from `channel_user_sqid` or `channel_hashtag`
4. **Enhanced Event Data**: Passes all new fields to Celery task
5. **Rate Limit Response**: Returns structured error with `retry_after` when rate limited

### 6. Celery Task Updates (`api/app/tasks.py`)

#### Updated `write_view_event()` Task
- Extended to handle new player-specific fields
- Parses `player_id` as UUID with error handling
- Stores all new fields in the database
- Maintains backward compatibility (all new fields are optional)

## Key Design Decisions

### Rate Limiting Strategy
- **Global per player**: 1 view per 5 seconds regardless of artwork
- **Redis-based**: Uses SETEX for atomic operation with TTL
- **Fail-open**: Allows requests if Redis is unavailable
- **Client-friendly**: Returns `retry_after` seconds for better UX

### Intent Mapping
- Supports both old and new values for backward compatibility
- `channel` and `automated` both map to `ViewType.LISTING`
- `artwork` and `intentional` both map to `ViewType.INTENTIONAL`

### Local Timezone Handling
- Stored as-is without processing
- Future work: Implement proper timezone support for analytics
- Allows understanding of viewing patterns by local time of day

### Channel Context
- Single field stores either user_sqid or hashtag based on channel type
- Simplifies database schema while maintaining flexibility
- Indexed for efficient channel-based queries

## Testing

The implementation has been deployed and tested:
- ✅ Database migration applied successfully (revision: 20251222000000)
- ✅ API service restarted and healthy
- ✅ Worker service restarted and healthy
- ✅ No errors in startup logs
- ✅ All linter checks passed

## Usage Example

### Player Device Request

```json
{
  "request_id": "req_12345",
  "request_type": "submit_view",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "post_id": 42,
  "view_intent": "channel",
  "local_datetime": "2025-12-22T14:30:00-05:00",
  "local_timezone": "America/New_York",
  "play_order": 2,
  "channel": "hashtag",
  "channel_hashtag": "pixelart"
}
```

### Success Response

```json
{
  "request_id": "req_12345",
  "success": true,
  "error": null,
  "error_code": null,
  "retry_after": null
}
```

### Rate Limited Response

```json
{
  "request_id": "req_12346",
  "success": false,
  "error": "Rate limit exceeded. Players can submit 1 view per 5 seconds.",
  "error_code": "rate_limited",
  "retry_after": 3.2
}
```

## Future Enhancements

1. **Timezone Analytics**: Implement proper timezone conversion and analytics
2. **Per-Artwork Rate Limiting**: Consider allowing different artworks to be viewed more frequently
3. **Channel Analytics**: Build dashboards showing view patterns by channel type
4. **Play Order Analytics**: Analyze which play orders result in more engagement

## Deployment Notes

- The migration is backward compatible (all new fields are nullable)
- Existing view events continue to work without the new fields
- Rate limiting is enforced immediately after deployment
- Redis is required for rate limiting (fails open if unavailable)

## Related Files

- `api/app/mqtt/schemas.py` - MQTT request/response schemas
- `api/app/models.py` - Database models
- `api/app/mqtt/player_requests.py` - MQTT request handlers
- `api/app/services/rate_limit.py` - Rate limiting service
- `api/app/tasks.py` - Celery background tasks
- `api/alembic/versions/20251222000000_add_player_view_context.py` - Database migration


# P3A Fire-and-Forget View Event Implementation

## Overview

This document describes the implementation of fire-and-forget view event support for p3a player devices. This is a separate implementation from the request/response pattern, designed specifically for p3a's MQTT-based view reporting.

## Implementation Date

December 22, 2025

## Architecture

### MQTT Topic Pattern

**Topic:** `makapix/player/{player_key}/view`

- **QoS:** 1 (at least once delivery)
- **Retained:** No
- **Direction:** Player → Server (fire-and-forget, no response)

### Key Components

1. **MQTT ACL** (`mqtt/aclfile`)
   - Players can write to `makapix/player/%u/view`
   - API server can read from `makapix/player/+/view`

2. **Schema** (`api/app/mqtt/schemas.py`)
   - `P3AViewEvent`: Pydantic model for p3a's payload format

3. **Subscriber** (`api/app/mqtt/player_views.py`)
   - Dedicated MQTT subscriber for `/view` topic
   - Fire-and-forget processing (no response sent)

4. **Deduplication** (`api/app/services/rate_limit.py`)
   - `check_view_duplicate()`: Prevents MQTT QoS 1 retransmissions from creating duplicates
   - Uses Redis with 60-second TTL

5. **Rate Limiting** (`api/app/services/rate_limit.py`)
   - `check_player_view_rate_limit()`: 1 view per 5 seconds per player
   - Silently discards excess views (fire-and-forget)

## P3A Payload Format

```json
{
  "post_id": 192,
  "timestamp": "2025-12-22T16:24:15Z",
  "timezone": "",
  "intent": "channel",
  "play_order": 2,
  "channel": "all",
  "player_key": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### Field Mapping

| P3A Field | Server Field | Notes |
|-----------|--------------|-------|
| `post_id` | `post_id` | Direct mapping |
| `timestamp` | `local_datetime` | Stored as-is; NULL if "1970-01-01T00:00:00Z" |
| `timezone` | `local_timezone` | Currently empty string from p3a |
| `intent` | `view_type` | `artwork` → `intentional`, `channel` → `listing` |
| `play_order` | `play_order` | Direct mapping (0-2) |
| `channel` | `channel` | Direct mapping |
| `player_key` | `player_id` | Validated against topic |

## Processing Flow

```
1. p3a publishes to makapix/player/{key}/view
2. Server receives message (QoS 1)
3. Validate player_key matches topic
4. Authenticate player (must be registered)
5. Check for duplicate (MQTT retransmission)
   → If duplicate: Discard silently
6. Check rate limit (1 per 5 seconds)
   → If rate limited: Discard silently
7. Validate post exists
8. Skip if player owner = post owner
9. Handle unsynced timestamp (1970-01-01)
   → Store NULL for local_datetime
10. Dispatch to Celery worker
11. Write to database asynchronously
```

## Special Handling

### Unsynced Device Time

p3a sends `"1970-01-01T00:00:00Z"` when time is not synchronized.

**Server behavior:**
- Detects this timestamp
- Stores `NULL` for `local_datetime`
- Uses server's `created_at` for ordering
- Logs debug message

### Duplicate Detection

MQTT QoS 1 may cause retransmissions.

**Deduplication key:** `view_dedup:{player_key}:{post_id}:{timestamp}`

**TTL:** 60 seconds (enough for retransmissions)

**Behavior:**
- First occurrence: Processed normally
- Duplicates: Silently discarded
- Logged at debug level

### Rate Limiting

**Limit:** 1 view per 5 seconds per player (global)

**Behavior:**
- Enforced before processing
- Excess views silently discarded
- No response sent (fire-and-forget)
- Logged at debug level

## Backward Compatibility

The existing request/response pattern (`submit_view` via `/request/+`) remains fully functional:

- Web clients can continue using the request/response pattern
- Future player firmware versions can choose either approach
- Both patterns write to the same `view_events` table

**Note:** Consider consolidating these approaches in a future refactor.

## Database Schema

All fields from the enhanced view tracking implementation are used:

- `player_id`: UUID reference to player
- `local_datetime`: ISO timestamp from p3a (or NULL)
- `local_timezone`: IANA timezone (currently empty)
- `play_order`: 0=server, 1=created, 2=random
- `channel`: Channel identifier
- `channel_context`: User sqid or hashtag (if applicable)

## Testing & Verification

### Deployment Status

✅ MQTT ACL updated and applied
✅ View subscriber started successfully
✅ All services healthy
✅ No errors in logs

### Log Verification

```bash
# Check subscriber status
docker compose logs api | grep "view.*subscriber"

# Expected output:
# INFO:app.mqtt.player_views:Player view event subscriber started
# INFO:app.mqtt.player_views:Subscribed to makapix/player/+/view
```

### Testing with p3a

When p3a sends view events, you should see:

```
INFO:app.mqtt.player_views:Recorded view for post {id} from player {key} (fire-and-forget)
```

Debug logs for rate limiting:
```
DEBUG:app.mqtt.player_views:Rate limited view from player {key}, retry after {seconds}s
```

Debug logs for duplicates:
```
DEBUG:app.mqtt.player_views:Discarded duplicate view: player={key}, post={id}
```

## Configuration

### Environment Variables

No new environment variables required. Uses existing MQTT configuration:

- `MQTT_BROKER_HOST` (default: `mqtt`)
- `MQTT_BROKER_PORT` (default: `1883`)
- `MQTT_USERNAME` (default: `api-server`)
- `MQTT_PASSWORD` (required)

### Redis

Required for deduplication and rate limiting:

- `REDIS_URL` or `CELERY_BROKER_URL`
- Falls back to `redis://cache:6379/0`

## Performance Considerations

### Fire-and-Forget Benefits

1. **No response overhead**: p3a doesn't wait for acknowledgment
2. **Faster processing**: No need to construct response messages
3. **Simpler error handling**: Errors logged server-side only

### Async Processing

- View events dispatched to Celery immediately
- Database writes happen asynchronously
- No blocking of MQTT message loop

### Redis Usage

- Deduplication keys: ~60 bytes per view
- Rate limit keys: ~50 bytes per player
- All keys expire automatically (60s for dedup, 5s for rate limit)

## Monitoring

### Key Metrics

1. **View event rate**: Messages per second on `/view` topic
2. **Duplicate rate**: Percentage of discarded duplicates
3. **Rate limit hits**: Percentage of rate-limited views
4. **Processing errors**: Exceptions in view handler

### Log Levels

- **INFO**: Successful view recording
- **DEBUG**: Rate limits, duplicates, unsynced timestamps
- **WARNING**: Invalid payloads, unregistered players, missing posts
- **ERROR**: Processing exceptions, Redis failures

## Future Enhancements

1. **Metrics Dashboard**: Grafana dashboard for view event monitoring
2. **Timezone Support**: Proper timezone conversion and analytics
3. **Channel Context**: Extract user_sqid/hashtag from p3a payload
4. **API Consolidation**: Merge request/response and fire-and-forget patterns
5. **Batch Processing**: Group multiple views for more efficient database writes

## Related Files

- `mqtt/aclfile` - MQTT access control list
- `api/app/mqtt/schemas.py` - P3AViewEvent schema
- `api/app/mqtt/player_views.py` - View event subscriber
- `api/app/services/rate_limit.py` - Deduplication and rate limiting
- `api/app/main.py` - Subscriber startup
- `api/app/tasks.py` - Celery task for database writes
- `api/app/models.py` - ViewEvent database model

## Troubleshooting

### Views not being recorded

1. Check subscriber is running:
   ```bash
   docker compose logs api | grep "view.*subscriber"
   ```

2. Check MQTT ACL allows player to write:
   ```bash
   docker compose exec mqtt cat /mosquitto/config/aclfile
   ```

3. Check player is registered:
   ```bash
   docker compose logs api | grep "unregistered player"
   ```

### Duplicate views

1. Check deduplication is working:
   ```bash
   docker compose logs api | grep "Duplicate view"
   ```

2. Verify Redis is available:
   ```bash
   docker compose ps cache
   ```

### Rate limiting issues

1. Check rate limit logs:
   ```bash
   docker compose logs api | grep "Rate limited view"
   ```

2. Verify 5-second window is appropriate for p3a's behavior
   (p3a sends first view at 5s, then every 30s)


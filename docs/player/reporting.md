# Reporting

Report player status, view events, and submit reactions.

## Status Updates

Report your player's connection status and current state.

### Topic

```
makapix/player/{player_key}/status
```

### Payload

```json
{
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "status": "online",
  "current_post_id": 12345,
  "firmware_version": "2.1.0"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `player_key` | string | Yes | Player's UUID |
| `status` | string | Yes | Connection status |
| `current_post_id` | integer | No | Currently displayed post ID |
| `firmware_version` | string | No | Current firmware version |

### Status Values

| Status | When to Send |
|--------|--------------|
| `online` | After successful connection |
| `offline` | Before graceful disconnect (if possible) |

### When to Update

Send status updates:

1. On initial connection
2. When `current_post_id` changes
3. Periodically (every 5-10 minutes) as a heartbeat
4. After firmware update

## View Events

Report when artwork is displayed. View events power artist analytics and trending.

### Topic

```
makapix/player/{player_key}/view
```

### Payload

```json
{
  "post_id": 12345,
  "timestamp": "2024-01-15T10:30:00Z",
  "timezone": "",
  "intent": "channel",
  "play_order": 0,
  "channel": "all",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "request_ack": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `post_id` | integer | Yes | Viewed post ID |
| `timestamp` | string | Yes | ISO 8601 UTC timestamp |
| `timezone` | string | Yes | Reserved (use empty string) |
| `intent` | string | Yes | View origin |
| `play_order` | integer | Yes | Playback order mode |
| `channel` | string | Yes | Active channel name |
| `player_key` | string | Yes | Player's UUID |
| `channel_user_sqid` | string | No | User sqid for by_user channel |
| `channel_hashtag` | string | No | Hashtag for hashtag channel |
| `request_ack` | boolean | No | Request acknowledgment |

### Intent Values

| Intent | Description |
|--------|-------------|
| `artwork` | User explicitly requested this artwork |
| `channel` | Artwork shown via automated playback |

### Play Order Values

| Value | Description |
|-------|-------------|
| 0 | Server order (default) |
| 1 | Created at (chronological) |
| 2 | Random |

### Acknowledgment

Set `request_ack: true` to receive confirmation:

**Ack Topic:** `makapix/player/{player_key}/view/ack`

```json
{
  "success": true
}
```

Or on error:

```json
{
  "success": false,
  "error": "Rate limited, retry after 5s",
  "error_code": "rate_limited"
}
```

### Rate Limiting

View events are rate limited to **1 per 5 seconds per player**. This matches typical artwork dwell times and prevents abuse.

Duplicate events (same post_id + timestamp) are automatically ignored.

### Unsynced Time

If your device doesn't have accurate time:

```json
{
  "timestamp": "1970-01-01T00:00:00Z"
}
```

The server recognizes this special timestamp and records the view with server time instead.

## Reactions

Submit emoji reactions on behalf of the device owner.

### Submit Reaction

**Request Topic:** `makapix/player/{player_key}/request/{request_id}`

```json
{
  "request_id": "react-001",
  "request_type": "submit_reaction",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "post_id": 12345,
  "emoji": "❤️"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | integer | Post to react to |
| `emoji` | string | Emoji to add (1-20 characters) |

**Response Topic:** `makapix/player/{player_key}/response/{request_id}`

```json
{
  "request_id": "react-001",
  "success": true
}
```

### Revoke Reaction

Remove a previously added reaction.

```json
{
  "request_id": "react-002",
  "request_type": "revoke_reaction",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "post_id": 12345,
  "emoji": "❤️"
}
```

Response:

```json
{
  "request_id": "react-002",
  "success": true
}
```

### Reaction Limits

- Maximum 5 reactions per user per post
- Reactions are idempotent (submitting twice has no effect)
- Revoking non-existent reactions succeeds silently

### Reaction Error Codes

| Error Code | Description |
|------------|-------------|
| `invalid_emoji` | Empty or too long emoji |
| `not_found` | Post doesn't exist |
| `deleted` | Post was deleted |
| `reaction_limit_exceeded` | Already have 5 reactions on this post |

## Comments

Retrieve comments for a post.

### Get Comments

**Request:**

```json
{
  "request_id": "comments-001",
  "request_type": "get_comments",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "post_id": 12345,
  "cursor": null,
  "limit": 50
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `post_id` | integer | required | Post ID |
| `cursor` | string | null | Pagination cursor |
| `limit` | integer | 50 | Comments per page (1-200) |

**Response:**

```json
{
  "request_id": "comments-001",
  "success": true,
  "comments": [
    {
      "comment_id": "123e4567-e89b-12d3-a456-426614174000",
      "post_id": 12345,
      "author_handle": "commenter",
      "body": "Great artwork!",
      "depth": 0,
      "parent_id": null,
      "created_at": "2024-01-15T11:00:00Z",
      "deleted": false
    }
  ],
  "next_cursor": "50",
  "has_more": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| `comment_id` | UUID | Unique comment identifier |
| `post_id` | integer | Parent post |
| `author_handle` | string | Comment author (null if anonymous) |
| `body` | string | Comment text |
| `depth` | integer | Nesting level (0-2) |
| `parent_id` | UUID | Parent comment (null for top-level) |
| `created_at` | datetime | Comment timestamp |
| `deleted` | boolean | Whether comment was deleted |

Comments are limited to depth 2 (replies to replies).

## Playsets

Retrieve playset configuration for advanced playback modes.

### Get Playset

**Request:**

```json
{
  "request_id": "playset-001",
  "request_type": "get_playset",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "playset_name": "followed_artists"
}
```

**Response:**

```json
{
  "request_id": "playset-001",
  "success": true,
  "playset_name": "followed_artists",
  "channels": [
    {
      "type": "user",
      "identifier": "k5fNx",
      "display_name": "@pixelartist",
      "weight": 10
    },
    {
      "type": "user",
      "identifier": "m8gPq",
      "display_name": "@otherartist",
      "weight": 5
    }
  ],
  "exposure_mode": "manual",
  "pick_mode": "recency"
}
```

### Channel Types

| Type | Description |
|------|-------------|
| `named` | Built-in channel (all, promoted) |
| `user` | Specific user's artwork |
| `hashtag` | Posts with hashtag |
| `sdcard` | Local SD card content |

### Exposure Modes

| Mode | Description |
|------|-------------|
| `equal` | Equal time for each channel |
| `manual` | Use weight values |
| `proportional` | Weight by content amount |

### Pick Modes

| Mode | Description |
|------|-------------|
| `recency` | Newest first |
| `random` | Random selection |

## Error Responses

All request types can return errors:

```json
{
  "request_id": "req-001",
  "success": false,
  "error": "Player not authenticated or not registered",
  "error_code": "authentication_failed"
}
```

### Common Error Codes

| Error Code | Description |
|------------|-------------|
| `authentication_failed` | Player not registered |
| `not_found` | Resource doesn't exist |
| `deleted` | Resource was deleted |
| `rate_limited` | Too many requests |
| `internal_error` | Server error |
| `invalid_request` | Malformed request |
| `unknown_request_type` | Unsupported request type |

## Best Practices

### View Event Timing

Send view events when:

1. Artwork display begins (not during loading)
2. After any minimum dwell threshold (e.g., 2 seconds)
3. Not for images that fail to load

### Reaction UX

For physical devices:

1. Dedicate a button for "like" (❤️)
2. Show reaction state on display
3. Handle offline mode (queue reactions)

### Status Heartbeat

```python
import time
import threading

def heartbeat_loop():
    while running:
        publish_status()
        time.sleep(300)  # 5 minutes

heartbeat_thread = threading.Thread(target=heartbeat_loop)
heartbeat_thread.start()
```

### Offline Handling

Queue events when disconnected:

```python
event_queue = []

def report_view(post_id):
    event = create_view_event(post_id)
    if is_connected():
        publish(event)
    else:
        event_queue.append(event)

def on_reconnect():
    while event_queue:
        event = event_queue.pop(0)
        publish(event)
```

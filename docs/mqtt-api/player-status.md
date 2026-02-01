# Player Status

Report connection status, playback state, and view events.

## Status Updates

Report your player's state to the server.

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
| `status` | string | Yes | Connection status (`online`, `offline`) |
| `current_post_id` | integer | No | Currently displayed post ID |
| `firmware_version` | string | No | Current firmware version |

### When to Send

| Event | Action |
|-------|--------|
| Connection established | Send `online` status |
| Artwork changes | Update `current_post_id` |
| Graceful disconnect | Send `offline` status (if possible) |
| Heartbeat | Send periodically (every 5-10 minutes) |
| Firmware update | Update `firmware_version` |

### Server Actions

When the server receives a status update:

1. Updates `connection_status` in player record
2. Updates `last_seen_at` timestamp
3. Updates `current_post_id` (if provided)
4. Updates `firmware_version` (if provided)

## View Events

Report when artwork is displayed. Powers artist analytics and trending.

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
  "channel_user_sqid": null,
  "channel_hashtag": null,
  "request_ack": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `post_id` | integer | Yes | Viewed post ID |
| `timestamp` | string | Yes | ISO 8601 UTC timestamp |
| `timezone` | string | Yes | Reserved (use empty string `""`) |
| `intent` | string | Yes | How view originated |
| `play_order` | integer | Yes | Playback order mode |
| `channel` | string | Yes | Active channel name |
| `player_key` | string | Yes | Player's UUID |
| `channel_user_sqid` | string | No | User sqid for `by_user` channel |
| `channel_hashtag` | string | No | Tag for `hashtag` channel |
| `request_ack` | boolean | No | Request acknowledgment |

### Intent Values

| Intent | Description | Example |
|--------|-------------|---------|
| `artwork` | User explicitly requested this artwork | Button press, web command |
| `channel` | Automated playback from channel | Normal rotation |

### Play Order Values

| Value | Description |
|-------|-------------|
| 0 | Server order (insertion order) |
| 1 | Created at (chronological) |
| 2 | Random |

### Channel Values

| Channel | Context Field |
|---------|---------------|
| `all` | none |
| `promoted` | none |
| `user` | none (player owner's artwork) |
| `by_user` | `channel_user_sqid` |
| `hashtag` | `channel_hashtag` |

### Timestamp Handling

#### Synced Device

Use current UTC time:

```json
{
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### Unsynced Device

If your device doesn't have accurate time, use the special "unsynced" timestamp:

```json
{
  "timestamp": "1970-01-01T00:00:00Z"
}
```

The server recognizes this and uses server time instead.

### Acknowledgment

Set `request_ack: true` to receive confirmation.

#### Ack Topic

```
makapix/player/{player_key}/view/ack
```

#### Success Response

```json
{
  "success": true
}
```

#### Error Response

```json
{
  "success": false,
  "error": "Rate limited, retry after 5s",
  "error_code": "rate_limited"
}
```

### Error Codes

| Error Code | Description |
|------------|-------------|
| `player_key_mismatch` | Topic player_key != payload player_key |
| `player_not_registered` | Player not found or not registered |
| `player_no_owner` | Player has no linked user |
| `duplicate` | Duplicate view event (already recorded) |
| `rate_limited` | Too many views (>1 per 5 seconds) |
| `post_not_found` | Post doesn't exist |
| `processing_error` | Server error |

### Rate Limiting

View events are rate limited to **1 per 5 seconds per player**.

This aligns with typical dwell times and prevents abuse. Excess events are silently dropped unless `request_ack: true`, in which case an error is returned.

### Duplicate Detection

The server detects duplicate events using:

- `player_key`
- `post_id`
- `timestamp`

If the same combination arrives twice (e.g., MQTT QoS 1 redelivery), the duplicate is discarded.

### Self-View Filtering

Views are not recorded when the player's owner is the post author. This keeps artist analytics accurate.

## Example: Status Reporting

```python
import json
import paho.mqtt.client as mqtt

def report_status(client, player_key, current_post_id=None):
    status = {
        "player_key": player_key,
        "status": "online",
        "firmware_version": "2.1.0"
    }
    if current_post_id:
        status["current_post_id"] = current_post_id

    client.publish(
        f"makapix/player/{player_key}/status",
        json.dumps(status),
        qos=1
    )

# On connect
def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        report_status(client, player_key)

# On artwork change
def display_artwork(client, player_key, post_id):
    # ... display the artwork ...
    report_status(client, player_key, post_id)
```

## Example: View Reporting

```python
from datetime import datetime, timezone

def report_view(client, player_key, post_id, channel, intent="channel"):
    view_event = {
        "post_id": post_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "timezone": "",
        "intent": intent,
        "play_order": 0,  # Server order
        "channel": channel,
        "player_key": player_key,
        "request_ack": False
    }

    client.publish(
        f"makapix/player/{player_key}/view",
        json.dumps(view_event),
        qos=1
    )

# When artwork is displayed
def on_artwork_displayed(post_id):
    report_view(client, player_key, post_id, "all")

# When user explicitly requests artwork
def on_user_request(post_id):
    report_view(client, player_key, post_id, "all", intent="artwork")
```

## Best Practices

### Status Updates

1. Send `online` immediately after connection
2. Include `firmware_version` to track deployments
3. Update `current_post_id` when display changes
4. Send heartbeat every 5-10 minutes
5. Attempt `offline` status on graceful shutdown

### View Events

1. Send after artwork is actually displayed (not during loading)
2. Consider minimum dwell time before reporting (e.g., 2 seconds)
3. Don't report views for failed image loads
4. Use correct `intent` to distinguish user actions from automation
5. Include channel context (`channel_user_sqid`, `channel_hashtag`) when applicable

### Offline Handling

Queue events when disconnected:

```python
event_queue = []

def report_view(post_id, channel):
    event = create_view_event(post_id, channel)
    if client.is_connected():
        client.publish(VIEW_TOPIC, json.dumps(event))
    else:
        event_queue.append(event)

def on_reconnect():
    for event in event_queue:
        client.publish(VIEW_TOPIC, json.dumps(event))
    event_queue.clear()
```

Note: Queued events with old timestamps may be deduplicated or rate-limited. Consider refreshing timestamps on reconnect.

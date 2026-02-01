# Commands

Server-to-player control messages initiated from the web interface.

## Overview

Commands allow users to control their player devices remotely. Commands are sent from the server to the device via MQTT.

### Topic

```
makapix/player/{player_key}/command
```

### Message Format

```json
{
  "command_id": "cmd-123e4567-e89b-12d3-a456-426614174000",
  "command_type": "show_artwork",
  "payload": { ... },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `command_id` | UUID | Unique command identifier |
| `command_type` | string | Type of command |
| `payload` | object | Command-specific data |
| `timestamp` | datetime | When command was issued |

## Command Types

| Type | Description |
|------|-------------|
| `swap_next` | Advance to next artwork |
| `swap_back` | Go to previous artwork |
| `show_artwork` | Display specific artwork |
| `play_channel` | Switch to channel |
| `play_playset` | Load playset configuration |

## swap_next

Advance to the next artwork in the current channel.

### Payload

```json
{
  "command_id": "cmd-001",
  "command_type": "swap_next",
  "payload": {},
  "timestamp": "2024-01-15T10:30:00Z"
}
```

The `payload` is empty for this command.

### Device Action

1. Advance cursor in current artwork list
2. Fetch and display next artwork
3. Update status with new `current_post_id`

## swap_back

Go to the previous artwork in the current channel.

### Payload

```json
{
  "command_id": "cmd-002",
  "command_type": "swap_back",
  "payload": {},
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Device Action

1. Move cursor back in artwork list
2. Fetch and display previous artwork
3. Update status with new `current_post_id`

## show_artwork

Display a specific artwork immediately.

### Payload

```json
{
  "command_id": "cmd-003",
  "command_type": "show_artwork",
  "payload": {
    "post_id": 12345,
    "storage_key": "abc123-def456-789",
    "art_url": "https://makapix.club/api/vault/a1/b2/c3/abc123-def456-789.png"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | integer | Post identifier |
| `storage_key` | string | Vault storage key |
| `art_url` | string | Full URL to artwork |

### Device Action

1. Fetch artwork from `art_url`
2. Display immediately
3. Report view event with `intent: "artwork"`
4. Update status with `current_post_id`

### Notes

- The server validates the post exists and is visible before sending
- The device should fetch the image from the provided URL
- Report the view as intentional (`intent: "artwork"`)

## play_channel

Switch to a different content channel.

### Payload: Named Channel

```json
{
  "command_id": "cmd-004",
  "command_type": "play_channel",
  "payload": {
    "channel_name": "promoted"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `channel_name` | string | Channel identifier |

### Payload: User Channel

```json
{
  "command_id": "cmd-005",
  "command_type": "play_channel",
  "payload": {
    "channel_name": "by_user",
    "user_sqid": "k5fNx",
    "user_handle": "pixelartist"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `channel_name` | string | `"by_user"` |
| `user_sqid` | string | User's public sqid |
| `user_handle` | string | User's display handle |

### Payload: Hashtag Channel

```json
{
  "command_id": "cmd-006",
  "command_type": "play_channel",
  "payload": {
    "channel_name": "hashtag",
    "hashtag": "landscape"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `channel_name` | string | `"hashtag"` |
| `hashtag` | string | Hashtag (without #) |

### Channel Names

| Name | Description |
|------|-------------|
| `all` | All public artwork |
| `promoted` | Featured artwork |
| `user` | Player owner's artwork |
| `by_user` | Specific user's artwork |
| `hashtag` | Posts with specific hashtag |

### Device Action

1. Switch to specified channel
2. Reset pagination cursor
3. Query posts for new channel
4. Display first artwork
5. Update status

## play_playset

Load a playset configuration for multi-channel playback.

### Payload

```json
{
  "command_id": "cmd-007",
  "command_type": "play_playset",
  "payload": {
    "playset_name": "followed_artists",
    "channels": [
      {
        "type": "user",
        "identifier": "k5fNx",
        "display_name": "@pixelartist",
        "weight": 10
      },
      {
        "type": "named",
        "name": "promoted",
        "display_name": "Promoted",
        "weight": 5
      }
    ],
    "exposure_mode": "manual",
    "pick_mode": "recency"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `playset_name` | string | Playset identifier |
| `channels` | array | Channel configurations |
| `exposure_mode` | string | How to distribute time |
| `pick_mode` | string | How to select within channel |

### Channel Object

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `named`, `user`, `hashtag`, `sdcard` |
| `name` | string | Channel name (for `named` type) |
| `identifier` | string | User sqid or hashtag |
| `display_name` | string | Human-readable name |
| `weight` | integer | Weight for `manual` exposure |

### Exposure Modes

| Mode | Description |
|------|-------------|
| `equal` | Equal time per channel |
| `manual` | Use weight values |
| `proportional` | Weight by content count |

### Pick Modes

| Mode | Description |
|------|-------------|
| `recency` | Newest first |
| `random` | Random selection |

### Device Action

1. Store playset configuration
2. Initialize channel cursors
3. Begin playback according to exposure/pick modes
4. Update status

## Handling Commands

### Subscribe on Connect

```python
def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        client.subscribe(f"makapix/player/{player_key}/command", qos=1)
```

### Process Commands

```python
def on_message(client, userdata, msg):
    if "/command" in msg.topic:
        command = json.loads(msg.payload)
        handle_command(command)

def handle_command(command):
    command_type = command["command_type"]
    payload = command.get("payload", {})

    if command_type == "swap_next":
        advance_artwork()
    elif command_type == "swap_back":
        previous_artwork()
    elif command_type == "show_artwork":
        show_specific_artwork(
            payload["post_id"],
            payload["art_url"]
        )
    elif command_type == "play_channel":
        switch_channel(payload)
    elif command_type == "play_playset":
        load_playset(payload)
```

## Rate Limiting

Commands are rate limited:

| Scope | Limit |
|-------|-------|
| Per player | 300 commands/minute |
| Per user | 1,000 commands/minute |

Exceeding limits results in HTTP 429 when issuing commands via the web API.

## Command Logging

All commands are logged server-side for auditing:

- `player_id`
- `command_type`
- `payload`
- `timestamp`

Special events like device registration and removal are logged as `add_device` and `remove_device` command types.

## Example: ESP32 Command Handler

```cpp
void onMqttMessage(char* topic, byte* payload, unsigned int length) {
    String topicStr = String(topic);

    if (topicStr.endsWith("/command")) {
        StaticJsonDocument<1024> doc;
        deserializeJson(doc, payload, length);

        String commandType = doc["command_type"];
        JsonObject commandPayload = doc["payload"];

        if (commandType == "swap_next") {
            currentIndex++;
            displayCurrentArtwork();
        }
        else if (commandType == "swap_back") {
            currentIndex--;
            displayCurrentArtwork();
        }
        else if (commandType == "show_artwork") {
            String artUrl = commandPayload["art_url"];
            int postId = commandPayload["post_id"];
            fetchAndDisplay(artUrl, postId);
        }
        else if (commandType == "play_channel") {
            String channelName = commandPayload["channel_name"];
            switchChannel(channelName, commandPayload);
        }
    }
}
```

## Best Practices

1. **Acknowledge visually** - Show feedback when command is received
2. **Handle offline** - Queue state changes, sync on reconnect
3. **Validate payloads** - Check required fields before acting
4. **Log commands** - Track for debugging device issues
5. **Update status** - Report new state after executing command

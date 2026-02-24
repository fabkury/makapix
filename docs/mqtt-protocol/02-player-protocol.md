# Player MQTT Protocol

This document covers all MQTT interactions between physical player devices and the Makapix server: request/response queries, remote commands, status updates, and view events.

## Message Flow Patterns

### Request/Response (Player → Server)

```
Player                         MQTT Broker              Server
  |                                 |                      |
  |-- Publish Request ------------->|                      |
  |   makapix/player/{key}/request/{id}                   |
  |                                 |-- Forward ---------> |
  |                                 |                      |
  |                                 |           Process & Query DB
  |                                 |                      |
  |                                 |<-- Publish Response --|
  |                                 |   makapix/player/{key}/response/{id}
  |<-- Receive Response ------------|                      |
```

### Command (Server → Player)

```
Server                         MQTT Broker              Player
  |                                 |                      |
  |-- Publish Command ------------->|                      |
  |   makapix/player/{key}/command  |                      |
  |                                 |-- Forward ---------> |
```

### Fire-and-Forget View (Player → Server)

```
Player                         MQTT Broker              Server
  |                                 |                      |
  |-- Publish View ---------------->|                      |
  |   makapix/player/{key}/view     |                      |
  |                                 |-- Forward ---------> |
  |                                 |                      |
  |                          (if request_ack=true)         |
  |                                 |<-- Publish Ack ------|
  |<-- Receive Ack -----------------|   .../view/ack       |
```

---

## Player-to-Server Requests

All requests are published to `makapix/player/{player_key}/request/{request_id}` with QoS 1. Responses arrive on `makapix/player/{player_key}/response/{request_id}`.

### Common Request Fields

Every request must include:

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Unique ID for correlation (UUID recommended) |
| `request_type` | string | Operation name |
| `player_key` | string (UUID) | Player's authentication key |

### Common Response Fields

Every response includes:

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Correlated with request |
| `success` | boolean | Whether the operation succeeded |
| `error` | string | Error message (only when `success` is false) |
| `error_code` | string | Machine-readable error code (only on error) |

### Supported Request Types

| Type | Description |
|------|-------------|
| `query_posts` | Query posts with channel filtering, sorting, pagination, and AMP criteria |
| `get_post` | Fetch a single post by ID |
| `submit_reaction` | Add an emoji reaction to a post |
| `revoke_reaction` | Remove an emoji reaction from a post |
| `get_comments` | Retrieve comments for a post with pagination |
| `get_playset` | Retrieve a named playset configuration |

---

### query_posts

Query posts from various channels with optional filtering, sorting, and pagination.

**Request:**

```json
{
  "request_id": "req-001",
  "request_type": "query_posts",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "channel": "all",
  "sort": "server_order",
  "limit": 50,
  "cursor": null,
  "criteria": [],
  "include_fields": null
}
```

**Request fields:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `channel` | string | `"all"` | `"all"`, `"promoted"`, `"user"`, `"by_user"`, `"artwork"`, `"hashtag"` |
| `user_handle` | string? | null | Required when `channel="by_user"` (alternative to `user_sqid`) |
| `user_sqid` | string? | null | Required when `channel="by_user"` (alternative to `user_handle`) |
| `hashtag` | string? | null | Required when `channel="hashtag"` (without `#` prefix) |
| `sort` | string | `"server_order"` | `"server_order"`, `"created_at"`, `"random"` |
| `random_seed` | int? | null | Seed for reproducible random ordering (only with `sort="random"`) |
| `cursor` | string? | null | Pagination cursor from previous response |
| `limit` | int | 50 | Number of posts to return (1-50) |
| `criteria` | array | `[]` | AMP field filter criteria (0-64 items, AND-ed together) |
| `include_fields` | array? | null | Optional fields to include in artwork payloads |

**Channel behavior:**
- `"all"` -- All visible posts.
- `"promoted"` -- Only posts where `promoted=true`.
- `"user"` -- Only the player owner's posts.
- `"by_user"` -- Posts by a specific user (requires `user_handle` or `user_sqid`).
- `"artwork"` -- Protocol compatibility alias (no additional filtering).
- `"hashtag"` -- Posts with a specific hashtag (requires `hashtag`).

**Response (artwork post):**

```json
{
  "request_id": "req-001",
  "success": true,
  "posts": [
    {
      "post_id": 123,
      "kind": "artwork",
      "created_at": "2025-12-09T01:30:00Z",
      "storage_key": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "art_url": "https://makapix.club/api/vault/7c/9e/66/7c9e6679.png",
      "storage_shard": "7c9e66",
      "native_format": "png"
    }
  ],
  "next_cursor": "50",
  "has_more": true
}
```

**Response (playlist post):**

```json
{
  "request_id": "req-001",
  "success": true,
  "posts": [
    {
      "post_id": 456,
      "kind": "playlist",
      "owner_handle": "artist123",
      "created_at": "2025-12-09T01:30:00Z",
      "metadata_modified_at": "2025-12-10T12:00:00Z",
      "total_artworks": 12,
      "dwell_time_ms": 30000
    }
  ],
  "next_cursor": null,
  "has_more": false
}
```

**Artwork post mandatory fields (always included):**

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | int | Post ID |
| `kind` | string | `"artwork"` |
| `created_at` | string | ISO 8601 timestamp |
| `storage_key` | string | UUID for vault path resolution |
| `art_url` | string | Full URL to artwork file |
| `storage_shard` | string | Vault shard prefix for path resolution |
| `native_format` | string? | File format: `"png"`, `"gif"`, `"webp"`, `"bmp"`, or null |

**Artwork post optional fields (only included if requested via `include_fields`):**

| Field | Type | Description |
|-------|------|-------------|
| `owner_handle` | string | Post owner's handle |
| `metadata_modified_at` | string | ISO 8601 timestamp of last metadata edit |
| `artwork_modified_at` | string | ISO 8601 timestamp of last artwork edit |
| `width` | int | Image width in pixels |
| `height` | int | Image height in pixels |
| `frame_count` | int | Number of frames (1 for static images) |
| `dwell_time_ms` | int | Display time in milliseconds (default: 30000) |
| `transparency_actual` | bool | Whether image has actual transparent pixels |
| `alpha_actual` | bool | Whether image has actual alpha channel |

**Playlist post fields (always included):**

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | int | Post ID |
| `kind` | string | `"playlist"` |
| `owner_handle` | string | Playlist owner's handle |
| `created_at` | string | ISO 8601 timestamp |
| `metadata_modified_at` | string | ISO 8601 timestamp |
| `total_artworks` | int | Number of artworks in the playlist |
| `dwell_time_ms` | int | Display time per artwork in milliseconds |

**Payload size limit:** Responses are capped at 128 KiB. If the post list exceeds this, posts are trimmed from the end and `has_more` remains true.

#### AMP Criteria Filtering

The `criteria` field accepts an array of filter objects that are AND-ed together:

```json
{
  "criteria": [
    { "field": "width", "op": "lte", "value": 64 },
    { "field": "height", "op": "lte", "value": 64 },
    { "field": "kind", "op": "eq", "value": "artwork" }
  ]
}
```

**Filterable fields:**

| Field | Type | Nullable | Valid Operators |
|-------|------|----------|-----------------|
| `width` | numeric | No | eq, neq, lt, gt, lte, gte, in, not_in |
| `height` | numeric | No | eq, neq, lt, gt, lte, gte, in, not_in |
| `file_bytes` | numeric | No | eq, neq, lt, gt, lte, gte, in, not_in |
| `frame_count` | numeric | No | eq, neq, lt, gt, lte, gte, in, not_in |
| `min_frame_duration_ms` | numeric | Yes | eq, neq, lt, gt, lte, gte, in, not_in, is_null, is_not_null |
| `max_frame_duration_ms` | numeric | Yes | eq, neq, lt, gt, lte, gte, in, not_in, is_null, is_not_null |
| `unique_colors` | numeric | Yes | eq, neq, lt, gt, lte, gte, in, not_in, is_null, is_not_null |
| `transparency_meta` | boolean | No | eq, neq |
| `alpha_meta` | boolean | No | eq, neq |
| `transparency_actual` | boolean | No | eq, neq |
| `alpha_actual` | boolean | No | eq, neq |
| `file_format` | string enum | No | eq, neq, in, not_in |
| `native_file_format` | string enum | No | eq, neq, in, not_in, is_null, is_not_null |
| `kind` | string enum | No | eq, neq, in, not_in |

Valid `file_format` / `native_file_format` values: `"png"`, `"gif"`, `"webp"`, `"bmp"`.
Valid `kind` values: `"artwork"`, `"playlist"`.

The `in` and `not_in` operators accept arrays of 1-128 values. The `is_null` and `is_not_null` operators accept no value.

---

### get_post

Fetch a single post by ID.

**Request:**

```json
{
  "request_id": "req-002",
  "request_type": "get_post",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "post_id": 123,
  "include_fields": ["owner_handle", "width", "height"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | int | Post ID to fetch |
| `include_fields` | array? | Optional fields to include (same as `query_posts`) |

**Response:**

```json
{
  "request_id": "req-002",
  "success": true,
  "post": {
    "post_id": 123,
    "kind": "artwork",
    "created_at": "2025-12-09T01:30:00Z",
    "storage_key": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "art_url": "https://makapix.club/api/vault/7c/9e/66/7c9e6679.png",
    "storage_shard": "7c9e66",
    "native_format": "png",
    "owner_handle": "artist123",
    "width": 64,
    "height": 64
  }
}
```

Visibility checks apply: deleted, hidden, non-conformant, or unapproved-monitored-hashtag posts return an error.

---

### submit_reaction

Add an emoji reaction to a post. Idempotent -- submitting an existing reaction returns success.

**Request:**

```json
{
  "request_id": "req-003",
  "request_type": "submit_reaction",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "post_id": 123,
  "emoji": "❤️"
}
```

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `post_id` | int | Required | Post ID to react to |
| `emoji` | string | 1-20 characters | Emoji to add |

**Response:**

```json
{
  "request_id": "req-003",
  "success": true
}
```

Maximum 5 reactions per user per post. Exceeding this returns `error_code: "reaction_limit_exceeded"`.

---

### revoke_reaction

Remove an emoji reaction from a post. Idempotent -- revoking a nonexistent reaction returns success.

**Request:**

```json
{
  "request_id": "req-004",
  "request_type": "revoke_reaction",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "post_id": 123,
  "emoji": "❤️"
}
```

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `post_id` | int | Required | Post ID |
| `emoji` | string | 1-20 characters | Emoji to remove |

**Response:**

```json
{
  "request_id": "req-004",
  "success": true
}
```

---

### get_comments

Retrieve comments for a post with pagination.

**Request:**

```json
{
  "request_id": "req-005",
  "request_type": "get_comments",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "post_id": 123,
  "cursor": null,
  "limit": 50
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `post_id` | int | Required | Post ID to get comments for |
| `cursor` | string? | null | Pagination cursor from previous response |
| `limit` | int | 50 | Number of comments to return (1-200) |

**Response:**

```json
{
  "request_id": "req-005",
  "success": true,
  "comments": [
    {
      "comment_id": "a1b2c3d4-...",
      "post_id": 123,
      "author_handle": "user42",
      "body": "Great pixel art!",
      "depth": 0,
      "parent_id": null,
      "created_at": "2025-12-09T02:00:00Z",
      "deleted": false
    }
  ],
  "next_cursor": "50",
  "has_more": false
}
```

**Comment fields:**

| Field | Type | Description |
|-------|------|-------------|
| `comment_id` | string (UUID) | Comment ID |
| `post_id` | int | Parent post ID |
| `author_handle` | string? | Author's handle (null for anonymous) |
| `body` | string | Comment text |
| `depth` | int | Nesting depth (0-2) |
| `parent_id` | string? (UUID) | Parent comment ID (null for top-level) |
| `created_at` | string | ISO 8601 timestamp |
| `deleted` | bool | Whether the comment was deleted by its author |

Comments ordered by `created_at` ascending. Deleted comments are excluded. Maximum depth is 2. Moderator-hidden comments are excluded for non-moderator players.

---

### get_playset

Retrieve a named playset configuration from the server.

**Request:**

```json
{
  "request_id": "req-006",
  "request_type": "get_playset",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "playset_name": "followed_artists"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `playset_name` | string | Name of the playset to retrieve |

**Success response:**

```json
{
  "request_id": "req-006",
  "success": true,
  "playset_name": "followed_artists",
  "channels": [
    {
      "type": "user",
      "identifier": "uvz",
      "display_name": "@PixelMaster"
    },
    {
      "type": "user",
      "identifier": "abc",
      "display_name": "@AnotherArtist"
    }
  ],
  "exposure_mode": "equal",
  "pick_mode": "random"
}
```

**Error response:**

```json
{
  "request_id": "req-006",
  "success": false,
  "error": "Playset 'unknown' not found",
  "error_code": "playset_not_found"
}
```

**Available playsets:**

| Name | Description | Generated From |
|------|-------------|----------------|
| `followed_artists` | User channels for all artists the player's owner follows | Follow table; only verified, active, non-banned users |

The `followed_artists` playset uses `exposure_mode: "equal"` and `pick_mode: "random"`.

**Channel payload fields:**

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"named"`, `"user"`, `"hashtag"`, or `"sdcard"` |
| `name` | string? | For `"named"` type: `"all"` or `"promoted"` |
| `identifier` | string? | For `"user"`: sqid. For `"hashtag"`: tag without `#` |
| `display_name` | string? | Human-readable name (e.g., `"@handle"`, `"#tag"`) |
| `weight` | int? | Weight for `"manual"` exposure mode |

---

## Server-to-Player Commands

Commands are published to `makapix/player/{player_key}/command` with QoS 1. Initiated via REST API by the player's owner.

### Command Message Format

```json
{
  "command_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "command_type": "show_artwork",
  "payload": {},
  "timestamp": "2025-12-09T01:30:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `command_id` | string (UUID) | Unique command identifier for tracking |
| `command_type` | string | One of the supported command types |
| `payload` | object | Command-specific data (may be empty `{}`) |
| `timestamp` | string | ISO 8601 UTC timestamp of when command was issued |

### Supported Commands

#### swap_next

Move to the next artwork in the current queue.

- **Command type:** `"swap_next"`
- **Payload:** `{}` (empty)

#### swap_back

Move to the previous artwork in the current queue.

- **Command type:** `"swap_back"`
- **Payload:** `{}` (empty)

#### show_artwork

Display a specific artwork.

- **Command type:** `"show_artwork"`
- **Payload:**

```json
{
  "post_id": 123,
  "storage_key": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "art_url": "https://makapix.club/api/vault/7c/9e/66/7c9e6679.png"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | int | Post ID |
| `storage_key` | string (UUID) | Storage identifier for vault path |
| `art_url` | string | Full URL to artwork file |

#### play_channel

Switch the player to a specific content channel.

- **Command type:** `"play_channel"`
- **Payload** varies by channel type:

Named channel (all posts or promoted):
```json
{ "channel_name": "all" }
```
```json
{ "channel_name": "promoted" }
```

User channel:
```json
{
  "channel_name": "by_user",
  "user_sqid": "uvz",
  "user_handle": "PixelMaster"
}
```

Hashtag channel:
```json
{
  "channel_name": "hashtag",
  "hashtag": "pixelart"
}
```

#### play_playset

Configure the player to play a multi-channel playset.

- **Command type:** `"play_playset"`
- **Payload:** A playset configuration object:

```json
{
  "playset_name": "followed_artists",
  "channels": [
    {
      "type": "user",
      "identifier": "uvz",
      "display_name": "@PixelMaster"
    },
    {
      "type": "user",
      "identifier": "abc",
      "display_name": "@AnotherArtist"
    }
  ],
  "exposure_mode": "equal",
  "pick_mode": "random"
}
```

The payload structure matches the `get_playset` response. See the `get_playset` section above for field descriptions.

**Channel types:**
- `"named"` -- Requires `name` field (`"all"` or `"promoted"`)
- `"user"` -- Requires `identifier` (user's sqid)
- `"hashtag"` -- Requires `identifier` (tag without `#`)
- `"sdcard"` -- No additional fields (plays local SD card files)

**Exposure modes:**
- `"equal"` -- Equal exposure across all channels (default)
- `"manual"` -- Use `weight` values from each channel
- `"proportional"` -- Proportional to content count with recency bias

**Pick modes:**
- `"recency"` -- Newest first, cursor moves toward older
- `"random"` -- Random selection from a sliding window

---

## Status Updates

Players send periodic status updates to `makapix/player/{player_key}/status` with QoS 1.

### Status Message Format

```json
{
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "status": "online",
  "current_post_id": 123,
  "firmware_version": "1.0.0"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `player_key` | string (UUID) | Player's key |
| `status` | string | `"online"` or `"offline"` |
| `current_post_id` | int? | Currently displayed post ID (null if none) |
| `firmware_version` | string? | Firmware version string (optional) |

### Server-Side Processing

On receiving a status update, the server:
- Updates `Player.connection_status` in the database
- Updates `Player.last_seen_at` to current UTC time
- Updates `Player.current_post_id` if provided
- Updates `Player.firmware_version` if provided

### Recommended Behavior

- Send a status update every 60 seconds as a heartbeat.
- Send immediately on state changes (e.g., artwork change, graceful disconnect).
- On graceful shutdown, send a status with `"status": "offline"`.

---

## Fire-and-Forget View Events

Players report artwork views by publishing to `makapix/player/{player_key}/view` with QoS 1. This is a dedicated fire-and-forget topic, separate from the request/response pattern.

### View Event Format

```json
{
  "post_id": 123,
  "timestamp": "2025-12-22T16:24:15Z",
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
| `post_id` | int | Yes | Artwork post ID |
| `timestamp` | string | Yes | ISO 8601 UTC timestamp. Use `"1970-01-01T00:00:00Z"` if device clock is unsynced. |
| `timezone` | string | Yes | Reserved for future use. Send empty string `""`. |
| `intent` | string | Yes | `"artwork"` (explicit user request) or `"channel"` (automated playback) |
| `play_order` | int | Yes | 0 = server order, 1 = created_at order, 2 = random |
| `channel` | string | Yes | Active channel (e.g., `"all"`, `"promoted"`, `"by_user"`, `"hashtag"`) |
| `player_key` | string (UUID) | Yes | Must match the topic's player_key |
| `channel_user_sqid` | string? | No | User sqid when channel is `"by_user"` |
| `channel_hashtag` | string? | No | Hashtag when channel is `"hashtag"` |
| `request_ack` | bool | No | If true, server sends acknowledgment to `view/ack` topic. Default: false. |

### View Acknowledgment

If `request_ack` is true, the server publishes to `makapix/player/{player_key}/view/ack`:

**Success:**
```json
{ "success": true }
```

**Error:**
```json
{
  "success": false,
  "error": "Rate limited, retry after 3s",
  "error_code": "rate_limited"
}
```

### Server-Side Processing

- **Authentication:** Player must be registered with an owner.
- **Player_key validation:** The `player_key` in the payload must match the topic.
- **Duplicate detection:** Events with the same player + post_id + timestamp are discarded (handles QoS 1 retransmissions).
- **Rate limiting:** 1 view per 5 seconds per player.
- **Self-view exclusion:** Views are not recorded when the player's owner is also the post owner.
- **Timestamp handling:** `"1970-01-01T00:00:00Z"` is treated as unsynced and stored as NULL.
- **Async write:** View events are dispatched to a Celery worker for asynchronous database insertion.

### View Error Codes

| Error Code | Description |
|------------|-------------|
| `player_key_mismatch` | Payload player_key doesn't match topic |
| `player_not_registered` | Player not found or not registered |
| `player_no_owner` | Player has no owner assigned |
| `duplicate` | Duplicate view event |
| `rate_limited` | Rate limit exceeded (1 per 5s) |
| `post_not_found` | Post does not exist |
| `processing_error` | Internal processing error |

---

## Error Handling

### Error Response Format

All request types return errors in this format:

```json
{
  "request_id": "req-001",
  "success": false,
  "error": "Human-readable error message",
  "error_code": "error_code_constant"
}
```

### Common Error Codes

| Error Code | Description |
|------------|-------------|
| `authentication_failed` | Player not registered or invalid player_key |
| `not_found` | Resource not found (post, user, comment) |
| `invalid_request` | Missing required fields or malformed request |
| `invalid_json` | Payload is not valid JSON |
| `invalid_emoji` | Emoji too long or invalid format |
| `invalid_criteria` | AMP criteria validation failed |
| `reaction_limit_exceeded` | Max 5 reactions per user per post |
| `missing_user_identifier` | `by_user` channel requires `user_handle` or `user_sqid` |
| `user_not_found` | User not found for `by_user` channel |
| `missing_hashtag` | `hashtag` channel requires `hashtag` field |
| `invalid_hashtag` | Empty hashtag |
| `playset_not_found` | Unknown playset name |
| `content_not_approved` | Post has monitored hashtags not approved by owner |
| `deleted` | Post has been deleted |
| `not_visible` | Post is not visible |
| `not_available` | Post is hidden or non-conformant |
| `unsupported_kind` | Post kind not supported |
| `unknown_request_type` | Unsupported `request_type` value |
| `internal_error` | Server-side processing error |

### Best Practices

1. **Subscribe before publishing:** Subscribe to `makapix/player/{key}/response/#` before sending requests.
2. **Use unique request IDs:** UUIDs are recommended for `request_id`.
3. **Implement timeouts:** Use a 30-second timeout for responses.
4. **Correlate responses:** Match `request_id` in responses to pending requests.
5. **Handle errors by code:** Use `error_code` for programmatic handling, `error` for logging.
6. **Retry transient errors:** Retry on `internal_error` with exponential backoff.
7. **Send periodic heartbeats:** Every 60 seconds via the status topic.
8. **Set keep-alive:** Use 60-second MQTT keep-alive interval.

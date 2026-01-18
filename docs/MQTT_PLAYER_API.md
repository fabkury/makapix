# MQTT Player API Documentation

## Overview

Physical players can communicate with the Makapix backend through MQTT to query posts, submit views, manage reactions, and retrieve comments. All operations inherit the access privileges and restrictions of the player's owner user account.

## Authentication

Players authenticate using their unique `player_key` UUID. This key is:
- Generated during player provisioning
- Required in all request payloads
- Used to validate the player is registered and active
- Mapped to the owner's user account for permission checks

## Topic Structure

### Request Topic Pattern
```
makapix/player/{player_key}/request/{request_id}
```

### Response Topic Pattern
```
makapix/player/{player_key}/response/{request_id}
```

The `request_id` is a unique identifier (UUID or string) provided by the player to correlate requests with responses.

## Operations

### 1. Query Posts

Query N posts from a channel with sorting and pagination.

**Request Schema:**
```json
{
  "request_id": "unique-request-id",
  "request_type": "query_posts",
  "player_key": "player-uuid",
  "channel": "all",  // "all", "promoted", "user", or "by_user"
  "user_handle": "artist123",  // required when channel="by_user"
  "sort": "server_order",  // "server_order", "created_at", or "random"
  "random_seed": 12345,  // optional, only used when sort="random"
  "cursor": null,  // optional, for pagination
  "limit": 50  // 1-50
}
```

**Channel Options:**
- `all`: Recent posts from all users (respects visibility settings)
- `promoted`: Only promoted posts (editor picks, frontpage, etc.)
- `user`: Posts from the player owner's account
- `by_user`: Posts from an arbitrary user specified by `user_handle`

**Sort Options:**
- `server_order`: Original insertion order (by post ID)
- `created_at`: Chronological order by creation timestamp
- `random`: Random order with optional seed for reproducibility

**Response Schema:**

The response contains a list of posts, where each post is either an artwork or a playlist. The `kind` field indicates the post type.

**Artwork Post:**
```json
{
  "request_id": "unique-request-id",
  "success": true,
  "posts": [
    {
      "post_id": 123,
      "kind": "artwork",
      "owner_handle": "artist123",
      "created_at": "2025-12-08T17:00:00Z",
      "metadata_modified_at": "2025-12-08T17:00:00Z",
      "storage_key": "uuid",
      "art_url": "https://...",
      "width": 64,
      "height": 64,
      "frame_count": 1,
      "transparency_actual": false,
      "alpha_actual": false,
      "artwork_modified_at": "2025-12-08T17:00:00Z",
      "dwell_time_ms": 30000
    }
  ],
  "next_cursor": "50",
  "has_more": false,
  "error": null
}
```

**Playlist Post:**
```json
{
  "request_id": "unique-request-id",
  "success": true,
  "posts": [
    {
      "post_id": 456,
      "kind": "playlist",
      "owner_handle": "artist123",
      "created_at": "2025-12-08T17:00:00Z",
      "metadata_modified_at": "2025-12-08T17:00:00Z",
      "total_artworks": 10,
      "dwell_time_ms": 30000
    }
  ],
  "next_cursor": null,
  "has_more": false,
  "error": null
}
```

**Example:**
```python
# Query first 10 promoted posts
request = {
    "request_id": "req-001",
    "request_type": "query_posts",
    "player_key": "your-player-uuid",
    "channel": "promoted",
    "sort": "created_at",
    "limit": 10
}

# Query posts from a specific user
request = {
    "request_id": "req-002",
    "request_type": "query_posts",
    "player_key": "your-player-uuid",
    "channel": "by_user",
    "user_handle": "artist123",
    "sort": "created_at",
    "limit": 20
}
```

#### AMP Field Filtering (Criteria)

The `query_posts` operation supports optional filtering by AMP (Artwork Metadata Platform) fields using the `criteria` parameter. This enables queries like "find all PNG images with width 64-128px that have no transparency".

**Criteria Structure:**
```json
{
  "criteria": [
    {"field": "width", "op": "gte", "value": 64},
    {"field": "width", "op": "lte", "value": 128},
    {"field": "file_format", "op": "in", "value": ["png", "bmp"]},
    {"field": "transparency_actual", "op": "eq", "value": false},
    {"field": "min_frame_duration_ms", "op": "is_null"}
  ]
}
```

**Rules:**
- 0 to 64 criteria per query
- All criteria are AND-ed together (must all match)
- Field names match database column names exactly
- `criteria` is optional (defaults to empty = no filtering)

**Queryable Fields:**

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `width` | numeric | no | Canvas width in pixels |
| `height` | numeric | no | Canvas height in pixels |
| `file_bytes` | numeric | no | File size in bytes |
| `frame_count` | numeric | no | Animation frame count (1 for static) |
| `min_frame_duration_ms` | numeric | yes | Shortest frame duration (ms), NULL for static |
| `max_frame_duration_ms` | numeric | yes | Longest frame duration (ms), NULL for static |
| `unique_colors` | numeric | yes | Max unique colors in any frame, NULL for playlists |
| `transparency_meta` | boolean | no | File metadata claims transparency |
| `alpha_meta` | boolean | no | File metadata claims alpha channel |
| `transparency_actual` | boolean | no | Actual transparent pixels found (alpha != 255) |
| `alpha_actual` | boolean | no | Semi-transparent pixels found (alpha not in {0, 255}) |
| `file_format` | enum | yes | Image format (png, gif, webp, bmp), NULL for playlists |
| `kind` | enum | no | Post type: "artwork" or "playlist" |

**Operators:**

| Operator | Symbol | Supported Types | Value |
|----------|--------|-----------------|-------|
| `eq` | = | all | single value |
| `neq` | != | all | single value |
| `lt` | < | numeric | single value |
| `gt` | > | numeric | single value |
| `lte` | <= | numeric | single value |
| `gte` | >= | numeric | single value |
| `in` | IN | numeric, string/enum | array (1-128 values) |
| `not_in` | NOT IN | numeric, string/enum | array (1-128 values) |
| `is_null` | IS NULL | nullable fields only | not required |
| `is_not_null` | IS NOT NULL | nullable fields only | not required |

**Valid `file_format` Values:**
- `"png"` - PNG images
- `"gif"` - GIF images, may be animated
- `"webp"` - WebP images, may be animated
- `"bmp"` - BMP images

**Valid `kind` Values:**
- `"artwork"` - Single artwork post
- `"playlist"` - Playlist containing multiple artworks

**Example: Find static PNG/BMP images 64-128px wide without transparency:**
```python
request = {
    "request_id": "criteria-example",
    "request_type": "query_posts",
    "player_key": "your-player-uuid",
    "channel": "all",
    "criteria": [
        {"field": "width", "op": "gte", "value": 64},
        {"field": "width", "op": "lte", "value": 128},
        {"field": "file_format", "op": "in", "value": ["png", "bmp"]},
        {"field": "frame_count", "op": "eq", "value": 1},
        {"field": "transparency_actual", "op": "eq", "value": False}
    ],
    "sort": "created_at",
    "limit": 20
}
```

**Example: Find animated images (GIF/WebP with multiple frames):**
```python
request = {
    "request_id": "animated-example",
    "request_type": "query_posts",
    "player_key": "your-player-uuid",
    "channel": "all",
    "criteria": [
        {"field": "file_format", "op": "in", "value": ["gif", "webp"]},
        {"field": "frame_count", "op": "gt", "value": 1}
    ],
    "limit": 10
}
```

**Example: Find small images (under 10KB) with transparency:**
```python
request = {
    "request_id": "small-transparent",
    "request_type": "query_posts",
    "player_key": "your-player-uuid",
    "channel": "all",
    "criteria": [
        {"field": "file_bytes", "op": "lt", "value": 10240},
        {"field": "transparency_actual", "op": "eq", "value": True}
    ],
    "limit": 50
}
```

### 2. Get Post

Fetch a single post by ID.

**Request Schema:**
```json
{
  "request_id": "unique-request-id",
  "request_type": "get_post",
  "player_key": "player-uuid",
  "post_id": 123
}
```

**Response Schema:**

Returns a single post object (artwork or playlist) with the same structure as `query_posts`.

```json
{
  "request_id": "unique-request-id",
  "success": true,
  "post": {
    "post_id": 123,
    "kind": "artwork",
    "owner_handle": "artist123",
    "created_at": "2025-12-08T17:00:00Z",
    "metadata_modified_at": "2025-12-08T17:00:00Z",
    "storage_key": "uuid",
    "art_url": "https://...",
    "width": 64,
    "height": 64,
    "frame_count": 1,
    "transparency_actual": false,
    "alpha_actual": false,
    "artwork_modified_at": "2025-12-08T17:00:00Z",
    "dwell_time_ms": 30000
  },
  "error": null
}
```

**Error Codes:**
- `not_found`: Post with given ID does not exist
- `not_visible`: Post exists but is not visible
- `not_available`: Post is hidden by user or moderator

**Example:**
```python
request = {
    "request_id": "get-post-1",
    "request_type": "get_post",
    "player_key": "your-player-uuid",
    "post_id": 123
}
```

### 3. Submit View

Record a view event for an artwork. Views are classified by intent and tracked for analytics.

**Request Schema:**
```json
{
  "request_id": "unique-request-id",
  "request_type": "submit_view",
  "player_key": "player-uuid",
  "post_id": 123,
  "view_intent": "intentional"  // "intentional" or "automated"
}
```

**View Intent:**
- `intentional`: User explicitly selected this post to view
- `automated`: Post displayed as part of playlist or auto-rotation

**Response Schema:**
```json
{
  "request_id": "unique-request-id",
  "success": true,
  "error": null
}
```

**Notes:**
- Views are recorded asynchronously via Celery
- Owner views are excluded (self-views not counted)
- All player views are classified as device_type="player"
- View tracking includes timestamps and source information

**Example:**
```python
# Record an intentional view
request = {
    "request_id": "req-002",
    "request_type": "submit_view",
    "player_key": "your-player-uuid",
    "post_id": 456,
    "view_intent": "intentional"
}
```

### 4. Submit Reaction

Add an emoji reaction to a post.

**Request Schema:**
```json
{
  "request_id": "unique-request-id",
  "request_type": "submit_reaction",
  "player_key": "player-uuid",
  "post_id": 123,
  "emoji": "❤️"
}
```

**Response Schema:**
```json
{
  "request_id": "unique-request-id",
  "success": true,
  "error": null
}
```

**Constraints:**
- Maximum 5 different reactions per user per post
- Emoji must be 1-20 characters
- Operation is idempotent (adding same reaction twice returns success)
- Reactions are attributed to the player owner's user account

**Example:**
```python
# Add a heart reaction
request = {
    "request_id": "req-003",
    "request_type": "submit_reaction",
    "player_key": "your-player-uuid",
    "post_id": 789,
    "emoji": "❤️"
}
```

### 5. Revoke Reaction

Remove a previously submitted emoji reaction.

**Request Schema:**
```json
{
  "request_id": "unique-request-id",
  "request_type": "revoke_reaction",
  "player_key": "player-uuid",
  "post_id": 123,
  "emoji": "❤️"
}
```

**Response Schema:**
```json
{
  "request_id": "unique-request-id",
  "success": true,
  "error": null
}
```

**Notes:**
- Operation is idempotent (revoking non-existent reaction returns success)
- Only the user's own reactions can be revoked

**Example:**
```python
# Revoke a heart reaction
request = {
    "request_id": "req-004",
    "request_type": "revoke_reaction",
    "player_key": "your-player-uuid",
    "post_id": 789,
    "emoji": "❤️"
}
```

### 6. Get Comments

Retrieve comments for a post with pagination.

**Request Schema:**
```json
{
  "request_id": "unique-request-id",
  "request_type": "get_comments",
  "player_key": "player-uuid",
  "post_id": 123,
  "cursor": null,  // optional, for pagination
  "limit": 50  // 1-200
}
```

**Response Schema:**
```json
{
  "request_id": "unique-request-id",
  "success": true,
  "comments": [
    {
      "comment_id": "comment-uuid",
      "post_id": 123,
      "author_handle": "commenter123",  // null for anonymous
      "body": "Great artwork!",
      "depth": 0,  // 0-2, nesting level
      "parent_id": null,  // parent comment UUID if reply
      "created_at": "2025-12-08T17:00:00Z",
      "deleted": false
    }
  ],
  "next_cursor": "50",  // null if no more results
  "has_more": false,
  "error": null
}
```

**Notes:**
- Comments are ordered by creation time (oldest first)
- Deleted comments without children are filtered out
- Comments hidden by moderators are filtered for non-moderators
- Maximum nesting depth is 2 levels

**Example:**
```python
# Get first 20 comments
request = {
    "request_id": "req-005",
    "request_type": "get_comments",
    "player_key": "your-player-uuid",
    "post_id": 101,
    "limit": 20
}
```

## Error Handling

All operations may return error responses:

```json
{
  "request_id": "unique-request-id",
  "success": false,
  "error": "Human-readable error message",
  "error_code": "error_code_constant"
}
```

**Common Error Codes:**
- `authentication_failed`: Player not registered or invalid player_key
- `not_found`: Requested resource (post, comment) not found
- `invalid_request`: Malformed request or missing required fields
- `invalid_criteria`: Invalid AMP criteria (unknown field, invalid operator for field type, type mismatch, invalid file_format value)
- `invalid_emoji`: Emoji format validation failed
- `reaction_limit_exceeded`: Maximum 5 reactions per post exceeded
- `internal_error`: Server-side processing error
- `unknown_request_type`: Unsupported request_type

## QoS and Reliability

- All messages use QoS 1 (at least once delivery)
- Responses are non-retained (transient)
- Request processing is asynchronous where possible
- View events are queued via Celery for eventual consistency

## Security and Privacy

- Player authentication required for all operations
- Players inherit owner's permissions and restrictions
- Visibility rules enforced (hidden/moderated content filtered)
- View tracking uses hashed identifiers for privacy
- Player device info (IP, user agent) not exposed

## Rate Limiting

Rate limits are inherited from the player owner's account:
- Player-specific: 300 commands/minute
- User-level: 1000 commands/minute across all devices

Exceeding limits returns HTTP 429 for REST endpoints (MQTT operations may be rejected silently).

## Implementation Notes

### For Player Developers

1. **Generate unique request_ids**: Use UUIDs or incremental counters
2. **Subscribe to response topic before sending request**: Pattern: `makapix/player/{your_player_key}/response/#`
3. **Handle response timeouts**: Implement 30-second timeout for responses
4. **Implement exponential backoff for retries**: On errors or timeouts
5. **Cache post metadata locally**: Reduce query frequency
6. **Batch operations when possible**: Queue multiple views/reactions

### Topic Subscription Example (Python with paho-mqtt)

```python
import paho.mqtt.client as mqtt
import json
import uuid

# Configuration
BROKER_HOST = "makapix.club"
BROKER_PORT = 8883
PLAYER_KEY = "your-player-uuid"

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    # Subscribe to responses
    response_topic = f"makapix/player/{PLAYER_KEY}/response/#"
    client.subscribe(response_topic, qos=1)
    print(f"Subscribed to {response_topic}")

def on_message(client, userdata, msg):
    print(f"Received response on {msg.topic}")
    response = json.loads(msg.payload)
    print(f"Response: {response}")

# Create client with mTLS
client = mqtt.Client(client_id=f"player-{PLAYER_KEY}", protocol=mqtt.MQTTv5)
client.tls_set(
    ca_certs="ca.crt",
    certfile="client.crt",
    keyfile="client.key"
)
client.on_connect = on_connect
client.on_message = on_message

# Connect and start loop
client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
client.loop_start()

# Send a request
request_id = str(uuid.uuid4())
request_topic = f"makapix/player/{PLAYER_KEY}/request/{request_id}"
request = {
    "request_id": request_id,
    "request_type": "query_posts",
    "player_key": PLAYER_KEY,
    "channel": "promoted",
    "sort": "created_at",
    "limit": 10
}
client.publish(request_topic, json.dumps(request), qos=1)
print(f"Sent request {request_id}")

# Keep running to receive response
input("Press Enter to exit...\n")
client.loop_stop()
```

## Testing

A complete test suite is available in `api/tests/test_mqtt_player_requests.py` covering:
- Authentication validation
- All operation types
- Error handling
- Pagination
- Idempotency
- Permission enforcement

### Manual Validation

A validation script is provided in `scripts/validate_mqtt_player_api.py` for manual testing:

```bash
# Basic validation (queries only)
python3 scripts/validate_mqtt_player_api.py \
    --player-key "your-player-uuid" \
    --host "localhost" \
    --port 1883

# Full validation including view/reaction/comment tests
python3 scripts/validate_mqtt_player_api.py \
    --player-key "your-player-uuid" \
    --host "makapix.club" \
    --port 8883 \
    --tls \
    --post-id 123
```

The script will run through all API operations and report success/failure for each.

## Changelog

### Version 1.3 (2026-01-03)
- Removed `bit_depth` field from queryable fields (no longer extracted)
- Removed `mime_type` field from queryable fields (replaced by `file_format`)
- Added `kind` as queryable field to filter by post type ("artwork" or "playlist")
- Removed `"unknown"` from valid `file_format` values (server rejects unrecognized formats)
- Updated `unique_colors` description: NULL for playlists
- 12 queryable fields: width, height, file_bytes, frame_count, min/max_frame_duration_ms, unique_colors, transparency_meta, alpha_meta, transparency_actual, alpha_actual, file_format, kind

### Version 1.2 (2025-12-31)
- Added `get_post` operation to fetch a single post by ID
- Post responses now include `kind` field ("artwork" or "playlist") to distinguish post types
- Artwork posts now include `transparency_actual` and `alpha_actual` fields (replaced `has_transparency`)
- Artwork posts now include `metadata_modified_at`, `artwork_modified_at`, and `dwell_time_ms` fields
- Removed redundant `canvas` field from artwork posts (use `width` and `height` instead)
- Playlist posts return metadata only (`total_artworks`, `dwell_time_ms`) without nested artworks
- Removed Playlist Expansion (PE) parameter - playlists no longer include artwork arrays

### Version 1.1 (2025-12-31)
- Added AMP field filtering (criteria) to query_posts operation
- 13 queryable fields: width, height, file_bytes, frame_count, min/max_frame_duration_ms, bit_depth, unique_colors, transparency_meta, alpha_meta, transparency_actual, alpha_actual, file_format, mime_type
- 10 operators: eq, neq, lt, gt, lte, gte, in, not_in, is_null, is_not_null
- Added `invalid_criteria` error code

### Version 1.0 (2025-12-08)
- Initial implementation of MQTT player API
- Added query_posts, submit_view, submit_reaction, revoke_reaction, get_comments operations
- Integrated with existing view tracking and reaction systems
- Comprehensive test coverage

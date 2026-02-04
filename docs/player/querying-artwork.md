# Querying Artwork

Fetch posts from the server with filtering, sorting, and pagination.

## Request-Response Pattern

All queries follow the same pattern:

1. Generate a unique `request_id` (UUID or incrementing counter)
2. Publish request to `makapix/player/{player_key}/request/{request_id}`
3. Receive response on `makapix/player/{player_key}/response/{request_id}`

## Query Posts

Fetch multiple posts with optional filtering.

### Request

**Topic:** `makapix/player/{player_key}/request/{request_id}`

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
  "include_fields": ["width", "height", "frame_count"]
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `request_id` | string | required | Unique identifier for correlation |
| `request_type` | string | required | Must be `"query_posts"` |
| `player_key` | UUID | required | Player's key for authentication |
| `channel` | string | `"all"` | Content source (see Channels below) |
| `sort` | string | `"server_order"` | Sort order (see Sorting below) |
| `random_seed` | integer | null | Seed for reproducible random order |
| `limit` | integer | 50 | Number of posts (1-50) |
| `cursor` | string | null | Pagination cursor from previous response |
| `criteria` | array | [] | AMP filter criteria (see Filtering below) |
| `include_fields` | array | null | Optional fields to include |

### Response

**Topic:** `makapix/player/{player_key}/response/{request_id}`

```json
{
  "request_id": "req-001",
  "success": true,
  "posts": [
    {
      "post_id": 12345,
      "kind": "artwork",
      "created_at": "2024-01-15T09:00:00Z",
      "storage_key": "abc123-def456",
      "art_url": "https://makapix.club/api/vault/a1/b2/c3/abc123-def456.png",
      "storage_shard": "a1/b2/c3",
      "native_format": "png",
      "width": 64,
      "height": 64,
      "frame_count": 1
    }
  ],
  "next_cursor": "50",
  "has_more": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Echoed from request |
| `success` | boolean | Whether request succeeded |
| `posts` | array | List of post objects |
| `next_cursor` | string | Cursor for next page (null if no more) |
| `has_more` | boolean | Whether more results exist |
| `error` | string | Error message (if success=false) |
| `error_code` | string | Machine-readable error code |

## Channels

The `channel` parameter determines which posts to query:

| Channel | Description |
|---------|-------------|
| `all` | All visible public artwork |
| `promoted` | Promoted/featured artwork |
| `user` | Current player owner's artwork |
| `by_user` | Specific user's artwork (requires `user_handle` or `user_sqid`) |
| `hashtag` | Posts with specific hashtag (requires `hashtag`) |
| `artwork` | Same as `all` (compatibility alias) |

### By User Example

```json
{
  "request_type": "query_posts",
  "channel": "by_user",
  "user_handle": "pixelmaster",
  "limit": 20
}
```

Or using sqid:

```json
{
  "channel": "by_user",
  "user_sqid": "k5fNx"
}
```

### Hashtag Example

```json
{
  "request_type": "query_posts",
  "channel": "hashtag",
  "hashtag": "landscape",
  "limit": 20
}
```

Note: Hashtag should not include the `#` prefix.

## Sorting

| Sort | Description |
|------|-------------|
| `server_order` | Default insertion order (newest first) |
| `created_at` | Chronological order (newest first) |
| `random` | Random order (use `random_seed` for reproducibility) |

### Random with Seed

```json
{
  "sort": "random",
  "random_seed": 42
}
```

Using the same seed returns the same order, useful for resuming playback.

## Filtering (AMP Criteria)

Filter artwork by metadata fields using the `criteria` array. See [AMP Protocol](../reference/amp-protocol.md) for complete documentation.

### Example: Posts with a GIF variant (any post that has a GIF file)

```json
{
  "criteria": [
    {"field": "file_format", "op": "eq", "value": "gif"}
  ]
}
```

This returns all posts that have a GIF file available, whether GIF is the native upload format or a server-converted variant. A post uploaded as WebP will match if the server generated a GIF conversion.

### Example: Posts natively uploaded as PNG

```json
{
  "criteria": [
    {"field": "native_file_format", "op": "eq", "value": "png"}
  ]
}
```

This returns only posts where the original upload was PNG. Posts with a PNG conversion from a WebP original will **not** match.

### Example: Natively GIF, small GIF file

```json
{
  "criteria": [
    {"field": "native_file_format", "op": "eq", "value": "gif"},
    {"field": "file_bytes", "op": "lt", "value": 10240}
  ]
}
```

### Example: 64x64 Animated GIFs

```json
{
  "criteria": [
    {"field": "width", "op": "eq", "value": 64},
    {"field": "height", "op": "eq", "value": 64},
    {"field": "frame_count", "op": "gt", "value": 1},
    {"field": "file_format", "op": "eq", "value": "gif"}
  ]
}
```

### Example: Small Static Images

```json
{
  "criteria": [
    {"field": "width", "op": "lte", "value": 32},
    {"field": "height", "op": "lte", "value": 32},
    {"field": "frame_count", "op": "eq", "value": 1}
  ]
}
```

### Available Fields

| Field | Type | Description |
|-------|------|-------------|
| `width` | integer | Image width in pixels |
| `height` | integer | Image height in pixels |
| `file_bytes` | integer | File size in bytes (per variant; combines with `file_format` on same variant) |
| `frame_count` | integer | Number of frames (1 = static) |
| `min_frame_duration_ms` | integer | Shortest frame duration |
| `max_frame_duration_ms` | integer | Longest frame duration |
| `unique_colors` | integer | Number of unique colors |
| `transparency_meta` | boolean | Format supports transparency |
| `alpha_meta` | boolean | Format supports alpha channel |
| `transparency_actual` | boolean | Image has transparent pixels |
| `alpha_actual` | boolean | Image has semi-transparent pixels |
| `file_format` | string | `"png"`, `"gif"`, `"webp"`, `"bmp"` (any variant) |
| `native_file_format` | string | `"png"`, `"gif"`, `"webp"`, `"bmp"` (native only) |
| `kind` | string | `"artwork"` or `"playlist"` |

### Operators

| Operator | Description |
|----------|-------------|
| `eq` | Equals |
| `neq` | Not equals |
| `lt` | Less than |
| `gt` | Greater than |
| `lte` | Less than or equal |
| `gte` | Greater than or equal |
| `in` | Value in array |
| `not_in` | Value not in array |
| `is_null` | Field is null |
| `is_not_null` | Field is not null |

## Include Fields

By default, responses include only mandatory fields to minimize payload size. Request optional fields with `include_fields`:

```json
{
  "include_fields": [
    "owner_handle",
    "width",
    "height",
    "frame_count",
    "dwell_time_ms",
    "transparency_actual",
    "alpha_actual"
  ]
}
```

### Mandatory Fields (Always Included)

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | integer | Unique post identifier |
| `kind` | string | Always `"artwork"` |
| `created_at` | datetime | Post creation time |
| `storage_key` | string | Vault storage identifier |
| `art_url` | string | Full URL to artwork |
| `storage_shard` | string | Vault path prefix |
| `native_format` | string | Original file format |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `owner_handle` | string | Author's username |
| `metadata_modified_at` | datetime | Last metadata update |
| `artwork_modified_at` | datetime | Last artwork update |
| `width` | integer | Image width |
| `height` | integer | Image height |
| `frame_count` | integer | Animation frame count |
| `dwell_time_ms` | integer | Suggested display duration |
| `transparency_actual` | boolean | Has transparent pixels |
| `alpha_actual` | boolean | Has semi-transparent pixels |

## Pagination

Responses are paginated. Use `next_cursor` to fetch subsequent pages:

```json
// First request
{"limit": 50}

// Response includes
{"next_cursor": "50", "has_more": true}

// Second request
{"limit": 50, "cursor": "50"}

// Response
{"next_cursor": "100", "has_more": true}
```

## Get Single Post

Fetch a specific post by ID.

### Request

```json
{
  "request_id": "req-002",
  "request_type": "get_post",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "post_id": 12345,
  "include_fields": ["owner_handle", "width", "height"]
}
```

### Response

```json
{
  "request_id": "req-002",
  "success": true,
  "post": {
    "post_id": 12345,
    "kind": "artwork",
    "created_at": "2024-01-15T09:00:00Z",
    "storage_key": "abc123-def456",
    "art_url": "https://makapix.club/api/vault/a1/b2/c3/abc123-def456.png",
    "storage_shard": "a1/b2/c3",
    "native_format": "png",
    "owner_handle": "pixelartist",
    "width": 64,
    "height": 64
  }
}
```

## Payload Size Limits

MQTT payloads are limited to 128 KB. The server automatically trims results if the response exceeds this limit. With typical artwork metadata, expect 30-50 posts per response.

## Error Handling

| Error Code | Description |
|------------|-------------|
| `invalid_criteria` | Malformed filter criteria |
| `missing_user_identifier` | by_user channel requires user_handle or user_sqid |
| `user_not_found` | Specified user doesn't exist |
| `missing_hashtag` | hashtag channel requires hashtag field |
| `invalid_hashtag` | Empty hashtag |
| `not_found` | Post doesn't exist (get_post) |
| `deleted` | Post was deleted |
| `not_visible` | Post is hidden |
| `authentication_failed` | Player not registered |

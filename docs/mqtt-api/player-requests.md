# Player Requests

Request-response protocol for querying data from the server.

## Overview

All requests follow the same pattern:

1. Publish to `makapix/player/{player_key}/request/{request_id}`
2. Receive response on `makapix/player/{player_key}/response/{request_id}`

## Request Types

| Type | Description |
|------|-------------|
| `query_posts` | Fetch multiple posts with filtering |
| `get_post` | Fetch single post by ID |
| `submit_reaction` | Add emoji reaction |
| `revoke_reaction` | Remove emoji reaction |
| `get_comments` | Fetch comments for a post |
| `get_playset` | Fetch playset configuration |

## query_posts

Fetch posts with optional filtering and pagination.

### Request

```json
{
  "request_id": "req-001",
  "request_type": "query_posts",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "channel": "all",
  "sort": "server_order",
  "random_seed": null,
  "cursor": null,
  "limit": 50,
  "criteria": [],
  "include_fields": null
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `request_id` | string | required | Correlation ID |
| `request_type` | string | required | `"query_posts"` |
| `player_key` | UUID | required | Player identifier |
| `channel` | string | `"all"` | Content source |
| `user_handle` | string | null | For `by_user` channel |
| `user_sqid` | string | null | For `by_user` channel (alternative) |
| `hashtag` | string | null | For `hashtag` channel |
| `sort` | string | `"server_order"` | Sort order |
| `random_seed` | integer | null | Seed for random sort |
| `cursor` | string | null | Pagination cursor |
| `limit` | integer | 50 | Results per page (1-50) |
| `criteria` | array | [] | AMP filter criteria |
| `include_fields` | array | null | Optional fields to include |

### Channels

| Channel | Parameters | Description |
|---------|------------|-------------|
| `all` | none | All public artwork |
| `promoted` | none | Featured artwork |
| `user` | none | Player owner's artwork |
| `by_user` | `user_handle` or `user_sqid` | Specific user's artwork |
| `hashtag` | `hashtag` | Posts with hashtag |
| `artwork` | none | Alias for `all` |

### Sort Options

| Sort | Description |
|------|-------------|
| `server_order` | Insertion order (newest first) |
| `created_at` | Chronological (newest first) |
| `random` | Random (use `random_seed` for reproducibility) |

### Response

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
      "native_format": "png"
    }
  ],
  "next_cursor": "50",
  "has_more": true
}
```

### Errors

| Error Code | Cause |
|------------|-------|
| `missing_user_identifier` | `by_user` without `user_handle` or `user_sqid` |
| `user_not_found` | Invalid user identifier |
| `missing_hashtag` | `hashtag` channel without `hashtag` |
| `invalid_hashtag` | Empty hashtag |
| `invalid_criteria` | Malformed filter criteria |

## get_post

Fetch a single post by ID.

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

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | integer | Post ID to fetch |
| `include_fields` | array | Optional fields to include |

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
    "owner_handle": "artist",
    "width": 64,
    "height": 64
  }
}
```

### Errors

| Error Code | Cause |
|------------|-------|
| `not_found` | Post doesn't exist |
| `deleted` | Post was deleted |
| `not_visible` | Post is hidden |
| `not_available` | Post hidden by user/mod |
| `content_not_approved` | Monitored content not approved |

## submit_reaction

Add an emoji reaction to a post.

### Request

```json
{
  "request_id": "req-003",
  "request_type": "submit_reaction",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "post_id": 12345,
  "emoji": "❤️"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | integer | Post to react to |
| `emoji` | string | Emoji (1-20 characters) |

### Response

```json
{
  "request_id": "req-003",
  "success": true
}
```

### Notes

- Maximum 5 reactions per user per post
- Submitting same reaction twice is idempotent (returns success)
- Reactions are attributed to the player's owner account

### Errors

| Error Code | Cause |
|------------|-------|
| `invalid_emoji` | Empty or >20 characters |
| `not_found` | Post doesn't exist |
| `deleted` | Post was deleted |
| `reaction_limit_exceeded` | Already 5 reactions on post |

## revoke_reaction

Remove a previously added reaction.

### Request

```json
{
  "request_id": "req-004",
  "request_type": "revoke_reaction",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "post_id": 12345,
  "emoji": "❤️"
}
```

### Response

```json
{
  "request_id": "req-004",
  "success": true
}
```

### Notes

- Revoking non-existent reaction succeeds (idempotent)

## get_comments

Fetch comments for a post.

### Request

```json
{
  "request_id": "req-005",
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
| `limit` | integer | 50 | Results per page (1-200) |

### Response

```json
{
  "request_id": "req-005",
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
    },
    {
      "comment_id": "234f5678-f90c-23e4-b567-537725285111",
      "post_id": 12345,
      "author_handle": "replier",
      "body": "Thanks!",
      "depth": 1,
      "parent_id": "123e4567-e89b-12d3-a456-426614174000",
      "created_at": "2024-01-15T11:05:00Z",
      "deleted": false
    }
  ],
  "next_cursor": null,
  "has_more": false
}
```

### Comment Fields

| Field | Type | Description |
|-------|------|-------------|
| `comment_id` | UUID | Unique identifier |
| `post_id` | integer | Parent post |
| `author_handle` | string | Author username (null if anonymous) |
| `body` | string | Comment text |
| `depth` | integer | Nesting level (0-2) |
| `parent_id` | UUID | Parent comment (null for top-level) |
| `created_at` | datetime | Creation timestamp |
| `deleted` | boolean | Soft-deleted flag |

### Notes

- Comments limited to depth 2
- Deleted comments not included
- Higher limit (200) than posts due to smaller payloads

## get_playset

Fetch playset configuration for multi-channel playback.

### Request

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
| `playset_name` | string | Playset identifier |

### Response

```json
{
  "request_id": "req-006",
  "success": true,
  "playset_name": "followed_artists",
  "channels": [
    {
      "type": "user",
      "name": null,
      "identifier": "k5fNx",
      "display_name": "@pixelartist",
      "weight": 10
    },
    {
      "type": "named",
      "name": "promoted",
      "identifier": null,
      "display_name": "Promoted",
      "weight": 5
    }
  ],
  "exposure_mode": "manual",
  "pick_mode": "recency"
}
```

### Channel Types

| Type | Fields | Description |
|------|--------|-------------|
| `named` | `name` | Built-in channel (all, promoted) |
| `user` | `identifier` (sqid), `display_name` | User's artwork |
| `hashtag` | `identifier` (tag), `display_name` | Hashtag posts |
| `sdcard` | none | Local SD card content |

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

### Errors

| Error Code | Cause |
|------------|-------|
| `playset_not_found` | Unknown playset name |

## Include Fields

Optional fields for artwork responses:

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

Example:

```json
{
  "include_fields": ["owner_handle", "width", "height", "frame_count"]
}
```

## Error Response Format

All errors follow the same format:

```json
{
  "request_id": "req-001",
  "success": false,
  "error": "Human-readable error message",
  "error_code": "machine_readable_code"
}
```

## Common Errors

| Error Code | Description |
|------------|-------------|
| `authentication_failed` | Player not registered |
| `invalid_request` | Malformed request payload |
| `invalid_json` | JSON parse error |
| `unknown_request_type` | Unsupported request type |
| `internal_error` | Server error |

# Playlists

Curated artwork collections.

## Overview

Playlists are collections of artwork that can be played on physical devices or browsed on the web. Each playlist has metadata and an ordered list of artwork items.

## List Playlists

### GET /playlist

List playlists with optional filters.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `owner_id` | UUID | null | Filter by owner |
| `cursor` | string | null | Pagination cursor |
| `limit` | integer | 50 | Results per page (1-200) |

**Response (200):**

```json
{
  "items": [
    {
      "id": 1,
      "public_sqid": "p5kNx",
      "title": "Favorite Landscapes",
      "description": "My favorite pixel art landscapes",
      "item_count": 12,
      "owner": {
        "id": 1,
        "handle": "artist",
        "public_sqid": "m8gPq"
      },
      "created_at": "2024-01-15T09:00:00Z",
      "updated_at": "2024-01-20T10:00:00Z"
    }
  ],
  "next_cursor": "eyJpZCI6MTJ9"
}
```

## Get Playlist

### GET /playlist/{id}

Get a single playlist with its items.

**Response (200):**

```json
{
  "id": 1,
  "public_sqid": "p5kNx",
  "title": "Favorite Landscapes",
  "description": "My favorite pixel art landscapes",
  "owner": {
    "id": 1,
    "handle": "artist",
    "public_sqid": "m8gPq"
  },
  "items": [
    {
      "id": 101,
      "position": 0,
      "post": {
        "id": 12345,
        "public_sqid": "k5fNx",
        "title": "Mountain View",
        "art_url": "https://...",
        "width": 64,
        "height": 64
      }
    },
    {
      "id": 102,
      "position": 1,
      "post": {
        "id": 12346,
        "public_sqid": "k6gMy",
        "title": "Ocean Sunset",
        "art_url": "https://...",
        "width": 64,
        "height": 64
      }
    }
  ],
  "item_count": 12,
  "created_at": "2024-01-15T09:00:00Z",
  "updated_at": "2024-01-20T10:00:00Z"
}
```

## Create Playlist

### POST /playlist

Create a new playlist. Requires authentication.

```json
{
  "title": "My New Playlist",
  "description": "A collection of pixel art"
}
```

**Response (201):**

```json
{
  "id": 2,
  "public_sqid": "p6lPy",
  "title": "My New Playlist",
  "description": "A collection of pixel art",
  "owner": {
    "id": 1,
    "handle": "artist",
    "public_sqid": "m8gPq"
  },
  "items": [],
  "item_count": 0,
  "created_at": "2024-01-21T09:00:00Z",
  "updated_at": "2024-01-21T09:00:00Z"
}
```

**Limits:**

- Title: 1-200 characters
- Description: 0-5000 characters

## Update Playlist

### PATCH /playlist/{id}

Update playlist metadata. Requires ownership.

```json
{
  "title": "Updated Title",
  "description": "Updated description"
}
```

**Response (200):** Updated playlist object

## Delete Playlist

### DELETE /playlist/{id}

Delete a playlist. Requires ownership.

**Response (204):** No content

## Playlist Items

### Add Item

#### POST /playlist/{id}/items

Add artwork to playlist. Requires ownership.

```json
{
  "post_id": 12345,
  "position": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `post_id` | integer | Yes | Artwork to add |
| `position` | integer | No | Position (null = append) |

**Response (201):**

```json
{
  "id": 103,
  "playlist_id": 1,
  "post_id": 12345,
  "position": 12
}
```

**Errors:**

| Status | Detail |
|--------|--------|
| 400 | Artwork already in playlist |
| 404 | Artwork not found |

### Remove Item

#### DELETE /playlist/{id}/items/{item_id}

Remove artwork from playlist. Requires ownership.

**Response (204):** No content

### Reorder Items

#### PUT /playlist/{id}/items/reorder

Reorder playlist items. Requires ownership.

```json
{
  "item_ids": [103, 101, 102]
}
```

**Response (204):** No content

Items not in the list are appended in their current order.

### Move Item

#### PATCH /playlist/{id}/items/{item_id}

Move item to specific position. Requires ownership.

```json
{
  "position": 0
}
```

**Response (200):**

```json
{
  "id": 103,
  "playlist_id": 1,
  "post_id": 12345,
  "position": 0
}
```

## Hide/Unhide Playlist

### POST /playlist/{id}/hide

Hide playlist from public view. Requires ownership.

**Response (201):** No content

### DELETE /playlist/{id}/hide

Unhide playlist. Requires ownership.

**Response (204):** No content

## Publish Playlist

### POST /playlist/{id}/publish

Publish playlist as a post (creates playlist post type). Requires ownership.

```json
{
  "title": "My Published Playlist",
  "description": "Check out this collection"
}
```

**Response (201):**

```json
{
  "post_id": 12400,
  "public_sqid": "pk7Rz",
  "playlist_id": 1
}
```

Published playlists:

- Appear in feeds like artwork
- Can be played on devices
- Have their own reactions/comments

## Playlist Posts

When querying posts, playlists have `kind: "playlist"`:

```json
{
  "id": 12400,
  "public_sqid": "pk7Rz",
  "kind": "playlist",
  "title": "My Published Playlist",
  "total_artworks": 12,
  "dwell_time_ms": 30000
}
```

## MQTT Integration

Players can query playlist posts and their items via MQTT. See [Player Requests](../mqtt-api/player-requests.md).

## Limits

| Resource | Limit |
|----------|-------|
| Playlists per user | No limit |
| Items per playlist | 1000 |
| Title length | 200 characters |
| Description length | 5000 characters |

# Playlists

Create and maintain ordered collections of artwork. Paths on this page are relative to `https://makapix.club/api/v1`.

## Identifiers and response shape

The `/playlist` API uses a **playlist UUID**, not the integer ID of its underlying feed post. Artwork IDs inside `post_ids` are integers. A playlist is already represented as a feed post; there is no separate publish endpoint.

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "owner_id": 42,
  "title": "Favorite landscapes",
  "description": "A collection for my display",
  "post_ids": [12345, 12346],
  "visible": true,
  "hidden_by_user": false,
  "hidden_by_mod": false,
  "created_at": "2026-10-27T12:00:00Z",
  "updated_at": null
}
```

## List Playlists

### GET /playlist

Returns `items` containing playlist objects and `next_cursor`.

| Parameter | Behavior |
|-----------|----------|
| `owner_id` | Optional **user_key UUID** identifying the owner; this differs from the integer `owner_id` in responses |
| `limit` | 1–200, default 50 |
| `q`, `cursor`, `sort`, `order` | Accepted by the route, but not currently applied |

The implementation returns newest-created playlists first and `next_cursor: null`. Do not rely on search, custom sorting, or pagination beyond the first page on this endpoint.

## Get Playlist

### GET /playlist/{id}

Returns one playlist object (200), or 404 if unavailable.

## Create Playlist

### POST /playlist

Requires a signed-in account. Returns the created playlist (201).

```json
{
  "title": "Favorite landscapes",
  "description": "A collection for my display",
  "post_ids": [12345, 12346]
}
```

| Field | Requirement |
|-------|-------------|
| `title` | Required; 1–128 characters |
| `description` | Optional; up to 1,000 characters |
| `post_ids` | Optional; up to 100 integer artwork IDs |

A nonexistent post ID causes a 400 response. The server filters out entries that do not meet its artwork visibility checks, so inspect the returned `post_ids`.

## Update Playlist

### PATCH /playlist/{id}

Requires ownership or the applicable moderator permission. Returns the updated playlist (200).

Send only the metadata fields you want to change. To add, remove, or reorder artwork, send the **entire desired `post_ids` array**:

```json
{
  "title": "Evening landscapes",
  "post_ids": [12346, 12345, 12347]
}
```

Omit `post_ids` to leave the list unchanged; send `[]` to empty it. There are no individual item-add, item-delete, item-update, or reorder endpoints. Fetch the current playlist before editing to avoid accidentally replacing someone else's recent changes.

The update schema also accepts `hidden_by_user` and `hidden_by_mod` visibility flags. The same title, description, and item-count limits apply as on creation.

## Delete Playlist

### DELETE /playlist/{id}

Requires ownership or the applicable moderator permission. Returns 204 with no body.

## Visibility

### POST /playlist/{id}/hide

Hide the playlist through the owner-access route. Returns 201.

### DELETE /playlist/{id}/hide

Remove owner hiding. Returns 204.

### POST /playlist/{id}/undelete

Moderator operation that sets the playlist visible and clears both hiding flags. Returns 201.

## Player Integration

Players can retrieve playlist posts through [MQTT requests](../mqtt-api/player-requests.md) or [HTTPS RPC](player-rpc.md). Those protocols use the integer feed post ID, not the UUID used by `/playlist/{id}`.

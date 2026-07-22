# Posts

Artwork upload, listing, and management.

## Upload Artwork

### POST /post/upload

Upload a new artwork image.

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `image` | file | Yes | Image file (PNG, GIF, WebP, BMP) |
| `title` | string | Yes | Title (1-200 characters) |
| `description` | string | No | Description (max 5000 characters) |
| `hashtags` | string | No | Comma-separated hashtags |
| `hidden_by_user` | string | No | `"true"` or `"false"` |
| `license_id` | integer | No | Creative Commons license ID |

**Response (201):**

```json
{
  "post": {
    "id": 12345,
    "public_sqid": "k5fNx",
    "storage_key": "abc123-def456",
    "title": "My Artwork",
    "description": "A pixel art landscape",
    "hashtags": ["landscape", "nature"],
    "art_url": "https://vault.makapix.club/21/32/abc123-def456.png",
    "width": 64,
    "height": 64,
    "file_bytes": 2048,
    "frame_count": 1,
    "file_format": "png",
    "created_at": "2024-01-15T09:00:00Z",
    "owner": {
      "id": 1,
      "handle": "artist",
      "public_sqid": "m8gPq"
    }
  },
  "message": "Artwork uploaded successfully"
}
```

**Image Requirements:**

- Dimensions: 128×128–256×256 (any width/height, square **or rectangular**); below 128, only a fixed whitelist of sizes and their 90° rotations; either side > 256 is rejected. Authoritative rules are served at `GET /api/v1/config` (`upload` block).
- Formats: PNG, GIF, WebP, BMP
- Max file size: 5 MB

**Rate Limits (by reputation):**

| Reputation | Limit |
|------------|-------|
| < 100 | 4/hour |
| 100-499 | 16/hour |
| 500+ | 64/hour |

**Errors:**

| Status | Detail |
|--------|--------|
| 400 | Invalid image dimensions/format |
| 409 | Artwork already exists (duplicate hash) |
| 413 | File too large |
| 429 | Upload rate limit exceeded |

## List Posts

### GET /post

List posts with filters. Requires authentication.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `owner_id` | UUID | null | Filter by owner's user_key |
| `hashtag` | string | null | Filter by hashtag |
| `promoted` | boolean | null | Filter promoted posts |
| `visible_only` | boolean | true | Show only visible posts |
| `cursor` | string | null | Pagination cursor |
| `limit` | integer | 50 | Results per page (1-200) |
| `sort` | string | `created_at` | Sort field |
| `order` | string | `desc` | `asc` or `desc` |

**Filter Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `width_min`, `width_max` | integer | Dimension range |
| `height_min`, `height_max` | integer | Dimension range |
| `file_bytes_min`, `file_bytes_max` | integer | File size range |
| `frame_count_min`, `frame_count_max` | integer | Frame count range |
| `unique_colors_min`, `unique_colors_max` | integer | Color count range |
| `created_after`, `created_before` | string | Date range (ISO) |
| `has_transparency` | boolean | Transparent pixels |
| `has_semitransparency` | boolean | Semi-transparent pixels |
| `file_format` | array | Format filter (PNG, GIF, etc.) |
| `kind` | array | `static` or `animated` |
| `base`, `base_gte` | integer | Base dimension filter |
| `size`, `size_gte` | integer | Size dimension filter |

**Response (200):**

```json
{
  "items": [
    {
      "id": 12345,
      "public_sqid": "k5fNx",
      "title": "My Artwork",
      "art_url": "https://...",
      "width": 64,
      "height": 64,
      "created_at": "2024-01-15T09:00:00Z",
      "reaction_count": 5,
      "comment_count": 2,
      "user_has_liked": true,
      "owner": {...}
    }
  ],
  "next_cursor": "eyJpZCI6MTIzNDR9"
}
```

## Recent Posts (Public)

### GET /post/recent

List recent public posts. No authentication required.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | null | Pagination cursor |
| `limit` | integer | 50 | Results per page (1-200) |

Cached for 2 minutes.

## Get Post by Sqid (Public)

### GET /p/{public_sqid}

Get a single post by its public sqid. No authentication required.

**Response (200):**

```json
{
  "id": 12345,
  "public_sqid": "k5fNx",
  "storage_key": "abc123-def456",
  "title": "My Artwork",
  "description": "A pixel art landscape",
  "hashtags": ["landscape", "nature"],
  "mod_hashtags": [],
  "art_url": "https://vault.makapix.club/21/32/abc123-def456.png",
  "width": 64,
  "height": 64,
  "file_bytes": 2048,
  "frame_count": 1,
  "file_format": "png",
  "unique_colors": 16,
  "transparency_actual": false,
  "alpha_actual": false,
  "created_at": "2024-01-15T09:00:00Z",
  "metadata_modified_at": "2024-01-15T09:00:00Z",
  "artwork_modified_at": "2024-01-15T09:00:00Z",
  "visible": true,
  "promoted": false,
  "public_visibility": true,
  "reaction_count": 5,
  "comment_count": 2,
  "view_count": 100,
  "owner": {
    "id": 1,
    "handle": "artist",
    "public_sqid": "m8gPq",
    "avatar_url": "https://..."
  },
  "license": {
    "id": 1,
    "identifier": "CC-BY-ND-4.0",
    "name": "Creative Commons Attribution-NoDerivatives 4.0"
  }
}
```

## Get Post by Storage Key

### GET /post/{storage_key}

Legacy route. Get post by UUID storage key.

## Update Post

### PATCH /post/{id}

Update post metadata. Requires ownership.

```json
{
  "title": "Updated Title",
  "description": "Updated description",
  "hashtags": ["new", "tags"],
  "hidden_by_user": false
}
```

**Response (200):** Updated post object

Notes:

- `hashtags` is the **artist-controlled** tag list. It is normalized
  server-side (trim, strip one leading `#`, lowercase, dedupe, max 64) and
  moderator-owned tags (`mod_hashtags`) are re-merged automatically — artists
  cannot remove them. The response body is the source of truth.
- `hidden_by_mod` is ignored unless the caller is a moderator.

## Moderator Hashtags

### PUT /post/{id}/mod-hashtags

Replace a post's moderator-owned hashtags. Requires the `moderator` (or
`owner`) role. Full contract: `docs/mod-hashtags/API-CONTRACT.md`.

```json
{
  "hashtags": ["nsfw", "politics"],
  "reason_code": "abuse",
  "note": "missing monitored tag"
}
```

Full replace of the mod set: added tags are also added to `hashtags`
(claiming them if the artist already had them); removed tags are removed from
`hashtags` entirely. Cap: 16 tags after normalization
(`max_mod_hashtags_per_post` in `GET /config`). Targets must be non-deleted
artwork posts.

**Response (200):** Updated post object (including `mod_hashtags`)

**Errors** (`/v1` envelope, branch on `error.code`): 401 `unauthorized`,
403 `forbidden`, 404 `not_found` (missing, playlist, or soft-deleted post),
422 `validation_error` (>16 tags after normalization or a tag >64 chars).

Changes are audit-logged (`update_mod_hashtags`) and notify the artist
(notification type `mod_hashtags_updated`, diff in `comment_preview`).

## Delete Post

### DELETE /post/{id}

Soft delete post. Requires ownership.

**Response (204):** No content

**Notes:**

- Sets `deleted_by_user=true`
- Artwork hash is freed for re-upload
- Permanent deletion after 7 days

## Hide/Unhide Post

### POST /post/{id}/hide

Hide post from public view.

```json
{
  "by": "user"
}
```

Or for moderators:

```json
{
  "by": "mod",
  "reason_code": "inappropriate",
  "note": "Reason for hiding"
}
```

**Response (201):** No content

### DELETE /post/{id}/hide

Unhide post.

**Response (204):** No content

## Replace Artwork

### POST /post/{id}/replace-artwork

Replace the image of an existing post. Requires ownership.

**Content-Type:** `multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `image` | file | Yes |

**Response (200):**

```json
{
  "message": "Artwork replaced successfully",
  "post": {
    "id": 12345,
    "public_sqid": "k5fNx",
    "art_url": "https://...",
    "width": 64,
    "height": 64,
    "frame_count": 1
  }
}
```

**Errors:**

| Status | Detail |
|--------|--------|
| 400 | Artwork is identical to current artwork |
| 409 | Artwork already exists elsewhere |

## Promote/Demote (Moderator)

### POST /post/{id}/promote

Promote a post. Moderator only.

```json
{
  "category": "daily's-best",
  "reason_code": "quality",
  "note": "Great artwork"
}
```

**Response (201):**

```json
{
  "promoted": true,
  "category": "daily's-best"
}
```

### DELETE /post/{id}/promote

Demote a post. Moderator only.

**Response (204):** No content

## Public Visibility (Moderator)

### POST /post/{id}/approve-public

Approve public visibility. Moderator only.

**Response (201):**

```json
{
  "post_id": 12345,
  "public_visibility": true
}
```

### DELETE /post/{id}/approve-public

Revoke public visibility. Moderator only.

**Response (200):**

```json
{
  "post_id": 12345,
  "public_visibility": false
}
```

## Admin Notes (Moderator)

### GET /post/{id}/admin-notes

List admin notes for a post.

**Response (200):**

```json
{
  "items": [
    {
      "id": "note-uuid",
      "note": "Reviewed for content",
      "created_by": 1,
      "created_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

### POST /post/{id}/admin-notes

Add admin note.

```json
{
  "note": "Reviewed for content"
}
```

**Response (201):** No content

### DELETE /post/admin-notes/{noteId}

Delete admin note.

**Response (204):** No content

## Direct Download

### GET /d/{public_sqid}.{extension}

Download artwork in specified format.

Example: `GET /d/k5fNx.png`

Redirects to vault URL.

### GET /d/{public_sqid}/upscaled

Download the upscaled preview (if available). It is a nearest-neighbor **WebP** fit so the longest side is **≤ 768 px** (not a fixed "4×").

Returns 404 if the upscaled version doesn't exist yet.

## Moderator Actions

### POST /post/{id}/undelete

Restore moderator-deleted post. Moderator only.

**Response (201):** No content

### POST /post/{id}/delete

Soft delete post. Moderator only.

**Response (201):** No content

### DELETE /post/{id}/permanent

Permanently delete post and vault files. Moderator only.

**Response (204):** No content

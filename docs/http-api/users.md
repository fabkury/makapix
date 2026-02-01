# Users

User profiles, follows, and highlights.

## Browse Users (Public)

### GET /user/browse

Browse user profiles. No authentication required.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | null | Pagination cursor |
| `limit` | integer | 50 | Results per page (1-200) |
| `sort` | string | `reputation` | Sort field |
| `order` | string | `desc` | `asc` or `desc` |
| `has_artwork` | boolean | null | Filter users with artwork |

**Response (200):**

```json
{
  "items": [
    {
      "id": 1,
      "user_key": "550e8400-e29b-41d4-a716-446655440000",
      "public_sqid": "m8gPq",
      "handle": "artist",
      "bio": "Pixel artist",
      "avatar_url": "https://...",
      "reputation": 500,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "next_cursor": "eyJpZCI6MTJ9"
}
```

## Get User by Sqid (Public)

### GET /user/u/{public_sqid}

Get user profile by public sqid.

**Response (200):**

```json
{
  "id": 1,
  "user_key": "550e8400-e29b-41d4-a716-446655440000",
  "public_sqid": "m8gPq",
  "handle": "artist",
  "bio": "Pixel artist creating retro games",
  "avatar_url": "https://...",
  "banner_url": "https://...",
  "reputation": 500,
  "created_at": "2024-01-01T00:00:00Z",
  "is_artist": true,
  "is_following": false
}
```

Authenticated users see additional fields:

```json
{
  "email": "user@example.com",
  "email_verified": true,
  "roles": ["user"],
  "welcome_completed": true
}
```

## Get User Profile

### GET /user/u/{public_sqid}/profile

Get enhanced user profile with stats.

**Response (200):**

```json
{
  "user": {
    "id": 1,
    "public_sqid": "m8gPq",
    "handle": "artist",
    "bio": "Pixel artist",
    "avatar_url": "https://...",
    "banner_url": "https://...",
    "reputation": 500
  },
  "stats": {
    "post_count": 42,
    "follower_count": 100,
    "following_count": 25,
    "total_reactions": 500,
    "total_views": 10000
  },
  "is_following": false,
  "highlights": [
    {
      "id": 12345,
      "public_sqid": "k5fNx",
      "art_url": "https://...",
      "width": 64,
      "height": 64
    }
  ],
  "recent_posts": [...]
}
```

## Update User

### PATCH /user/{id}

Update user profile. Requires ownership.

```json
{
  "bio": "Updated bio",
  "banner_url": "https://..."
}
```

**Response (200):** Updated user object

## Upload Avatar

### POST /user/{id}/avatar

Upload user avatar. Requires ownership.

**Content-Type:** `multipart/form-data`

| Field | Type | Required |
|-------|------|----------|
| `image` | file | Yes |

**Requirements:**

- Formats: PNG, GIF, WebP, JPEG
- Max size: 5 MB
- Recommended: Square images

**Response (200):** Updated user object

### DELETE /user/{id}/avatar

Remove user avatar.

**Response (200):** Updated user object

## Follow/Unfollow

### POST /user/u/{public_sqid}/follow

Follow a user. Requires authentication.

**Response (201):**

```json
{
  "following": true,
  "follower_count": 101
}
```

### DELETE /user/u/{public_sqid}/follow

Unfollow a user. Requires authentication.

**Response (200):**

```json
{
  "following": false,
  "follower_count": 100
}
```

## List Followers/Following

### GET /user/u/{public_sqid}/followers

List users following this user.

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `cursor` | string | null |
| `limit` | integer | 50 |

**Response (200):**

```json
{
  "items": [
    {
      "id": 2,
      "public_sqid": "n9hRs",
      "handle": "follower",
      "avatar_url": "https://...",
      "is_following": false
    }
  ],
  "next_cursor": "eyJpZCI6MTJ9",
  "total_count": 100
}
```

### GET /user/u/{public_sqid}/following

List users this user follows.

Same response format as followers.

## Highlights

Profile highlights are pinned artworks shown on the user's profile.

### GET /user/me/highlights

List current user's highlights.

**Response (200):**

```json
{
  "items": [
    {
      "id": 12345,
      "public_sqid": "k5fNx",
      "title": "My Best Work",
      "art_url": "https://...",
      "width": 64,
      "height": 64,
      "position": 0
    }
  ]
}
```

### POST /user/me/highlights

Add post to highlights.

```json
{
  "post_id": 12345
}
```

**Response (201):**

```json
{
  "id": "highlight-uuid",
  "post_id": 12345,
  "position": 3
}
```

**Limits:**

- Maximum 6 highlights
- Must own the post

### DELETE /user/me/highlights/{post_id}

Remove post from highlights.

**Response (204):** No content

### PUT /user/me/highlights/reorder

Reorder highlights.

```json
{
  "post_ids": [12345, 12346, 12347]
}
```

**Response (204):** No content

## User Posts

### GET /user/{id}/artworks

List user's artwork posts.

**Query Parameters:**

| Parameter | Type | Default |
|-----------|------|---------|
| `cursor` | string | null |
| `limit` | integer | 50 |
| `sort` | string | `created_at` |
| `order` | string | `desc` |

**Response (200):**

```json
{
  "items": [...],
  "next_cursor": "...",
  "total_count": 42
}
```

### GET /user/{id}/blog-posts

List user's blog posts.

### GET /user/{id}/blog-posts/recent

List user's recent blog posts (max 5).

## Account Deletion

### POST /user/delete-account

Request account deletion. Requires authentication.

**Response (202):**

```json
{
  "message": "Account deletion scheduled",
  "deletion_date": "2024-01-22T00:00:00Z"
}
```

**Notes:**

- 7-day waiting period
- All posts are soft-deleted immediately
- Account is permanently deleted after waiting period

## Admin Endpoints

### GET /user

List all users. Admin only.

### POST /user

Create user. Admin only.

```json
{
  "handle": "newuser",
  "email": "new@example.com",
  "password": "password123"
}
```

### DELETE /user/{id}

Delete user. Admin only.

## User Artwork Route

### GET /u/{public_sqid}

Shorthand to get user by sqid (same as `/user/u/{public_sqid}`).

### GET /artwork/u/{public_sqid}

Alternative route for user lookup.

# Users

User profiles, follows, and highlights. Paths are relative to `https://makapix.club/api/v1`. Unless a route explicitly uses a sqid, `{id}` in `/user/{id}` is the user's **user_key UUID**, not their integer database ID.

## Browse Users (Public)

### GET /user/browse

Browse user profiles. No authentication required.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | null | Pagination cursor |
| `limit` | integer | 50 | Results per page (1-200) |
| `sort` | string | `alphabetical` | Sort mode; see the route contract |
| `q` | string | null | Search query |

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
  "reputation": 500,
  "created_at": "2024-01-01T00:00:00Z",
  "tagline": "Pixel artist"
}
```

This public lookup returns private fields only for authorized moderators/owners. Regular users retrieve their own full account through `/auth/me`. Simply signing in does not reveal another user's email:

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

**Response (200):** A flat profile object containing `id`, `user_key`, `public_sqid`, `handle`, `bio`, `avatar_url`, `stats`, `highlights`, `is_following`, `is_own_profile`, and `is_blocked_by_viewer`, plus other public profile fields. It is not wrapped in a `user` property. See `UserProfileEnhanced` in the [OpenAPI contract](../../api/openapi.json) for the full schema.

## Update User

### PATCH /user/{id}

Update user profile. Requires ownership.

```json
{
  "bio": "Updated bio",
  "tagline": "Pixel artist"
}
```

`mention_policy` controls who may @mention this user: `everyone` (default),
`following` (only members **this user follows**), or `nobody`. Any other value
is a 422. Returned on the full user object (`/auth/me`, this response), never
on public profiles.

**Response (200):** Updated user object

## Mention Candidates

### GET /user/mention-candidates

Users the caller may @mention, ranked for an autocomplete
([`docs/mentions/`](../mentions/README.md)). Requires authentication.
Rate limit: 120 requests/minute per user (429).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `q` | string | null | Handle prefix, matched on the handle skeleton (case- and confusable-insensitive). Empty → contextual tiers only |
| `post_id` | integer | null | Enables the `owner`/`thread` tiers; ignored if the caller cannot access the post |
| `limit` | integer | 8 | 1–20 |

```json
{"items": [
  {"handle": "artist", "public_sqid": "m8gPq", "avatar_url": "https://...", "reason": "owner"}
]}
```

`reason` ∈ `owner` · `thread` · `following` · `follower` · `search`, ranked in
that order, then by handle. Applies exactly the write path's mentionability
rule (browse visibility, including for the site owner; no block either way; the
target's `mention_policy`) and never lists the caller.

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

**Response (201):** Updated user object

### DELETE /user/{id}/avatar

Remove user avatar.

**Response (200):** Updated user object

## Follow/Unfollow

### POST /user/u/{public_sqid}/follow

Follow a user. Requires authentication.

**Response (200):**

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

### GET /user/u/{public_sqid}/highlights

List a user's highlights by public sqid.

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
  "position": 3
}
```

**Limits:**

- Maximum 128 highlights
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

Use `GET /post?owner_id={user_key}` with the user's UUID to list their artwork. See [Posts](posts.md) for filters and pagination. There is no `/user/{id}/artworks` endpoint.

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
  "status": "accepted",
  "message": "Account deletion has been queued"
}
```

The account is deactivated immediately and permanent deletion is queued for background processing. There is **no seven-day grace period** and no cancellation endpoint. The site owner cannot use this endpoint (403).

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

Deactivate and hide an account using the ownership/role checks. This is distinct from the queued permanent deletion through `/user/delete-account`.

## User Artwork Route

### GET /u/{public_sqid}

Shorthand to get user by sqid (same as `/user/u/{public_sqid}`).

Use `/user/u/{public_sqid}` for profile lookup; `/artwork/u/{public_sqid}` is not an API route.

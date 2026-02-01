# Reactions and Comments

Emoji reactions and comments on posts.

## Reactions

### Get Reactions

#### GET /post/{post_id}/reactions

Get reaction counts for a post.

**Response (200):**

```json
{
  "reactions": {
    "❤️": 15,
    "🔥": 8,
    "😍": 5,
    "👍": 3
  },
  "total": 31,
  "user_reactions": ["❤️"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `reactions` | object | Emoji to count mapping |
| `total` | integer | Total reaction count |
| `user_reactions` | array | Current user's reactions (if authenticated) |

### Add Reaction

#### POST /post/{post_id}/reactions

Add an emoji reaction. Requires authentication.

```json
{
  "emoji": "❤️"
}
```

**Response (201):**

```json
{
  "id": "reaction-uuid",
  "post_id": 12345,
  "user_id": 1,
  "emoji": "❤️",
  "created_at": "2024-01-15T10:30:00Z"
}
```

**Notes:**

- Maximum 5 reactions per user per post
- Adding same emoji twice is idempotent (returns existing)

**Errors:**

| Status | Detail |
|--------|--------|
| 400 | Maximum 5 reactions per post |
| 404 | Post not found |

### Remove Reaction

#### DELETE /post/{post_id}/reactions/{emoji}

Remove an emoji reaction. Requires authentication.

The `emoji` path parameter should be URL-encoded (e.g., `%E2%9D%A4%EF%B8%8F` for ❤️).

**Response (204):** No content

### Toggle Reaction

#### PUT /post/{post_id}/reactions/{emoji}

Toggle a reaction (add if not present, remove if present). Requires authentication.

**Response (200):**

```json
{
  "toggled": true,
  "emoji": "❤️",
  "reactions": {
    "❤️": 16,
    "🔥": 8
  },
  "total": 24
}
```

| Field | Type | Description |
|-------|------|-------------|
| `toggled` | boolean | true if added, false if removed |

## Comments

### List Comments

#### GET /post/{post_id}/comments

Get comments for a post.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | null | Pagination cursor |
| `limit` | integer | 50 | Results per page (1-200) |
| `sort` | string | `created_at` | Sort field |
| `order` | string | `asc` | `asc` or `desc` |

**Response (200):**

```json
{
  "items": [
    {
      "id": "comment-uuid",
      "post_id": 12345,
      "body": "Great artwork!",
      "depth": 0,
      "parent_id": null,
      "author": {
        "id": 2,
        "handle": "commenter",
        "public_sqid": "n9hRs",
        "avatar_url": "https://..."
      },
      "created_at": "2024-01-15T11:00:00Z",
      "deleted_by_owner": false,
      "hidden_by_mod": false
    },
    {
      "id": "reply-uuid",
      "post_id": 12345,
      "body": "Thanks!",
      "depth": 1,
      "parent_id": "comment-uuid",
      "author": {
        "id": 1,
        "handle": "artist",
        "public_sqid": "m8gPq"
      },
      "created_at": "2024-01-15T11:05:00Z",
      "deleted_by_owner": false,
      "hidden_by_mod": false
    }
  ],
  "next_cursor": null,
  "total_count": 2
}
```

### Add Comment

#### POST /post/{post_id}/comments

Add a comment. Requires authentication.

```json
{
  "body": "Great artwork!",
  "parent_id": null
}
```

For replies, include `parent_id`:

```json
{
  "body": "Thanks!",
  "parent_id": "comment-uuid"
}
```

**Response (201):**

```json
{
  "id": "new-comment-uuid",
  "post_id": 12345,
  "body": "Great artwork!",
  "depth": 0,
  "parent_id": null,
  "author": {
    "id": 2,
    "handle": "commenter",
    "public_sqid": "n9hRs"
  },
  "created_at": "2024-01-15T11:00:00Z"
}
```

**Limits:**

- Maximum depth: 2 (comments, replies, replies to replies)
- Body: 1-5000 characters

**Errors:**

| Status | Detail |
|--------|--------|
| 400 | Maximum nesting depth exceeded |
| 400 | Comment body required |
| 404 | Post not found |
| 404 | Parent comment not found |

### Update Comment

#### PATCH /post/{post_id}/comments/{comment_id}

Edit a comment. Requires ownership.

```json
{
  "body": "Updated comment text"
}
```

**Response (200):** Updated comment object

### Delete Comment

#### DELETE /post/{post_id}/comments/{comment_id}

Delete a comment. Requires ownership.

**Response (204):** No content

**Notes:**

- Soft delete (sets `deleted_by_owner=true`)
- If comment has replies, placeholder shown: "[deleted]"
- If comment has no replies, removed from list

## Moderator Actions

### Hide Comment

#### POST /post/{post_id}/comments/{comment_id}/hide

Hide a comment. Moderator only.

```json
{
  "reason_code": "inappropriate",
  "note": "Reason for hiding"
}
```

**Response (201):** No content

### Unhide Comment

#### DELETE /post/{post_id}/comments/{comment_id}/hide

Unhide a comment. Moderator only.

**Response (204):** No content

## Blog Post Reactions

Blog posts also support reactions with the same format.

### GET /blog/{id}/reactions

### PUT /blog/{id}/reactions/{emoji}

### DELETE /blog/{id}/reactions/{emoji}

## Blog Post Comments

### GET /blog/{id}/comments

### POST /blog/{id}/comments

### PATCH /blog/comments/{comment_id}

### DELETE /blog/comments/{comment_id}

## Rate Limits

Comments and reactions are not explicitly rate limited, but excessive activity may trigger abuse detection.

## Anonymous Comments

Anonymous comments are supported on some posts:

```json
{
  "body": "Anonymous comment",
  "anonymous": true
}
```

Anonymous comments show `author: null` in responses.

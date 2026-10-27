# Reactions and Comments

Emoji reactions and comments on posts.

Paths below are relative to `https://makapix.club/api/v1`. Reactions and comment creation support signed-in and anonymous visitors; anonymous ownership is associated with the request IP.

## Reactions

### Get Reactions

#### GET /post/{post_id}/reactions

Returns counts and the current visitor's selected emojis:

```json
{
  "totals": {"❤️": 15, "🔥": 8},
  "authenticated_totals": {"❤️": 12, "🔥": 8},
  "anonymous_totals": {"❤️": 3},
  "mine": ["❤️"]
}
```

`totals` combines signed-in and anonymous reactions. `mine` contains the current account's reactions, or the anonymous visitor's reactions associated with their IP.

### Add Reaction

#### PUT /post/{post_id}/reactions/{emoji}

Adds the emoji idempotently. No body is required. Returns **204 with no body**, including when the reaction already exists. This is not a toggle, and there is no `POST` reaction endpoint.

URL-encode the emoji path parameter (for example, `%E2%9D%A4%EF%B8%8F` for ❤️). A visitor may have at most five different reactions per post; exceeding the cap returns 409 with `reaction_cap_reached`.

### Remove Reaction

#### DELETE /post/{post_id}/reactions/{emoji}

Removes the selected emoji. Returns 204 with no body. Use this operation explicitly when the visitor deselects a reaction.

## Comments

### List Comments

#### GET /post/{post_id}/comments

Get comments for a post.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `cursor` | string | null | Pagination cursor |
| `limit` | integer | 50 | Results per page (1-200) |
| `view` | string | `flat` | `flat` or `tree` |

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
      "author_id": 2,
      "author_handle": "commenter",
      "author_public_sqid": "n9hRs",
      "author_avatar_url": "https://...",
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
      "author_id": 1,
      "author_handle": "artist",
      "author_public_sqid": "m8gPq",
      "author_avatar_url": null,
      "created_at": "2024-01-15T11:05:00Z",
      "deleted_by_owner": false,
      "hidden_by_mod": false
    }
  ],
  "next_cursor": null
}
```

**Mentions** ([`docs/mentions/`](../mentions/README.md)). A comment body may
carry `<@SQID>` mention markup (SQID = a user's `public_sqid`). Every comment
payload (list, create, edit, `GET /post/{id}/widget-data`) serves:

| Field | Content |
|---|---|
| `body` | Plain rendering: each `<@SQID>` replaced by the target's current `@handle` (`@user` for a deleted account). What legacy clients display. |
| `body_markup` | The stored source, with `<@SQID>` (equals `body` when there are no mentions). |
| `mentions` | `[{public_sqid, handle, avatar_url}]`: the resolved sqids, in order of first appearance. |

`POST`/`PATCH` accept markup in `body`. A mention the writer may not make
(target hidden from `/user/browse`, a block either way, the target's
`mention_policy`), mentions past 16 per text, and all mentions from anonymous
commenters are silently flattened to plain `@handle` text without rejecting the request.

### Add Comment

#### POST /post/{post_id}/comments

Add a comment as a signed-in or anonymous visitor. Anonymous requests omit the bearer token; there is no `anonymous` request field.

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
  "author_id": 2,
      "author_handle": "commenter",
      "author_public_sqid": "n9hRs",
      "author_avatar_url": null,
  "created_at": "2024-01-15T11:00:00Z"
}
```

**Limits:**

- Maximum depth: 2 (comments, replies, replies to replies)
- Body: 1–2,000 characters
- Maximum 1,000 comments per post

**Errors:**

| Status | Detail |
|--------|--------|
| 400 | Maximum nesting depth exceeded |
| 400 | Comment body required |
| 404 | Post not found |
| 404 | Parent comment not found |

### Update Comment

#### PATCH /post/comments/{comment_id}

Edit a comment. Requires ownership.

```json
{
  "body": "Updated comment text"
}
```

**Response (200):** Updated comment object

### Delete Comment

#### DELETE /post/comments/{comment_id}

Delete a comment. Requires ownership.

**Response (204):** No content

**Notes:**

- Soft delete (sets `deleted_by_owner=true`)
- If comment has replies, placeholder shown: "[deleted]"
- If comment has no replies, removed from list

## Moderator Actions

### Hide Comment

#### POST /post/comments/{comment_id}/hide

Hide a comment. Moderator only.

```json
{
  "reason_code": "inappropriate",
  "note": "Reason for hiding"
}
```

**Response (201):** No content

### Unhide Comment

#### DELETE /post/comments/{comment_id}/hide

Unhide a comment. Moderator only.

**Response (204):** No content

## Blog Post Reactions and Comments

Blog endpoints use `/blog-post`, not `/blog`. Blog features are currently disabled by the server and return 503. See the [OpenAPI contract](../../api/openapi.json) for their route definitions; use `/post` for artwork interactions.

## Rate Limits

Comment creation is limited to **30 requests per five minutes** per signed-in user or anonymous IP. A 429 response means the client should wait before retrying. Reactions have a five-emoji cap per user/IP per post.

## Anonymous Comments

Use the same comment body without an Authorization header. Anonymous comments have `author_id: null`, a generated `Guest_…` handle, and no public profile link. The response uses `author_handle`, `author_avatar_url`, and `author_public_sqid` fields rather than a nested `author` object. Raw IP addresses are not included in public comment responses.

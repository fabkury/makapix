# Social Notifications (REST + SSE)

Social notifications are an **HTTP-only** feature: the inbox is served over
REST and live delivery over an authenticated Server-Sent Events stream.
Browsers and apps never connect to the MQTT broker for notifications — MQTT is
the device plane (see `docs/notification-architecture/`).

All endpoints require a Bearer token. Base path: `/api/v1`.

## REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/social-notifications/` | List notifications (newest first, cursor-paginated) |
| GET | `/social-notifications/unread-count` | Unread count (block-filtered, matches the list) |
| POST | `/social-notifications/mark-read` | Mark specific notifications read (JSON array of IDs, max 200) |
| POST | `/social-notifications/mark-all-read` | Mark all notifications read |
| DELETE | `/social-notifications/{id}` | Delete one notification |

### Listing and pagination

`GET /social-notifications/?limit=50[&cursor=...][&unread_only=true]`

- `limit`: 1–200, default 50.
- `cursor`: **opaque** string from the previous page's `next_cursor` — echo it
  verbatim, do not parse it. (Keyset on `(created_at, id)`; bare ISO-timestamp
  cursors issued before 2026-08 are still accepted.)
- Notifications from actors the viewer has blocked are hidden (ugc-safety D10).

### Item payload

```json
{
  "id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "user_id": 42,
  "notification_type": "reaction",
  "post_id": 123,
  "actor_handle": "user42",
  "actor_avatar_url": "https://vault.makapix.club/.../avatar.png",
  "actor_public_sqid": "t5",
  "emoji": "❤️",
  "comment_preview": null,
  "content_title": "Cool Pixel Art",
  "content_sqid": "abc123",
  "content_art_url": "https://vault.makapix.club/.../art.png",
  "is_read": false,
  "created_at": "2026-08-09T02:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (UUID) | Notification ID — dedupe key across REST and SSE |
| `user_id` | int | Recipient's user id |
| `notification_type` | string | See table below |
| `post_id` | int? | Related post ID (null for system notifications) |
| `actor_handle` | string? | Handle of the acting user (`"Anonymous"` if no actor) |
| `actor_avatar_url` | string? | Avatar URL of the actor |
| `actor_public_sqid` | string? | Actor's public sqid for `/u/{sqid}` links (null when anonymous or deleted) |
| `emoji` | string? | Emoji for reaction notifications |
| `comment_preview` | string? | First 100 chars of the comment (nulled if the comment is later deleted) |
| `content_title` | string? | Title of the related post |
| `content_sqid` | string? | Public sqid of the related post |
| `content_art_url` | string? | Art URL of the related post |
| `is_read` | bool | Read state |
| `created_at` | string | ISO 8601 timestamp |

### Notification types

Source of truth: `api/app/constants.py:NotificationType`.

| Type | Trigger |
|------|---------|
| `reaction` | Someone reacts to your post |
| `comment` | Someone comments on your post |
| `comment_reply` | Someone replies to your comment |
| `comment_like` | Someone likes your comment |
| `follow` | Someone follows you |
| `post_promoted` | A moderator promotes your post to a category |
| `mod_hashtags_updated` | A moderator updates tags on your artwork |
| `reputation_change` | A moderator changes your reputation |
| `moderator_granted` | You are granted the moderator role |
| `moderator_revoked` | Your moderator role is revoked |
| `new_report` | (moderators) A new content report was filed |
| `report_resolved` | Your report was reviewed and resolved |
| `remix` | Someone published a Remix of your artwork |
| `post_approved` | A moderator approved your pending post for public release |
| `trust_granted` | A moderator granted you Trust (future uploads auto-approved) |

### Rate limiting

Notification creation is limited to 720/hour per actor–recipient pair;
self-actions never notify.

### Retention

Read notifications are deleted after 90 days; all notifications after 365 days
(nightly task, see `reference/scheduled-tasks.md`).

## SSE Stream

```
GET /api/v1/realtime/notifications
Authorization: Bearer <access_token>
Accept: text/event-stream
```

Live push of the authenticated user's notifications. Delivery is in-process
push (no polling); the stream carries only events created while it is open —
clients backfill history via the REST list.

### Events

| Event | Data | Meaning |
|-------|------|---------|
| `connected` | `{"unread_count": N}` | Greeting on every (re)connect. **Authoritative** — reconcile your badge to it. |
| `notification` | full item payload (above) | A new notification. Dedupe by `id` against your list/badge. |
| `: keepalive` | — | Comment frame roughly every 15 s of silence; ignore. |
| `timeout` | `{"message": ...}` | Bounded-lifetime close (~300 s). Reconnect immediately. |

### Client integration notes

- **Browsers must use fetch-streaming, not `EventSource`** — the endpoint
  authenticates via the `Authorization` header, which `EventSource` cannot
  send. Reference client: `web/src/hooks/useNotificationsSSE.ts` (frame
  parser, immediate reconnect on `timeout`, exponential backoff on errors).
- A notification from an actor the recipient has blocked is neither streamed
  nor counted (consistent with the REST list).
- REST polling of `unread-count` remains a valid fallback when the stream is
  unavailable.

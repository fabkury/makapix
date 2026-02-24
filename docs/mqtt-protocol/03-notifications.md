# Notifications and REST API

This document covers MQTT notification topics (post notifications and social notifications), web client integration, and the REST API endpoints related to MQTT and player management.

## Post Notifications

The server publishes notifications when new posts are created or promoted. These are consumed by web clients (via WebSocket) and can be used by physical players for real-time awareness.

### Topics

| Topic | Trigger | Audience |
|-------|---------|----------|
| `makapix/post/new/{post_id}` | Any new post | Monitoring/debugging |
| `makapix/post/new/user/{follower_id}/{post_id}` | New post from followed artist | Per-follower delivery |
| `makapix/post/new/category/{category}/{post_id}` | Post promoted to category | Category followers |

All published with QoS 1, no retention.

### Post Notification Payload

```json
{
  "post_id": 123,
  "owner_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "owner_handle": "artist123",
  "title": "Cool Pixel Art",
  "art_url": "https://makapix.club/api/vault/7c/9e/66/7c9e6679.png",
  "width": 64,
  "height": 64,
  "promoted_category": null,
  "created_at": "2025-12-09T01:30:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `post_id` | int | Post ID |
| `owner_id` | string (UUID) | Creator's user ID |
| `owner_handle` | string | Creator's handle |
| `title` | string | Post title |
| `art_url` | string (URL) | Full URL to artwork file |
| `width` | int | Image width in pixels |
| `height` | int | Image height in pixels |
| `promoted_category` | string? | Promotion category name (e.g., `"daily's-best"`) or null |
| `created_at` | string | ISO 8601 timestamp |

### New Post Notifications

When an artist creates a new post, the server:

1. Queries all followers of the post owner.
2. Filters out followers who haven't approved the post's monitored hashtags.
3. Publishes to `makapix/post/new/user/{follower_id}/{post_id}` for each remaining follower.
4. Publishes to `makapix/post/new/{post_id}` (generic, for monitoring).

Source: `api/app/mqtt/notifications.py:publish_new_post_notification()`

### Category Promotion Notifications

When a post is promoted to a category (e.g., `"daily's-best"`), the server:

1. Queries all users following that category.
2. Filters out followers who haven't approved the post's monitored hashtags.
3. Publishes to `makapix/post/new/category/{category}/{post_id}` for each follower.

Source: `api/app/mqtt/notifications.py:publish_category_promotion_notification()`

---

## Social Notifications

Social notifications deliver real-time alerts for reactions, comments, follows, and moderation events.

### Topic

```
makapix/social-notifications/user/{user_id}
```

Published with QoS 1, no retention. One topic per user -- all notification types for a given user arrive on the same topic.

### Payload

```json
{
  "id": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
  "notification_type": "reaction",
  "post_id": 123,
  "actor_handle": "user42",
  "actor_avatar_url": "https://makapix.club/api/vault/.../avatar.png",
  "emoji": "❤️",
  "comment_preview": null,
  "content_title": "Cool Pixel Art",
  "content_sqid": "abc123",
  "content_art_url": "https://makapix.club/api/vault/.../art.png",
  "created_at": "2025-12-09T02:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (UUID) | Notification ID |
| `notification_type` | string | See table below |
| `post_id` | int? | Related post ID (null for system notifications) |
| `actor_handle` | string? | Handle of the user who performed the action (`"Anonymous"` if no actor) |
| `actor_avatar_url` | string? | Avatar URL of the actor |
| `emoji` | string? | Emoji for reaction notifications |
| `comment_preview` | string? | First 100 characters of comment body (with `...` if truncated) |
| `content_title` | string? | Title of the related post |
| `content_sqid` | string? | Public sqid of the related post |
| `content_art_url` | string? | Art URL of the related post |
| `created_at` | string | ISO 8601 timestamp |

### Notification Types

| Type | Trigger | Key Fields |
|------|---------|------------|
| `reaction` | Someone reacts to your post | `emoji`, `post_id`, `actor_handle` |
| `comment` | Someone comments on your post | `comment_preview`, `post_id`, `actor_handle` |
| `comment_reply` | Someone replies to your comment | `comment_preview`, `post_id`, `actor_handle` |
| `follow` | Someone follows you | `actor_handle` |
| `moderator_granted` | You are granted moderator role | `actor_handle` |
| `moderator_revoked` | Your moderator role is revoked | `actor_handle` |
| `reputation_change` | Your reputation score changed | `content_title` |

### Rate Limiting

Social notifications are rate-limited to 720 per hour per actor-recipient pair. Self-actions (actor = recipient) are skipped entirely.

Source: `api/app/services/social_notifications.py`

---

## Web Client Integration

### Connection

Web browsers connect via WebSocket through Caddy:

```typescript
import mqtt from "mqtt";

const client = mqtt.connect("wss://makapix.club/mqtt", {
  username: "webclient",
  password: process.env.NEXT_PUBLIC_MQTT_WEBCLIENT_PASSWORD,
  clientId: `web-${userId}-${Date.now()}`,
  reconnectPeriod: 5000,
  connectTimeout: 10000,
  clean: true,
});
```

### Subscriptions

The web client subscribes to three topic patterns:

| Topic Pattern | Purpose |
|---------------|---------|
| `makapix/post/new/user/{userId}/+` | New posts from followed artists |
| `makapix/post/new/category/daily's-best/+` | Daily's best category promotions |
| `makapix/social-notifications/user/{userId}` | Reactions, comments, follows, etc. |

All subscriptions use QoS 1.

### Message Routing

Messages are routed by topic prefix:
- Topics starting with `makapix/social-notifications/` are dispatched to social notification callbacks.
- All other topics are dispatched to post notification callbacks.

### Frontend Implementation

The MQTT client is implemented in `web/src/lib/mqtt-client.ts` as the `MQTTClient` class:
- `connect(userId)` -- Connect and subscribe to topics.
- `onNotification(callback)` -- Register a post notification callback. Returns an unsubscribe function.
- `onSocialNotification(callback)` -- Register a social notification callback. Returns an unsubscribe function.
- `disconnect()` -- Disconnect and clear all callbacks.

The `SocialNotificationsContext` React context (in `web/src/contexts/SocialNotificationsContext.tsx`) wraps the MQTT client, managing connection lifecycle, unread counts, and notification state.

### Known Issue

The frontend subscribes to `makapix/posts/new/...` (plural "posts") but the backend publishes to `makapix/post/new/...` (singular "post"). This means web clients do not currently receive post notifications via MQTT. Social notifications (which use `makapix/social-notifications/...`) are unaffected.

---

## REST API Endpoints

### Player Management

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/player/provision` | None | Provision a new player device |
| POST | `/player/register` | Bearer token | Register a player to user's account |
| GET | `/player/{player_key}/credentials` | None (rate limited) | Download TLS certificates |
| GET | `/u/{sqid}/player` | Bearer token | List user's players |
| GET | `/u/{sqid}/player/{player_id}` | Bearer token | Get player details |
| PATCH | `/u/{sqid}/player/{player_id}` | Bearer token | Update player (name) |
| DELETE | `/u/{sqid}/player/{player_id}` | Bearer token | Remove player |
| GET | `/u/{sqid}/player/{player_id}/certs` | Bearer token | Download player certs (owner access) |
| POST | `/u/{sqid}/player/{player_id}/command` | Bearer token | Send command to player |
| POST | `/u/{sqid}/player/command/all` | Bearer token | Send command to all user's players |
| POST | `/u/{sqid}/player/{player_id}/renew-cert` | Bearer token | Renew TLS certificate |

### MQTT Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/mqtt/bootstrap` | None | Get MQTT broker connection info |
| POST | `/mqtt/demo` | Bearer token | Publish demo message (dev only) |

### Player Lifecycle

```
Provision ──► Register ──► Download Certs ──► MQTT Connect ──► Active
  (device)     (owner)       (device)          (device)
```

1. **Provision**: Device calls `POST /player/provision` with `device_model` and `firmware_version`. Returns `player_key` (UUID) and `registration_code` (6-char, expires in 15 minutes).
2. **Register**: Owner calls `POST /player/register` with the registration code and a display name. Binds the player to the owner's account.
3. **Download certificates**: Device calls `GET /player/{player_key}/credentials`. Returns CA cert, client cert, and private key as PEM strings, plus broker host/port.
4. **MQTT connect**: Device connects via mTLS on port 8883.
5. **Active**: Player participates in request/response, receives commands, sends status and view events.

### Command Endpoint

`POST /u/{sqid}/player/{player_id}/command`

Request body:

```json
{
  "command_type": "show_artwork",
  "post_id": 123
}
```

| Field | Type | Description |
|-------|------|-------------|
| `command_type` | string | `"swap_next"`, `"swap_back"`, `"show_artwork"`, `"play_channel"`, `"play_playset"` |
| `post_id` | int? | Required for `show_artwork` |
| `channel_name` | string? | For `play_channel`: `"all"`, `"promoted"`, `"by_user"` |
| `hashtag` | string? | For `play_channel` with hashtag |
| `user_sqid` | string? | For `play_channel` with user profile |
| `user_handle` | string? | For `play_channel` with user profile |
| `playset_name` | string? | Required for `play_playset` (e.g., `"followed_artists"`) |

Response:

```json
{
  "command_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "sent"
}
```

Rate limits: 300 commands/minute per player, 1000 commands/minute per user.

### Certificate Renewal

`POST /u/{sqid}/player/{player_id}/renew-cert`

Available only when the certificate is within 30 days of expiry or already expired.

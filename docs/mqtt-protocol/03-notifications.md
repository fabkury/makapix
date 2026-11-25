# REST API and Player Lifecycle

> **Social notifications are HTTP-only** (REST + SSE); see
> [Notifications](../http-api/notifications.md). Browsers do not connect to the MQTT
> broker. Player devices can use MQTT or HTTPS for queries and reporting. The former MQTT notification topics
> (`makapix/post/new/*`, `makapix/social-notifications/*`) and the browser
> WebSocket listener were removed in 2026-08.

This document covers the REST API endpoints related to player management and
the player lifecycle. Paths are relative to `https://makapix.club/api`.

## REST API Endpoints

### Player Management

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/player/provision` | None | Provision a new player device |
| POST | `/player/register` | Bearer token | Register a player to user's account |
| GET | `/player/{player_key}/credentials` | Secret `player_key` (rate limited) | Download TLS certificates and the initial HTTPS token |
| GET | `/u/{sqid}/player` | Bearer token | List user's players |
| GET | `/u/{sqid}/player/{player_id}` | Bearer token | Get player details |
| PATCH | `/u/{sqid}/player/{player_id}` | Bearer token | Update player (name) |
| DELETE | `/u/{sqid}/player/{player_id}` | Bearer token | Remove player |
| GET | `/u/{sqid}/player/{player_id}/certs` | Bearer token | Download player certs (owner access) |
| POST | `/u/{sqid}/player/{player_id}/command` | Bearer token | Send command to player |
| POST | `/u/{sqid}/player/command/all` | Bearer token | Send command to all user's players |
| POST | `/u/{sqid}/player/{player_id}/renew-cert` | Bearer token | Renew TLS certificate |

### Player Lifecycle

1. **Provision:** The device calls `POST /player/provision` and receives a player key and a six-character code valid for 15 minutes.
2. **Register:** The signed-in owner enters that code to link the player.
3. **Save credentials:** The device retrieves its certificate bundle and initial HTTPS token from `/player/{player_key}/credentials`.
4. **Connect:** Use MQTT with mTLS for commands and presence, HTTPS for queries/reporting, or both.

See the [registration sequence](../player/registration.md#overview) and [transport comparison](../player/README.md#choosing-a-transport).

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

Available only when the certificate is within the default 90-day expiry window or already expired.

Devices can also renew using `POST /player/renew-cert` with their HTTPS bearer token. See [Certificate Renewal](../player/registration.md#certificate-renewal).

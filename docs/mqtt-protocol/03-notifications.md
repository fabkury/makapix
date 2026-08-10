# REST API and Player Lifecycle

> **Social notifications are HTTP-only** (REST + SSE) — see
> `docs/http-api/notifications.md`. Browsers do not connect to the MQTT
> broker: MQTT is the device plane, HTTPS is the human plane
> (`docs/notification-architecture/`). The former MQTT notification topics
> (`makapix/post/new/*`, `makapix/social-notifications/*`) and the browser
> WebSocket listener were removed in 2026-08.

This document covers the REST API endpoints related to player management and
the player lifecycle.

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

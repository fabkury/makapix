# Player HTTP API

Device management and control via HTTP.

## Overview

The Player HTTP API handles device registration, credential management, and command sending. Real-time communication happens over MQTT (see [MQTT API](../mqtt-api/README.md)).

## Device Provisioning

### POST /player/provision

Provision a new player device. No authentication required.

```json
{
  "device_model": "p3a-64x64",
  "firmware_version": "2.1.0"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `device_model` | string | Yes | Hardware identifier |
| `firmware_version` | string | Yes | Current firmware |

**Response (201):**

```json
{
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "registration_code": "A7B3K9",
  "registration_code_expires_at": "2024-01-15T10:30:00Z",
  "mqtt_broker": {
    "host": "makapix.club",
    "port": 8884
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `player_key` | UUID | Permanent device identifier |
| `registration_code` | string | 6-character code (15 min validity) |
| `registration_code_expires_at` | datetime | Code expiration time |
| `mqtt_broker.host` | string | MQTT broker hostname |
| `mqtt_broker.port` | integer | MQTT broker TLS port |

## Device Registration

### POST /player/register

Link a provisioned device to user account. Requires authentication.

```json
{
  "registration_code": "A7B3K9",
  "name": "Living Room Display"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `registration_code` | string | Yes | 6-character code from provision |
| `name` | string | Yes | Friendly device name |

**Response (201):**

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Living Room Display",
  "device_model": "p3a-64x64",
  "firmware_version": "2.1.0",
  "registration_status": "registered",
  "registered_at": "2024-01-15T10:20:00Z"
}
```

**Errors:**

| Status | Detail |
|--------|--------|
| 400 | Maximum 128 players allowed per user |
| 404 | Invalid or expired registration code |

## Get Credentials

### GET /player/{player_key}/credentials

Get TLS certificates for MQTT connection. No authentication required.

**Response (200):**

```json
{
  "ca_pem": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n",
  "cert_pem": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n",
  "key_pem": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n",
  "broker": {
    "host": "makapix.club",
    "port": 8884
  }
}
```

**Rate Limit:** 20 requests/minute/IP

**Errors:**

| Status | Detail |
|--------|--------|
| 404 | Player not found or not registered |
| 404 | Certificates not available |
| 429 | Rate limited |

## List Players

### GET /u/{sqid}/player

List all players for a user. Requires authentication and ownership.

**Response (200):**

```json
{
  "items": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "player_key": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Living Room Display",
      "device_model": "p3a-64x64",
      "firmware_version": "2.1.0",
      "registration_status": "registered",
      "registered_at": "2024-01-15T10:20:00Z",
      "connection_status": "online",
      "last_seen_at": "2024-01-15T12:00:00Z",
      "current_post_id": 12345,
      "cert_expires_at": "2025-01-15T10:20:00Z"
    }
  ]
}
```

## Get Player

### GET /u/{sqid}/player/{player_id}

Get a single player. Requires authentication and ownership.

**Response (200):** Player object (same as list item)

## Update Player

### PATCH /u/{sqid}/player/{player_id}

Update player name. Requires authentication and ownership.

```json
{
  "name": "New Display Name"
}
```

**Response (200):** Updated player object

## Delete Player

### DELETE /u/{sqid}/player/{player_id}

Remove player registration. Requires authentication and ownership.

**Response (204):** No content

**Effects:**

- TLS certificate revoked
- MQTT connection terminated
- Player record deleted
- Command logs preserved for audit

## Download Certificates

### GET /u/{sqid}/player/{player_id}/certs

Download certificates for a registered player. Requires authentication and ownership.

**Response (200):** Same as `/player/{player_key}/credentials`

## Renew Certificate

### POST /u/{sqid}/player/{player_id}/renew-cert

Renew player certificate. Requires authentication and ownership.

**Response (200):**

```json
{
  "cert_expires_at": "2025-01-20T10:20:00Z",
  "message": "Certificate renewed successfully"
}
```

**Notes:**

- Only available within 30 days of expiry
- Device must re-fetch credentials after renewal

**Errors:**

| Status | Detail |
|--------|--------|
| 400 | Certificate still valid for X days |

## Send Command

### POST /u/{sqid}/player/{player_id}/command

Send command to a player. Requires authentication and ownership.

```json
{
  "command_type": "show_artwork",
  "post_id": 12345
}
```

### Command Types

#### swap_next / swap_back

Advance to next/previous artwork.

```json
{
  "command_type": "swap_next"
}
```

#### show_artwork

Display specific artwork.

```json
{
  "command_type": "show_artwork",
  "post_id": 12345
}
```

#### play_channel

Switch to a channel.

```json
{
  "command_type": "play_channel",
  "channel_name": "promoted"
}
```

Or for user channel:

```json
{
  "command_type": "play_channel",
  "channel_name": "by_user",
  "user_sqid": "m8gPq"
}
```

Or for hashtag:

```json
{
  "command_type": "play_channel",
  "hashtag": "landscape"
}
```

#### play_playset

Load playset configuration.

```json
{
  "command_type": "play_playset",
  "playset_name": "followed_artists"
}
```

**Response (200):**

```json
{
  "command_id": "cmd-uuid",
  "status": "sent"
}
```

**Rate Limits:**

| Scope | Limit |
|-------|-------|
| Per player | 300/minute |
| Per user | 1,000/minute |

## Send Command to All Players

### POST /u/{sqid}/player/command/all

Send command to all registered players. Requires authentication and ownership.

Same request body as single player command.

**Response (200):**

```json
{
  "sent_count": 3,
  "commands": [
    {"command_id": "cmd-1", "status": "sent"},
    {"command_id": "cmd-2", "status": "sent"},
    {"command_id": "cmd-3", "status": "sent"}
  ]
}
```

## Constants

| Constant | Value |
|----------|-------|
| Max players per user | 128 |
| Registration code validity | 15 minutes |
| Certificate validity | 365 days |
| Certificate renewal threshold | 30 days |
| Credential request rate limit | 20/minute/IP |
| Command rate limit (player) | 300/minute |
| Command rate limit (user) | 1,000/minute |

## Error Codes

| Status | Detail |
|--------|--------|
| 400 | Maximum players reached |
| 400 | Invalid command parameters |
| 400 | Certificate not due for renewal |
| 403 | Post is not visible |
| 404 | Player not found |
| 404 | Post not found |
| 404 | User not found |
| 404 | Playset not found |
| 429 | Rate limit exceeded |

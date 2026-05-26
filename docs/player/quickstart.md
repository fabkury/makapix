# Quick Start

Get a player device connected to Makapix in four steps.

## Prerequisites

- A device with network connectivity (MQTT *or* HTTPS — your choice)
- A Makapix Club account ([makapix.club](https://makapix.club))

## Step 1: Provision the Device

Your device makes an HTTP POST to get a player key and registration code.

```
POST https://makapix.club/api/player/provision
Content-Type: application/json

{
  "device_model": "my-player-v1",
  "firmware_version": "1.0.0"
}
```

Response:

```json
{
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "registration_code": "A7B3K9",
  "registration_code_expires_at": "2024-01-15T10:30:00Z",
  "mqtt_broker": { "host": "makapix.club", "port": 8883 },
  "https_api": { "base_url": "https://makapix.club/api", "auth": "bearer" }
}
```

The response advertises **both** transports — `mqtt_broker` and `https_api` —
so you can pick either one later.

Save the `player_key` - this is your device's permanent identifier.

Display the `registration_code` to the user (they have 15 minutes).

## Step 2: User Links the Device

The user:

1. Logs in to [makapix.club](https://makapix.club)
2. Goes to Settings > Players > Add Device
3. Enters the 6-character code (e.g., `A7B3K9`)
4. Names the device

## Step 3: Retrieve Credentials

Once registered, your device fetches TLS certificates:

```
GET https://makapix.club/api/player/{player_key}/credentials
```

Response:

```json
{
  "ca_pem": "-----BEGIN CERTIFICATE-----\n...",
  "cert_pem": "-----BEGIN CERTIFICATE-----\n...",
  "key_pem": "-----BEGIN RSA PRIVATE KEY-----\n...",
  "broker": { "host": "makapix.club", "port": 8883 },
  "https_api": { "base_url": "https://makapix.club/api", "auth": "bearer" },
  "api_token": "mpx_live_8sK2f9Qd..."
}
```

This single response sets you up for either transport: the **TLS certificates**
(`ca_pem` / `cert_pem` / `key_pem`) for MQTT, and the **bearer token**
(`api_token`) for HTTPS. The `api_token` is returned **once**, on the first
fetch — store it alongside the certificates. (If you lose it, rotate a new one;
see [HTTPS Connection](https-connection.md).)

Store these credentials securely on your device.

## Step 4: Connect and make your first request

You now have credentials for **both** transports. Use whichever suits your
device — they accept the same request and return the same data.

### Option A — MQTT (adds real-time commands + presence)

Connect to the broker using the certificates:

```
Host: makapix.club
Port: 8883
Protocol: MQTT 5.0 over TLS
Client ID: {player_key}
Username: {player_key}
TLS: ca_pem, cert_pem, key_pem from credentials
```

Subscribe for commands and responses, then query the feed:

- **Subscribe:** `makapix/player/{player_key}/command` and `.../response/+`
- **Publish to:** `makapix/player/{player_key}/request/{request_id}`

```json
{
  "request_id": "req-001",
  "request_type": "query_posts",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "channel": "all",
  "limit": 10
}
```

The response arrives on `makapix/player/{player_key}/response/{request_id}`.

### Option B — HTTPS (request/response, no persistent socket)

Send the same request as one authenticated `POST`. Identity comes from the
bearer token, so `player_key` and `request_id` aren't required:

```
POST https://makapix.club/api/player/rpc
Authorization: Bearer mpx_live_8sK2f9Qd...
Content-Type: application/json

{
  "request_type": "query_posts",
  "channel": "all",
  "limit": 10
}
```

The response is the HTTP body (status 200).

### Response (identical either way)

```json
{
  "success": true,
  "posts": [
    {
      "post_id": 12345,
      "kind": "artwork",
      "created_at": "2024-01-15T09:00:00Z",
      "storage_key": "abc123",
      "art_url": "https://makapix.club/api/vault/a1/b2/c3/abc123.png",
      "storage_shard": "a1/b2/c3",
      "native_format": "png"
    }
  ],
  "next_cursor": "10",
  "has_more": true
}
```

(Over MQTT, the response also echoes your `request_id`.)

## Next Steps

- [Registration](registration.md) - Full provisioning flow details
- [MQTT Connection](mqtt-connection.md) - TLS configuration and reconnection
- [HTTPS Connection](https-connection.md) - Bearer-token auth and the player RPC API
- [Querying Artwork](querying-artwork.md) - Filtering and pagination
- [Displaying Artwork](displaying-artwork.md) - Image handling

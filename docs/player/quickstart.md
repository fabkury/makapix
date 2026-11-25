# Quick Start

Get a player connected to Makapix Club in four steps. To try the full flow on your computer first, run the [Python HTTPS example](https-connection.md#reference-example-start-here).

## Prerequisites

- A device with network connectivity (MQTT or HTTPS)
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

The response advertises both connection options through `mqtt_broker` and `https_api`. Choose one when you connect.

Save the `player_key` securely. It is your device's permanent identifier and grants access to credential recovery.

Display the `registration_code` to the user (they have 15 minutes).

## Step 2: User Links the Device

The user:

1. Logs in to [makapix.club](https://makapix.club)
2. Opens their profile menu, chooses **Manage Players**, then **Register Player**
3. Enters the 6-character code (e.g., `A7B3K9`)
4. Names the device

## Step 3: Retrieve Credentials

Once registered, your device fetches TLS certificates and an HTTPS token:

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
fetch. Store it alongside the certificates. (If you lose it, rotate a new one;
see [HTTPS Connection](https-connection.md).)

Store these credentials securely on your device. A 404 before the owner enters the code means registration is still pending; retry about every five seconds until the code expires. Honor `Retry-After` if rate limited.

## Step 4: Connect and make your first request

You now have credentials for **both** transports. Use whichever suits your
device. They support the same operations and artwork data.

### Option A: MQTT (adds real-time commands + presence)

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

### Option B: HTTPS (request/response, no persistent socket)

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

> Prefer a working example? [`scripts/test_https_player_api.py`](../../scripts/test_https_player_api.py)
> runs this entire flow (provision → token → query → download); see
> [HTTPS Connection](https-connection.md#reference-example-start-here).

### Example response

```json
{
  "success": true,
  "posts": [
    {
      "post_id": 12345,
      "kind": "artwork",
      "created_at": "2024-01-15T09:00:00Z",
      "storage_key": "abc123",
      "art_url": "https://vault.makapix.club/21/32/abc123.png",
      "storage_shard": "21/32",
      "native_format": "png"
    }
  ],
  "next_cursor": "10",
  "has_more": true
}
```

This abbreviated response illustrates the shape; use the actual `art_url` and opaque `next_cursor` returned by the server. MQTT also echoes your `request_id`. Download `art_url` separately, decode the image, and display it; see [Displaying Artwork](displaying-artwork.md).

## Next Steps

- [Registration](registration.md) - Full provisioning flow details
- [MQTT Connection](mqtt-connection.md) - TLS configuration and reconnection
- [HTTPS Connection](https-connection.md) - Bearer-token auth and the player RPC API
- [Querying Artwork](querying-artwork.md) - Filtering and pagination
- [Displaying Artwork](displaying-artwork.md) - Image handling

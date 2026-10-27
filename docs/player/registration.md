# Device Registration

The registration flow links a physical device to a Makapix user account.

## Overview

Registration is a three-step handshake:

1. **Provision** - Device requests an identifier and registration code (no login required)
2. **Register** - User authenticates on web and enters the code
3. **Credentials** - Device retrieves its TLS certificates **and** HTTPS bearer token

The same flow sets up both transports: the certificates are used for MQTT, and
the bearer token for HTTPS. A device only needs whichever it intends to use.

```mermaid
flowchart TD
    Provision["Device requests a code"] --> Show["Device displays the code"]
    Show --> Link["Owner signs in and enters code"]
    Link --> Fetch["Device retrieves credentials"]
    Fetch --> Save["Device saves credentials"]
    Save --> Connect["Device connects via HTTPS or MQTT"]
```

The API returns the HTTPS bearer token only once. Save it securely before
connecting. The endpoint paths and request bodies are shown below.

## Step 1: Provision

The device initiates registration by requesting a player key.

### Request

```
POST /api/player/provision
Content-Type: application/json
```

```json
{
  "device_model": "p3a-720x720",
  "firmware_version": "2.1.0"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `device_model` | string | Yes | Device hardware identifier |
| `firmware_version` | string | Yes | Current firmware version |

### Response

```json
{
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "registration_code": "A7B3K9",
  "registration_code_expires_at": "2024-01-15T10:30:00Z",
  "mqtt_broker": { "host": "makapix.club", "port": 8883 },
  "https_api": { "base_url": "https://makapix.club/api", "auth": "bearer" }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `player_key` | UUID | Permanent device identifier |
| `registration_code` | string | 6-character alphanumeric code |
| `registration_code_expires_at` | datetime | Code expiry (15 minutes from creation) |
| `mqtt_broker.host` | string | MQTT broker hostname |
| `mqtt_broker.port` | integer | MQTT broker TLS port |
| `https_api.base_url` | string | Base URL of the HTTPS player API |
| `https_api.auth` | string | HTTPS auth scheme (`bearer`) |

### Device Actions

1. Store `player_key` permanently (survives reboots)
2. Display `registration_code` prominently
3. Optionally show a countdown timer (15 minutes)
4. Begin polling for credentials

## Step 2: User Registration

The user completes registration through the web interface.

This step requires authentication - the user must be logged in to link a device.

### Web Interface Flow

1. User opens their profile menu, chooses **Manage Players**, then **Register Player**
2. User enters the 6-character code
3. User provides a friendly name (e.g., "Living Room Display")
4. Server validates code and links device to user

### API Endpoint (Web App Use)

```
POST /api/player/register
Authorization: Bearer {access_token}
Content-Type: application/json
```

```json
{
  "registration_code": "A7B3K9",
  "name": "Living Room Display"
}
```

### Response

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Living Room Display",
  "device_model": "p3a-720x720",
  "firmware_version": "2.1.0",
  "registration_status": "registered",
  "registered_at": "2024-01-15T10:20:00Z"
}
```

### What Happens

1. Server validates the registration code
2. Server generates mTLS certificates (CN = player_key)
3. Server adds player_key to MQTT password file
4. Player record is linked to user account
5. Registration code is cleared (one-time use)

## Step 3: Retrieve Credentials

Once registered, the device retrieves its TLS certificates and HTTPS bearer token.

### Request

```
GET /api/player/{player_key}/credentials
```

No separate login token is required. Possession of `player_key` grants access to this endpoint and token recovery, so treat it as a secret. Do not publish it in logs or bug reports.

### Response

```json
{
  "ca_pem": "-----BEGIN CERTIFICATE-----\nMIID...\n-----END CERTIFICATE-----\n",
  "cert_pem": "-----BEGIN CERTIFICATE-----\nMIID...\n-----END CERTIFICATE-----\n",
  "key_pem": "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----\n",
  "broker": { "host": "makapix.club", "port": 8883 },
  "https_api": { "base_url": "https://makapix.club/api", "auth": "bearer" },
  "api_token": "mpx_live_8sK2f9Qd..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ca_pem` | string | CA certificate (PEM format) |
| `cert_pem` | string | Client certificate (PEM format) for MQTT |
| `key_pem` | string | Client private key (PEM format) for MQTT |
| `broker.host` | string | MQTT broker hostname |
| `broker.port` | integer | MQTT broker TLS port |
| `https_api.base_url` | string | Base URL of the HTTPS player API |
| `https_api.auth` | string | HTTPS auth scheme (`bearer`) |
| `api_token` | string \| null | HTTPS bearer token; present **only on the first fetch** |

### Rate Limiting

This endpoint is rate limited to **30 requests per minute per IP** to prevent brute-force attacks.

### Device Actions

1. Store the certificates and `api_token` securely in flash/EEPROM
2. Connect over MQTT or HTTPS; see [MQTT Connection](mqtt-connection.md) or [HTTPS Connection](https-connection.md)

### The HTTPS device token

`api_token` is the bearer credential for the HTTPS transport. It is returned
**once**, on the first successful credentials fetch (later fetches do not return the token), so
store it persistently like the private key.

If a device loses its token, rotate a fresh one (this revokes the old token):

```
POST /api/player/{player_key}/token/rotate
```

```json
{ "api_token": "mpx_live_<new>", "rotated_at": "2024-01-15T12:00:00Z" }
```

Owners can also use the authenticated [owner token-rotation endpoint](../http-api/player-rpc.md#rotating-and-revoking-tokens), for example if a token may have leaked.

## Polling for Credentials

Before registration completes, credentials return 404. The device should poll:

```
# Pseudocode
while not registered and now() < registration_code_expires_at:
    response = GET /api/player/{player_key}/credentials
    if response.status == 200:
        store_credentials(response.body)
        registered = true
    else if response.status == 404:
        wait(5 seconds)
    else if response.status == 429:
        wait(response.retry_after or 60 seconds)
    else:
        report_error_and_back_off()
```

Recommended polling interval: 5 seconds. Stop when the code expires and ask the owner to restart provisioning; do not poll indefinitely. A 404 can mean either that registration is pending or that the player does not exist.

## Error Handling

### Provision Errors

| Status | Meaning |
|--------|---------|
| 201 | Success |
| 400 | Invalid request body |
| 500 | Server error |

### Registration Errors

| Status | Meaning |
|--------|---------|
| 201 | Success |
| 400 | Max players (128) reached |
| 401 | Not authenticated |
| 404 | Invalid or expired code |

### Credential Errors

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 404 | Not registered or player not found |
| 429 | Rate limited |
| 500 | Certificates not available |

## Certificate Renewal

Client certificates are valid for 1095 days (3 years). Devices can renew over HTTPS when within the default 90-day renewal window, or after the client certificate has expired:

```http
POST https://makapix.club/api/player/renew-cert
Authorization: Bearer {api_token}
```

No request body is needed. The response contains `cert_pem`, `key_pem`, `ca_pem`, and `cert_expires_at`. Save the new bundle securely and reconnect MQTT using it. Keep the HTTPS bearer token even if you normally use MQTT; it enables renewal without the owner pairing the device again.

The endpoint returns 400 if renewal is too early, 401 for an invalid token, and 429 when rate limited (10 requests per day per player and 30 per hour per IP). Use backoff and avoid having every device retry at the same time.

Owners can also open **Manage Players** and select **Renew Certificate** when the expiry warning appears. The **Certs** button downloads the certificate bundle. See the [HTTP player reference](../http-api/player.md) for the corresponding owner endpoints.

## Deregistration

When a user removes a device:

1. TLS certificate is revoked
2. MQTT connection is terminated
3. Player record is deleted
4. Device can no longer connect

Removal also invalidates the device token. If credentials have been revoked, ask the owner to pair the device again. A temporary network disconnection alone should trigger reconnection with backoff, not new provisioning.

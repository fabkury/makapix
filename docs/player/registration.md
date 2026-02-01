# Device Registration

The registration flow links a physical device to a Makapix user account.

## Overview

Registration is a three-step handshake:

1. **Provision** - Device requests credentials from server (no auth required)
2. **Register** - User authenticates on web and enters the code
3. **Credentials** - Device retrieves TLS certificates

```
┌──────────┐                    ┌──────────┐                    ┌──────────┐
│  Device  │                    │  Server  │                    │   User   │
└────┬─────┘                    └────┬─────┘                    └────┬─────┘
     │                               │                               │
     │  POST /player/provision       │                               │
     │──────────────────────────────▶│                               │
     │                               │                               │
     │  {player_key, code, broker}   │                               │
     │◀──────────────────────────────│                               │
     │                               │                               │
     │  Display code "A7B3K9"        │                               │
     │───────────────────────────────────────────────────────────────▶│
     │                               │                               │
     │                               │  POST /player/register        │
     │                               │  (with JWT + code)            │
     │                               │◀──────────────────────────────│
     │                               │                               │
     │                               │  {success}                    │
     │                               │──────────────────────────────▶│
     │                               │                               │
     │  GET /player/{key}/credentials│                               │
     │──────────────────────────────▶│                               │
     │                               │                               │
     │  {ca_pem, cert_pem, key_pem}  │                               │
     │◀──────────────────────────────│                               │
     │                               │                               │
```

## Step 1: Provision

The device initiates registration by requesting a player key.

### Request

```
POST /api/player/provision
Content-Type: application/json
```

```json
{
  "device_model": "p3a-64x64",
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
  "mqtt_broker": {
    "host": "makapix.club",
    "port": 8884
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `player_key` | UUID | Permanent device identifier |
| `registration_code` | string | 6-character alphanumeric code |
| `registration_code_expires_at` | datetime | Code expiry (15 minutes from creation) |
| `mqtt_broker.host` | string | MQTT broker hostname |
| `mqtt_broker.port` | integer | MQTT broker TLS port |

### Device Actions

1. Store `player_key` permanently (survives reboots)
2. Display `registration_code` prominently
3. Optionally show a countdown timer (15 minutes)
4. Begin polling for credentials

## Step 2: User Registration

The user completes registration through the web interface.

This step requires authentication - the user must be logged in to link a device.

### Web Interface Flow

1. User navigates to Settings > Players > Add Device
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
  "device_model": "p3a-64x64",
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

Once registered, the device retrieves its TLS certificates.

### Request

```
GET /api/player/{player_key}/credentials
```

No authentication required - the player_key serves as authentication for this endpoint.

### Response

```json
{
  "ca_pem": "-----BEGIN CERTIFICATE-----\nMIID...\n-----END CERTIFICATE-----\n",
  "cert_pem": "-----BEGIN CERTIFICATE-----\nMIID...\n-----END CERTIFICATE-----\n",
  "key_pem": "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----\n",
  "broker": {
    "host": "makapix.club",
    "port": 8884
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `ca_pem` | string | CA certificate (PEM format) |
| `cert_pem` | string | Client certificate (PEM format) |
| `key_pem` | string | Client private key (PEM format) |
| `broker.host` | string | MQTT broker hostname |
| `broker.port` | integer | MQTT broker TLS port |

### Rate Limiting

This endpoint is rate limited to **20 requests per minute per IP** to prevent brute-force attacks.

### Device Actions

1. Store certificates securely in flash/EEPROM
2. Proceed to MQTT connection

## Polling for Credentials

Before registration completes, credentials return 404. The device should poll:

```
# Pseudocode
while not registered:
    response = GET /api/player/{player_key}/credentials
    if response.status == 200:
        store_credentials(response.body)
        registered = true
    else if response.status == 404:
        wait(5 seconds)
    else if response.status == 429:
        wait(60 seconds)  # Rate limited
```

Recommended polling interval: 5 seconds.

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

Certificates are valid for 365 days. The web interface shows certificate status and allows renewal when within 30 days of expiry.

Users can also download certificates manually from Settings > Players > [Device] > Download Certificates.

## Deregistration

When a user removes a device:

1. TLS certificate is revoked
2. MQTT connection is terminated
3. Player record is deleted
4. Device can no longer connect

The device should detect disconnection and return to the provisioning state.

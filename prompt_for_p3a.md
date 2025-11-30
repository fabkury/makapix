# Integration Guide for p3a Player Device

This document provides complete instructions for integrating the p3a physical player device with the Makapix Club system. Follow these steps in order to enable your device to display pixel art from Makapix Club.

## Overview

The p3a device must:
1. Provision itself with the Makapix Club API to obtain a registration code
2. Display the registration code for the user to enter on makapix.club
3. Poll for TLS certificates after registration completes
4. Connect to the MQTT broker using TLS certificates and username authentication
5. Subscribe to command topics and publish status updates
6. Execute commands to display artwork

---

## 1. Initial Provisioning

### API Endpoint
```
POST https://makapix.club/api/player/provision
Content-Type: application/json
```

### Request Body
```json
{
  "device_model": "p3a",
  "firmware_version": "1.0.0"
}
```

Both fields are optional but recommended for tracking purposes.

### Response (201 Created)
```json
{
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "registration_code": "A3F8X2",
  "registration_code_expires_at": "2025-01-29T12:15:00Z",
  "mqtt_broker": {
    "host": "makapix.club",
    "port": 8883
  }
}
```

### Critical Actions
- **Store `player_key` permanently** in non-volatile memory (EEPROM/flash). This UUID is your device's identity.
- **Display `registration_code`** prominently on the device screen.
- The registration code expires in 15 minutes.

---

## 2. Certificate Retrieval After Registration

After the user enters the registration code on makapix.club, the device must retrieve TLS certificates before connecting to MQTT.

### API Endpoint
```
GET https://makapix.club/api/player/{player_key}/credentials
```

Replace `{player_key}` with the UUID received during provisioning.

### Response (200 OK)
```json
{
  "ca_pem": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----",
  "cert_pem": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----",
  "key_pem": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----",
  "broker": {
    "host": "makapix.club",
    "port": 8883
  }
}
```

### Polling Strategy
- Poll this endpoint every 5-10 seconds after displaying the registration code
- Continue polling until you receive a 200 response (certificates available)
- If you receive 404, registration has not completed yet - keep polling
- Once certificates are received, **store them securely** in non-volatile memory

### Error Handling
- **404 Not Found**: Registration not complete yet - continue polling
- **500 Internal Server Error**: Server issue - retry with exponential backoff
- **Network errors**: Retry with exponential backoff, max 5 minutes

---

## 3. MQTT Connection Setup

### Connection Parameters

| Parameter | Value |
|-----------|-------|
| **Protocol** | MQTT v5 over TLS |
| **Host** | `makapix.club` (or from broker.host in credentials) |
| **Port** | `8883` (TLS) |
| **Username** | `player_key` UUID (e.g., `550e8400-e29b-41d4-a716-446655440000`) |
| **Password** | Empty string `""` |
| **Client ID** | Any unique string (e.g., `p3a-{player_key}`) |
| **Keep Alive** | 60 seconds |
| **TLS** | Enabled with client certificate authentication |

### TLS Configuration

1. **CA Certificate**: Use `ca_pem` from credentials response
   - Verify server certificate against this CA
   - Reject connection if server certificate doesn't match

2. **Client Certificate**: Use `cert_pem` from credentials response
   - Present this certificate during TLS handshake
   - Certificate is valid for 1 year

3. **Client Private Key**: Use `key_pem` from credentials response
   - Keep this secret - never expose it
   - Used to authenticate the client certificate

### Connection Flow
```
1. Load stored player_key, cert_pem, key_pem, ca_pem
2. Configure MQTT client with TLS:
   - Set CA certificate for server verification
   - Set client certificate and private key
   - Set username to player_key
   - Set password to empty string
3. Connect to broker (host:port from credentials)
4. On successful connection, proceed to topic subscription
```

### Connection Errors
- **Certificate errors**: Verify certificates are valid and not expired
- **Authentication errors**: Ensure player_key is correct and registered
- **Network errors**: Check internet connectivity and broker availability

---

## 4. MQTT Topics

All topics use the `player_key` UUID in the path.

### Command Topic (Subscribe)
- **Topic**: `makapix/player/{player_key}/command`
- **QoS**: 1 (at least once delivery)
- **Direction**: Server → Device
- **Purpose**: Receive commands from the owner

**Example**: For `player_key` = `550e8400-e29b-41d4-a716-446655440000`
```
makapix/player/550e8400-e29b-41d4-a716-446655440000/command
```

### Status Topic (Publish)
- **Topic**: `makapix/player/{player_key}/status`
- **QoS**: 1 (at least once delivery)
- **Direction**: Device → Server
- **Purpose**: Report device status

**Example**: For `player_key` = `550e8400-e29b-41d4-a716-446655440000`
```
makapix/player/550e8400-e29b-41d4-a716-446655440000/status
```

### Subscription Flow
```
1. After successful MQTT connection
2. Subscribe to command topic: makapix/player/{player_key}/command
3. Wait for CONNACK with success
4. Immediately publish initial status message
```

---

## 5. Command Messages

### Command Message Format

Commands are JSON objects published to the command topic:

```json
{
  "command_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "command_type": "swap_next",
  "payload": {},
  "timestamp": "2025-01-29T12:00:00+00:00"
}
```

### Command Types

#### 1. `swap_next`
Move to the next artwork in the device's internal playlist.

```json
{
  "command_id": "...",
  "command_type": "swap_next",
  "payload": {},
  "timestamp": "..."
}
```

**Action**: Display the next artwork in rotation.

#### 2. `swap_back`
Move to the previous artwork in the device's internal playlist.

```json
{
  "command_id": "...",
  "command_type": "swap_back",
  "payload": {},
  "timestamp": "..."
}
```

**Action**: Display the previous artwork in rotation.

#### 3. `show_artwork`
Display a specific artwork immediately.

```json
{
  "command_id": "...",
  "command_type": "show_artwork",
  "payload": {
    "post_id": 123,
    "storage_key": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "art_url": "https://makapix.club/api/vault/a1b2c3d4-e5f6-7890-abcd-ef1234567890.png",
    "canvas": "64x64"
  },
  "timestamp": "..."
}
```

**Payload Fields**:
- `post_id`: Database ID of the artwork
- `storage_key`: Storage identifier (UUID)
- `art_url`: Full URL to download the artwork image
- `canvas`: Canvas dimensions (e.g., "64x64", "128x128")

**Action**:
1. Download image from `art_url`
2. Display immediately
3. Optionally add to internal rotation
4. Update `current_post_id` in next status report

---

## 6. Status Messages

### Status Message Format

Publish status updates to the status topic:

```json
{
  "player_key": "550e8400-e29b-41d4-a716-446655440000",
  "status": "online",
  "current_post_id": 123,
  "firmware_version": "1.0.0",
  "timestamp": "2025-01-29T12:00:00+00:00"
}
```

### Status Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `player_key` | UUID | Yes | The device's player_key |
| `status` | String | Yes | `"online"` or `"offline"` |
| `current_post_id` | Integer | No | ID of currently displayed artwork |
| `firmware_version` | String | No | Device firmware version |
| `timestamp` | ISO 8601 | Yes | Current time in UTC |

### When to Publish Status

1. **On connect**: Immediately after MQTT connection (status: "online")
2. **Periodically**: Every 30-60 seconds while online
3. **On state change**: When displayed artwork changes
4. **On disconnect**: Send status with `"status": "offline"` if possible (Last Will)

### Last Will and Testament

Configure MQTT Last Will to automatically publish offline status if connection drops:

```
Will Topic: makapix/player/{player_key}/status
Will Payload: {"player_key": "{player_key}", "status": "offline", "timestamp": "..."}
Will QoS: 1
```

---

## 7. Complete Integration Flow

### Boot Sequence

```
1. Boot device
2. Load stored player_key from non-volatile memory
3. If player_key exists:
   - Load stored certificates (cert_pem, key_pem, ca_pem)
   - Go to MQTT connection (step 4)
4. If player_key does NOT exist:
   - Call POST /api/player/provision
   - Store player_key
   - Display registration_code
   - Poll GET /api/player/{player_key}/credentials every 5-10s
   - When certificates received, store them
   - Go to MQTT connection (step 4)
```

### MQTT Connection Sequence

```
1. Configure MQTT client:
   - TLS with CA cert, client cert, client key
   - Username = player_key
   - Password = ""
   - Client ID = "p3a-{player_key}"
   - Keep alive = 60s
   - Last Will = offline status message

2. Connect to broker (makapix.club:8883)

3. On successful connection:
   - Subscribe to makapix/player/{player_key}/command (QoS 1)
   - Publish initial status: {"status": "online", ...}

4. Enter main loop:
   - Process incoming command messages
   - Every 30-60s: publish status update
   - Handle reconnection if connection drops
```

### Command Processing Loop

```
While connected:
  1. Wait for message on command topic
  2. Parse JSON command
  3. Execute command:
     - swap_next: show next artwork
     - swap_back: show previous artwork
     - show_artwork: download and display specific artwork
  4. Update current_post_id if artwork changed
  5. Publish status update
  6. Repeat
```

---

## 8. Error Handling

### Network Errors
- Implement exponential backoff for retries
- Maximum retry delay: 5 minutes
- Log errors for debugging

### Certificate Errors
- If certificates expire, device must re-provision
- Check certificate expiry before connecting
- Renew certificates if within 30 days of expiry (via website)

### MQTT Connection Errors
- Reconnect with exponential backoff
- Maintain subscription on reconnect
- Republish status after reconnection

### Command Processing Errors
- Log errors but don't crash
- Continue listening for next command
- Report errors in status message if possible

---

## 9. Security Considerations

1. **Store certificates securely**: Use encrypted storage if available
2. **Never expose private key**: Keep `key_pem` secret
3. **Verify server certificate**: Always verify broker certificate against CA
4. **Use TLS**: Never connect without TLS encryption
5. **Validate commands**: Verify command structure before executing
6. **Sanitize URLs**: Validate art_url before downloading

---

## 10. Testing Checklist

- [ ] Device provisions successfully and displays registration code
- [ ] Device polls for certificates after registration
- [ ] Certificates are stored correctly
- [ ] MQTT connection succeeds with TLS
- [ ] Device subscribes to command topic
- [ ] Device publishes status messages
- [ ] Device receives and processes swap_next command
- [ ] Device receives and processes swap_back command
- [ ] Device receives and processes show_artwork command
- [ ] Device downloads and displays artwork from art_url
- [ ] Device handles reconnection gracefully
- [ ] Last Will publishes offline status on disconnect

---

## API Base URL

Production: `https://makapix.club`
Development: `https://dev.makapix.club` (if available)

All API endpoints are under `/api/` prefix.

---

## Support

For issues or questions:
- Check logs for error messages
- Verify network connectivity
- Ensure certificates are valid and not expired
- Confirm player_key matches registered device


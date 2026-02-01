# MQTT API Reference

Real-time messaging protocol for player devices and notifications.

## Broker Connection

| Setting | Production | Development |
|---------|------------|-------------|
| Host | `makapix.club` | `development.makapix.club` |
| TLS Port | 8884 | 8884 |
| WebSocket | wss://makapix.club:8884/mqtt | wss://development.makapix.club:8884/mqtt |
| Protocol | MQTT 5.0 | MQTT 5.0 |

## Authentication Methods

### Player Devices (mTLS)

Player devices authenticate using mutual TLS certificates obtained during registration:

```
TLS Client Certificate: CN={player_key}
Username: {player_key}
Password: (empty)
```

Both the certificate and username must match. See [Registration](../player/registration.md) for certificate provisioning.

### Web Clients (Username/Password)

Browser clients connect via WebSocket with username/password:

```
Username: webclient
Password: (configured in environment)
```

Web clients have read-only access to notification topics.

### Internal Services (Username/Password)

Backend services connect without TLS on the internal network:

```
Host: mqtt (Docker service name)
Port: 1883
Username: svc_backend
Password: (configured in environment)
```

## Topic Structure

All Makapix topics follow the pattern:

```
makapix/{domain}/{identifier}/{action}[/{suffix}]
```

### Player Topics

| Topic Pattern | Direction | Description |
|---------------|-----------|-------------|
| `makapix/player/{player_key}/request/{request_id}` | Device -> Server | Player requests |
| `makapix/player/{player_key}/response/{request_id}` | Server -> Device | Request responses |
| `makapix/player/{player_key}/status` | Device -> Server | Status updates |
| `makapix/player/{player_key}/view` | Device -> Server | View events |
| `makapix/player/{player_key}/view/ack` | Server -> Device | View acknowledgments |
| `makapix/player/{player_key}/command` | Server -> Device | Commands from web |

### Notification Topics

| Topic | Description |
|-------|-------------|
| `makapix/posts/new` | New post notifications |
| `makapix/posts/promoted` | Promoted post notifications |

## QoS Levels

| Topic Type | QoS | Rationale |
|------------|-----|-----------|
| Requests | 1 | Ensure delivery |
| Responses | 1 | Ensure delivery |
| Commands | 1 | Ensure delivery |
| Status | 1 | Track connection state |
| View events | 1 | Server deduplicates |
| Notifications | 0 | Best effort |

QoS 1 provides at-least-once delivery. The server handles duplicate detection for view events.

## Message Format

All messages use JSON payloads:

```json
{
  "field": "value",
  "nested": {
    "object": true
  },
  "array": [1, 2, 3]
}
```

### Common Fields

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Client-generated UUID for correlation |
| `request_type` | string | Request type identifier |
| `player_key` | string | Player's UUID |
| `success` | boolean | Whether operation succeeded |
| `error` | string | Error message (on failure) |
| `error_code` | string | Machine-readable error code |

## Request-Response Pattern

Player requests follow a consistent pattern:

1. Generate unique `request_id`
2. Publish to `makapix/player/{player_key}/request/{request_id}`
3. Subscribe to `makapix/player/{player_key}/response/{request_id}` (or wildcard `+`)
4. Wait for response with matching `request_id`

```
Device                              Server
  |                                   |
  |-- Publish request/{req-123} ----->|
  |                                   |
  |<-- Publish response/{req-123} ----|
  |                                   |
```

### Timeout Handling

Recommended timeout: 30 seconds

```python
response = wait_for_response(request_id, timeout=30)
if response is None:
    # Request timed out, retry or fail
```

## Payload Size Limits

| Direction | Limit |
|-----------|-------|
| Device -> Server | 256 KB |
| Server -> Device | 128 KB |

The server automatically trims query results to fit within the 128 KB limit.

## Rate Limits

| Resource | Limit |
|----------|-------|
| Commands per player | 300/minute |
| Commands per user | 1,000/minute |
| View events | 1 per 5 seconds per player |
| Connection attempts | 10/minute/IP |

## Retained Messages

| Topic | Retained |
|-------|----------|
| Status | No |
| Commands | No |
| Notifications | No |
| Responses | No |

No messages are retained. Devices should query state on connect.

## Keep-Alive

Recommended keep-alive: 60 seconds

The broker sends PINGREQ/PINGRESP to detect dead connections. Clients that don't respond within 1.5x keep-alive are disconnected.

## Clean Session

Use `clean_session=true` (MQTT 3.1.1) or `clean_start=true` (MQTT 5.0) for player devices. Queued messages during disconnection are not useful for real-time displays.

## Error Handling

### Connection Errors

| Reason Code | Description | Action |
|-------------|-------------|--------|
| 0 | Success | Proceed |
| 1 | Protocol error | Check MQTT version |
| 2 | Client ID rejected | Verify player_key format |
| 3 | Server unavailable | Retry with backoff |
| 4 | Bad credentials | Re-fetch certificates |
| 5 | Not authorized | Check certificate validity |

### Request Errors

Errors are returned in the response:

```json
{
  "request_id": "req-001",
  "success": false,
  "error": "Post not found",
  "error_code": "not_found"
}
```

See [Error Codes](../reference/error-codes.md) for complete list.

## Topic Reference

### Player Requests

- [Player Requests](player-requests.md) - Query posts, get artwork, submit reactions

### Player Status

- [Player Status](player-status.md) - Connection and playback reporting

### Commands

- [Commands](commands.md) - Server-to-player control messages

## Example: Complete Session

```python
import json
import uuid
import paho.mqtt.client as mqtt

player_key = "550e8400-e29b-41d4-a716-446655440000"

def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        # Subscribe to responses and commands
        client.subscribe(f"makapix/player/{player_key}/response/+")
        client.subscribe(f"makapix/player/{player_key}/command")

        # Report online status
        client.publish(
            f"makapix/player/{player_key}/status",
            json.dumps({"player_key": player_key, "status": "online"})
        )

        # Query artwork
        request_id = str(uuid.uuid4())
        client.publish(
            f"makapix/player/{player_key}/request/{request_id}",
            json.dumps({
                "request_id": request_id,
                "request_type": "query_posts",
                "player_key": player_key,
                "channel": "all",
                "limit": 10
            })
        )

def on_message(client, userdata, msg):
    payload = json.loads(msg.payload)

    if "/response/" in msg.topic:
        if payload.get("success"):
            posts = payload.get("posts", [])
            print(f"Received {len(posts)} posts")
        else:
            print(f"Error: {payload.get('error')}")

    elif "/command" in msg.topic:
        command_type = payload.get("command_type")
        print(f"Received command: {command_type}")

client = mqtt.Client(client_id=player_key, protocol=mqtt.MQTTv5)
client.tls_set(ca_certs="ca.pem", certfile="cert.pem", keyfile="key.pem")
client.username_pw_set(player_key, "")
client.on_connect = on_connect
client.on_message = on_message

client.connect("makapix.club", 8884)
client.loop_forever()
```

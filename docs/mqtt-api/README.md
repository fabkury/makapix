# MQTT API Reference

Real-time messaging for player devices, including remote commands and live presence. For a first implementation, start with the [Player Device Guide](../player/README.md) and its [transport comparison](../player/README.md#choosing-a-transport).

Website and app notifications use HTTP and Server-Sent Events (SSE), not the MQTT broker. See [Notifications](../http-api/notifications.md).

## Broker Connection

| Setting | Production | Development |
|---------|------------|-------------|
| Host | `makapix.club` | `development.makapix.club` |
| TLS Port | 8883 | 8884 |
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

| Topic Pattern The server caps player response payloads at **128 KiB** (131,072 bytes) and trims artwork query results to fit. Process the returned page length rather than assuming it equals your requested `limit`; follow the returned cursor for more results.

Keep request payloads small and use the documented operation limits. Broker packet limits may depend on deployment configuration.

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

client.connect("makapix.club", 8883)
client.loop_forever()
```

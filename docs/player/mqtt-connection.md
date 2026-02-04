# MQTT Connection

Connect your player device to the Makapix MQTT broker.

## Broker Details

| Setting | Value |
|---------|-------|
| Host | `makapix.club` (production) or `development.makapix.club` (dev) |
| Port | `8883` (production) or `8884` (dev) — mTLS |
| Protocol | MQTT 5.0 |
| Transport | TCP with mutual TLS |
| WebSocket | `wss://makapix.club/mqtt` (production) or `wss://development.makapix.club/mqtt` (dev) — via reverse proxy |

## Authentication

Players authenticate using mutual TLS (mTLS):

1. **Client Certificate** - Issued during registration, CN matches player_key
2. **Username** - Set to `player_key` (UUID string)
3. **Password** - Empty (certificate provides authentication)

Both the certificate and username are required. The broker validates that the certificate's Common Name matches the provided username.

## TLS Configuration

Use the certificates from the credentials endpoint:

```python
# Example using paho-mqtt (Python)
import ssl
import paho.mqtt.client as mqtt

client = mqtt.Client(
    client_id=player_key,
    protocol=mqtt.MQTTv5
)

# Configure TLS with mTLS
client.tls_set(
    ca_certs="/path/to/ca.pem",
    certfile="/path/to/cert.pem",
    keyfile="/path/to/key.pem",
    cert_reqs=ssl.CERT_REQUIRED,
    tls_version=ssl.PROTOCOL_TLS
)

# Set username (password can be empty)
client.username_pw_set(username=player_key, password="")

# Connect
client.connect("makapix.club", 8883)
```

## Topic Structure

All player topics follow the pattern:

```
makapix/player/{player_key}/{topic_type}[/{suffix}]
```

### Topics to Subscribe

| Topic | Purpose |
|-------|---------|
| `makapix/player/{player_key}/command` | Receive commands from server/web |
| `makapix/player/{player_key}/response/+` | Receive responses to requests |

### Topics to Publish

| Topic | Purpose |
|-------|---------|
| `makapix/player/{player_key}/request/{request_id}` | Send requests to server |
| `makapix/player/{player_key}/status` | Report connection/playback status |
| `makapix/player/{player_key}/view` | Report artwork view events |

## Connection Flow

```python
def on_connect(client, userdata, flags, rc, properties):
    if rc == 0:
        print("Connected successfully")
        # Subscribe to receive commands
        client.subscribe(f"makapix/player/{player_key}/command", qos=1)
        # Subscribe to receive request responses
        client.subscribe(f"makapix/player/{player_key}/response/+", qos=1)
        # Publish online status
        client.publish(
            f"makapix/player/{player_key}/status",
            json.dumps({
                "player_key": player_key,
                "status": "online",
                "firmware_version": "2.1.0"
            }),
            qos=1
        )
    else:
        print(f"Connection failed with code {rc}")

client.on_connect = on_connect
client.connect("makapix.club", 8883)
client.loop_forever()
```

## QoS Levels

| Topic Type | Recommended QoS |
|------------|-----------------|
| Commands | QoS 1 (at least once) |
| Requests | QoS 1 |
| Responses | QoS 1 |
| Status | QoS 1 |
| View events | QoS 1 |

QoS 1 ensures message delivery while avoiding the complexity of QoS 2. The server handles duplicate detection for view events.

## Keep-Alive

Set keep-alive to 60 seconds:

```python
client.connect("makapix.club", 8883, keepalive=60)
```

The broker expects regular PINGREQ packets. If no message is sent within the keep-alive interval, the broker may disconnect the client.

## Reconnection

Implement exponential backoff for reconnection:

```python
import time

reconnect_delay = 1  # Initial delay in seconds
max_delay = 300      # Maximum delay (5 minutes)

def on_disconnect(client, userdata, flags, rc, properties):
    global reconnect_delay
    if rc != 0:
        print(f"Unexpected disconnect, reconnecting in {reconnect_delay}s...")
        time.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, max_delay)
        client.reconnect()

def on_connect(client, userdata, flags, rc, properties):
    global reconnect_delay
    if rc == 0:
        reconnect_delay = 1  # Reset on successful connection
        # ... subscribe to topics
```

## Connection States

Your device should track and display connection state:

| State | Description |
|-------|-------------|
| `disconnected` | No network or broker connection |
| `connecting` | Attempting TLS handshake |
| `connected` | Successfully connected, subscribed |
| `reconnecting` | Connection lost, attempting reconnect |

## Error Codes

Common MQTT connection errors:

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Proceed with subscriptions |
| 1 | Protocol version | Ensure MQTT 5.0 |
| 2 | Client ID rejected | Check player_key format |
| 3 | Server unavailable | Retry with backoff |
| 4 | Bad credentials | Re-fetch certificates |
| 5 | Not authorized | Check certificate validity |

## Certificate Expiry

Certificates are valid for 365 days. Your device should:

1. Track certificate expiry date
2. Warn user when within 30 days of expiry
3. Support certificate refresh via web interface

After certificate renewal, the device must fetch new credentials and reconnect.

## ESP32 Example

```cpp
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

WiFiClientSecure espClient;
PubSubClient client(espClient);

void setupMQTT() {
    espClient.setCACert(ca_pem);
    espClient.setCertificate(cert_pem);
    espClient.setPrivateKey(key_pem);

    client.setServer("makapix.club", 8883);
    client.setCallback(messageCallback);
}

void connectMQTT() {
    while (!client.connected()) {
        if (client.connect(player_key, player_key, "")) {
            // Subscribe to topics
            client.subscribe(String("makapix/player/" + player_key + "/command").c_str());
            client.subscribe(String("makapix/player/" + player_key + "/response/+").c_str());

            // Publish online status
            String statusTopic = "makapix/player/" + player_key + "/status";
            String statusPayload = "{\"player_key\":\"" + player_key + "\",\"status\":\"online\"}";
            client.publish(statusTopic.c_str(), statusPayload.c_str());
        } else {
            delay(5000);  // Retry after 5 seconds
        }
    }
}
```

## Debugging

Enable MQTT logging to troubleshoot connection issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

client.enable_logger()
```

Common issues:

1. **TLS handshake fails** - Check certificate format, ensure newlines preserved
2. **Connection refused** - Verify hostname and port
3. **Not authorized** - Certificate may be revoked or expired
4. **Timeout** - Check firewall allows outbound port (8883 production, 8884 dev)

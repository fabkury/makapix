# MQTT Denial-of-Service Vulnerabilities

This document details the denial-of-service vulnerabilities identified in the Makapix Club MQTT architecture.

---

## Architecture Overview

Makapix Club uses Mosquitto MQTT broker with three listeners:

| Port | Protocol | Purpose | Authentication |
|------|----------|---------|----------------|
| 1883 | TCP | Internal API server | Password (docker network) |
| 8883 | TLS/mTLS | Physical player devices | Client certificates |
| 9001 | WebSocket | Web browser clients | Password (shared) |

**Configuration file:** `mqtt/config/mosquitto.conf`

---

## Vulnerability 1: WebSocket Connection Flooding

**Severity:** HIGH  
**CVSS Base Score:** 7.5 (High)  
**Location:** `mqtt/config/mosquitto.conf:25-30`

### Description

The WebSocket listener on port 9001 accepts connections with shared credentials that are hardcoded in the frontend source code:

```typescript
// web/src/lib/mqtt-client.ts:82-84
username: "webclient",
password: "webclient",
```

Anyone with access to the source code (or who inspects network traffic) can use these credentials to open unlimited connections.

### Current Configuration

```conf
# mqtt/config/mosquitto.conf:25-30
listener 9001 0.0.0.0
protocol websockets
# WebSocket doesn't use client certs, so we'll use password auth
# Note: This is less secure but necessary for browser compatibility
```

### Missing Controls

- No `max_connections` directive
- No per-IP connection limits
- No connection rate limiting
- Credentials are publicly known

### Impact

- Complete service unavailability
- Memory exhaustion on VPS
- File descriptor exhaustion
- Affects all legitimate users

### Proof of Concept

See [ATTACK_VECTORS.md](./ATTACK_VECTORS.md#websocket-connection-flood) for attack details.

---

## Vulnerability 2: No Message Queue Limits

**Severity:** MEDIUM  
**Location:** `mqtt/config/mosquitto.conf` (missing configuration)

### Description

Mosquitto defaults allow unlimited message queuing for disconnected clients using QoS 1 or 2. An attacker can:

1. Connect many clients subscribed to high-volume topics
2. Disconnect all clients
3. Trigger message publishing to those topics
4. Messages queue in broker memory indefinitely

### Missing Configuration

The following settings are not present in the configuration:

```conf
# NOT CONFIGURED - should be added
max_queued_messages 1000
max_inflight_messages 20
max_packet_size 65536
```

### Impact

- Gradual memory exhaustion
- OOM killer terminates broker
- Service restart required

---

## Vulnerability 3: Internal Port Exposure

**Severity:** MEDIUM  
**Location:** `deploy/stack/docker-compose.yml:82-84`

### Description

Port 1883 (internal listener) is exposed to the host:

```yaml
ports:
  - "1883:1883"   # EXPOSED - should be removed
  - "8883:8883"
```

This listener is intended for internal docker network communication only and has no TLS protection.

### Risk Factors

- Relies entirely on VPS firewall for protection
- If firewall misconfigured, unauthenticated access possible
- Password file provides some protection, but reduces defense-in-depth

### Impact

- Direct broker access if firewall fails
- Bypass of TLS encryption
- Potential for unauthorized message publishing

---

## Vulnerability 4: Subscription Amplification

**Severity:** LOW  
**Location:** `mqtt/config/acls`

### Description

The ACL configuration allows web clients to subscribe to wildcard topics:

```conf
# mqtt/config/acls:33-37
user webclient
topic read makapix/post/new/user/#
topic read makapix/post/new/category/#
topic read makapix/social-notifications/#
```

While wildcards are necessary for functionality, they can be abused:

1. Attacker subscribes to `makapix/social-notifications/#` (all users)
2. Receives notifications for ALL users (privacy issue)
3. Creates broker overhead processing subscriptions

### Note on ACL Syntax

The final line in the ACL file may be ambiguous:

```conf
# Default: deny all (this should be last)
topic read #
```

This line without a `user` directive may not function as intended. Mosquitto ACL processing should be verified.

---

## Vulnerability 5: TLS Handshake CPU Exhaustion

**Severity:** LOW  
**Location:** `mqtt/config/mosquitto.conf:13-23`

### Description

The mTLS listener (port 8883) requires TLS handshakes for every connection. While mTLS provides strong authentication, the handshake process consumes CPU resources.

### Attack Vector

An attacker could:
1. Initiate many TLS connections without completing handshake
2. Complete handshakes with invalid certificates (fails after CPU work)
3. Repeatedly connect/disconnect with a valid certificate

### Mitigating Factors

- Requires valid certificate for successful connection
- Certificate revocation (CRL) prevents compromised certs
- mTLS overhead deters casual attacks

### Impact

- CPU exhaustion on VPS
- Slower legitimate connections
- Limited by attacker's resources

---

## Vulnerability 6: No Connection Monitoring

**Severity:** MEDIUM (operational)  
**Location:** N/A (missing capability)

### Description

There is no monitoring or alerting for:
- Total active connections
- Connection rate per IP
- Failed authentication attempts
- Unusual subscription patterns

### Impact

- Attacks may go undetected
- No forensic data for incident response
- Cannot identify attack sources

---

## Summary Table

| ID | Vulnerability | Severity | Exploitability | Fix Complexity |
|----|--------------|----------|----------------|----------------|
| V1 | WebSocket connection flooding | HIGH | Trivial | Medium |
| V2 | No message queue limits | MEDIUM | Easy | Low (config) |
| V3 | Internal port exposure | MEDIUM | Requires network | Low (config) |
| V4 | Subscription amplification | LOW | Easy | Medium |
| V5 | TLS handshake CPU | LOW | Difficult | N/A |
| V6 | No connection monitoring | MEDIUM | N/A | Medium |

---

## References

- [Mosquitto Configuration Documentation](https://mosquitto.org/man/mosquitto-conf-5.html)
- [MQTT Security Fundamentals](https://www.hivemq.com/mqtt-security-fundamentals/)
- [OWASP IoT Attack Surface](https://owasp.org/www-project-internet-of-things/)

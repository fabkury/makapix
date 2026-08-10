# MQTT Architecture and Configuration

## Overview

Makapix Club uses MQTT for real-time communication between the server and connected clients. The system supports physical player devices (ESP32-P4, microcontrollers), web browsers, and the internal API server.

Capabilities:

- **Bidirectional player communication**: Players query content and submit interactions; the server sends commands and notifications.
- **Real-time notifications**: New post alerts, category promotions, social notifications (reactions, comments, follows).
- **Request/response pattern**: Asynchronous request-response with correlation IDs for player queries.
- **Fire-and-forget view events**: Lightweight view tracking with optional acknowledgment.
- **Status tracking**: Online/offline status, current artwork display, heartbeats.

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   Client Devices                         │
│  - Physical Players (ESP32-P4, etc.) ── mTLS :8883      │
└─────────────────────────┬────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────┐
│              Mosquitto MQTT Broker                        │
│  Listener 1883: Internal (password auth, Docker network) │
│  Listener 8883: mTLS (physical players, CRL-checked)     │
└──────────┬──────────────┬──────────────┬─────────────────┘
           │              │              │
  ┌────────▼────────┐ ┌──▼───────────┐ ┌▼────────────────┐
  │ Request Sub     │ │ Status Sub   │ │ View Sub         │
  │ player_requests │ │ player_status│ │ player_views     │
  └────────┬────────┘ └──┬───────────┘ └┬────────────────┘
           └──────────────┼──────────────┘
                          ▼
               ┌────────────────────┐
               │  FastAPI Server    │
               │  + Celery Worker   │
               └──────────┬─────────┘
                          ▼
               ┌────────────────────┐
               │  PostgreSQL + Redis│
               └────────────────────┘
```

## Connection Methods

### 1. mTLS (Port 8883) -- Physical Players

Mutual TLS authentication using client certificates issued by the Makapix CA. The certificate's Common Name (CN) is the player's `player_key` UUID, which becomes the MQTT username via `use_identity_as_username`.

| Setting | Value |
|---------|-------|
| Host | `makapix.club` (prod) or via dev hostname |
| Port | 8883 (container); dev exposes as **8884** |
| Protocol | MQTT v5 |
| TLS | Required, TLS 1.2+ |
| Client certificate | Required (CN = `player_key` UUID) |
| CRL checking | Enabled (`crl.pem`) |

Certificates required on the device:
- `ca.crt` -- Makapix CA certificate
- `client.crt` -- Client certificate (CN = player_key)
- `client.key` -- Client private key

Certificate validity is 365 days. Renewal is available within 30 days of expiry via REST API.

### 2. Internal Password Auth (Port 1883) -- API Server

Used by the backend API server and Celery workers within the Docker network. Not exposed publicly.

| Setting | Value |
|---------|-------|
| Host | `mqtt` (Docker service name) |
| Port | 1883 (container); dev exposes as **1884** |
| Protocol | MQTT v5 |
| TLS | None (Docker network isolation) |
| Username | `svc_backend` |
| Password | Set via `MQTT_PASSWORD` env var |

> There is no browser connection method. The former WebSocket listener
> (9001, shared `webclient` account, Caddy `/mqtt` route) was removed 2026-08:
> browsers receive social notifications over the authenticated SSE stream
> (`docs/http-api/notifications.md`); MQTT is the device plane only
> (`docs/notification-architecture/`).

## Authentication

### Player Authentication Flow

Physical players use a provisioning and registration process:

1. **Provision** -- Device calls `POST /player/provision` with device model and firmware version. Receives `player_key` (UUID) and a 6-character `registration_code` (expires in 15 minutes).
2. **Register** -- Owner calls `POST /player/register` with the registration code and a display name. Binds the player to their account.
3. **Download certificates** -- Device calls `GET /player/{player_key}/credentials` to obtain CA cert, client cert, and private key.
4. **MQTT connect** -- Device connects via mTLS on port 8883 using the downloaded certificates.

### Backend Authentication

The API server connects internally on port 1883 as `svc_backend` with password auth. It has full read/write access to all `makapix/` topics.

## Topic Hierarchy

All topics use the prefix `makapix/`.

```
makapix/
├── player/
│   └── {player_key}/
│       ├── request/{request_id}   # Player → Server (request/response)
│       ├── response/{request_id}  # Server → Player (request/response)
│       ├── command                # Server → Player (remote control)
│       ├── status                 # Player → Server (heartbeat/state)
│       ├── view                   # Player → Server (fire-and-forget)
│       └── view/ack              # Server → Player (optional ack)
```

(The former `makapix/post/new/*` and `makapix/social-notifications/*` topics
were removed 2026-08 — social notifications are HTTP-only.)

### Topic Details

| Topic Pattern | Direction | QoS | Retained | Purpose |
|---------------|-----------|-----|----------|---------|
| `makapix/player/{key}/request/{id}` | Player → Server | 1 | No | Player queries and actions |
| `makapix/player/{key}/response/{id}` | Server → Player | 1 | No | Responses correlated by request_id |
| `makapix/player/{key}/command` | Server → Player | 1 | No | Remote control commands |
| `makapix/player/{key}/status` | Player → Server | 1 | No | Heartbeat and state updates |
| `makapix/player/{key}/view` | Player → Server | 1 | No | Fire-and-forget view events |
| `makapix/player/{key}/view/ack` | Server → Player | 1 | No | Optional view acknowledgment |

Server subscribes to wildcard patterns:
- `makapix/player/+/request/+` (request subscriber)
- `makapix/player/+/status` (status subscriber)
- `makapix/player/+/view` (view subscriber)

## Broker Configuration

### Mosquitto Listeners

Defined in `mqtt/config/mosquitto.conf`:

```
persistence false
allow_anonymous false
acl_file /mosquitto/config/acls
password_file /mosquitto/config/passwords

listener 1883 0.0.0.0                    # Internal (Docker network)

listener 8883 0.0.0.0                    # mTLS (players)
cafile /mosquitto/certs/ca.crt
certfile /mosquitto/certs/server.crt
keyfile /mosquitto/certs/server.key
require_certificate true
use_identity_as_username true
tls_version tlsv1.2
crlfile /mosquitto/certs/crl.pem
```

### ACL Rules

Defined in `mqtt/config/acls`. Two principal types:

**`svc_backend`** (API server) -- full read/write:

| Access | Topic |
|--------|-------|
| write | `makapix/player/+/command` |
| read | `makapix/player/+/status` |
| read | `makapix/player/+/request/+` |
| write | `makapix/player/+/response/+` |
| read | `makapix/player/+/view` |
| write | `makapix/player/+/view/ack` |
| read | `$SYS/#` |

**Registered players** (pattern `%u` = player_key from cert CN):

| Access | Topic |
|--------|-------|
| read | `makapix/player/%u/command` |
| write | `makapix/player/%u/status` |
| write | `makapix/player/%u/request/+` |
| read | `makapix/player/%u/response/#` |
| write | `makapix/player/%u/view` |
| read | `makapix/player/%u/view/ack` |

### Password Management

Passwords are generated at container startup by `mqtt/config/scripts/gen-passwd.sh`:

| Username | Source Env Var |
|----------|---------------|
| `svc_backend` | `BACKEND_PASSWORD` (from `MQTT_PASSWORD`) |
| `player_client` | `PLAYER_PASSWORD` |

### Certificate Management

- CA cert/key: `/certs/ca.crt`, `/certs/ca.key` (mounted into API container)
- CRL: `/certs/crl.pem` (auto-renewed if expiring within 7 days)
- Client certs: Generated per player, CN = `player_key` UUID, valid 365 days
- Server cert SANs: `makapix.club`, `www.makapix.club`, `mqtt`, `localhost`, `127.0.0.1`
- Cert generation at startup: `mqtt/config/scripts/gen-certs.sh`

## Security

### Transport Security

- **mTLS (port 8883)**: Full mutual TLS with CRL checking. Certificate CN becomes the MQTT username.
- **Internal (port 1883)**: No encryption; relies on Docker network isolation. Not exposed to the host in production.

### Authorization

Players inherit permissions from their owner's user account:

- View access respects post visibility settings and monitored hashtag preferences.
- Reaction limit: Max 5 reactions per user per post.
- Owner views are excluded from tracking (no self-views).

### Input Validation

- All MQTT payloads validated with Pydantic schemas on the server side.
- Parameterized SQL queries for all database operations.
- Emoji validation: 1-20 characters.

## Rate Limiting

### Player Commands (via REST API)

| Scope | Limit | Window |
|-------|-------|--------|
| Per player | 300 commands | 60 seconds |
| Per user (all players) | 1000 commands | 60 seconds |

### Player View Events (via MQTT)

| Scope | Limit | Window |
|-------|-------|--------|
| Per player | 1 view | 5 seconds |

Duplicate view events (same player + post_id + timestamp) are discarded.

### Social Notifications

| Scope | Limit | Window |
|-------|-------|--------|
| Per actor-recipient pair | 720 | 1 hour |

### Credential Requests

| Scope | Limit | Window |
|-------|-------|--------|
| Per IP | 20 requests | 60 seconds |

## MQTT Protocol Version

Makapix Club uses **MQTT v5**. All server-side clients (publisher, subscribers) specify `MQTTv5` protocol. Physical player clients should also use MQTT v5.

## QoS

All topics use **QoS 1** (at-least-once delivery). No topics currently use QoS 0 or QoS 2.

## Message Retention

No topics use retained messages. The database is the source of truth for all persistent state (player status, post data, etc.).

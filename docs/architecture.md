# Architecture

System architecture and component overview.

## Overview

Makapix Club is a monolithic application designed to run on a single VPS. All services are containerized with Docker Compose and communicate over internal networks.

```
                                    Internet
                                        │
                                        ▼
                                ┌───────────────┐
                                │     Caddy     │
                                │ (reverse proxy│
                                │  + auto-TLS)  │
                                └───────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
              ▼                         ▼                         ▼
       ┌───────────┐             ┌───────────┐             ┌───────────┐
       │    Web    │             │    API    │             │   MQTT    │
       │ (Next.js) │             │ (FastAPI) │             │(Mosquitto)│
       └───────────┘             └───────────┘             └───────────┘
                                        │                         │
                                        │                         │
                    ┌───────────────────┼───────────────────┐     │
                    │                   │                   │     │
                    ▼                   ▼                   ▼     │
             ┌───────────┐       ┌───────────┐       ┌───────────┐│
             │    DB     │       │   Cache   │       │  Worker   ││
             │(PostgreSQL│       │  (Redis)  │       │ (Celery)  ││
             └───────────┘       └───────────┘       └───────────┘│
                                                                   │
                                                                   ▼
                                                          ┌───────────────┐
                                                          │ Physical      │
                                                          │ Players       │
                                                          │ (ESP32, Pi)   │
                                                          └───────────────┘
```

## Services

### Caddy (Reverse Proxy)

Auto-discovers containers via Docker labels and handles:

- TLS termination (automatic Let's Encrypt certificates)
- Request routing by domain
- Static file serving for the vault

| Port | Protocol |
|------|----------|
| 80 | HTTP (redirects to HTTPS) |
| 443 | HTTPS |

### Web (Next.js)

React-based frontend serving the user interface.

| Aspect | Detail |
|--------|--------|
| Framework | Next.js 14 |
| Language | TypeScript |
| Port | 3000 (internal) |

### API (FastAPI)

Python backend handling all business logic.

| Aspect | Detail |
|--------|--------|
| Framework | FastAPI |
| Language | Python 3.12+ |
| ORM | SQLAlchemy 2.0+ |
| Port | 8000 (internal) |

Key modules:

| Module | Purpose |
|--------|---------|
| `routers/` | 26 API endpoint modules |
| `services/` | Business logic services |
| `mqtt/` | Player communication |
| `models.py` | Database models |
| `schemas.py` | Pydantic validation |
| `vault.py` | Image storage |
| `auth.py` | JWT + OAuth |

### Worker (Celery)

Background task processor for async operations.

| Aspect | Detail |
|--------|--------|
| Framework | Celery |
| Broker | Redis |
| Port | None (internal) |

Tasks:

- Email notifications
- Image processing
- Periodic cleanup

### DB (PostgreSQL)

Primary data store for all application data.

| Aspect | Detail |
|--------|--------|
| Version | PostgreSQL 17 |
| Port | 5432 (internal) |

### Cache (Redis)

In-memory cache and Celery broker.

| Aspect | Detail |
|--------|--------|
| Version | Redis 7 |
| Memory | 256 MB (LRU eviction) |
| Port | 6379 (internal) |

Uses:

- Database query caching
- Rate limiting state
- Celery task queue

### MQTT (Mosquitto)

Message broker for real-time player communication.

| Aspect | Detail |
|--------|--------|
| Version | Mosquitto |
| Protocol | MQTT 5.0 |
| Auth | mTLS (players), password (services) |

| Port | Protocol | Use |
|------|----------|-----|
| 1883 | MQTT | Internal services |
| 8884 | MQTTS | External players (TLS) |

### Vault

Hash-based file storage for artwork images.

| Aspect | Detail |
|--------|--------|
| Path | `/mnt/vault-dev` (dev), `/mnt/vault-1` (prod) |
| Structure | `/{h1}/{h2}/{h3}/{artwork_id}.{ext}` |

Hash sharding uses first 6 characters of SHA-256(artwork_id) split into 3 directories.

## Networks

```
┌─────────────────────────────────────────────────────────────┐
│                        caddy_net                            │
│  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐     │
│  │Caddy│  │ Web │  │ API │  │MQTT │  │Vault│  │Redis│     │
│  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        internal                             │
│        ┌─────┐  ┌─────┐  ┌─────┐  ┌──────┐                 │
│        │ DB  │  │Cache│  │ API │  │Worker│                 │
│        └─────┘  └─────┘  └─────┘  └──────┘                 │
└─────────────────────────────────────────────────────────────┘
```

| Network | Purpose |
|---------|---------|
| `caddy_net` | External services reachable by Caddy |
| `internal` | Backend services (DB, cache) |

## Data Flow

### Web Request

```
User → Caddy → Web (SSR) → API → DB
                              → Cache
```

### API Request

```
Client → Caddy → API → DB
                    → Cache
                    → MQTT (for player commands)
```

### Player Connection

```
Player → Caddy (TLS) → MQTT → API (via internal MQTT)
                           → DB
```

### Background Task

```
API → Redis (queue) → Worker → DB
                            → SMTP (email)
```

## Authentication

### Web Users

JWT-based authentication with refresh tokens stored in HTTP-only cookies.

```
Login → API validates credentials
      → Returns access token (15 min) + refresh token (7 days)
      → Access token in response body
      → Refresh token in HTTP-only cookie
```

### Players

mTLS certificate-based authentication.

```
Provision → Device gets player_key + registration code
Register  → User enters code, links device to account
Certs     → Device fetches CA, cert, key
Connect   → Device connects to MQTT with client certificate
```

## Storage

### Database Schema

Key tables:

| Table | Purpose |
|-------|---------|
| `user` | User accounts |
| `post` | Artwork and playlists |
| `reaction` | Emoji reactions |
| `comment` | Comments on posts |
| `follow` | User follows |
| `player` | Physical devices |
| `playlist` | Curated collections |
| `playset` | Device configurations |

### Vault Structure

```
/mnt/vault/
├── a1/
│   └── b2/
│       └── c3/
│           ├── {artwork_id}.png
│           └── {artwork_id}.gif
```

Path derived from `SHA256(artwork_id)[0:6]` split into 2-char directories.

## Environments

| Environment | Directory | Branch | Domain |
|-------------|-----------|--------|--------|
| Production | `/opt/makapix` | `main` | makapix.club |
| Development | `/opt/makapix-dev` | `develop` | development.makapix.club |

Both environments share:

- Caddy instance (routes by domain)
- Caddy certificates and config
- External network (`caddy_net`)

Separate resources:

- Database volumes
- Vault directories
- Redis instances

## Scalability

Current architecture is optimized for single-server deployment. Scaling considerations:

| Component | Horizontal Scaling |
|-----------|-------------------|
| Web | Load balancer + multiple instances |
| API | Load balancer + multiple instances |
| Worker | Multiple worker instances |
| DB | Read replicas |
| Cache | Redis cluster |
| MQTT | MQTT bridge/cluster |
| Vault | Object storage (S3-compatible) |

## Security

### Network Isolation

- Database only accessible from internal network
- API validates all requests
- MQTT requires authentication

### TLS

- All external traffic over HTTPS (Caddy auto-TLS)
- Player MQTT connections use mTLS
- Internal services use plain connections (isolated network)

### Rate Limiting

- API endpoints rate-limited by IP and user
- Redis-backed rate limiting state
- Per-endpoint configurable limits

See [Security Quick Reference](security/QUICK_REFERENCE.md) for details.

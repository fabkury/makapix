# Makapix Architecture Documentation

**Version:** 2.0  
**Last Updated:** December 2025  
**Repository:** [fabkury/makapix](https://github.com/fabkury/makapix)

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Repository Structure](#repository-structure)
4. [Core Components](#core-components)
5. [Data Architecture](#data-architecture)
6. [Storage Architecture](#storage-architecture)
7. [Communication Patterns](#communication-patterns)
8. [Security Architecture](#security-architecture)
9. [Deployment Architecture](#deployment-architecture)
10. [Technology Stack](#technology-stack)

---

## Overview

Makapix is a lightweight pixel-art social network designed to run efficiently on a single VPS with minimal operational costs. The platform supports artwork hosting via a local vault, social interactions (reactions, comments, playlists), real-time notifications via MQTT, and moderation features.

### Design Principles

- **Cost-Effective**: Operates on a ~$7-$18/month budget (VPS only, no external storage costs)
- **Scalable to 10K MAU**: Architecture supports up to 10,000 monthly active users
- **Single VPS Deployment**: All services run on one server using Docker containers
- **Local Storage**: Images stored in a vault directly on the VPS (no third-party object storage)
- **Real-Time Updates**: MQTT protocol for instant notifications to web and physical players
- **Monorepo**: All code managed in a single repository for simplified development

---

## System Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Internet / Users                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   Caddy Proxy   │
                    │  (TLS, HTTP/2)  │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
    ┌────▼─────┐      ┌─────▼──────┐      ┌────▼────┐
    │   Web    │      │  FastAPI   │      │  MQTT   │
    │ (Next.js)│      │    API     │      │ Broker  │
    └────┬─────┘      └─────┬──────┘      └────┬────┘
         │                  │                   │
         └──────────┬───────┴───────┬───────────┘
                    │               │
         ┌──────────▼───────┐  ┌────▼─────────┐
         │   PostgreSQL     │  │    Redis     │
         │   (Database)     │  │   (Cache)    │
         └──────────────────┘  └──────────────┘
                    │
         ┌──────────▼───────┐
         │  Background      │
         │    Worker        │
         │   (Celery)       │
         └──────────────────┘
                    │
         ┌──────────▼───────┐
         │   Image Vault    │
         │ (Local Storage)  │
         └──────────────────┘
```

### Service Responsibilities

| Service | Purpose | Technology | Ports |
|---------|---------|------------|-------|
| **Proxy** | TLS termination, reverse proxy | Caddy 2 | 80, 443 |
| **Web** | Frontend UI, SSR/SSG | Next.js 14 (TypeScript) | 3000 |
| **API** | REST API, business logic, auth | FastAPI (Python 3.12+) | 8000 |
| **Worker** | Background tasks, async processing | Celery (Python) | - |
| **Database** | Persistent data storage | PostgreSQL 16 | 5432 |
| **Cache** | Session store, rate limiting, queues | Redis 7.2 | 6379 |
| **MQTT** | Real-time pub/sub messaging | Eclipse Mosquitto | 1883, 8883, 9001 |
| **Vault** | Image storage | VPS filesystem (mounted volume) | - |

---

## Repository Structure

The repository follows a **monorepo** architecture with clear separation of concerns:

```
makapix/
├── api/                      # FastAPI backend
│   ├── alembic/             # Database migrations
│   ├── app/                 # Application code
│   │   ├── routers/         # API endpoints
│   │   ├── mqtt/            # MQTT integration
│   │   ├── utils/           # Utilities
│   │   ├── vault.py         # Vault storage system
│   │   ├── models.py        # SQLAlchemy models
│   │   ├── schemas.py       # Pydantic schemas
│   │   ├── auth.py          # Authentication logic
│   │   ├── db.py            # Database connection
│   │   └── main.py          # FastAPI app
│   ├── tests/               # API tests
│   └── Dockerfile           # API container
│
├── web/                      # Next.js frontend
│   ├── src/
│   │   ├── pages/           # Page components
│   │   ├── components/      # React components
│   │   ├── hooks/           # Custom hooks
│   │   └── lib/             # Utilities & API client
│   ├── public/              # Static assets
│   └── Dockerfile           # Web container
│
├── worker/                   # Background worker
│   ├── worker.py            # Celery worker
│   └── Dockerfile           # Worker container
│
├── db/                       # Database scripts
│   ├── init.sql             # Bootstrap script
│   └── seed.sql             # Seed data
│
├── mqtt/                     # MQTT broker config
│   ├── config/              # Mosquitto config
│   ├── certs/               # TLS certificates
│   └── Dockerfile           # MQTT container
│
├── apps/                     # Additional apps
│   └── cta/                 # Marketing/CTA site
│
├── deploy/                   # Deployment configs
│   └── stack/               # VPS stack orchestration
│
├── proxy/                    # Proxy configuration
├── scripts/                  # Utility scripts
├── docs/                     # Documentation
│   ├── ARCHITECTURE.md      # This document
│   ├── DEVELOPMENT.md       # Developer guide
│   ├── DEPLOYMENT.md        # Deployment guide
│   ├── PHYSICAL_PLAYER.md   # Hardware integration
│   └── ROADMAP.md           # Project roadmap
│
├── docker-compose.yml        # Local development stack
├── Makefile                  # Development commands
├── README.md                 # Project overview
└── makapix_full_project_spec.md  # Full specification
```

---

## Core Components

### 1. FastAPI Backend (API)

**Location:** `/api`

The API is the central nervous system of Makapix, handling all business logic and data operations.

#### Key Features

- **RESTful API**: All endpoints follow REST conventions
- **Authentication**: JWT-based auth with refresh tokens, GitHub OAuth support
- **Authorization**: Role-based access control (user, moderator, owner)
- **Database ORM**: SQLAlchemy for type-safe database operations
- **Validation**: Pydantic schemas for request/response validation
- **Background Tasks**: Celery integration for async operations
- **Real-time**: MQTT integration for push notifications
- **Migrations**: Alembic for database schema versioning
- **Image Storage**: Direct vault management for uploaded artwork

#### Router Modules

| Router | Endpoints | Purpose |
|--------|-----------|---------|
| **auth** | `/auth/*` | Authentication (login, logout, refresh) |
| **user** | `/user/*` | User management |
| **profile** | `/profile/*` | Public profile views |
| **post** | `/post/*` | Post CRUD, listing, filtering |
| **artwork** | `/vault/*` | Artwork file serving from vault |
| **playlist** | `/playlist/*` | Playlist management |
| **comment** | `/post/*/comments` | Comment CRUD |
| **reaction** | `/post/*/reactions` | Emoji reactions |
| **report** | `/report/*` | Abuse reporting |
| **badge** | `/badge/*` | Badge system |
| **devices** | `/devices/*` | Physical player management |
| **admin** | `/admin/*` | Administrative actions |
| **system** | `/health`, `/metrics` | System monitoring |

### 2. Next.js Frontend (Web)

**Location:** `/web`

Modern React-based frontend with server-side rendering capabilities.

#### Key Features

- **React 18**: Modern React with hooks
- **TypeScript**: Type-safe frontend code
- **SSR/SSG**: Server-side rendering and static generation
- **API Integration**: Type-safe API client
- **Real-time Updates**: MQTT WebSocket integration
- **Responsive Design**: Mobile-first approach
- **Component Library**: Reusable UI components

### 3. Background Worker

**Location:** `/worker`

Handles asynchronous tasks that shouldn't block API requests.

#### Responsibilities

- **Asset Processing**: Validate and process uploaded artwork
- **Notifications**: Send MQTT notifications for new posts
- **Batch Operations**: Bulk moderation actions
- **Scheduled Tasks**: Periodic cleanup, analytics

### 4. PostgreSQL Database

**Location:** Containerized service

Primary data store for all persistent data.

#### Schema Highlights

**Core Tables:**
- `users`: User accounts and profiles
- `posts`: Artwork posts (storage_key references vault files)
- `comments`: Post comments (threaded, depth 0-2)
- `reactions`: Emoji reactions to posts
- `playlists`: Ordered lists of posts
- `badges`: Badge definitions
- `badge_grants`: User badge assignments

**Moderation Tables:**
- `reports`: Abuse reports
- `moderation_log`: Audit trail
- `reputation_history`: Reputation changes

**Device Management:**
- `devices`: Physical player devices

### 5. Redis Cache

**Location:** Containerized service

High-performance in-memory data store.

#### Use Cases

- **Session Storage**: User session data
- **Rate Limiting**: IP and user-based rate limits
- **Task Queue**: Celery broker and result backend
- **API Caching**: Response caching for expensive queries
- **MQTT State**: Track online/offline devices

### 6. MQTT Broker (Mosquitto)

**Location:** `/mqtt`

Real-time message broker for push notifications.

#### Features

- **TLS Support**: Secure connections (port 8883)
- **WebSocket**: Browser-compatible (port 9001)
- **Authentication**: Password and certificate-based auth
- **ACLs**: Topic-based access control
- **QoS 1**: At-least-once delivery

#### Topic Structure

```
makapix/
├── posts/
│   ├── new              # New post notifications
│   └── promoted         # Promoted post notifications
├── player/
│   └── [player_key]/    # Physical player commands/status
│       ├── command      # Server → Player commands
│       └── status       # Player → Server status reports
└── system/
    └── announcements    # System-wide announcements
```

---

## Data Architecture

### Entity Relationships

```
┌──────────┐         ┌──────────┐         ┌──────────┐
│   User   │◄────────│   Post   │────────►│ Reaction │
└────┬─────┘         └────┬─────┘         └──────────┘
     │                    │
     │                    ├──────────────► Comment
     │                    │
     │                    └──────────────► Playlist Entry
     │
     ├──────────────────► Device
     ├──────────────────► Badge Grant
     ├──────────────────► Report
     └──────────────────► Reputation History
```

### Data Flow: Publishing Artwork

```
1. User uploads artwork file via /post/upload endpoint
2. API validates metadata and image (format, size, dimensions)
3. API generates UUID storage_key for the artwork
4. API saves image to vault using hash-based folder structure
5. API creates post record in database with vault reference
6. API publishes MQTT notification
7. Web clients and physical players receive notification
8. Devices fetch artwork directly from vault via /api/vault/ endpoint
```

---

## Storage Architecture

### Image Vault System

Makapix uses a **local vault** for image storage instead of third-party object storage services:

#### Vault Structure

```
/vault/
├── a1/
│   ├── b2/
│   │   ├── c3/
│   │   │   ├── a1b2c3d4-e5f6-7890-abcd-ef1234567890.png
│   │   │   ├── a1b2c3d4-e5f6-7890-abcd-ef1234567891.webp
│   │   │   └── ...
│   │   └── c4/
│   │       └── ...
│   └── b3/
│       └── ...
└── a2/
    └── ...
```

#### Key Features

1. **Hash-Based Organization**: First 6 characters of SHA-256 hash of the artwork ID determine folder structure (a1/b2/c3/)
2. **No Single-Folder Overcrowding**: Hash-based distribution ensures no folder has too many files
3. **Direct Serving**: Caddy proxy serves files directly from vault via `/api/vault/` route
4. **Deterministic URLs**: URL path is derived from artwork ID: `/api/vault/a1/b2/c3/{id}.png`

#### Storage Limits

- **Maximum file size**: 5 MB per image
- **Allowed formats**: PNG, GIF, WebP
- **Canvas validation**: Images must be perfect squares within allowed dimensions
- **Per-user quotas**: Tracked in database (`storage_used_bytes` field)

#### Vault Operations

```python
# Save artwork to vault
save_artwork_to_vault(artwork_id, file_content, mime_type)
# Generates: /vault/a1/b2/c3/artwork-id.png

# Get artwork URL
get_artwork_url(artwork_id, extension)
# Returns: /api/vault/a1/b2/c3/artwork-id.png

# Delete artwork from vault
delete_artwork_from_vault(artwork_id, extension)
```

#### Advantages Over External Storage

- **Zero External Costs**: No S3/R2 fees
- **Simplified Architecture**: No API keys or SDK dependencies
- **Fast Local Access**: Direct filesystem reads
- **Full Control**: Complete ownership of data
- **Easy Backups**: Standard filesystem backup tools work

---

## Communication Patterns

### 1. HTTP/REST (Primary)

**Client → API → Database**

- Synchronous request/response
- Used for all CRUD operations
- JWT authentication
- JSON payloads

### 2. MQTT (Real-time)

**API → MQTT Broker → Clients**

- Asynchronous pub/sub
- Used for notifications
- Lightweight payloads
- QoS 1 (at-least-once)

### 3. Task Queue (Background)

**API → Redis → Worker → Database**

- Asynchronous task execution
- Used for heavy processing
- Result tracking
- Retry logic

---

## Security Architecture

### Authentication & Authorization

1. **JWT Tokens**
   - Access token: 15 minutes
   - Refresh token: 7 days
   - Stored in httpOnly cookies (web) or secure storage (mobile)

2. **Role-Based Access Control**
   - User: Basic access
   - Moderator: Content moderation
   - Owner: System administration

3. **OAuth Integration**
   - GitHub OAuth for social login
   - No password storage for OAuth users

### Data Security

1. **TLS Everywhere**
   - HTTPS for all web traffic
   - TLS for MQTT connections
   - Certificate-based auth for physical players

2. **Input Validation**
   - Pydantic schemas for API validation
   - SQL injection prevention (ORM)
   - XSS prevention (React escaping)
   - File type validation (magic bytes)

3. **Content Security**
   - Hash verification for uploaded images
   - File type validation (magic bytes)
   - Size limits enforced
   - Canvas dimension validation

4. **Rate Limiting**
   - Per-IP limits
   - Per-user limits
   - Redis-backed counters

### Vault Security

1. **Access Control**
   - Files served only through authenticated API
   - No directory listing
   - Path traversal prevention

2. **Storage Isolation**
   - Vault mounted as Docker volume
   - Separate from application code
   - Configurable location via `VAULT_LOCATION` env var

---

## Deployment Architecture

### Development Environment

**Local Docker Compose Stack**

```bash
make local     # Switch to local config
make up        # Start all services
make logs      # View logs
```

- All services run locally
- Hot reload enabled
- Test data seeded
- Vault stored in `./vault` directory

### Production Environment

**Single VPS Deployment**

**Location:** `/deploy/stack`

#### VPS Configuration

- **Provider**: Any VPS provider (DigitalOcean, Linode, Vultr, etc.)
- **Size**: 2 vCPU, 2-4 GB RAM minimum
- **OS**: Ubuntu 22.04 LTS
- **Docker**: Latest stable
- **Storage**: SSD with sufficient space for vault

#### Service Layout

```
VPS (makapix.club)
├── Caddy (reverse proxy)
│   ├── makapix.club → CTA site (static)
│   └── dev.makapix.club → Full app (Next.js)
├── Docker Containers
│   ├── web (Next.js)
│   ├── api (FastAPI)
│   ├── worker (Celery)
│   ├── db (PostgreSQL)
│   ├── cache (Redis)
│   └── mqtt (Mosquitto)
└── Volumes
    ├── vault (image storage)
    ├── pg_data (database)
    ├── caddy_data (certificates)
    └── caddy_config (proxy config)
```

### Backup Strategy

1. **Database Backups**
   - Nightly pg_dump
   - Encrypted off-site storage
   - 30-day retention

2. **Vault Backups**
   - Daily rsync to backup location
   - Incremental backups
   - 90-day retention

3. **Configuration**
   - Environment files in secure storage
   - Infrastructure as code in git

---

## Technology Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.12+ | Primary language |
| **FastAPI** | 0.110+ | Web framework |
| **SQLAlchemy** | 2.0+ | ORM |
| **Alembic** | 1.13+ | Migrations |
| **Pydantic** | 2.7+ | Validation |
| **Celery** | 5.3+ | Task queue |
| **PyJWT** | 2.8+ | JWT handling |

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| **Node.js** | 20+ | Runtime |
| **Next.js** | 14.2+ | React framework |
| **React** | 18.2+ | UI library |
| **TypeScript** | 5.5+ | Type safety |
| **mqtt** | 5.3+ | MQTT client |

### Infrastructure

| Technology | Version | Purpose |
|------------|---------|---------|
| **PostgreSQL** | 16 | Database |
| **Redis** | 7.2 | Cache/Queue |
| **Mosquitto** | 2.0+ | MQTT broker |
| **Caddy** | 2+ | Reverse proxy |
| **Docker** | 24+ | Containerization |
| **Docker Compose** | 2.20+ | Orchestration |

---

## Performance Considerations

### Database Optimization

- **Indexes**: Strategic indexes on frequently queried columns
- **Pagination**: Cursor-based pagination to avoid OFFSET performance issues
- **Connection Pooling**: Reuse database connections
- **Query Optimization**: Eager loading to avoid N+1 queries

### Caching Strategy

- **API Response Caching**: Redis cache for expensive queries
- **Static Asset Caching**: Long-lived cache headers for vault files
- **Session Caching**: Redis-backed sessions

### Vault Performance

- **Hash-Based Distribution**: Ensures even file distribution across folders
- **Direct Serving**: Caddy serves files directly without hitting Python
- **OS-Level Caching**: Filesystem cache for frequently accessed files

### Scaling Considerations

**Current Capacity (Single VPS):**
- 10,000 MAU target
- ~100 concurrent users
- ~1,000 posts/day

**Horizontal Scaling Path:**
1. Add API replicas behind load balancer
2. Separate database to dedicated server
3. Add read replicas for database
4. Use NFS or distributed filesystem for vault
5. Add worker replicas for background tasks

---

## References

- **[Full Specification](../makapix_full_project_spec.md)** - Comprehensive feature spec
- **[README](../README.md)** - Quick start guide
- **[Deployment Guide](DEPLOYMENT.md)** - Production deployment
- **[Development Guide](DEVELOPMENT.md)** - Developer workflows
- **[Roadmap](ROADMAP.md)** - Project milestones

---

Built for efficiency, simplicity, and cost-effectiveness.

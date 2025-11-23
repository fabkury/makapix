# Makapix Architecture Documentation

**Version:** 1.0  
**Last Updated:** November 2025  
**Repository:** [fabkury/makapix](https://github.com/fabkury/makapix)

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Repository Structure](#repository-structure)
4. [Core Components](#core-components)
5. [Data Architecture](#data-architecture)
6. [Communication Patterns](#communication-patterns)
7. [Security Architecture](#security-architecture)
8. [Deployment Architecture](#deployment-architecture)
9. [Development Workflow](#development-workflow)
10. [Technology Stack](#technology-stack)

---

## Overview

Makapix is a lightweight pixel-art social network designed to run efficiently on a single VPS with minimal operational costs. The platform supports artwork hosting, social interactions (reactions, comments, playlists), real-time notifications via MQTT, and moderation features.

### Design Principles

- **Cost-Effective**: Operates on a ~$7-$18/month budget (VPS + object storage)
- **Scalable to 10K MAU**: Architecture supports up to 10,000 monthly active users
- **Single VPS Deployment**: All services run on one server using Docker containers
- **Asset Offloading**: Heavy binaries stored in object storage (Cloudflare R2/AWS S3) served via CDN
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
         │ Object Storage   │
         │  (R2/S3 + CDN)   │
         └──────────────────┘
```

### Service Responsibilities

| Service | Purpose | Technology | Ports |
|---------|---------|------------|-------|
| **Proxy** | TLS termination, reverse proxy, load balancing | Caddy 2 | 80, 443 |
| **Web** | Frontend UI, SSR/SSG | Next.js 14 (TypeScript) | 3000 |
| **API** | REST API, business logic, auth | FastAPI (Python) | 8000 |
| **Worker** | Background tasks, async processing | Celery (Python) | - |
| **Database** | Persistent data storage | PostgreSQL 16 | 5432 |
| **Cache** | Session store, rate limiting, queues | Redis 7.2 | 6379 |
| **MQTT** | Real-time pub/sub messaging | Eclipse Mosquitto | 1883, 8883, 9001 |

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
├── infra/                    # Infrastructure code
├── docs/                     # Documentation
│
├── docker-compose.yml        # Local development stack
├── Makefile                  # Development commands
├── README.md                 # Project overview
├── makapix_full_project_spec.md  # Full specification
└── ARCHITECTURE.md           # This document
```

### Key Files

- **docker-compose.yml**: Orchestrates all services for local development
- **Makefile**: Provides convenient commands for common tasks
- **makapix_full_project_spec.md**: Comprehensive feature specification
- **.env.example**: Environment variable template
- **alembic/**: Database migration management

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

#### Router Modules

| Router | Endpoints | Purpose |
|--------|-----------|---------|
| **auth** | `/auth/*` | Authentication (login, logout, refresh) |
| **users** | `/users/*` | User management |
| **profiles** | `/profiles/*` | Public profile views |
| **posts** | `/posts/*` | Post CRUD, listing, filtering |
| **playlists** | `/playlists/*` | Playlist management |
| **comments** | `/comments/*` | Comment CRUD |
| **reactions** | `/reactions/*` | Emoji reactions |
| **reports** | `/reports/*` | Abuse reporting |
| **badges** | `/badges/*` | Badge system |
| **reputation** | `/reputation/*` | Reputation management |
| **categories** | `/categories/*` | Content categorization |
| **search** | `/search/*` | Full-text search |
| **devices** | `/devices/*` | Physical player management |
| **mqtt** | `/mqtt/*` | MQTT credential issuance |
| **admin** | `/admin/*` | Administrative actions |
| **system** | `/health`, `/metrics` | System monitoring |

#### Authentication Flow

```
1. User initiates GitHub OAuth
2. GitHub redirects to /auth/github/callback
3. API creates/updates user record
4. API issues JWT access token (15 min) + refresh token (7 days)
5. Client stores tokens (httpOnly cookies or localStorage)
6. Access token used for authenticated requests
7. Refresh endpoint used when access token expires
```

#### Database Layer

- **SQLAlchemy ORM**: Type-safe database operations
- **Connection Pooling**: Efficient database connection management
- **Transactions**: ACID guarantees for critical operations
- **Indexes**: Optimized for common queries
- **Foreign Keys**: Enforced referential integrity

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

#### Page Structure

| Page | Route | Purpose |
|------|-------|---------|
| **Home** | `/` | Landing page, promoted content feed |
| **Recent** | `/recent` | Latest posts feed |
| **Search** | `/search` | Search interface |
| **Post Detail** | `/posts/[id]` | Individual post view |
| **Publish** | `/publish` | Upload artwork |
| **Mod Dashboard** | `/mod-dashboard` | Moderation tools |
| **Owner Dashboard** | `/owner-dashboard` | Owner controls |

#### State Management

- **React Hooks**: useState, useEffect for local state
- **Custom Hooks**: Reusable logic (useMQTTNotifications, etc.)
- **API Client**: Centralized API communication layer
- **Session Management**: JWT token handling

#### Real-time Features

- **MQTT Notifications**: WebSocket connection to broker
- **Live Updates**: Posts, comments, reactions update in real-time
- **Notification Center**: Central hub for user notifications

### 3. Background Worker

**Location:** `/worker`

Handles asynchronous tasks that shouldn't block API requests.

#### Responsibilities

- **Asset Processing**: Validate and process uploaded artwork
- **Notifications**: Send MQTT notifications for new posts
- **Batch Operations**: Bulk moderation actions
- **Scheduled Tasks**: Periodic cleanup, analytics
- **Email Delivery**: (Future) Email notifications

#### Task Queue

- **Broker**: Redis
- **Backend**: Redis (result storage)
- **Concurrency**: Configurable worker processes
- **Retry Logic**: Automatic retry for failed tasks

### 4. PostgreSQL Database

**Location:** Containerized service

Primary data store for all persistent data.

#### Schema Highlights

**Core Tables:**
- `users`: User accounts and profiles
- `posts`: Artwork posts
- `comments`: Post comments (threaded, depth 0-2)
- `reactions`: Emoji reactions to posts
- `playlists`: Ordered lists of posts
- `badges`: Badge definitions
- `badge_grants`: User badge assignments

**Moderation Tables:**
- `reports`: Abuse reports
- `moderation_log`: Audit trail
- `reputation_history`: Reputation changes

**Authentication:**
- `refresh_tokens`: JWT refresh tokens

**Device Management:**
- `devices`: Physical player devices

#### Data Integrity

- **UUIDs**: All primary keys use UUID v4
- **Timestamps**: created_at, updated_at on all tables
- **Soft Deletes**: Moderator actions use soft delete
- **Hard Deletes**: User-initiated deletes are permanent
- **Foreign Keys**: Enforced relationships
- **Constraints**: Check constraints for business rules

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
├── users/
│   └── [user_id]/       # User-specific notifications
│       ├── comments     # New comments on user's posts
│       ├── reactions    # Reactions to user's posts
│       └── mentions     # User mentions
└── system/
    └── announcements    # System-wide announcements
```

#### Client Types

1. **Web Clients**: Connect via WebSocket (port 9001)
2. **Physical Players**: Connect via TLS (port 8883) with client certificates
3. **Server**: Publishes notifications to topics

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
1. User uploads artwork ZIP via /publish endpoint
2. API validates metadata and queues processing task
3. Worker processes ZIP:
   - Extracts and validates images
   - Uploads to object storage (R2/S3)
   - Generates CDN URLs
4. Worker creates post record in database
5. Worker publishes MQTT notification
6. Web clients receive notification and update UI
7. CDN serves artwork to viewers
```

### Data Flow: Social Interaction

```
1. User adds reaction/comment via API
2. API validates and saves to database
3. API publishes MQTT notification to post owner
4. Post owner's client receives notification
5. UI updates in real-time
```

### Caching Strategy

- **Static Content**: CDN caching for artwork (1 year)
- **API Responses**: Redis caching for expensive queries (5-60 min)
- **User Sessions**: Redis (7 days)
- **Feed Data**: Short-lived cache (5 min)

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

### 4. Server-to-Server (Internal)

**Web (SSR) → API**

- Internal API calls during SSR
- No external network latency
- Same auth mechanisms

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

3. **Content Security**
   - Hash pinning for artwork
   - File type validation (magic bytes)
   - Size limits enforced

4. **Rate Limiting**
   - Per-IP limits
   - Per-user limits
   - Redis-backed counters

### Asset Storage Security

1. **Private Bucket**
   - No public ACLs
   - CDN origin access only

2. **Hash Verification**
   - SHA-256 hash stored in DB
   - Periodic re-verification
   - Auto-hide on mismatch

3. **Access Control**
   - Signed URLs for sensitive content
   - Scoped IAM credentials

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
- Local TLS certificates
- Test data seeded

### Staging Environment

**Remote Development (dev.makapix.club)**

```bash
make remote    # Switch to remote config
make up        # Start with remote settings
```

- Same stack as production
- Uses remote database
- Real TLS certificates
- Subset of production data

### Production Environment

**Single VPS Deployment**

**Location:** `/deploy/stack`

```bash
cd deploy/stack
docker compose up -d
```

#### VPS Configuration

- **Provider**: Any VPS provider (DigitalOcean, Linode, Vultr, etc.)
- **Size**: 2 vCPU, 2-4 GB RAM minimum
- **OS**: Ubuntu 22.04 LTS
- **Docker**: Latest stable
- **Network**: Public IP with DNS configured

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
    ├── pg_data (database)
    ├── caddy_data (certificates)
    └── caddy_config (proxy config)
```

#### External Services

1. **Object Storage**
   - Cloudflare R2 (preferred) or AWS S3
   - Private bucket
   - CDN in front

2. **DNS**
   - Cloudflare or similar
   - A records for makapix.club and subdomains

3. **Monitoring** (Optional)
   - Uptime monitoring
   - Error alerting
   - Log aggregation

### Deployment Workflow

1. **Code Changes**
   ```bash
   git push origin main
   ```

2. **VPS Update**
   ```bash
   ssh user@makapix.club
   cd /opt/makapix
   make deploy-vps
   ```

3. **Verification**
   - Check health endpoints
   - View logs
   - Test key functionality

### Backup Strategy

1. **Database Backups**
   - Nightly pg_dump
   - Encrypted off-site storage
   - 30-day retention

2. **Object Storage**
   - Versioning enabled
   - Weekly full backup to secondary region
   - 90-day retention

3. **Configuration**
   - Environment files in secure storage
   - Infrastructure as code in git

### Disaster Recovery

1. **Database Restore**
   - Restore from latest backup
   - Replay transaction logs if available

2. **Service Recovery**
   - Pull latest code
   - Restore environment configuration
   - Run migrations
   - Start services

3. **RTO/RPO Targets**
   - RTO (Recovery Time Objective): 4 hours
   - RPO (Recovery Point Objective): 24 hours

---

## Development Workflow

### Local Development Setup

1. **Prerequisites**
   ```bash
   # Install required tools
   - Docker & Docker Compose
   - Node.js 18+
   - Python 3.11+
   - Git
   ```

2. **Clone Repository**
   ```bash
   git clone https://github.com/fabkury/makapix.git
   cd makapix
   ```

3. **Configure Environment**
   ```bash
   make local
   # Edit .env if needed
   ```

4. **Start Services**
   ```bash
   make up
   ```

5. **Access Services**
   - Web: http://localhost:3000
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Database: localhost:5432

### Common Commands

```bash
# Environment management
make local          # Switch to local development
make remote         # Switch to remote development
make status         # Show current environment

# Service control
make up             # Start all services
make down           # Stop all services
make restart        # Restart services
make rebuild        # Rebuild and restart

# Logs
make logs           # All service logs
make logs-api       # API logs only
make logs-web       # Web logs only

# Development
make test           # Run API tests
make shell-api      # Shell in API container
make shell-db       # PostgreSQL shell

# Cleanup
make clean          # Remove containers and volumes
```

### Database Migrations

```bash
# Create new migration
docker compose exec api alembic revision --autogenerate -m "description"

# Apply migrations
docker compose exec api alembic upgrade head

# View migration history
docker compose exec api alembic history
```

### Testing

```bash
# Run all tests
make test

# Run specific test file
docker compose exec api pytest tests/test_posts.py

# Run with coverage
docker compose exec api pytest --cov=app tests/
```

### Code Quality

```bash
# Format code
docker compose exec api black app/
docker compose exec api isort app/

# Lint
docker compose exec api flake8 app/
docker compose exec api mypy app/
```

---

## Technology Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.12+ | Primary language |
| **FastAPI** | 0.110+ | Web framework |
| **SQLAlchemy** | 2.0.29+ | ORM |
| **Alembic** | 1.13+ | Migrations |
| **Pydantic** | 2.7+ | Validation |
| **Celery** | 5.3+ | Task queue |
| **PyJWT** | 2.8+ | JWT handling |
| **httpx** | 0.27+ | HTTP client |
| **psycopg** | 3.1+ | PostgreSQL adapter |

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| **Node.js** | 20+ | Runtime |
| **Next.js** | 14.2+ | React framework |
| **React** | 18.2+ | UI library |
| **TypeScript** | 5.5+ | Type safety |
| **mqtt** | 5.3+ | MQTT client |
| **JSZip** | 3.10+ | ZIP file handling |

### Infrastructure

| Technology | Version | Purpose |
|------------|---------|---------|
| **PostgreSQL** | 16 (Alpine) | Database |
| **Redis** | 7.2 (Alpine) | Cache/Queue |
| **Mosquitto** | 2.0+ | MQTT broker |
| **Caddy** | 2+ | Reverse proxy |
| **Docker** | 24+ | Containerization |
| **Docker Compose** | 2.20+ | Orchestration |

### External Services

| Service | Purpose |
|---------|---------|
| **Cloudflare R2** | Object storage |
| **Cloudflare CDN** | Content delivery |
| **GitHub OAuth** | Authentication |

---

## Performance Considerations

### Database Optimization

- **Indexes**: Strategic indexes on frequently queried columns
- **Pagination**: Cursor-based pagination to avoid OFFSET performance issues
- **Connection Pooling**: Reuse database connections
- **Query Optimization**: Eager loading to avoid N+1 queries

### Caching Strategy

- **API Response Caching**: Redis cache for expensive queries
- **CDN Caching**: Long-lived cache for static assets
- **Session Caching**: Redis-backed sessions

### Asset Delivery

- **CDN**: All artwork served via CDN
- **Image Optimization**: Size and format validation
- **Lazy Loading**: Images loaded on-demand

### Scaling Considerations

**Current Capacity (Single VPS):**
- 10,000 MAU target
- ~100 concurrent users
- ~1,000 posts/day

**Horizontal Scaling Path:**
1. Add API replicas behind load balancer
2. Separate database to dedicated server
3. Add read replicas for database
4. Add worker replicas for background tasks
5. Use managed services (RDS, ElastiCache)

---

## Monitoring & Observability

### Health Checks

- `/health`: Basic health endpoint
- `/metrics`: Prometheus metrics
- Docker health checks on all services

### Logging

- **Structured Logging**: JSON format
- **Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Log Aggregation**: Centralized logging (future)

### Metrics

- Request latency
- Error rates
- Database query performance
- Background task completion
- MQTT connection count

### Alerting

- Service downtime
- High error rates
- Database connection issues
- Disk space warnings

---

## Future Enhancements

### Planned Features

1. **Artist Recognition Platform (ARP)**
   - View tracking and analytics
   - Recognition badges
   - Trending metrics

2. **Advanced Search**
   - Full-text search with PostgreSQL FTS
   - Filters and facets
   - Search suggestions

3. **Social Features**
   - User following
   - Activity feeds
   - Notifications

4. **Mobile App**
   - Native iOS/Android apps
   - Push notifications
   - Offline support

### Technical Improvements

1. **Performance**
   - Read replicas for database
   - CDN optimization
   - Query optimization

2. **Observability**
   - Distributed tracing
   - APM integration
   - Log aggregation

3. **Reliability**
   - Multi-region backup
   - Automated failover
   - Chaos engineering

---

## References

- **Full Specification**: See `makapix_full_project_spec.md`
- **README**: See `README.md` for quick start
- **API Documentation**: http://localhost:8000/docs (when running)
- **Deployment Guide**: See `deploy/stack/README.stack.md`

---

## Appendix

### Glossary

- **MAU**: Monthly Active Users
- **VPS**: Virtual Private Server
- **CDN**: Content Delivery Network
- **MQTT**: Message Queuing Telemetry Transport
- **ORM**: Object-Relational Mapping
- **SSR**: Server-Side Rendering
- **SSG**: Static Site Generation
- **JWT**: JSON Web Token
- **RTO**: Recovery Time Objective
- **RPO**: Recovery Point Objective

### Contact

For questions or contributions, please open an issue on GitHub.

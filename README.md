# Makapix Club

A place to publish pixel art and document maker projects — free, open-source, and ad-free.

## What Makapix is

Makapix Club is a lightweight social network for people who create things: pixel artists, DIY makers working with embedded systems, and anyone who values craftsmanship over algorithms.

If you've ever wanted a place to share your work that respects what you build, gives you control over how it's presented, and won't disappear when a company pivots or shuts down — that's what we're building here.

## Why Makapix exists

Most social platforms optimize for engagement and growth. They control what people see, sell ads against your work, and treat creators as content suppliers.

Makapix takes a different approach:

- No ads, ever
- No algorithmic feed trying to maximize your time on site
- No subscription tiers hiding basic features
- No venture capital pressuring us to extract value from the community

Your work stays yours. The platform is open-source. The project is built to last.

## What you can do on Makapix

- Publish pixel art and document your projects
- Create playlists and galleries to organize work
- Display artwork on physical devices through MQTT
- Connect with a community that values patience and craft
- Contribute to an open-source platform that respects its users

This is not a place to chase viral moments or follower counts. It's a place to build a catalog of work you're proud of.

## Who Makapix is for

- Makers building embedded projects and microcontroller displays
- Pixel artists creating constrained, deliberate work
- People who want their projects documented somewhere permanent
- Open-source contributors who believe software should be transparent
- Anyone tired of platforms that treat craft as content

If you value permanence, ownership, and community over growth metrics, this is for you.

## Open-source and community values

Makapix is fully open-source. The code, the architecture, and the infrastructure are all visible and available for inspection, contribution, or self-hosting.

We invite:

- Code contributions and bug reports
- Documentation improvements
- Feedback on features and design
- Self-hosters who want to run their own instance

The platform is designed to run affordably on a single VPS, making it accessible to operate independently without relying on us.

Transparency and long-term sustainability matter more than rapid growth.

## Join Makapix

Create an account at [dev.makapix.club](https://dev.makapix.club) and start publishing.

No pressure. No urgency. Just a place to share the things you make.

---

## Technical Documentation

The sections below provide technical details for developers, deployers, and contributors.

### Technical Architecture

**Tech Stack:**
- **Frontend**: Next.js 14 with TypeScript and React 18
- **Backend**: FastAPI (Python 3.12+) with SQLAlchemy ORM
- **Database**: PostgreSQL 16 for structured data
- **Cache/Queue**: Redis for sessions, rate limiting, and background tasks
- **Messaging**: Eclipse Mosquitto for real-time MQTT notifications
- **Proxy**: Caddy for TLS termination and reverse proxy
- **Storage**: Local vault (hash-based folder structure) mounted on VPS

**Deployment**: All services containerized with Docker Compose, designed to run on a single VPS (2 vCPU, 2-4 GB RAM) supporting up to 10,000 monthly active users.

### Repository Structure

This is a **monorepo** containing all project components:

```
makapix/
├── apps/cta/              # Marketing website (live at makapix.club)
├── web/                   # Next.js frontend application
├── api/                   # FastAPI backend with Alembic migrations
├── worker/                # Celery background worker
├── db/                    # Database initialization scripts
├── mqtt/                  # MQTT broker configuration
├── proxy/                 # Caddy reverse proxy configuration
├── deploy/stack/          # VPS deployment orchestration
├── docs/                  # Technical documentation
└── docker-compose.yml     # Local development stack
```

### Quick Start

#### Local Development

```bash
# Clone the repository
git clone https://github.com/fabkury/makapix.git
cd makapix

# Set up local environment
make local

# Start all services
make up

# Access the application
# - Web UI: http://localhost:3000
# - API docs: http://localhost:8000/docs
# - API endpoints: http://localhost:8000/api/

# View logs
make logs

# Stop services
make down
```

#### For Developers

- **[Development Guide](docs/DEVELOPMENT.md)** - Complete local setup, workflows, and testing
- **[Architecture Documentation](docs/ARCHITECTURE.md)** - System design, components, and data flows
- **[API Documentation](http://localhost:8000/docs)** - Interactive API reference (when running locally)
- **[Naming Conventions](docs/NAMING_CONVENTIONS.md)** - Clear definitions for CTA vs web preview, compose files, and service names

#### For Deployers

- **[Deployment Guide](docs/DEPLOYMENT.md)** - VPS setup and production deployment
- **[Physical Player Integration](docs/PHYSICAL_PLAYER.md)** - Guide for integrating display devices

### Documentation

- **[Full Project Specification](makapix_full_project_spec.md)** - Comprehensive feature and technical spec
- **[Architecture Overview](docs/ARCHITECTURE.md)** - System design and component details
- **[Development Guide](docs/DEVELOPMENT.md)** - Developer workflows and best practices
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment instructions
- **[Physical Player Guide](docs/PHYSICAL_PLAYER.md)** - Hardware integration documentation
- **[Roadmap](docs/ROADMAP.md)** - Project milestones and planned features

### Key Features

#### For Artists

- **Upload and Share**: Post pixel art with titles, descriptions, and hashtags
- **Organize**: Create playlists to curate collections of artwork
- **Engage**: Receive reactions and comments from the community
- **Reputation**: Earn reputation points through community participation
- **Badges**: Display achievement badges on your profile

#### For Viewers

- **Discover**: Browse promoted artworks, recent posts, and search by hashtags
- **Interact**: React with up to 5 emojis per post, leave threaded comments
- **Follow**: Create playlists of your favorite artworks
- **Real-Time**: Get instant updates via MQTT when new artwork is posted

#### For Physical Players

- **MQTT Integration**: Devices receive real-time notifications of new artwork
- **Vault Access**: Direct download of artwork images from the VPS vault
- **Remote Control**: Owners can control what displays on their devices
- **Status Reporting**: Devices report online/offline status and current artwork

### Image Storage

Makapix uses a **local vault** storage system:

- Images are stored directly on the VPS in a hash-based folder structure
- Files are organized using the first 6 characters of the artwork ID's hash (e.g., `/vault/a1/b2/c3/artwork-id.png`)
- The vault is mounted as a Docker volume and served directly by the API
- Maximum file size: 5 MB per image
- Supported formats: PNG, GIF, WebP
- Canvas dimensions: Configurable, validated on upload

This approach eliminates third-party hosting costs while keeping the system simple and performant.

### Development Commands

```bash
# Environment management
make local          # Switch to local development config
make remote         # Switch to remote development config
make status         # Show current environment

# Service control
make up             # Start all services
make down           # Stop all services
make restart        # Restart services
make rebuild        # Rebuild containers and restart

# Logs
make logs           # View all service logs
make logs-api       # View API logs only
make logs-web       # View web logs only

# Database
make db.reset       # Reset database with seed data
make db.shell       # Open PostgreSQL shell

# Code quality
make fmt            # Format code (API)
make api.test       # Run API tests
```

### Current Status

- **CTA Site**: Live at https://makapix.club (marketing/landing page)
- **Web (Live Preview)**: Testing at https://dev.makapix.club (full application)
- **Production**: Full application launch planned

### Contributing

Contributions are welcome! Please ensure your changes:

1. Follow existing code style and conventions
2. Include tests for new functionality
3. Update documentation as needed
4. Pass all linting and tests (`make fmt`, `make api.test`)

### License

[License information to be added]

### Links

- **Website**: https://makapix.club
- **Web (Live Preview)**: https://dev.makapix.club
- **Repository**: https://github.com/fabkury/makapix


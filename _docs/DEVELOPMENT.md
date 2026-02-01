# Makapix Development Guide

Guide for developers working on Makapix Club. All development happens directly on the VPS.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Project Structure](#project-structure)
3. [Common Tasks](#common-tasks)
4. [Database Management](#database-management)
5. [Testing](#testing)
6. [Code Quality](#code-quality)
7. [Debugging](#debugging)

---

## Getting Started

### Prerequisites

- SSH access to the VPS
- Git configured with repository access

### Quick Start

```bash
# SSH to VPS
ssh user@makapix.club

# Navigate to project
cd /opt/makapix

# Start all services
make up

# View logs
make logs
```

### Access Points

- **Website**: https://makapix.club
- **API Documentation**: https://makapix.club/api/docs

---

## Project Structure

```
makapix/
├── api/                   # FastAPI backend
│   ├── app/
│   │   ├── main.py        # Application entry point
│   │   ├── models.py      # SQLAlchemy models
│   │   ├── schemas.py     # Pydantic schemas
│   │   ├── routers/       # API endpoints
│   │   └── services/      # Business logic
│   ├── alembic/           # Database migrations
│   └── tests/             # API tests
├── web/                   # Next.js frontend
│   ├── src/
│   │   ├── pages/         # Next.js pages
│   │   ├── components/    # React components
│   │   └── lib/           # Utilities
│   └── public/            # Static assets
├── worker/                # Celery background tasks
├── mqtt/                  # MQTT broker config
├── apps/cta/              # Marketing site
├── deploy/stack/          # Docker Compose stack
│   ├── docker-compose.yml # All services
│   └── .env               # Environment config
└── docs/                  # Documentation
```

---

## Common Tasks

### Service Management

```bash
# Start all services
make up

# Stop all services
make down

# Restart all services
make restart

# Rebuild and restart (after code changes)
make rebuild

# Deploy latest changes
make deploy
```

### Viewing Logs

```bash
# All services
make logs

# Specific service
make logs-api
make logs-web
make logs-db

# Or directly with docker compose
cd deploy/stack && docker compose logs -f api worker
```

### Shell Access

```bash
# API container
make shell-api

# Database shell
make shell-db
# or: make db.shell
```

---

## Database Management

### Migrations

```bash
# Create a new migration
cd deploy/stack && docker compose exec api alembic revision --autogenerate -m "description"

# Apply migrations
cd deploy/stack && docker compose exec api alembic upgrade head

# Rollback one migration
cd deploy/stack && docker compose exec api alembic downgrade -1

# Check current revision
cd deploy/stack && docker compose exec api alembic current
```

### Direct Database Access

```bash
# PostgreSQL shell
make shell-db

# Common queries
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM posts WHERE deleted_at IS NULL;
\dt                    # List tables
\d+ posts              # Describe table
```

---

## Testing

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
cd deploy/stack && docker compose exec api pytest tests/test_auth.py

# Run specific test
cd deploy/stack && docker compose exec api pytest -k "test_create_post"

# Run with verbose output
cd deploy/stack && docker compose exec api pytest -v

# Run with coverage
cd deploy/stack && docker compose exec api pytest --cov=app
```

### Writing Tests

Tests are located in `api/tests/`. Use pytest fixtures from `conftest.py`:

```python
def test_create_post(client, test_user, db):
    """Test creating a new post."""
    token = create_access_token(test_user.user_key)
    response = client.post(
        "/post",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Test", "art_url": "https://...", "canvas": "64x64"}
    )
    assert response.status_code == 201
```

---

## Code Quality

### Python (Backend)

```bash
# Format code
make fmt

# Or directly
cd deploy/stack && docker compose exec api black .
cd deploy/stack && docker compose exec api ruff check .
```

### TypeScript (Frontend)

```bash
cd deploy/stack && docker compose exec web npm run lint
cd deploy/stack && docker compose exec web npm run typecheck
```

---

## Debugging

### Checking Service Health

```bash
# Service status
cd deploy/stack && docker compose ps

# Container resource usage
docker stats

# API health endpoint
curl https://makapix.club/api/health
```

### Common Issues

**Services won't start:**
```bash
# Check for port conflicts
sudo lsof -i :80
sudo lsof -i :443

# Check Docker logs
cd deploy/stack && docker compose logs caddy
```

**Database connection issues:**
```bash
# Verify database is running
cd deploy/stack && docker compose exec db pg_isready

# Check connection from API
cd deploy/stack && docker compose exec api python -c "from app.database import engine; print(engine.url)"
```

**API errors:**
```bash
# Check API logs
make logs-api

# Test API directly
cd deploy/stack && docker compose exec api python -c "from app.main import app; print('OK')"
```

### Accessing Container Internals

```bash
# API container shell
cd deploy/stack && docker compose exec api bash

# Inside container:
python -c "from app.models import User; print(User.__table__.columns.keys())"

# Web container shell
cd deploy/stack && docker compose exec web sh
```

---

## Environment Variables

Key environment variables are configured in `deploy/stack/.env`:

```bash
# Database
DB_ADMIN_USER, DB_ADMIN_PASSWORD, DB_DATABASE
DB_API_WORKER_USER, DB_API_WORKER_PASSWORD

# API
SECRET_KEY, JWT_SECRET_KEY
GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET

# MQTT
MQTT_PASSWORD

# Storage
VAULT_HOST_PATH, VAULT_LOCATION

# Domains
ROOT_DOMAIN, WEB_DOMAIN, VAULT_DOMAIN
```

---

## Deployment Workflow

1. Make changes on the VPS (or push to git and pull)
2. Run `make rebuild` to apply changes
3. Check logs with `make logs`
4. Verify functionality at https://makapix.club

For production deployments:
```bash
make deploy   # Pulls latest from git and rebuilds
```

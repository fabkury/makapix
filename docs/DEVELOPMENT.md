# Makapix Development Guide

Complete guide for developers working on Makapix Club.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Environment](#development-environment)
3. [Project Structure](#project-structure)
4. [Development Workflow](#development-workflow)
5. [Common Tasks](#common-tasks)
6. [Database Management](#database-management)
7. [Testing](#testing)
8. [Code Quality](#code-quality)
9. [Debugging](#debugging)
10. [Contributing](#contributing)

---

## Getting Started

### Prerequisites

Ensure you have the following installed:

```bash
# Required
- Docker 24+ and Docker Compose 2.20+
- Git
- Make

# Optional but recommended
- Node.js 20+ (for local frontend development)
- Python 3.12+ (for local API development)
- PostgreSQL client tools (for database inspection)
```

### Initial Setup

1. **Clone the repository**

```bash
git clone https://github.com/fabkury/makapix.git
cd makapix
```

2. **Set up environment**

```bash
# Copy environment template
cp .env.example .env

# Or use the make command which copies the local template
make local
```

3. **Start all services**

```bash
make up
```

4. **Verify services are running**

```bash
# Check service status
docker compose ps

# Check logs
make logs
```

5. **Access the application**

- **Web UI**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **API Endpoints**: http://localhost:8000/api/

---

## Development Environment

### Environment Configuration

The project uses environment templates for different contexts:

- **`.env.example`**: Default values for local development
- **`env.local.template`**: Template for local development
- **`env.remote.template`**: Template for remote/staging deployment

#### Key Environment Variables

```bash
# Database
POSTGRES_USER=appuser
POSTGRES_PASSWORD=apppassword
POSTGRES_DB=appdb
DATABASE_URL=postgresql+psycopg://appuser:apppassword@db:5432/appdb

# Redis
REDIS_URL=redis://cache:6379/0
CELERY_BROKER_URL=redis://cache:6379/0
CELERY_RESULT_BACKEND=redis://cache:6379/0

# MQTT
MQTT_HOST=mqtt
MQTT_PORT=8883
MQTT_TLS=true
MQTT_CA_FILE=/certs/ca.crt

# Vault Storage
VAULT_LOCATION=/vault
VAULT_HOST_PATH=./vault  # Local filesystem path

# Service Ports
API_PORT=8000
WEB_PORT=3000
PROXY_PORT=80

# Logging
LOG_LEVEL=INFO
```

### Docker Compose Services

The development stack includes:

| Service | Container | Purpose | Port(s) |
|---------|-----------|---------|---------|
| **web** | makapix-web | Next.js frontend | 3000 |
| **api** | makapix-api | FastAPI backend | 8000 |
| **worker** | makapix-worker | Celery background tasks | - |
| **db** | makapix-db | PostgreSQL database | 5432 |
| **cache** | makapix-cache | Redis cache/queue | 6379 |
| **mqtt** | makapix-mqtt | Mosquitto MQTT broker | 1883, 8883, 9001 |
| **proxy** | makapix-proxy | Caddy reverse proxy | 80, 443 |

---

## Project Structure

### Backend (API)

```
api/
├── alembic/                  # Database migrations
│   ├── versions/            # Migration files
│   └── env.py              # Migration configuration
├── app/
│   ├── routers/            # API route handlers
│   │   ├── auth.py         # Authentication
│   │   ├── posts.py        # Post management
│   │   ├── artwork.py      # Artwork serving
│   │   ├── player.py       # Physical player integration
│   │   └── ...
│   ├── models.py           # SQLAlchemy models
│   ├── schemas.py          # Pydantic schemas
│   ├── vault.py            # Vault storage system
│   ├── db.py               # Database connection
│   ├── auth.py             # Authentication logic
│   └── main.py             # FastAPI application
├── tests/                  # Test files
├── Dockerfile              # Docker image definition
└── requirements.txt        # Python dependencies
```

### Frontend (Web)

```
web/
├── src/
│   ├── pages/              # Next.js pages
│   │   ├── index.tsx       # Home page
│   │   ├── publish.tsx     # Upload artwork
│   │   └── ...
│   ├── components/         # React components
│   │   ├── Layout.tsx
│   │   ├── PostCard.tsx
│   │   └── ...
│   ├── lib/                # Utilities
│   │   ├── api.ts          # API client
│   │   └── mqtt.ts         # MQTT integration
│   └── styles/             # CSS modules
├── public/                 # Static assets
├── Dockerfile              # Docker image definition
├── package.json            # Node dependencies
└── tsconfig.json           # TypeScript config
```

---

## Development Workflow

### Daily Development Cycle

```bash
# 1. Start your day
make up                     # Start all services
make logs                   # Check logs for any issues

# 2. Make changes to code
# - Edit files in your IDE
# - Changes auto-reload (hot reload enabled)

# 3. View changes
# - Web: http://localhost:3000
# - API docs: http://localhost:8000/docs

# 4. Run tests
make api.test              # Test API changes

# 5. Format code
make fmt                   # Format Python code

# 6. Stop services when done
make down                  # Stop all services
```

### Hot Reload Behavior

- **Frontend (Next.js)**: Automatic hot module replacement
- **Backend (FastAPI)**: Uvicorn watches for file changes and auto-reloads
- **Database**: Changes require migrations
- **MQTT**: Config changes require container restart

---

## Common Tasks

### Service Control

```bash
# Start all services
make up

# Stop all services
make down

# Restart all services
make restart

# Rebuild containers and restart
make rebuild

# View logs for all services
make logs

# View logs for specific service
make logs-api
make logs-web

# Enter a shell in a container
docker compose exec api bash
docker compose exec web sh
```

### Switching Environments

```bash
# Switch to local development
make local

# Switch to remote/staging
make remote

# Check current environment
make status
```

### Working with the API

```bash
# Access Python shell
docker compose exec api python

# Run specific API command
docker compose exec api python -m app.some_module

# View API logs
make logs-api

# Test API endpoint
curl http://localhost:8000/api/health
```

### Working with the Frontend

```bash
# Access Node shell
docker compose exec web sh

# Install new npm package
docker compose exec web npm install package-name

# Run Next.js build
docker compose exec web npm run build

# View web logs
make logs-web
```

---

## Database Management

### Accessing the Database

```bash
# PostgreSQL shell via make
make db.shell

# Or via docker compose
docker compose exec db psql -U appuser -d appdb

# Run SQL file
docker compose exec db psql -U appuser -d appdb < script.sql
```

### Database Migrations

Makapix uses Alembic for database schema migrations.

#### Creating a New Migration

```bash
# Auto-generate migration from model changes
docker compose exec api alembic revision --autogenerate -m "Description of changes"

# Create empty migration for manual changes
docker compose exec api alembic revision -m "Description of changes"
```

#### Applying Migrations

```bash
# Apply all pending migrations
docker compose exec api alembic upgrade head

# Apply one migration at a time
docker compose exec api alembic upgrade +1

# Revert last migration
docker compose exec api alembic downgrade -1
```

#### Migration History

```bash
# View migration history
docker compose exec api alembic history

# View current migration
docker compose exec api alembic current

# View pending migrations
docker compose exec api alembic heads
```

### Resetting the Database

```bash
# Complete database reset with seed data
make db.reset

# Manual reset
docker compose down -v          # Stop and remove volumes
docker compose up -d db         # Start database
docker compose exec api alembic upgrade head  # Run migrations
```

### Seed Data

Seed data is automatically loaded on first startup via `app.seed.ensure_seed_data()`.

To manually reload seed data:

```bash
docker compose exec api python -c "from app.seed import ensure_seed_data; ensure_seed_data()"
```

---

## Testing

### Running Tests

```bash
# Run all API tests
make api.test

# Run tests in specific file
docker compose exec api pytest tests/test_posts.py

# Run tests with verbose output
docker compose exec api pytest -v

# Run tests with coverage
docker compose exec api pytest --cov=app tests/

# Run tests matching pattern
docker compose exec api pytest -k "test_create"
```

### Writing Tests

Tests are located in `api/tests/`. Example test structure:

```python
# tests/test_posts.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_post():
    """Test creating a new post."""
    response = client.post(
        "/api/post",
        json={
            "title": "Test Post",
            "description": "Test description"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Post"
```

### Test Database

Tests use a separate test database. Configuration is in `api/tests/conftest.py`.

---

## Code Quality

### Formatting

```bash
# Format Python code (Black + isort)
make fmt

# Manual formatting
docker compose exec api black app/
docker compose exec api isort app/
```

### Linting

```bash
# Lint Python code
docker compose exec api flake8 app/

# Type checking
docker compose exec api mypy app/
```

### Pre-commit Hooks

The project uses pre-commit hooks for automated checks:

```bash
# Install pre-commit (if working locally outside Docker)
pip install pre-commit
pre-commit install

# Run pre-commit manually
pre-commit run --all-files
```

---

## Debugging

### Viewing Logs

```bash
# All services
make logs

# Specific service
docker compose logs -f api
docker compose logs -f web

# Last 100 lines
docker compose logs --tail=100 api
```

### Interactive Debugging

#### Python (API)

Add breakpoint in code:

```python
# In your code
import pdb; pdb.set_trace()
```

Then attach to the container:

```bash
docker compose exec api python -m pdb
```

#### JavaScript (Web)

Use browser DevTools or add:

```javascript
debugger;
```

### Database Debugging

```bash
# View active connections
docker compose exec db psql -U appuser -d appdb -c "SELECT * FROM pg_stat_activity;"

# View table structure
docker compose exec db psql -U appuser -d appdb -c "\d posts"

# Query data
docker compose exec db psql -U appuser -d appdb -c "SELECT * FROM posts LIMIT 10;"
```

### MQTT Debugging

```bash
# Subscribe to all topics
docker compose exec mqtt mosquitto_sub -h localhost -t '#' -v

# Subscribe to specific topic
docker compose exec mqtt mosquitto_sub -h localhost -t 'makapix/posts/new'

# Publish test message
docker compose exec mqtt mosquitto_pub -h localhost -t 'test/topic' -m 'Hello'
```

---

## Contributing

### Code Style

- **Python**: Follow PEP 8, use Black for formatting
- **JavaScript/TypeScript**: Follow project ESLint config
- **SQL**: Use lowercase for keywords, snake_case for identifiers
- **Commits**: Use clear, descriptive commit messages

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and commit
git add .
git commit -m "Description of changes"

# Push to remote
git push origin feature/your-feature-name

# Create pull request on GitHub
```

### Pull Request Checklist

Before submitting a PR:

- [ ] Code follows project style guidelines
- [ ] Tests added for new functionality
- [ ] All tests pass (`make api.test`)
- [ ] Code formatted (`make fmt`)
- [ ] Documentation updated if needed
- [ ] Database migrations created if schema changed
- [ ] No secrets or credentials committed

### Adding New Dependencies

#### Python Dependencies

```bash
# Add to requirements.txt
docker compose build api worker
docker compose up -d
```

#### Node Dependencies

```bash
# Add via npm
docker compose exec web npm install package-name

# Rebuild container to persist
docker compose build web
docker compose up -d web
```

---

## Troubleshooting

### Common Issues

#### Port Already in Use

```bash
# Find process using port
lsof -i :3000
lsof -i :8000

# Kill process
kill -9 <PID>
```

#### Database Connection Errors

```bash
# Restart database
docker compose restart db

# Check database logs
docker compose logs db
```

#### Hot Reload Not Working

```bash
# Restart service
docker compose restart api
docker compose restart web
```

#### Volume Permission Issues

```bash
# Fix vault permissions
sudo chown -R $(id -u):$(id -g) ./vault
```

### Getting Help

- Check existing documentation in `/docs`
- Review the [Full Specification](../makapix_full_project_spec.md)
- Look for similar issues in GitHub
- Ask in project discussions

---

## Additional Resources

- **[Architecture Documentation](ARCHITECTURE.md)** - System design details
- **[Deployment Guide](DEPLOYMENT.md)** - Production deployment
- **[Physical Player Guide](PHYSICAL_PLAYER.md)** - Hardware integration
- **[API Documentation](http://localhost:8000/docs)** - Interactive API reference
- **[Roadmap](ROADMAP.md)** - Project milestones

---

Happy coding! 🎨

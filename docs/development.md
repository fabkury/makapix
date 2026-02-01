# Development

Local development setup and workflow.

## Prerequisites

- Docker and Docker Compose
- Git
- Make

## Quick Start

```bash
# Clone repository
git clone https://github.com/fabkury/makapix.git /opt/makapix-dev
cd /opt/makapix-dev

# Checkout develop branch
git checkout develop

# Start services
make up

# View logs
make logs
```

Access at: https://development.makapix.club

## Directory Structure

```
/opt/makapix-dev/
├── api/                  # FastAPI backend
│   ├── app/              # Application code
│   │   ├── routers/      # API endpoints
│   │   ├── services/     # Business logic
│   │   ├── mqtt/         # Player communication
│   │   ├── models.py     # Database models
│   │   ├── schemas.py    # Pydantic schemas
│   │   └── main.py       # Application entry
│   ├── tests/            # Pytest test suite
│   └── alembic/          # Database migrations
├── web/                  # Next.js frontend
│   ├── src/pages/        # Page components
│   ├── src/components/   # React components
│   └── src/lib/          # Utilities
├── worker/               # Celery background tasks
├── mqtt/                 # Mosquitto configuration
│   ├── config/           # Broker config
│   └── certs/            # TLS certificates
├── deploy/stack/         # Docker Compose files
├── docs/                 # Documentation
└── Makefile              # Development commands
```

## Make Commands

### Service Management

```bash
make up              # Start all services
make down            # Stop all services
make restart         # Restart all services
make rebuild         # Rebuild containers and restart
make deploy          # Pull latest code and rebuild
make ps              # Show container status
```

### Logs

```bash
make logs            # All services (follow mode)
make logs-api        # API only
make logs-web        # Web only
make logs-db         # Database only
```

### Development

```bash
make test            # Run API tests
make fmt             # Format Python code (Black)
make shell-api       # Open shell in API container
make shell-db        # Open PostgreSQL shell
```

## Running Tests

```bash
# All tests
make test

# Specific file
cd deploy/stack && docker compose exec api pytest tests/test_posts.py

# By name pattern
cd deploy/stack && docker compose exec api pytest -k "test_upload"

# With coverage
cd deploy/stack && docker compose exec api pytest -v --cov=app
```

## Database Operations

### Shell Access

```bash
make shell-db
# or
make db.shell
```

### Migrations

```bash
# Create new migration
cd deploy/stack && docker compose exec api \
  alembic revision --autogenerate -m "add user preferences"

# Apply migrations
cd deploy/stack && docker compose exec api alembic upgrade head

# Rollback one migration
cd deploy/stack && docker compose exec api alembic downgrade -1

# Show current revision
cd deploy/stack && docker compose exec api alembic current
```

Migrations run automatically on API startup.

## Container Access

```bash
# API container (Python)
cd deploy/stack && docker compose exec api bash

# Web container (Node)
cd deploy/stack && docker compose exec web sh

# Database container
cd deploy/stack && docker compose exec db psql -U owner -d makapix
```

## Code Style

### Python

- Formatter: Black (line length 88)
- Linter: Ruff (rules: E, F, I, B)

```bash
# Format all Python
make fmt

# Or manually
cd deploy/stack && docker compose exec api black .
```

### TypeScript

- Linter: ESLint (next/core-web-vitals)
- Formatter: Prettier

```bash
# Inside web container
npm run lint
npm run format
npm run typecheck
```

## Environment Variables

Configuration in `deploy/stack/.env.dev`:

| Variable | Description |
|----------|-------------|
| `DB_*` | Database credentials |
| `MQTT_*` | MQTT broker settings |
| `VAULT_*` | Image storage paths |
| `MAKAPIX_*` | Admin credentials |
| `GITHUB_*` | OAuth credentials |

## Deployment Workflow

### Development to Production

1. Develop and test in `/opt/makapix-dev`:

```bash
# Make changes
make rebuild
# Test at development.makapix.club
```

2. Push to develop branch:

```bash
git add .
git commit -m "feat: add feature"
git push origin develop
```

3. Create pull request on GitHub:

```bash
make deploy-to-prod
# Opens: https://github.com/fabkury/makapix/compare/main...develop
```

4. Merge PR on GitHub

5. Deploy to production:

```bash
cd /opt/makapix
make deploy
```

### Syncing with Remote

```bash
# Pull latest develop
make sync

# Or manually
git fetch origin
git pull origin develop
```

## Troubleshooting

### Services Won't Start

```bash
# Check status
make ps

# View logs
make logs

# Rebuild from scratch
make down
make rebuild
```

### Database Issues

```bash
# Reset database (DESTRUCTIVE)
make clean  # Warning: 10 second delay before execution

# Or manually
cd deploy/stack && docker compose down -v
make up
```

### API Not Responding

```bash
# Check health
curl http://localhost:8000/health

# View API logs
make logs-api

# Restart API only
cd deploy/stack && docker compose restart api
```

### MQTT Connection Issues

```bash
# Check MQTT broker
cd deploy/stack && docker compose logs mqtt

# Verify certificates exist
ls -la mqtt/certs/
```

## Adding New Features

### New API Endpoint

1. Create router in `api/app/routers/`:

```python
# api/app/routers/feature.py
from fastapi import APIRouter, Depends
from ..db import get_db

router = APIRouter(prefix="/feature", tags=["feature"])

@router.get("/")
def list_features(db: Session = Depends(get_db)):
    return {"items": []}
```

2. Register in `api/app/main.py`:

```python
from .routers import feature
app.include_router(feature.router, prefix="/api")
```

### New Database Model

1. Add model to `api/app/models.py`
2. Create migration:

```bash
cd deploy/stack && docker compose exec api \
  alembic revision --autogenerate -m "add feature table"
```

3. Apply migration:

```bash
cd deploy/stack && docker compose exec api alembic upgrade head
```

### New Background Task

1. Add task to `api/app/tasks.py`:

```python
@celery_app.task
def process_feature(item_id: int):
    # Task implementation
    pass
```

2. Call from API:

```python
from .tasks import process_feature
process_feature.delay(item_id)
```

## Useful Docker Commands

```bash
# View all containers
docker ps -a

# Remove unused images
docker image prune

# View container resource usage
docker stats

# Inspect container
docker inspect makapix-dev-api-1
```

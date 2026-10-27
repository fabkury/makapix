# Development

Develop and test Makapix Club using its Docker Compose stack. The standard workflow uses the development checkout at `/opt/makapix-dev`; it is a server environment, not a localhost setup that automatically owns `development.makapix.club`.

## Prerequisites

- Git, Docker Engine with Compose V2, and GNU Make.
- A configured development environment: secrets, database, vault storage, MQTT certificates, and routing. See [Deployment](deployment.md) before starting a fresh installation.
- A shell compatible with the Bash examples below. On Windows, use an appropriate Linux environment for these server commands.

Cloning the repository alone does not create secrets, DNS records, or certificates. The committed environment templates are starting points, not complete production configurations.

## Start an already configured development stack

```bash
cd /opt/makapix-dev
git checkout develop
make up
make ps
make logs-api
```

For the project's hosted development environment, the site is at `https://development.makapix.club`. A separate installation needs its own configured hostname and routing.

The Makefile selects production only when run from `/opt/makapix`; other directories select the development overlay and Compose project. Run Make commands from the repository root.

For service-specific commands, define this helper once in your shell:

```bash
cd /opt/makapix-dev
mpxdev() {
  docker compose --project-directory deploy/stack \
    -f deploy/stack/docker-compose.yml \
    -f deploy/stack/docker-compose.dev.yml \
    --env-file deploy/stack/.env.dev -p makapix-dev "$@"
}
```

This preserves the environment file, overlay, and project name. Bare `docker compose` commands can address the wrong project or fail to find the running services.

## Repository map

| Path | Purpose |
|------|---------|
| `api/app/routers/` | HTTP endpoints |
| `api/app/services/` | Shared business logic |
| `api/app/player_protocol/` | Shared MQTT/HTTPS player schemas |
| `api/app/mqtt/` | MQTT adapters and handlers |
| `api/app/tasks.py` | Celery tasks and schedule |
| `api/tests/` | API tests |
| `api/alembic/` | Database migrations |
| `api/openapi.json` | Committed app-facing API contract |
| `web/src/` | Next.js pages, components, and client utilities |
| `worker/` | Celery container entry point |
| `mqtt/` | Mosquitto configuration and certificate tooling |
| `deploy/stack/` | Compose files and routing configuration |

## Everyday commands

| Command | Purpose |
|---------|---------|
| `make up` / `make down` | Start / stop the selected stack |
| `make rebuild` | Build first, then recreate changed services |
| `make ps` | Show service status |
| `make logs` | Follow all service logs |
| `make logs-api` / `make logs-web` / `make logs-db` | Follow one service |
| `make shell-api` | Open an API container shell |
| `make shell-db` | Open PostgreSQL using the Makefile's configured command |
| `make fmt` | Format Python with Black |
| `make openapi` | Regenerate the committed OpenAPI contract |
| `make check` | Check OpenAPI drift and Python formatting |
| `make test` | Run the API suite in chunks |
| `make check-full` | Run contract/format checks and the full API suite |
| `make e2e` | Run browser tests using `web/.env.e2e` |

Tests write to the configured database, Redis, and broker. Run them against development. `make test` refuses production; run `make check-full` from the development checkout as well.

## Tests and formatting

```bash
make test
mpxdev exec -T api pytest tests/test_posts.py
mpxdev exec -T api pytest -k test_upload
make check-full
```

`make test` uses `api/scripts/run_tests.py` to avoid exhausting memory with one large pytest process. Prefer it for the full suite.

For frontend checks, install the dependencies in the `web` working copy, then use its package scripts:

```bash
cd web
npm ci
npm run lint
npm run typecheck
```

`npm run format` rewrites files with Prettier; review its diff before committing. Use the Compose/Make build workflow for the deployed frontend rather than running a standalone build in a live checkout.

## Database migrations

From the repository root, with the `mpxdev` helper defined:

```bash
mpxdev exec api alembic revision --autogenerate -m "add user preferences"
# Review the generated migration before applying it.
mpxdev exec api alembic upgrade head
mpxdev exec api alembic current
```

The API startup also applies migrations. Review compatibility before deploying: checking out old code does not reverse a schema migration. A deliberate `alembic downgrade -1` requires a compatible downgrade and a recovery plan.

## Add an API endpoint

Create a router, using `deps.get_db` for the database dependency:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..deps import get_db

router = APIRouter(prefix="/feature", tags=["Feature"])

@router.get("/")
def list_features(db: Session = Depends(get_db)):
    return {"items": []}
```

Register app-facing routers in the versioned router list in `api/app/main.py`. Caddy strips `/api`; FastAPI mounts those routers at `/v1`. Device endpoints use their separate unversioned contract. See [API versioning](api-versioning-policy.md).

Add appropriate tests, run `make openapi` for contract changes, and commit the updated schema. Background tasks live in `api/app/tasks.py` and are enqueued with `.delay(...)`.

## Development to production

1. Make and review changes in development.
2. Run the relevant checks, including `make check-full` before an application merge/deployment.
3. Commit and push to `develop`, then open a `develop` → `main` pull request. `make deploy-to-prod` opens the comparison page; it does not deploy.
4. After merging, use the [production update procedure](deployment.md#updates-and-rollback).

`make install-hooks` installs the repository's pre-push contract/format hook. The project uses these local checks rather than cloud CI.

## Troubleshooting

```bash
make ps
make logs-api
mpxdev logs --tail=100 mqtt
mpxdev restart api
curl https://development.makapix.club/api/health
```

Check environment configuration, mount paths, DNS, and service logs before resetting data. `make clean` removes containers and Compose-managed volumes for the selected environment; it is destructive and is not a routine troubleshooting step.

See [Deployment](deployment.md) for operations and [Architecture](architecture.md) for service relationships.

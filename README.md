# Makapix Dev Environment

A batteries-included Docker-based development environment for the Makapix social network prototype. It is optimised for first-time contributors: one command to boot the full stack, consistent tooling, hot reload, and docs that explain what’s happening.

## Quickstart

1. Install Docker (with Compose) and Visual Studio Code.
2. Clone this repo and copy the defaults:

   ```bash
   cp .env.example .env
   ```

3. Generate MQTT certificates (first boot only happens automatically when the container starts) and start everything:

   ```bash
   docker compose up -d
   ```

4. Tail logs or run helpers from the `Makefile`, e.g. `make logs`, `make api.test`.
5. Visit http://localhost to see the Next.js UI proxied through Caddy. The API is available at http://localhost/api.

For a deeper walkthrough (VS Code devcontainer, debugging, troubleshooting) read [`docs/dev-quickstart.md`](docs/dev-quickstart.md).

## Stack Overview

| Service | Tech | Purpose |
| --- | --- | --- |
| `proxy` | Caddy | Fronts the stack at `http://localhost`, reverse proxies `/api/*`, handles WebSockets/HMR. |
| `web` | Node 20 + Next.js 14 | SSR and client UI. Hot reload + TypeScript strictness. |
| `api` | Python 3.12 + FastAPI | Auth placeholder, posts/comments scaffold, MQTT + Celery endpoints. |
| `worker` | Celery (Redis broker) | Background tasks; demo hash job. Shares code with API. |
| `db` | PostgreSQL 16 | Application database with named volume + init scripts. |
| `cache` | Redis 7 | Cache + Celery broker/result backend. |
| `mqtt` | Eclipse Mosquitto | MQTT broker with dev TLS (self-signed) and WebSocket listener. |

## Developer Experience Highlights

- **Hot reload everywhere**: bind-mounted code for API, worker, and web.
- **One-command tooling**: `Makefile` wraps common compose invocations.
- **Testing**: `make api.test` runs pytest in the `test` profile.
- **Formatting/linting**: Python via Ruff+Black, TypeScript via ESLint+Prettier.
- **Pre-commit**: automatically installed in the devcontainer.
- **Docs & diagrams**: architecture notes in [`docs/architecture.md`](docs/architecture.md).

## Smoke Test

After `docker compose up -d`, run these commands from the repo root to verify each component:

```bash
# API health
curl -s http://localhost/api/healthz
# → {"status":"ok"}

# Create a post (persists to Postgres)
curl -s -X POST http://localhost/api/posts \
  -H "Content-Type: application/json" \
  -d '{"title":"Smoke Test","body":"Created from README smoke test."}'
# → {"id":2,"title":"Smoke Test","body":"Created from README smoke test.","created_at":"2025-10-25T12:00:00+00:00"}

# Queue a Celery job
curl -s -X POST http://localhost/api/tasks/hash-url \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.org"}'
# → {"task_id":"<uuid>"}

# Publish to MQTT demo topic (retained)
curl -s -X POST http://localhost/api/mqtt/demo
# → {"status":"sent","topic":"posts/new/demo"}
```

Then open http://localhost/demo to watch the WebSocket MQTT client receive the retained message. The page can also publish again via the same API endpoint.

## Next Steps

- Explore [`docs/dev-quickstart.md`](docs/dev-quickstart.md) for detailed workflows.
- Read [`docs/architecture.md`](docs/architecture.md) to understand how services interact.
- Use `make fmt` before commits to keep formatting consistent.
- For debugging, use the VS Code launch configurations installed by the devcontainer.

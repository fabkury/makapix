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

# Test GitHub OAuth login (redirects to GitHub)
curl -s -I http://localhost/api/auth/github/login
# → 307 redirect to GitHub

# List posts (public endpoint)
curl -s http://localhost/api/posts
# → {"items":[...],"next_cursor":null}

# Test authenticated endpoints (requires GitHub OAuth setup)
# First, visit http://localhost/api/auth/github/login to get a JWT token
# Then use the token:
# TOKEN="your_jwt_token_here"
# curl -H "Authorization: Bearer $TOKEN" http://localhost/api/auth/me
# curl -H "Authorization: Bearer $TOKEN" -X POST http://localhost/api/posts \
#   -H "Content-Type: application/json" \
#   -d '{"title":"Test Art","art_url":"https://example.com/test.png","canvas":"64x64","file_kb":32}'

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

**Note**: For full authentication testing, you need to set up GitHub OAuth credentials in your `.env` file. See [docs/dev-quickstart.md](docs/dev-quickstart.md) for detailed setup instructions.

## Production Deployment

This repository is **production-ready**! To deploy to https://makapix.club:

1. **Quick Start**: See [`DEPLOY.md`](DEPLOY.md) for condensed deployment steps
2. **Full Guide**: See [`docs/production-deployment.md`](docs/production-deployment.md) for complete instructions
3. **Checklist**: Use [`docs/deployment-checklist.md`](docs/deployment-checklist.md) for step-by-step verification
4. **Status**: See [`docs/PRODUCTION-READY.md`](docs/PRODUCTION-READY.md) for implementation details

### Key Changes for Production

- **SSL/TLS**: Automatic certificate management via Let's Encrypt (Caddy)
- **Domain**: Configured for https://makapix.club
- **Environment**: All URLs configurable via environment variables
- **Security**: Production credentials in `.env` (not committed)
- **GitHub**: OAuth and App configured for production callbacks

## Next Steps

- Explore [`docs/dev-quickstart.md`](docs/dev-quickstart.md) for detailed workflows.
- Read [`docs/architecture.md`](docs/architecture.md) to understand how services interact.
- Use `make fmt` before commits to keep formatting consistent.
- For debugging, use the VS Code launch configurations installed by the devcontainer.

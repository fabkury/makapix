# Architecture Overview

## High-Level Diagram

```
┌────────┐    ┌────────┐     ┌───────────┐
│  web   │    │  api   │     │  worker   │
│ Next.js│───▶│FastAPI │◀────│ Celery    │
└──┬──▲──┘    └──┬──▲──┘     └───────────┘
   │  │          │  │
   │  │          │  └────────────┐
   │  │          │               │
   ▼  │          ▼               ▼
┌─────┴────┐ ┌──────────┐ ┌──────────┐
│  proxy   │ │ Postgres │ │  Redis   │
│  Caddy   │ │   db     │ │  cache   │
└─────┬────┘ └──────────┘ └──────────┘
      │
      ▼
┌──────────┐
│ Mosquitto│
│  MQTT    │
└──────────┘
```

- Caddy is the single ingress point on `http://localhost`.
- Web (Next.js) serves SSR pages and client assets; it calls the API via the proxy.
- API handles REST endpoints, runs Alembic migrations at startup, publishes to MQTT, and enqueues Celery jobs.
- Worker shares the API application package and executes Celery tasks.
- Postgres stores relational data (currently the `posts` table).
- Redis is both cache placeholder and Celery broker/result backend.
- Mosquitto exposes TLS MQTT on 8883 and WebSockets on 9001 for the browser demo.

## Service Notes

### API & Worker

- Single Python package (`app`) shared between API and worker containers by bind mount.
- Startup hook runs `alembic upgrade head` and `app.seed.ensure_seed_data()`; makes first boot idempotent.
- Celery task `hash_url` streams response bodies and caps download size to 1 MB to keep dev environments safe.

### Web

- Next.js 14 with TypeScript and ESLint strict mode.
- `/` SSR health check page demonstrates server-side calls via internal URL.
- `/demo` uses `mqtt` npm package over WebSockets to subscribe to `posts/new/demo` and triggers the API MQTT publisher.

### Messaging

- Mosquitto TLS certificates generated automatically via `mqtt/scripts/gen-certs.sh`.
- `aclfile` keeps demo simple: anonymous access allowed but limited to `posts/new/#`.
- For browsers, WebSocket port 9001 is plaintext; the docs highlight that TLS is still enforced for device endpoints on 8883.

### Proxy

- Caddy proxies `/api/*` to FastAPI and everything else to Next.js.
- Handles CORS preflight and WebSocket upgrades for both Uvicorn and Next.js HMR.
- Healthcheck endpoint `/proxy-healthz` is defined for Compose.

### Tooling

- Devcontainer uses Docker-outside-of-Docker to reuse host engine.
- Pre-commit ensures formatting; Make targets mirror common workflows (`up`, `down`, `fmt`, `api.test`, `db.reset`).
- `.editorconfig` enforces LF, UTF-8, and trimmed whitespace across editors.

## Data Flow Examples

1. **Create Post**
   - Web client POST `/api/posts` (through Caddy).
   - FastAPI validates payload, stores via SQLAlchemy.
   - Response includes persisted post.

2. **Hash URL Task**
   - API enqueues Celery task via Redis broker.
   - Worker downloads target URL (size-capped), hashes content, stores result in Redis backend.
   - Client polls Celery if needed (not implemented in demo but supports `AsyncResult`).

3. **MQTT Demo**
   - API publishes retained JSON payload on `posts/new/demo` using TLS to Mosquitto.
   - Browser Next.js page (via WebSockets) receives retained message and displays it.

This architecture is minimal yet mirrors production concerns: reverse proxy, background jobs, messaging, and shared code between synchronous and asynchronous workers.

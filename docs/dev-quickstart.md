# Developer Quickstart

## Prerequisites

- Docker Desktop (or Docker Engine + Compose v2) with enough resources (4 CPU / 6 GB RAM recommended).
- Visual Studio Code with the “Dev Containers” extension **or** a terminal with Make.
- Optional: `mkcert` or similar if you want to trust the generated MQTT CA.

## First Run

1. **Clone & configure**

   ```bash
   git clone https://github.com/your-org/makapix-dev.git
   cd makapix-dev
   cp .env.example .env
   ```

2. **Set up GitHub OAuth (required for authentication)**

   To enable user authentication, you need to create a GitHub OAuth App:
   
   a. Go to https://github.com/settings/developers
   b. Click "New OAuth App"
   c. Configure:
      - **Application name**: Makapix (Local Development)
      - **Homepage URL**: http://localhost
      - **Authorization callback URL**: http://localhost/auth/github/callback
   d. Save the **Client ID** and generate a **Client Secret**
   e. Update your `.env` file with the credentials:
      ```env
      GITHUB_CLIENT_ID=your_client_id_here
      GITHUB_CLIENT_SECRET=your_client_secret_here
      GITHUB_REDIRECT_URI=http://localhost/auth/github/callback
      
      # JWT Configuration (generate a secure random key)
      JWT_SECRET_KEY=your_secure_random_key_here
      JWT_ALGORITHM=HS256
      JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
      JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
      ```

2. **Boot the stack**

   ```bash
   docker compose up -d
   ```

   Compose will build images, generate Mosquitto TLS certificates on first boot, run database init scripts, migrate, and seed data via the API startup hook.

3. **Watch logs**

   ```bash
   make logs
   ```

   Press `Ctrl+C` to detach. Individual service logs (`docker compose logs api`) are also useful.

4. **Test authentication flow**

   a. Visit http://localhost/auth/github/login to test GitHub OAuth
   b. After authorizing with GitHub, you should be redirected back with a JWT token
   c. Test the API with authentication:
      ```bash
      # Get your JWT token from the OAuth callback
      TOKEN="your_jwt_token_here"
      
      # Test authenticated endpoints
      curl -H "Authorization: Bearer $TOKEN" http://localhost/api/auth/me
      curl -H "Authorization: Bearer $TOKEN" http://localhost/api/posts
      
      # Create a test post
      curl -X POST -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"title":"Test Art","art_url":"https://example.com/test.png","canvas":"64x64","file_kb":32}' \
        http://localhost/api/posts
      ```

5. **Run tests**

   ```bash
   make api.test
   ```

6. **Lint/format**

   ```bash
   make fmt
   make web.lint
   ```

## VS Code Devcontainer

1. Open the folder in VS Code.
2. Use `Dev Containers: Reopen in Container`.
3. The devcontainer mounts the repo at `/workspace`, reuses the `docker-compose.yml`, and installs:
   - Python 3.12, Node 20
   - Docker CLI (socket shared from host)
   - Extensions: Python, Pylance, Ruff, ESLint, Prettier, Docker, GitHub Actions, Markdown
4. `postCreate.sh` runs automatically: installs Python deps (`pip install -e ./api[dev]`), runs `npm install` in `web`, and installs pre-commit hooks.

### Debugging

- **API (FastAPI/Uvicorn)**: Use the “Attach to API (Uvicorn)” launch config (attaches to port 5678 exposed by `debugpy`, enabled via `UVICORN_CMD` overrides if needed).
- **Pytest**: “Debug API Tests” runs `pytest` with the VS Code debugger.
- **Web (Next.js)**: “Attach to Next.js dev server” attaches to the Node inspector at port 9229 (exposed when running `npm run dev -- --inspect`).

## Common Workflows

### Database resets

```bash
make db.reset
```

Stops API/worker, drops the Postgres volume, recreates the database, reruns Alembic migrations, and reseeds via `app.seed`.

### Seeding & migrations

- Create new migrations with:

  ```bash
  docker compose run --rm api alembic revision -m "add comments table"
  ```

- Apply migrations:

  ```bash
  docker compose run --rm api alembic upgrade head
  ```

- Seed additional data:

  ```bash
  make seed
  ```

### Celery worker autoscale

Change concurrency in `docker-compose.yml` or run:

```bash
docker compose exec worker celery control autoscale 4 1
```

### MQTT WebSocket demo

1. Ensure `mqtt` service is running (`docker compose ps mqtt`).
2. Open http://localhost/demo — the page auto-subscribes to `posts/new/demo`.
3. Use the “Publish MQTT Demo” button or CLI:

   ```bash
   docker compose exec mqtt mosquitto_pub \
     -h localhost -p 9001 -t posts/new/demo -m '{"title":"CLI Event"}' --protocol-version 5
   ```

## Troubleshooting

- **Caddy healthcheck failing**: ensure port 80 is free; stop other web servers (IIS/Apache).
- **MQTT TLS errors**: copy `mqtt/certs/ca.crt` to your system trust store if you want to connect externally. Inside Docker the API/worker mount `/certs`.
- **Node modules missing**: `npm install` runs on container start, but you can force reinstall via `docker compose run --rm web npm install`.
- **Postgres migration race**: the API runs Alembic on startup; if you see a race condition, restart `api` after `db` is healthy.

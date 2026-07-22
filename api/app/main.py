from __future__ import annotations

import asyncio
import logging
import mimetypes
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse

from .routers import (
    admin,
    artwork,
    auth,
    badges,
    blog_posts,
    categories,
    comment_likes,
    comments,
    licenses,
    me,
    mqtt,
    player,
    player_rpc,
    playlists,
    pmd,
    posts,
    reactions,
    realtime,
    reports,
    reputation,
    search,
    sitemap,
    social_notifications,
    stats,
    system,
    tracking,
    umd,
    users,
)
from .seed import ensure_seed_data
from .errors import register_exception_handlers
from .middleware import RequestIdMiddleware, SecurityHeadersMiddleware
from .vault_serving import LegacyShardFallbackStaticFiles

load_dotenv()

# Fail fast on missing required configuration: every generated asset URL
# depends on VAULT_PUBLIC_BASE_URL (the /api/vault fallback mount is gone),
# so a misconfigured deployment must refuse to start rather than mint dead
# URLs. The call raises RuntimeError when the variable is unset.
from .settings import vault_public_base_url  # noqa: E402

vault_public_base_url()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Initialise error monitoring as early as possible so import/startup failures
# are captured too. No-op unless SENTRY_DSN is set.
from .observability import init_sentry  # noqa: E402

init_sentry("api")

_STARTUP_COMPLETE = False


def run_migrations() -> None:
    logger.info("run_migrations: Starting...")
    # Under pytest the schema is built directly from the models (conftest
    # create_all) against the isolated makapix_test DB. Alembic's configured URL
    # points at the LIVE (admin) database, so running it here would apply any
    # unapplied working-tree migration to the live DB via admin creds — exactly
    # the surprise the deploy flow exists to prevent. Skip entirely under test.
    if os.getenv("TEST_DATABASE_URL"):
        logger.info("run_migrations: TEST_DATABASE_URL set — skipping (test schema).")
        return
    try:
        logger.info("Running Alembic migrations...")
        alembic_cfg = _alembic_config()

        # Check current revision first to avoid unnecessary upgrade calls
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from .db import engine

        try:
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                # Use get_current_heads() instead of get_current_revision() when there are multiple heads
                current_heads = context.get_current_heads()
                if not current_heads:
                    current_rev = None
                else:
                    # If multiple heads, check if any of them match the available heads
                    current_rev = current_heads[0] if len(current_heads) == 1 else None

                script = ScriptDirectory.from_config(alembic_cfg)
                heads = script.get_heads()

                # If we have a single current revision and it's in heads, we're up to date
                if current_rev and current_rev in heads:
                    logger.info(
                        f"Database is up to date (revision: {current_rev}), skipping migrations."
                    )
                    return

                # Multiple heads = divergent migration branches. Do NOT guess
                # which to apply: many revision ids are random hex (they sort to
                # 0), so the old max()-by-prefix pick was arbitrary and could
                # deploy a schema the running code doesn't expect. Fail loudly so
                # the operator creates an explicit merge revision.
                if len(heads) > 1:
                    raise RuntimeError(
                        f"Refusing to auto-migrate: multiple Alembic heads {heads}. "
                        "Divergent migration branches must be merged explicitly. "
                        f"Run: alembic merge -m 'merge heads' {' '.join(heads)} "
                        "then commit the merge revision and redeploy."
                    )
                target_rev = heads[0]

                logger.info(
                    f"Current revision(s): {current_heads}, Target revision: {target_rev}. Running migrations..."
                )
        finally:
            # Ensure connection is closed before calling command.upgrade
            engine.dispose()

        # Now run migrations with a fresh connection pool
        command.upgrade(alembic_cfg, target_rev)
        logger.info("run_migrations: command.upgrade() returned")
        logger.info("run_migrations: Completed successfully.")
    except Exception as e:
        logger.error(f"run_migrations: Error occurred: {e}", exc_info=True)
        raise


def _alembic_config() -> Config:
    base_dir = Path(__file__).resolve().parent.parent
    cfg = Config(str(base_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(base_dir / "alembic"))
    return cfg


def run_startup_tasks() -> None:
    global _STARTUP_COMPLETE
    logger.info("run_startup_tasks: Starting...")
    if _STARTUP_COMPLETE:
        logger.info("run_startup_tasks: Already completed, skipping.")
        return
    try:
        logger.info("run_startup_tasks: Running migrations...")
        run_migrations()
        logger.info("run_startup_tasks: Migrations completed, running seed data...")
        ensure_seed_data()
        logger.info("run_startup_tasks: Seed data completed, ensuring CRL exists...")
        # Initialize empty CRL if it doesn't exist
        from .mqtt.crl_init import ensure_crl_exists

        ensure_crl_exists()
        logger.info("run_startup_tasks: CRL ensured, verifying CA keypair...")
        # Defense-in-depth: surface a ca.key/ca.crt mismatch loudly at boot.
        # Non-fatal — signing is independently guarded in generate_client_certificate.
        from .mqtt.cert_generator import check_ca_keypair

        check_ca_keypair()
        _STARTUP_COMPLETE = True
        logger.info("Startup tasks completed.")
    except Exception as e:
        logger.error(f"Startup tasks failed: {e}", exc_info=True)
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting application...")
    # Run startup tasks synchronously - server won't start until these complete
    run_startup_tasks()
    from .services import player_events

    # Hand the running loop to the in-process bus so MQTT callbacks can
    # forward events to SSE subscribers from their worker threads.
    player_events.set_loop(asyncio.get_running_loop())

    # Skip the MQTT subscribers under pytest: every test spins up the app
    # lifespan, so starting four real paho clients per test made the broker a
    # hard test dependency and churned connections (the OOM the chunk runner
    # papers over). The MQTT handlers are unit-tested directly.
    if not os.getenv("TEST_DATABASE_URL"):
        from .mqtt.player_status import start_status_subscriber
        from .mqtt.player_requests import start_request_subscriber
        from .mqtt.player_views import start_view_subscriber
        from .mqtt.player_optional import start_optional_subscriber

        start_status_subscriber()
        start_request_subscriber()
        start_view_subscriber()
        start_optional_subscriber()
    logger.info("Makapix API server ready")
    yield
    # Shutdown
    logger.info("Shutting down application...")
    # Stop MQTT subscribers
    from .mqtt.player_status import stop_status_subscriber
    from .mqtt.player_requests import stop_request_subscriber
    from .mqtt.player_optional import stop_optional_subscriber
    from .mqtt.publisher import stop_publisher

    stop_status_subscriber()
    stop_request_subscriber()
    stop_optional_subscriber()
    stop_publisher()


app = FastAPI(
    title="Makapix API",
    version="1.0.0",
    description="Lightweight pixel-art social network API",
    lifespan=lifespan,
    # The app sits behind Caddy, which strips the public `/api` prefix
    # (handle_path /api/*). Declaring `/api` as the OpenAPI server base means a
    # generated client composes `/api` + `/v1/...` = `/api/v1/...` correctly.
    servers=[{"url": "/api", "description": "Public API base (Caddy strips /api)"}],
    # Publish the contract and docs under the versioned path.
    openapi_url="/v1/openapi.json",
    docs_url="/v1/docs",
    redoc_url="/v1/redoc",
)

# Standardized v1 error envelope ({ "error": { code, message, details? } }).
# Scoped to /v1/* paths; non-versioned surfaces keep FastAPI's default shape.
register_exception_handlers(app)

# CORS Configuration - restrict to specific origins
# In production, set CORS_ORIGINS environment variable to comma-separated list of allowed origins
cors_origins_str = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost")
if cors_origins_str == "*":
    logger.warning(
        "CORS is configured to allow all origins. "
        "This is insecure for production. Set CORS_ORIGINS to specific domains."
    )
cors_origins = [origin.strip() for origin in cors_origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
    ],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Add request ID middleware for audit trail correlation
app.add_middleware(RequestIdMiddleware)


# --- App-facing JSON API (versioned) ---
# Canonical mount is `/api/v1/...` (Caddy strips `/api`, so the app sees
# `/v1/...`). Each router is ALSO mounted at the bare root with
# include_in_schema=False as a one-release transition safety net while the web
# client migrates to `/api/v1`; the bare-root copies are removed once web is
# fully on v1. Only `/v1/*` paths get the new error envelope (see errors.py).
_V1_ROUTERS = [
    system.router,
    auth.router,
    users.router,
    artwork.router,
    posts.router,
    blog_posts.router,
    playlists.router,
    comments.router,
    comment_likes.router,
    reactions.router,
    social_notifications.router,
    reports.router,
    badges.router,
    licenses.router,
    reputation.router,
    categories.router,
    admin.router,
    search.router,
    stats.router,
    tracking.router,
    realtime.router,
    me.router,
]
for _router in _V1_ROUTERS:
    app.include_router(_router, prefix="/v1")
    app.include_router(_router, include_in_schema=False)  # legacy root (transition)

# --- Hardware/player + web-infra surfaces (unversioned, separate contracts) ---
# Physical players reach these via `/api/...` and must NOT move under `/v1`.
app.include_router(player.router)
app.include_router(player_rpc.router)
app.include_router(mqtt.router)
app.include_router(pmd.router)
app.include_router(umd.router)
app.include_router(sitemap.router)


# Register MIME types not present in all Docker base images.
# Without this, StaticFiles serves unknown extensions as text/plain, which browsers
# reject when X-Content-Type-Options: nosniff is set.
mimetypes.add_type("image/webp", ".webp")

# Mount vault directory for serving uploaded artwork images
# Note: Caddy strips /api prefix, so mount at /vault (requests arrive as /vault/...)
# LegacyShardFallbackStaticFiles keeps legacy 3-level URLs valid (D16).
vault_location = os.environ.get("VAULT_LOCATION")
if vault_location:
    vault_path = Path(vault_location)
    if vault_path.exists():
        app.mount(
            "/vault",
            LegacyShardFallbackStaticFiles(directory=str(vault_path)),
            name="vault",
        )
        logger.info(f"Mounted vault at /vault from {vault_location}")
    else:
        # Create the vault directory if it doesn't exist
        vault_path.mkdir(parents=True, exist_ok=True)
        app.mount(
            "/vault",
            LegacyShardFallbackStaticFiles(directory=str(vault_path)),
            name="vault",
        )
        logger.info(f"Created and mounted vault at /vault from {vault_location}")

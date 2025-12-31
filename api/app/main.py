from __future__ import annotations

import logging
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
from fastapi.staticfiles import StaticFiles

from .routers import (
    admin,
    artwork,
    auth,
    badges,
    blog_posts,
    categories,
    comments,
    legacy,
    mqtt,
    player,
    playlists,
    posts,
    profiles,
    reactions,
    relay,
    reports,
    reputation,
    search,
    social_notifications,
    stats,
    system,
    tracking,
    users,
)
from .seed import ensure_seed_data
from .middleware import SecurityHeadersMiddleware

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

_STARTUP_COMPLETE = False


def run_migrations() -> None:
    logger.info("run_migrations: Starting...")
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
                    logger.info(f"Database is up to date (revision: {current_rev}), skipping migrations.")
                    return
                
                # If multiple heads, upgrade to the latest one (highest revision number)
                if len(heads) > 1:
                    logger.info(f"Multiple heads detected: {heads}. Upgrading to latest...")
                    # Sort heads by revision number and take the latest
                    latest_head = max(heads, key=lambda h: int(h.split('_')[0]) if h.split('_')[0].isdigit() else 0)
                    logger.info(f"Selected latest head: {latest_head}")
                    target_rev = latest_head
                else:
                    target_rev = heads[0]
                
                logger.info(f"Current revision(s): {current_heads}, Target revision: {target_rev}. Running migrations...")
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
    # Start MQTT subscribers
    from .mqtt.player_status import start_status_subscriber
    from .mqtt.player_requests import start_request_subscriber
    from .mqtt.player_views import start_view_subscriber
    start_status_subscriber()
    start_request_subscriber()
    start_view_subscriber()
    logger.info("Makapix API server ready")
    yield
    # Shutdown
    logger.info("Shutting down application...")
    # Stop MQTT subscribers
    from .mqtt.player_status import stop_status_subscriber
    from .mqtt.player_requests import stop_request_subscriber
    stop_status_subscriber()
    stop_request_subscriber()


app = FastAPI(
    title="Makapix API",
    version="1.0.0",
    description="Lightweight pixel-art social network API",
    lifespan=lifespan,
)

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
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)


# Include all routers
app.include_router(system.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(profiles.router)
app.include_router(artwork.router)
app.include_router(posts.router)
app.include_router(blog_posts.router)
app.include_router(playlists.router)
app.include_router(comments.router)
app.include_router(reactions.router)
app.include_router(social_notifications.router)
app.include_router(reports.router)
app.include_router(badges.router)
app.include_router(reputation.router)
app.include_router(player.router)
app.include_router(categories.router)
app.include_router(admin.router)
app.include_router(search.router)
app.include_router(stats.router)
app.include_router(tracking.router)
app.include_router(relay.router)
app.include_router(mqtt.router)
app.include_router(legacy.router)


# Mount vault directory for serving uploaded artwork images
# Note: Caddy strips /api prefix, so mount at /vault (requests arrive as /vault/...)
vault_location = os.environ.get("VAULT_LOCATION")
if vault_location:
    vault_path = Path(vault_location)
    if vault_path.exists():
        app.mount("/vault", StaticFiles(directory=str(vault_path)), name="vault")
        logger.info(f"Mounted vault at /vault from {vault_location}")
    else:
        # Create the vault directory if it doesn't exist
        vault_path.mkdir(parents=True, exist_ok=True)
        app.mount("/vault", StaticFiles(directory=str(vault_path)), name="vault")
        logger.info(f"Created and mounted vault at /vault from {vault_location}")

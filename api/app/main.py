from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    admin,
    auth,
    badges,
    comments,
    devices,
    legacy,
    mqtt,
    playlists,
    posts,
    profiles,
    reactions,
    relay,
    reports,
    reputation,
    search,
    system,
    users,
)
from .seed import ensure_seed_data

load_dotenv()

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Makapix API",
    version="1.0.0",
    description="Lightweight pixel-art social network API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_STARTUP_COMPLETE = False


def _alembic_config() -> Config:
    base_dir = Path(__file__).resolve().parent.parent
    cfg = Config(str(base_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(base_dir / "alembic"))
    return cfg


def run_migrations() -> None:
    logger.info("Running Alembic migrations...")
    command.upgrade(_alembic_config(), "head")


def run_startup_tasks() -> None:
    global _STARTUP_COMPLETE
    if _STARTUP_COMPLETE:
        return
    run_migrations()
    ensure_seed_data()
    _STARTUP_COMPLETE = True
    logger.info("Startup tasks completed.")


@app.on_event("startup")
def on_startup() -> None:
    run_startup_tasks()


# Include all routers
app.include_router(system.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(profiles.router)
app.include_router(posts.router)
app.include_router(playlists.router)
app.include_router(comments.router)
app.include_router(reactions.router)
app.include_router(reports.router)
app.include_router(badges.router)
app.include_router(reputation.router)
app.include_router(devices.router)
app.include_router(admin.router)
app.include_router(search.router)
app.include_router(relay.router)
app.include_router(mqtt.router)
app.include_router(legacy.router)

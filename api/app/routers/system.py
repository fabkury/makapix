"""System endpoints (health, config)."""

from __future__ import annotations

import time

from fastapi import APIRouter

from .. import schemas

router = APIRouter(prefix="", tags=["System"])

# Global startup time for uptime calculation
_STARTUP_TIME = time.time()


@router.get("/health", response_model=schemas.HealthResponse)
def get_health() -> schemas.HealthResponse:
    """
    Liveness & minimal readiness check.
    
    TODO: Add rate limiting headers (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)
    """
    uptime_s = time.time() - _STARTUP_TIME
    return schemas.HealthResponse(status="ok", uptime_s=uptime_s)


@router.get("/config", response_model=schemas.Config)
def get_public_config() -> schemas.Config:
    """
    Public configuration limits for the client.
    
    TODO: Load from environment variables or database
    TODO: Add caching to avoid repeated queries
    """
    return schemas.Config()

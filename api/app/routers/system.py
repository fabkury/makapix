"""System endpoints (health, config)."""

from __future__ import annotations

import time
import logging

from fastapi import APIRouter, HTTPException, status

from .. import schemas
from ..cache import get_redis

router = APIRouter(prefix="", tags=["System"])
logger = logging.getLogger(__name__)

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


@router.get("/health/redis")
def check_redis_health() -> dict:
    """
    Redis health check endpoint.
    
    Returns 200 if Redis is available, 503 if not.
    """
    redis = get_redis()
    if not redis:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis unavailable"
        )
    
    try:
        redis.ping()
        return {"status": "ok", "message": "Redis is available"}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Redis error: {str(e)}"
        )

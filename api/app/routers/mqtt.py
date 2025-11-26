"""MQTT and rate limiting endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, status

from .. import models, schemas
from ..auth import get_current_user
from ..mqtt import publish_demo_message

router = APIRouter(prefix="", tags=["MQTT", "RateLimit"])


@router.get("/mqtt/bootstrap", response_model=schemas.MQTTBootstrap, tags=["MQTT"])
def mqtt_bootstrap() -> schemas.MQTTBootstrap:
    """
    MQTT broker bootstrap info.
    
    TODO: Load from environment variables
    """
    # MQTT_PUBLIC_HOST is what external clients should connect to
    return schemas.MQTTBootstrap(
        host=os.getenv("MQTT_PUBLIC_HOST", os.getenv("MQTT_HOST", "makapix.club")),
        port=int(os.getenv("MQTT_WS_PORT", "9001")),
        tls=False,  # WebSocket port is not TLS
        topics={"new_posts": "posts/new/#"},
    )


@router.post("/mqtt/demo", response_model=schemas.MQTTPublishResponse, tags=["MQTT"])
def mqtt_demo() -> schemas.MQTTPublishResponse:
    """
    Publish demo MQTT message.
    
    TODO: Remove in production or restrict to development environment
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        topic = publish_demo_message()
    except Exception as exc:  # pragma: no cover
        logger.exception("MQTT publish failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to publish MQTT demo message: {exc}",
        ) from exc
    return schemas.MQTTPublishResponse(status="sent", topic=topic)


@router.get("/rate-limit", response_model=schemas.RateLimitStatus, tags=["RateLimit"])
def get_rate_limit(current_user: models.User = Depends(get_current_user)) -> schemas.RateLimitStatus:
    """
    Get caller's rate limit budgets.
    
    TODO: Implement Redis-based rate limiter
    TODO: Return actual bucket status
    TODO: Add rate limit headers to response
    """
    # PLACEHOLDER: Return unlimited
    return schemas.RateLimitStatus(
        buckets={
            "global": schemas.RateLimitBucket(remaining=1000, reset_in_s=3600),
            "posts": schemas.RateLimitBucket(remaining=100, reset_in_s=3600),
        }
    )

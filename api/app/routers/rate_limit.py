"""Rate limiting endpoints.

Formerly ``routers/mqtt.py`` — the browser-facing MQTT endpoints
(``/mqtt/bootstrap``, ``/mqtt/demo``) were deleted when the browser MQTT
path was retired (docs/notification-architecture/); only the rate-limit
placeholder remains.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from .. import models, schemas
from ..auth import get_current_user

router = APIRouter(prefix="", tags=["RateLimit"])


@router.get("/rate-limit", response_model=schemas.RateLimitStatus, tags=["RateLimit"])
def get_rate_limit(
    current_user: models.User = Depends(get_current_user),
) -> schemas.RateLimitStatus:
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

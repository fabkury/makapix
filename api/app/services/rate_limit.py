"""Rate limiting service using Redis."""

from __future__ import annotations

import logging
from ..cache import get_redis_client

logger = logging.getLogger(__name__)


def check_rate_limit(key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
    """
    Check and increment rate limit counter.
    
    Uses Redis INCR with EXPIRE for sliding window rate limiting.
    
    Args:
        key: Redis key for the rate limit counter (e.g., "ratelimit:player:{id}:cmd")
        limit: Maximum number of requests allowed in the window
        window_seconds: Time window in seconds (default: 60)
    
    Returns:
        Tuple of (allowed: bool, remaining: int)
        - allowed: True if request is allowed, False if rate limit exceeded
        - remaining: Number of requests remaining in the current window
    """
    client = get_redis_client()
    
    # If Redis is unavailable, allow the request (fail open)
    if not client:
        logger.warning(f"Redis unavailable, allowing request for key '{key}'")
        return True, limit
    
    try:
        # Get current count
        current = client.get(key)
        count = int(current) if current else 0
        
        # Check if limit exceeded
        if count >= limit:
            return False, 0
        
        # Increment counter
        # Use pipeline for atomic operation
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        results = pipe.execute()
        
        new_count = results[0]
        remaining = max(0, limit - new_count)
        
        return True, remaining
    
    except Exception as e:
        logger.error(f"Rate limit check error for key '{key}': {e}")
        # Fail open - allow request if Redis error
        return True, limit


def get_rate_limit_remaining(key: str, limit: int) -> int:
    """
    Get remaining requests without incrementing counter.
    
    Args:
        key: Redis key for the rate limit counter
        limit: Maximum number of requests allowed
    
    Returns:
        Number of requests remaining
    """
    client = get_redis_client()
    
    if not client:
        return limit
    
    try:
        current = client.get(key)
        count = int(current) if current else 0
        return max(0, limit - count)
    except Exception as e:
        logger.error(f"Rate limit get error for key '{key}': {e}")
        return limit


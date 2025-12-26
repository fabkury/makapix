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


def check_player_view_rate_limit(player_key: str) -> tuple[bool, float | None]:
    """
    Check if player can submit a view (1 per 5 seconds).
    
    Uses Redis SETEX for strict rate limiting with TTL tracking.
    Players are limited to 1 view submission per 5 seconds globally
    (not per artwork).
    
    Args:
        player_key: Player's unique key (UUID as string)
    
    Returns:
        Tuple of (allowed: bool, retry_after: float | None)
        - allowed: True if view submission is allowed, False if rate limited
        - retry_after: Seconds until next submission allowed (only set when blocked)
    """
    client = get_redis_client()
    
    # If Redis is unavailable, allow the request (fail open)
    if not client:
        logger.warning(f"Redis unavailable, allowing view for player '{player_key}'")
        return True, None
    
    try:
        key = f"ratelimit:player_view:{player_key}"
        
        # Check if key exists (player is rate limited)
        if client.exists(key):
            # Get TTL (time remaining until key expires)
            ttl = client.ttl(key)
            retry_after = float(ttl) if ttl > 0 else 0.0
            logger.debug(f"Player {player_key} rate limited, retry after {retry_after}s")
            return False, retry_after
        
        # Set key with 5-second expiry (rate limit window)
        client.setex(key, 5, "1")
        return True, None
    
    except Exception as e:
        logger.error(f"Player view rate limit check error for key '{player_key}': {e}")
        # Fail open - allow request if Redis error
        return True, None


def check_view_duplicate(player_key: str, post_id: int, timestamp: str) -> bool:
    """
    Check if a view event is a duplicate.
    
    Uses Redis to track recent view events and prevent MQTT QoS 1 retransmissions
    from creating duplicate view records. Deduplication key expires after 60 seconds.
    
    Args:
        player_key: Player's unique key (UUID as string)
        post_id: Post ID being viewed
        timestamp: ISO 8601 timestamp from the view event
    
    Returns:
        True if this is a duplicate (should be discarded), False if it's unique
    """
    client = get_redis_client()
    
    # If Redis is unavailable, allow the view (fail open - prefer duplicates over lost data)
    if not client:
        logger.warning(f"Redis unavailable, allowing potentially duplicate view for player '{player_key}'")
        return False
    
    try:
        # Create deduplication key from player + post + timestamp
        dedup_key = f"view_dedup:{player_key}:{post_id}:{timestamp}"
        
        # Check if key exists (this is a duplicate)
        if client.exists(dedup_key):
            logger.debug(f"Duplicate view detected: {dedup_key}")
            return True
        
        # Set key with 60-second expiry (enough time for MQTT retransmissions)
        client.setex(dedup_key, 60, "1")
        return False
    
    except Exception as e:
        logger.error(f"View deduplication check error: {e}")
        # Fail open - allow potentially duplicate view
        return False


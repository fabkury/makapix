"""Rate limiting service using Redis with in-memory fallback."""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Tuple

from ..cache import get_redis_client

logger = logging.getLogger(__name__)

# In-memory fallback rate limiter for when Redis is unavailable.
# This provides basic rate limiting protection during Redis outages.
# Structure: {key: (count, window_start_time)}
_fallback_cache: Dict[str, Tuple[int, float]] = {}
_fallback_cache_lock = threading.Lock()

# Maximum number of keys to track in fallback cache (prevents memory growth)
_FALLBACK_MAX_KEYS = 10000


def _cleanup_fallback_cache(window_seconds: int) -> None:
    """Remove expired entries from fallback cache."""
    now = time.time()
    expired_keys = [
        key
        for key, (_, start_time) in _fallback_cache.items()
        if now - start_time > window_seconds
    ]
    for key in expired_keys:
        del _fallback_cache[key]


def _check_fallback_rate_limit(
    key: str, limit: int, window_seconds: int
) -> Tuple[bool, int]:
    """
    In-memory fallback rate limiter for when Redis is unavailable.

    Uses a simple sliding window approach with a dictionary.
    Thread-safe via lock.
    """
    now = time.time()

    with _fallback_cache_lock:
        # Periodic cleanup to prevent memory growth
        if len(_fallback_cache) > _FALLBACK_MAX_KEYS:
            _cleanup_fallback_cache(window_seconds)

        if key in _fallback_cache:
            count, window_start = _fallback_cache[key]

            # Check if window has expired
            if now - window_start > window_seconds:
                # Start new window
                _fallback_cache[key] = (1, now)
                return True, limit - 1
            else:
                # Within window, check limit
                if count >= limit:
                    return False, 0

                # Increment count
                _fallback_cache[key] = (count + 1, window_start)
                return True, limit - count - 1
        else:
            # New key, start tracking
            _fallback_cache[key] = (1, now)
            return True, limit - 1


def check_rate_limit(
    key: str, limit: int, window_seconds: int = 60
) -> tuple[bool, int]:
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

    # If Redis is unavailable, use in-memory fallback instead of allowing all requests
    if not client:
        logger.warning(f"Redis unavailable, using in-memory fallback for key '{key}'")
        return _check_fallback_rate_limit(key, limit, window_seconds)

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
        # Fall back to in-memory limiter instead of allowing all requests
        return _check_fallback_rate_limit(key, limit, window_seconds)


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
            logger.debug(
                f"Player {player_key} rate limited, retry after {retry_after}s"
            )
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
        logger.warning(
            f"Redis unavailable, allowing potentially duplicate view for player '{player_key}'"
        )
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

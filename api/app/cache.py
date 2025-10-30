"""Redis cache utility functions."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = logging.getLogger(__name__)

# Redis connection
_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis | None:
    """
    Get or create Redis client instance.
    
    Returns None if Redis is not available or connection fails.
    """
    global _redis_client
    
    if not REDIS_AVAILABLE:
        return None
    
    if _redis_client is not None:
        return _redis_client
    
    try:
        # Try to get Redis URL from environment, fallback to Celery broker URL
        redis_url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL", "redis://cache:6379/0")
        
        # Parse Redis URL to get database number if specified
        # Format: redis://host:port/db or redis://host:port
        if "/" in redis_url.split("://")[1]:
            base_url, db_str = redis_url.rsplit("/", 1)
            try:
                db_num = int(db_str)
                redis_url = base_url
            except ValueError:
                db_num = 0
        else:
            db_num = 0
        
        _redis_client = redis.from_url(redis_url, db=db_num, decode_responses=True)
        # Test connection
        _redis_client.ping()
        logger.info("Redis cache connected successfully")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis cache unavailable: {e}. Continuing without cache.")
        return None


def cache_get(key: str) -> Any | None:
    """
    Retrieve a cached value by key.
    
    Args:
        key: Cache key
        
    Returns:
        Cached value if found, None otherwise
    """
    client = get_redis_client()
    if not client:
        return None
    
    try:
        value = client.get(key)
        if value is None:
            return None
        
        # Try to deserialize JSON
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            # Return as-is if not JSON
            return value
    except Exception as e:
        logger.warning(f"Cache get error for key '{key}': {e}")
        return None


def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    """
    Set a cached value with TTL.
    
    Args:
        key: Cache key
        value: Value to cache (will be JSON-serialized if dict/list)
        ttl: Time to live in seconds (default: 300 = 5 minutes)
        
    Returns:
        True if successful, False otherwise
    """
    client = get_redis_client()
    if not client:
        return False
    
    try:
        # Serialize value to JSON if it's a dict/list
        if isinstance(value, (dict, list)):
            serialized = json.dumps(value)
        else:
            serialized = str(value)
        
        client.setex(key, ttl, serialized)
        return True
    except Exception as e:
        logger.warning(f"Cache set error for key '{key}': {e}")
        return False


def cache_invalidate(pattern: str) -> int:
    """
    Invalidate cache entries matching a pattern.
    
    Args:
        pattern: Redis key pattern (e.g., "feed:promoted:*")
        
    Returns:
        Number of keys deleted
    """
    client = get_redis_client()
    if not client:
        return 0
    
    try:
        # Find all keys matching pattern
        keys = client.keys(pattern)
        if not keys:
            return 0
        
        # Delete keys
        deleted = client.delete(*keys)
        logger.info(f"Invalidated {deleted} cache entries matching pattern '{pattern}'")
        return deleted
    except Exception as e:
        logger.warning(f"Cache invalidate error for pattern '{pattern}': {e}")
        return 0


def cache_delete(key: str) -> bool:
    """
    Delete a specific cache key.
    
    Args:
        key: Cache key to delete
        
    Returns:
        True if deleted, False otherwise
    """
    client = get_redis_client()
    if not client:
        return False
    
    try:
        return bool(client.delete(key))
    except Exception as e:
        logger.warning(f"Cache delete error for key '{key}': {e}")
        return False


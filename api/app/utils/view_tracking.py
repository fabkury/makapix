"""
View tracking utility module.

Provides functions for recording artwork views with rich metadata
including device detection, IP hashing, and GeoIP resolution.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from fastapi import Request
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from uuid import UUID
    from ..models import User

logger = logging.getLogger(__name__)


class DeviceType(str, Enum):
    """Device type classification."""
    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"
    PLAYER = "player"  # Physical pixel art player device


class ViewSource(str, Enum):
    """Source of the view."""
    WEB = "web"
    API = "api"
    WIDGET = "widget"
    PLAYER = "player"


class ViewType(str, Enum):
    """Type of view interaction."""
    INTENTIONAL = "intentional"  # User clicked to view artwork
    LISTING = "listing"  # Artwork appeared in a feed/list
    SEARCH = "search"  # Artwork appeared in search results
    WIDGET = "widget"  # Viewed via embedded widget


# User-Agent patterns for device detection
MOBILE_PATTERNS = [
    r"iPhone",
    r"iPod",
    r"Android.*Mobile",
    r"Mobile.*Safari",
    r"webOS",
    r"BlackBerry",
    r"Opera Mini",
    r"Opera Mobi",
    r"IEMobile",
    r"Windows Phone",
    r"Fennec",
    r"BB10",
]

TABLET_PATTERNS = [
    r"iPad",
    r"Android(?!.*Mobile)",
    r"Tablet",
    r"PlayBook",
    r"Silk",
    r"Kindle",
]

# Custom User-Agent identifier for Makapix physical players
PLAYER_PATTERN = r"Makapix-Player|PixelFrame|Divoom"

# Compile patterns for performance
_mobile_regex = re.compile("|".join(MOBILE_PATTERNS), re.IGNORECASE)
_tablet_regex = re.compile("|".join(TABLET_PATTERNS), re.IGNORECASE)
_player_regex = re.compile(PLAYER_PATTERN, re.IGNORECASE)


def hash_ip(ip: str) -> str:
    """
    Create a SHA256 hash of an IP address for privacy-preserving storage.
    
    Args:
        ip: IPv4 or IPv6 address string
        
    Returns:
        64-character hex string (SHA256 hash)
    """
    if not ip:
        ip = "unknown"
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


def hash_user_agent(user_agent: str | None) -> str | None:
    """
    Create a SHA256 hash of a User-Agent string for device fingerprinting.
    
    Args:
        user_agent: User-Agent header string
        
    Returns:
        64-character hex string (SHA256 hash) or None
    """
    if not user_agent:
        return None
    return hashlib.sha256(user_agent.encode("utf-8")).hexdigest()


def detect_device_type(user_agent: str | None) -> DeviceType:
    """
    Detect device type from User-Agent string.
    
    Args:
        user_agent: User-Agent header string
        
    Returns:
        DeviceType enum value
    """
    if not user_agent:
        return DeviceType.DESKTOP
    
    # Check for physical player first (custom User-Agent)
    if _player_regex.search(user_agent):
        return DeviceType.PLAYER
    
    # Check for tablet (before mobile, as some tablets match mobile patterns too)
    if _tablet_regex.search(user_agent):
        return DeviceType.TABLET
    
    # Check for mobile
    if _mobile_regex.search(user_agent):
        return DeviceType.MOBILE
    
    # Default to desktop
    return DeviceType.DESKTOP


def extract_referrer_domain(referrer: str | None) -> str | None:
    """
    Extract the domain from a referrer URL.
    
    Args:
        referrer: Referer header string
        
    Returns:
        Domain string (e.g., "google.com") or None
    """
    if not referrer:
        return None
    
    try:
        parsed = urlparse(referrer)
        domain = parsed.netloc
        
        # Remove www. prefix for consistency
        if domain.startswith("www."):
            domain = domain[4:]
        
        # Limit length
        if len(domain) > 255:
            domain = domain[:255]
        
        return domain if domain else None
    except Exception:
        return None


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request, handling proxies.
    
    Checks X-Forwarded-For header first (for reverse proxy setups),
    then falls back to direct client IP.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        IP address string
    """
    # Check X-Forwarded-For header (set by reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs; take the first one
        return forwarded_for.split(",")[0].strip()
    
    # Check X-Real-IP header (alternative proxy header)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fall back to direct client IP
    if request.client:
        return request.client.host
    
    # Fallback if neither is available
    return "unknown"


def record_view(
    db: Session,
    post_id: UUID,
    request: Request,
    user: User | None = None,
    view_type: ViewType = ViewType.INTENTIONAL,
    view_source: ViewSource = ViewSource.WEB,
    post_owner_id: UUID | None = None,
) -> None:
    """
    Record a view event for an artwork.
    
    This function extracts metadata from the request and creates a ViewEvent record.
    It uses a separate database session to avoid interfering with the main transaction.
    It is designed to be non-blocking and fail gracefully.
    
    Author views are excluded - if the authenticated user is the post owner, the view is not recorded.
    
    Args:
        db: Database session (not used, kept for API compatibility)
        post_id: UUID of the post being viewed
        request: FastAPI Request object
        user: Current user (if authenticated)
        view_type: Type of view (intentional, listing, search, widget)
        view_source: Source of view (web, api, widget, player)
        post_owner_id: UUID of the post owner (if provided, used to exclude author views)
    """
    # Use a separate session to avoid transaction conflicts
    from ..db import SessionLocal
    view_db = SessionLocal()
    try:
        from ..models import ViewEvent, Post
        from ..geoip import get_country_code
        
        # Get post owner_id if not provided
        if post_owner_id is None:
            post = view_db.query(Post).filter(Post.id == post_id).first()
            if not post:
                logger.debug(f"Post {post_id} not found, skipping view recording")
                return
            post_owner_id = post.owner_id
        
        # Skip recording if user is the post owner
        if user is not None and user.id == post_owner_id:
            logger.debug(f"Skipping view recording for post {post_id} - user is the owner")
            return
        
        # Extract request metadata
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("User-Agent")
        referrer = request.headers.get("Referer")
        
        # Detect device type
        device_type = detect_device_type(user_agent)
        
        # Override view_source if device is a player
        if device_type == DeviceType.PLAYER:
            view_source = ViewSource.PLAYER
        
        # Resolve country code from IP
        country_code = get_country_code(client_ip)
        
        # Create view event
        view_event = ViewEvent(
            id=uuid.uuid4(),
            post_id=post_id,
            viewer_user_id=user.id if user else None,
            viewer_ip_hash=hash_ip(client_ip),
            country_code=country_code,
            device_type=device_type.value,
            view_source=view_source.value,
            view_type=view_type.value,
            user_agent_hash=hash_user_agent(user_agent),
            referrer_domain=extract_referrer_domain(referrer),
            created_at=datetime.now(timezone.utc),
        )
        
        view_db.add(view_event)
        view_db.commit()
        
        logger.info(
            f"Recorded view for post {post_id}: "
            f"device={device_type.value}, source={view_source.value}, "
            f"type={view_type.value}, country={country_code}"
        )
        
    except Exception as e:
        # Log error but don't fail the request
        view_db.rollback()
        logger.warning(f"Failed to record view for post {post_id}: {e}", exc_info=True)
    finally:
        view_db.close()


def record_views_batch(
    db: Session,
    post_ids: list[UUID],
    request: Request,
    user: User | None = None,
    view_type: ViewType = ViewType.LISTING,
    view_source: ViewSource = ViewSource.WEB,
    post_owner_ids: dict[UUID, UUID] | None = None,
) -> None:
    """
    Record view events for multiple artworks (batch operation).
    
    Used when artworks appear in feeds or search results.
    Uses a separate database session to avoid interfering with the main transaction.
    
    Author views are excluded - posts where the authenticated user is the owner are filtered out.
    
    Args:
        db: Database session (not used, kept for API compatibility)
        post_ids: List of post UUIDs being viewed
        request: FastAPI Request object
        user: Current user (if authenticated)
        view_type: Type of view (default: listing)
        view_source: Source of view (default: web)
        post_owner_ids: Dict mapping post_id -> owner_id (if None, will query database)
    """
    if not post_ids:
        return
    
    # Use a separate session to avoid transaction conflicts
    from ..db import SessionLocal
    view_db = SessionLocal()
    try:
        from ..models import ViewEvent, Post
        from ..geoip import get_country_code
        
        # Get owner_ids if not provided
        if post_owner_ids is None:
            posts = view_db.query(Post.id, Post.owner_id).filter(Post.id.in_(post_ids)).all()
            post_owner_ids = {post.id: post.owner_id for post in posts}
        
        # Filter out posts where user is the owner
        if user is not None:
            filtered_post_ids = [
                post_id for post_id in post_ids
                if post_id not in post_owner_ids or post_owner_ids[post_id] != user.id
            ]
        else:
            filtered_post_ids = post_ids
        
        if not filtered_post_ids:
            logger.debug(f"All {len(post_ids)} posts filtered out (user is owner), skipping batch view recording")
            return
        
        # Extract request metadata once
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("User-Agent")
        referrer = request.headers.get("Referer")
        
        # Process metadata once
        device_type = detect_device_type(user_agent)
        if device_type == DeviceType.PLAYER:
            view_source = ViewSource.PLAYER
        
        country_code = get_country_code(client_ip)
        ip_hash = hash_ip(client_ip)
        ua_hash = hash_user_agent(user_agent)
        referrer_domain = extract_referrer_domain(referrer)
        now = datetime.now(timezone.utc)
        user_id = user.id if user else None
        
        # Create view events for filtered posts
        view_events = [
            ViewEvent(
                id=uuid.uuid4(),
                post_id=post_id,
                viewer_user_id=user_id,
                viewer_ip_hash=ip_hash,
                country_code=country_code,
                device_type=device_type.value,
                view_source=view_source.value,
                view_type=view_type.value,
                user_agent_hash=ua_hash,
                referrer_domain=referrer_domain,
                created_at=now,
            )
            for post_id in filtered_post_ids
        ]
        
        view_db.add_all(view_events)
        view_db.commit()
        
        logger.info(
            f"Recorded {len(filtered_post_ids)} batch views (filtered {len(post_ids) - len(filtered_post_ids)} owner views): "
            f"device={device_type.value}, type={view_type.value}"
        )
        
    except Exception as e:
        view_db.rollback()
        logger.warning(f"Failed to record batch views: {e}", exc_info=True)
    finally:
        view_db.close()


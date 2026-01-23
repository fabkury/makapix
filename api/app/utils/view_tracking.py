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
    post_id: int,  # Changed from UUID to int
    request: Request,
    user: User | None = None,
    view_type: ViewType = ViewType.INTENTIONAL,
    view_source: ViewSource = ViewSource.WEB,
    post_owner_id: UUID | None = None,
) -> None:
    """
    Queue an artwork view event for async writing via Celery.

    Extracts all metadata from the request synchronously, then dispatches
    to Celery for non-blocking database write. Zero database interaction
    in the request path.

    Author views are excluded - if the authenticated user is the post owner, the view is not recorded.

    Args:
        db: Database session (used only to query post owner if not provided)
        post_id: Integer ID of the post being viewed
        request: FastAPI Request object
        user: Current user (if authenticated)
        view_type: Type of view (intentional, listing, search, widget)
        view_source: Source of view (web, api, widget, player)
        post_owner_id: UUID of the post owner (if provided, used to exclude author views)
    """
    try:
        from ..models import Post
        from ..geoip import get_country_code
        from ..tasks import write_view_event

        # Get post owner_id if not provided (minimal DB query)
        if post_owner_id is None:
            post = db.query(Post).filter(Post.id == post_id).first()
            if not post:
                logger.debug(f"Post {post_id} not found, skipping view recording")
                return
            post_owner_id = post.owner_id

        # Skip recording if user is the post owner
        if user is not None and user.id == post_owner_id:
            logger.debug(
                f"Skipping view recording for post {post_id} - user is the owner"
            )
            return

        # Extract request metadata synchronously
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

        # Prepare event data for Celery
        event_data = {
            "post_id": str(post_id),
            "viewer_user_id": str(user.id) if user else None,
            "viewer_ip_hash": hash_ip(client_ip),
            "country_code": country_code,
            "device_type": device_type.value,
            "view_source": view_source.value,
            "view_type": view_type.value,
            "user_agent_hash": hash_user_agent(user_agent),
            "referrer_domain": extract_referrer_domain(referrer),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Dispatch to Celery for async write (non-blocking)
        write_view_event.delay(event_data)

        logger.debug(
            f"Queued view event for post {post_id}: "
            f"device={device_type.value}, source={view_source.value}, "
            f"type={view_type.value}, country={country_code}"
        )

    except Exception as e:
        # Log error but don't fail the request
        logger.warning(
            f"Failed to queue view event for post {post_id}: {e}", exc_info=True
        )


def record_views_batch(
    db: Session,
    post_ids: list[int],  # Changed from list[UUID] to list[int]
    request: Request,
    user: User | None = None,
    view_type: ViewType = ViewType.LISTING,
    view_source: ViewSource = ViewSource.WEB,
    post_owner_ids: (
        dict[int, UUID] | None
    ) = None,  # Changed from dict[UUID, UUID] to dict[int, UUID]
) -> None:
    """
    Queue view events for multiple artworks for async writing via Celery (batch operation).

    Used when artworks appear in feeds or search results.
    Extracts metadata once and dispatches multiple events to Celery.

    Author views are excluded - posts where the authenticated user is the owner are filtered out.

    Args:
        db: Database session (used only to query post owners if not provided)
        post_ids: List of post integer IDs being viewed
        request: FastAPI Request object
        user: Current user (if authenticated)
        view_type: Type of view (default: listing)
        view_source: Source of view (default: web)
        post_owner_ids: Dict mapping post_id -> owner_id (if None, will query database)
    """
    if not post_ids:
        return

    try:
        from ..models import Post
        from ..geoip import get_country_code
        from ..tasks import write_view_event

        # Get owner_ids if not provided (minimal DB query)
        if post_owner_ids is None:
            posts = db.query(Post.id, Post.owner_id).filter(Post.id.in_(post_ids)).all()
            post_owner_ids = {post.id: post.owner_id for post in posts}

        # Filter out posts where user is the owner
        if user is not None:
            filtered_post_ids = [
                post_id
                for post_id in post_ids
                if post_id not in post_owner_ids or post_owner_ids[post_id] != user.id
            ]
        else:
            filtered_post_ids = post_ids

        if not filtered_post_ids:
            logger.debug(
                f"All {len(post_ids)} posts filtered out (user is owner), skipping batch view recording"
            )
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
        now_iso = datetime.now(timezone.utc).isoformat()
        user_id_str = str(user.id) if user else None

        # Queue events for filtered posts (non-blocking Celery dispatch)
        for post_id in filtered_post_ids:
            event_data = {
                "post_id": str(post_id),
                "viewer_user_id": user_id_str,
                "viewer_ip_hash": ip_hash,
                "country_code": country_code,
                "device_type": device_type.value,
                "view_source": view_source.value,
                "view_type": view_type.value,
                "user_agent_hash": ua_hash,
                "referrer_domain": referrer_domain,
                "created_at": now_iso,
            }
            write_view_event.delay(event_data)

        logger.debug(
            f"Queued {len(filtered_post_ids)} batch views (filtered {len(post_ids) - len(filtered_post_ids)} owner views): "
            f"device={device_type.value}, type={view_type.value}"
        )

    except Exception as e:
        logger.warning(f"Failed to queue batch views: {e}", exc_info=True)


def record_blog_post_view(
    db: Session,
    blog_post_id: int,
    request: Request,
    user: User | None = None,
    view_type: ViewType = ViewType.INTENTIONAL,
    view_source: ViewSource = ViewSource.WEB,
    blog_post_owner_id: int | None = None,
) -> None:
    """
    Queue a blog post view event for async writing via Celery.

    Extracts all metadata from the request synchronously, then dispatches
    to Celery for non-blocking database write. Zero database interaction
    in the request path.

    Author views are excluded - if the authenticated user is the blog post owner, the view is not recorded.

    Args:
        db: Database session (used only to query blog post owner if not provided)
        blog_post_id: Integer ID of the blog post being viewed
        request: FastAPI Request object
        user: Current user (if authenticated)
        view_type: Type of view (intentional, listing, search, widget)
        view_source: Source of view (web, api, widget, player)
        blog_post_owner_id: Integer ID of the blog post owner (if provided, used to exclude author views)
    """
    try:
        from ..models import BlogPost
        from ..geoip import get_country_code
        from ..tasks import write_blog_post_view_event

        # Get blog post owner_id if not provided (minimal DB query)
        if blog_post_owner_id is None:
            blog_post = db.query(BlogPost).filter(BlogPost.id == blog_post_id).first()
            if not blog_post:
                logger.debug(
                    f"Blog post {blog_post_id} not found, skipping view recording"
                )
                return
            blog_post_owner_id = blog_post.owner_id

        # Skip recording if user is the blog post owner
        if user is not None and user.id == blog_post_owner_id:
            logger.debug(
                f"Skipping view recording for blog post {blog_post_id} - user is the owner"
            )
            return

        # Extract request metadata synchronously
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

        # Prepare event data for Celery
        event_data = {
            "blog_post_id": str(blog_post_id),
            "viewer_user_id": str(user.id) if user else None,
            "viewer_ip_hash": hash_ip(client_ip),
            "country_code": country_code,
            "device_type": device_type.value,
            "view_source": view_source.value,
            "view_type": view_type.value,
            "user_agent_hash": hash_user_agent(user_agent),
            "referrer_domain": extract_referrer_domain(referrer),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Dispatch to Celery for async write (non-blocking)
        write_blog_post_view_event.delay(event_data)

        logger.debug(
            f"Queued view event for blog post {blog_post_id}: "
            f"device={device_type.value}, source={view_source.value}, "
            f"type={view_type.value}, country={country_code}"
        )

    except Exception as e:
        # Log error but don't fail the request
        logger.warning(
            f"Failed to queue view event for blog post {blog_post_id}: {e}",
            exc_info=True,
        )


def record_blog_post_views_batch(
    db: Session,
    blog_post_ids: list[int],
    request: Request,
    user: User | None = None,
    view_type: ViewType = ViewType.LISTING,
    view_source: ViewSource = ViewSource.WEB,
    blog_post_owner_ids: dict[int, int] | None = None,
) -> None:
    """
    Queue view events for multiple blog posts for async writing via Celery (batch operation).

    Used when blog posts appear in feeds or search results.
    Extracts metadata once and dispatches multiple events to Celery.

    Author views are excluded - blog posts where the authenticated user is the owner are filtered out.

    Args:
        db: Database session (used only to query blog post owners if not provided)
        blog_post_ids: List of blog post integer IDs being viewed
        request: FastAPI Request object
        user: Current user (if authenticated)
        view_type: Type of view (default: listing)
        view_source: Source of view (default: web)
        blog_post_owner_ids: Dict mapping blog_post_id -> owner_id (if None, will query database)
    """
    if not blog_post_ids:
        return

    try:
        from ..models import BlogPost
        from ..geoip import get_country_code
        from ..tasks import write_blog_post_view_event

        # Get owner_ids if not provided (minimal DB query)
        if blog_post_owner_ids is None:
            blog_posts = (
                db.query(BlogPost.id, BlogPost.owner_id)
                .filter(BlogPost.id.in_(blog_post_ids))
                .all()
            )
            blog_post_owner_ids = {bp.id: bp.owner_id for bp in blog_posts}

        # Filter out blog posts where user is the owner
        if user is not None:
            filtered_blog_post_ids = [
                blog_post_id
                for blog_post_id in blog_post_ids
                if blog_post_id not in blog_post_owner_ids
                or blog_post_owner_ids[blog_post_id] != user.id
            ]
        else:
            filtered_blog_post_ids = blog_post_ids

        if not filtered_blog_post_ids:
            logger.debug(
                f"All {len(blog_post_ids)} blog posts filtered out (user is owner), skipping batch view recording"
            )
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
        now_iso = datetime.now(timezone.utc).isoformat()
        user_id_str = str(user.id) if user else None

        # Queue events for filtered blog posts (non-blocking Celery dispatch)
        for blog_post_id in filtered_blog_post_ids:
            event_data = {
                "blog_post_id": str(blog_post_id),
                "viewer_user_id": user_id_str,
                "viewer_ip_hash": ip_hash,
                "country_code": country_code,
                "device_type": device_type.value,
                "view_source": view_source.value,
                "view_type": view_type.value,
                "user_agent_hash": ua_hash,
                "referrer_domain": referrer_domain,
                "created_at": now_iso,
            }
            write_blog_post_view_event.delay(event_data)

        logger.debug(
            f"Queued {len(filtered_blog_post_ids)} blog post batch views (filtered {len(blog_post_ids) - len(filtered_blog_post_ids)} owner views): "
            f"device={device_type.value}, type={view_type.value}"
        )

    except Exception as e:
        logger.warning(f"Failed to queue blog post batch views: {e}", exc_info=True)

"""
Sitewide event tracking utility module.

Provides functions for recording sitewide events (page views, signups, uploads, etc.)
with deferred writes via Celery for optimal performance.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import Request

if TYPE_CHECKING:
    from ..models import User

logger = logging.getLogger(__name__)


def record_site_event(
    request: Request,
    event_type: str,
    user: User | None = None,
    event_data: dict | None = None,
) -> None:
    """
    Queue a sitewide event for async writing via Celery.

    Zero database interaction in the request path - all data is
    serialized and dispatched to the Celery task queue.

    Args:
        request: FastAPI Request object
        event_type: Type of event (page_view, signup, upload, api_call, error)
        user: Current user (if authenticated)
        event_data: Optional event-specific data dict (can include "client_path" for frontend tracking)
    """
    try:
        from ..utils.view_tracking import (
            get_client_ip,
            hash_ip,
            detect_device_type,
            extract_referrer_domain,
        )
        from ..geoip import get_country_code
        from ..tasks import write_site_event

        # Extract request metadata synchronously
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("User-Agent")
        referrer = request.headers.get("Referer")

        # Use client-provided path if available (for frontend tracking), otherwise use request path
        if event_data and "client_path" in event_data:
            page_path = event_data["client_path"]
        else:
            page_path = str(request.url.path)

        # Detect device type
        device_type = detect_device_type(user_agent)

        # Resolve country code from IP
        country_code = get_country_code(client_ip)

        # Prepare event payload for Celery
        event_payload = {
            "event_type": event_type,
            "page_path": page_path,
            "visitor_ip_hash": hash_ip(client_ip),
            "user_id": str(user.id) if user else None,
            "device_type": device_type.value,
            "country_code": country_code,
            "referrer_domain": extract_referrer_domain(referrer),
            "event_data": event_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # Dispatch to Celery for async write (non-blocking)
        write_site_event.delay(event_payload)

        logger.debug(f"Queued site event: {event_type} on {page_path}")

    except Exception as e:
        # Log error but don't fail the request
        logger.warning(f"Failed to queue site event {event_type}: {e}", exc_info=True)

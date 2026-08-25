"""Client-side page view tracking endpoint."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_user_optional
from ..deps import get_db
from ..utils.site_tracking import record_site_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/track", tags=["Tracking"])


class PageViewRequest(BaseModel):
    """Request body for page view tracking."""

    path: str  # Page path (e.g., "/", "/search", "/blog")
    referrer: Optional[str] = None  # Optional referrer URL


@router.post("/page-view", status_code=status.HTTP_204_NO_CONTENT)
async def track_page_view(
    payload: PageViewRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_current_user_optional),
) -> None:
    """
    Track a page view from the frontend.

    This endpoint is called by the frontend on page load to track sitewide page views.
    It's a lightweight, fire-and-forget endpoint that queues the event for async processing.

    **Public endpoint** - No authentication required.

    Args:
        payload: Page view details (path, optional referrer)
        request: FastAPI Request object (for IP, user agent, etc.)
        db: Database session
        current_user: Current user if authenticated, None otherwise

    Returns:
        204 No Content (always succeeds, errors are logged but don't fail)
    """
    try:
        # The Referer header on this POST is always our own origin (the page
        # making the call), so the browser-side document.referrer must come
        # from the payload for external referral attribution to work.
        record_site_event(
            request=request,
            event_type="page_view",
            user=current_user,
            event_data={"client_path": payload.path} if payload.path else None,
            # "" (not None) so a referrer-less visit records as direct instead
            # of falling back to the header
            referrer=payload.referrer or "",
        )

        logger.debug(f"Tracked client page view: {payload.path}")
    except Exception as e:
        # Log error but don't fail the request (tracking should be non-blocking)
        logger.warning(f"Failed to track client page view: {e}", exc_info=True)

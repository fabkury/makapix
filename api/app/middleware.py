"""Security middleware for the API."""

from __future__ import annotations

import logging
import os
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .utils.site_tracking import record_site_event

logger = logging.getLogger(__name__)

# Paths to exclude from API call tracking
# These are either internal endpoints, high-frequency endpoints, or already tracked elsewhere
EXCLUDED_PATHS = {
    "/health",
    "/readiness",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/track/page-view",  # Already tracked as page_view event from frontend
}

# Path prefixes to exclude from API call tracking
EXCLUDED_PATH_PREFIXES = (
    "/vault/",  # Static file serving
)


class APITelemetryMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track API calls for telemetry purposes.
    
    Records API call events to the site events table for moderator dashboard metrics.
    Only tracks meaningful API calls (excludes health checks, static files, etc.).
    
    Note: This middleware does not associate API calls with users to avoid
    blocking on database lookups. User association happens only for events
    explicitly tracked by route handlers (page_view, signup, upload, etc.).
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get the path
        path = request.url.path
        
        # Determine if this request should be tracked
        should_track = self._should_track_request(request, path)
        
        # Process the request
        response = await call_next(request)
        
        # Track the API call if appropriate (after response to not block)
        if should_track:
            self._record_api_call(request, response)
        
        return response
    
    def _should_track_request(self, request: Request, path: str) -> bool:
        """Determine if an API request should be tracked."""
        # Skip OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return False
        
        # Skip excluded exact paths
        if path in EXCLUDED_PATHS:
            return False
        
        # Skip excluded path prefixes
        if path.startswith(EXCLUDED_PATH_PREFIXES):
            return False
        
        return True
    
    def _record_api_call(self, request: Request, response: Response) -> None:
        """Record an API call event for telemetry."""
        try:
            # Record the API call event
            # Note: We don't pass user here as middleware doesn't have access to
            # authenticated user. User association is done by route handlers for
            # specific events (page_view, signup, upload, etc.).
            record_site_event(
                request=request,
                event_type="api_call",
                user=None,
                event_data={
                    "method": request.method,
                    "status_code": response.status_code,
                }
            )
            
            # Also record an error event for 4xx and 5xx responses
            if response.status_code >= 400:
                error_type = self._classify_error(response.status_code)
                record_site_event(
                    request=request,
                    event_type="error",
                    user=None,
                    event_data={
                        "error_type": error_type,
                        "status_code": response.status_code,
                        "method": request.method,
                    }
                )
        except Exception as e:
            # Log error but don't fail the request (tracking should be non-blocking)
            logger.warning(f"Failed to record API call telemetry: {e}")
    
    def _classify_error(self, status_code: int) -> str:
        """Classify an HTTP error status code into an error type."""
        if status_code == 400:
            return "bad_request"
        elif status_code == 401:
            return "unauthorized"
        elif status_code == 403:
            return "forbidden"
        elif status_code == 404:
            return "not_found"
        elif status_code == 405:
            return "method_not_allowed"
        elif status_code == 422:
            return "validation_error"
        elif status_code == 429:
            return "rate_limited"
        elif status_code >= 500:
            return "server_error"
        else:
            return f"http_{status_code}"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.
    
    Implements OWASP recommended security headers to protect against
    common web vulnerabilities.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        
        # Enable XSS protection (legacy header, but still useful for older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        
        # Referrer policy - only send origin on cross-origin requests
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Permissions policy - disable unnecessary browser features
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=(), "
            "magnetometer=(), gyroscope=(), accelerometer=()"
        )
        
        # HSTS - Force HTTPS in production
        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production" or request.url.scheme == "https":
            # Enable HSTS with 1 year max-age, include subdomains
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        
        # Content Security Policy
        # This is a restrictive CSP suitable for API endpoints
        # The API primarily serves JSON, but also some HTML (OAuth callbacks, error pages)
        # Adjust if serving more complex HTML content
        csp_directives = [
            "default-src 'self'",  # Allow same-origin by default
            "script-src 'self' 'unsafe-inline'",  # Allow inline scripts for OAuth callback
            "style-src 'self' 'unsafe-inline'",  # Allow inline styles for OAuth callback
            "img-src 'self' data:",  # Allow images from same origin and data URIs
            "frame-ancestors 'none'",  # Prevent embedding in iframes
            "base-uri 'self'",  # Restrict base tag to same origin
            "form-action 'self'",  # Only allow form submissions to same origin
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        return response

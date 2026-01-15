"""Security middleware for the API."""

from __future__ import annotations

import os
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


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


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Add unique request ID to all requests for audit trail correlation.

    Generates a short UUID for each request and adds it to:
    - request.state.request_id (for use in logging throughout the request)
    - X-Request-Id response header (for client correlation)
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate a short request ID (8 chars from UUID)
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id

        return response

"""Security middleware for the API."""

from __future__ import annotations

import os
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
        # Note: This is a basic CSP. Adjust based on your actual needs.
        # For API endpoints, we're mostly concerned with preventing XSS in error pages
        csp_directives = [
            "default-src 'none'",  # Block everything by default
            "frame-ancestors 'none'",  # Prevent embedding in iframes
            "base-uri 'self'",  # Restrict base tag to same origin
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)
        
        return response

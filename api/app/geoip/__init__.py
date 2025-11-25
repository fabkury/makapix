"""
GeoIP lookup module using MaxMind GeoLite2 database.

This module provides IP-to-country resolution for view tracking.
The database file should be downloaded from MaxMind and placed in this directory.

Usage:
    from app.geoip import get_country_code
    
    country = get_country_code("8.8.8.8")  # Returns "US" or None
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Path to the GeoLite2 database file
GEOIP_DB_PATH = os.getenv(
    "GEOIP_DB_PATH",
    str(Path(__file__).parent / "GeoLite2-Country.mmdb")
)

# Global reader instance (lazy loaded)
_reader = None
_reader_initialized = False


def _get_reader():
    """
    Get or initialize the GeoIP reader.
    
    Returns None if the database file is not available or geoip2 is not installed.
    """
    global _reader, _reader_initialized
    
    if _reader_initialized:
        return _reader
    
    _reader_initialized = True
    
    try:
        import geoip2.database
    except ImportError:
        logger.warning(
            "geoip2 library not installed. GeoIP lookups will be disabled. "
            "Install with: pip install geoip2"
        )
        return None
    
    if not os.path.exists(GEOIP_DB_PATH):
        logger.warning(
            f"GeoIP database not found at {GEOIP_DB_PATH}. "
            "Download GeoLite2-Country.mmdb from MaxMind and place it in api/app/geoip/. "
            "See api/app/geoip/README.md for instructions."
        )
        return None
    
    try:
        _reader = geoip2.database.Reader(GEOIP_DB_PATH)
        logger.info(f"GeoIP database loaded from {GEOIP_DB_PATH}")
        return _reader
    except Exception as e:
        logger.error(f"Failed to load GeoIP database: {e}")
        return None


def get_country_code(ip: str) -> str | None:
    """
    Look up the country code for an IP address.
    
    Args:
        ip: IPv4 or IPv6 address string
        
    Returns:
        ISO 3166-1 alpha-2 country code (e.g., "US", "BR") or None if lookup fails
    """
    if not ip or ip == "unknown":
        return None
    
    # Skip localhost and private IP ranges
    if ip.startswith(("127.", "10.", "192.168.", "172.16.", "172.17.", "172.18.",
                       "172.19.", "172.20.", "172.21.", "172.22.", "172.23.",
                       "172.24.", "172.25.", "172.26.", "172.27.", "172.28.",
                       "172.29.", "172.30.", "172.31.", "::1", "fe80:")):
        return None
    
    reader = _get_reader()
    if reader is None:
        return None
    
    try:
        response = reader.country(ip)
        return response.country.iso_code
    except Exception as e:
        # AddressNotFoundError is common for reserved IPs, don't log as error
        if "AddressNotFoundError" in str(type(e).__name__):
            logger.debug(f"IP address not found in GeoIP database: {ip}")
        else:
            logger.warning(f"GeoIP lookup failed for {ip}: {e}")
        return None


def close_reader() -> None:
    """
    Close the GeoIP reader and release resources.
    
    Should be called on application shutdown.
    """
    global _reader, _reader_initialized
    
    if _reader is not None:
        try:
            _reader.close()
        except Exception:
            pass
        _reader = None
    
    _reader_initialized = False


def is_available() -> bool:
    """
    Check if GeoIP lookups are available.
    
    Returns:
        True if the database is loaded and ready, False otherwise
    """
    return _get_reader() is not None


def get_database_info() -> dict | None:
    """
    Get information about the loaded GeoIP database.
    
    Returns:
        Dictionary with database metadata, or None if not available
    """
    reader = _get_reader()
    if reader is None:
        return None
    
    try:
        metadata = reader.metadata()
        return {
            "database_type": metadata.database_type,
            "build_epoch": metadata.build_epoch,
            "node_count": metadata.node_count,
            "languages": metadata.languages,
        }
    except Exception:
        return None


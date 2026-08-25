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
    "GEOIP_DB_PATH", str(Path(__file__).parent / "GeoLite2-Country.mmdb")
)

# Global reader instance (lazy loaded). The reader is keyed to the database
# file's mtime so a refreshed file (refresh_geoip_database beat task, or a
# manual drop-in) is picked up by running processes without a restart — the
# original load-once latch meant a process started before the file existed
# returned None forever.
_reader = None
_loaded_mtime: float | None = None
_warned_missing = False


def _get_reader():
    """
    Get the GeoIP reader, (re)opening it if the database file appeared or
    changed since the last call.

    Returns None if the database file is not available or geoip2 is not
    installed. A previously opened reader keeps serving if the file vanishes
    or a reload fails. Old readers are left to GC rather than closed so a
    concurrent lookup on one is never invalidated mid-call.
    """
    global _reader, _loaded_mtime, _warned_missing

    try:
        mtime = os.stat(GEOIP_DB_PATH).st_mtime
    except OSError:
        if _reader is None and not _warned_missing:
            logger.warning(
                f"GeoIP database not found at {GEOIP_DB_PATH}. "
                "Set MAXMIND_LICENSE_KEY so the refresh_geoip_database beat task "
                "downloads it, or place GeoLite2-Country.mmdb there manually. "
                "See api/app/geoip/README.md for instructions."
            )
            _warned_missing = True
        return _reader

    if _reader is not None and mtime == _loaded_mtime:
        return _reader

    try:
        import geoip2.database
    except ImportError:
        if not _warned_missing:
            logger.warning(
                "geoip2 library not installed. GeoIP lookups will be disabled. "
                "Install with: pip install geoip2"
            )
            _warned_missing = True
        return None

    try:
        new_reader = geoip2.database.Reader(GEOIP_DB_PATH)
    except Exception as e:
        logger.error(f"Failed to load GeoIP database: {e}")
        # Remember the mtime so a broken file isn't re-tried on every lookup.
        _loaded_mtime = mtime
        return _reader

    _reader = new_reader
    _loaded_mtime = mtime
    _warned_missing = False
    logger.info(f"GeoIP database loaded from {GEOIP_DB_PATH}")
    return _reader


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
    if ip.startswith(
        (
            "127.",
            "10.",
            "192.168.",
            "172.16.",
            "172.17.",
            "172.18.",
            "172.19.",
            "172.20.",
            "172.21.",
            "172.22.",
            "172.23.",
            "172.24.",
            "172.25.",
            "172.26.",
            "172.27.",
            "172.28.",
            "172.29.",
            "172.30.",
            "172.31.",
            "::1",
            "fe80:",
        )
    ):
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
    global _reader, _loaded_mtime, _warned_missing

    if _reader is not None:
        try:
            _reader.close()
        except Exception:
            pass
        _reader = None

    _loaded_mtime = None
    _warned_missing = False


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

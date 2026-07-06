"""Tests for canonical client-IP extraction (docs/ugc-safety/ D23b).

Regression coverage for two historical defects:
1. Four divergent get_client_ip copies; the one in routers/auth.py read only
   request.client.host — behind Caddy always the proxy IP — turning every
   "per-IP" login/OTP throttle into one global bucket for all users.
2. The XFF-reading copies took the LEFTMOST entry, which is client-controlled
   in any append topology.
"""

from __future__ import annotations

from fastapi import Request

from app.utils.client_ip import get_client_ip, get_trusted_client_ip


def _request(
    headers: dict[str, str] | None = None, client_host: str | None = "10.0.0.9"
):
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
        ],
        "client": (client_host, 12345) if client_host else None,
    }
    return Request(scope)


def test_rightmost_xff_hop_wins():
    """Multi-hop XFF: the proxy-appended (rightmost) entry is used, never the
    client-controlled leftmost one."""
    req = _request({"X-Forwarded-For": "6.6.6.6, 7.7.7.7, 203.0.113.5"})
    assert get_client_ip(req) == "203.0.113.5"


def test_single_xff_value():
    req = _request({"X-Forwarded-For": "203.0.113.5"})
    assert get_client_ip(req) == "203.0.113.5"


def test_falls_back_to_peer_without_xff():
    """No XFF (direct access): the socket peer is used — routers/auth.py's old
    copy stopped here even WITH an XFF header present."""
    req = _request(client_host="172.18.0.9")
    assert get_client_ip(req) == "172.18.0.9"


def test_unknown_without_peer():
    req = _request(client_host=None)
    assert get_client_ip(req) == "unknown"


def test_trusted_alias_is_same_function():
    assert get_trusted_client_ip is get_client_ip


def test_all_modules_share_canonical_helper():
    """No module may grow a local copy again (the root cause of the global-
    bucket login-throttle bug)."""
    from app import auth
    from app.routers import auth as routers_auth
    from app.routers import player, reports
    from app.utils import view_tracking

    assert auth.get_client_ip is get_client_ip
    assert auth.get_trusted_client_ip is get_client_ip
    assert routers_auth.get_client_ip is get_client_ip
    assert player.get_client_ip is get_client_ip
    assert view_tracking.get_client_ip is get_client_ip
    assert reports.get_trusted_client_ip is get_client_ip

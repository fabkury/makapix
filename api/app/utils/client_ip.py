"""Canonical client-IP extraction (docs/ugc-safety/ D23b).

THE single implementation — do not add local copies in routers/utils again.
Before 2026-07 there were four divergent copies; the one in routers/auth.py
read only ``request.client.host``, which behind the reverse proxy is always
Caddy's container IP, silently turning every "per-IP" login/OTP throttle
into one global bucket shared by all external users.

Topology note: a single Caddy instance fronts all external HTTP traffic,
and (Caddy >= 2.5 with ``trusted_proxies`` unset) it REPLACES any
client-supplied X-Forwarded-For with the real peer address — verified
empirically 2026-07-06: forged single- and multi-hop XFF headers both
arrived at the API as exactly the caller's real IP. So via Caddy the header
always carries one trusted value.

We still take the RIGHTMOST entry, never the leftmost: the rightmost hop is
the one appended by the proxy nearest to us, so this stays correct if the
edge is ever switched to append mode (``trusted_proxies``, a CDN in front),
while the leftmost value is client-controlled in any append topology.
"""

from __future__ import annotations

from fastapi import Request


def get_client_ip(request: Request) -> str:
    """Best available client IP: rightmost X-Forwarded-For hop, else peer."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[-1].strip()
    if request.client:
        return request.client.host
    return "unknown"


# Alias for call sites that want to signal security-sensitive intent
# (rate limits, abuse attribution). Identical behavior.
get_trusted_client_ip = get_client_ip

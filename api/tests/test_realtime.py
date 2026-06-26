"""Tests for the authenticated SSE realtime stream (change-request §5).

Note: the streaming happy-path is validated out-of-band with curl (a long-lived
text/event-stream hangs the synchronous TestClient). Here we cover the auth gate
and the event formatting.
"""

from __future__ import annotations

import json

from app.routers.realtime import _sse


def test_realtime_requires_auth(client):
    r = client.get("/v1/realtime/notifications")
    assert r.status_code == 401


def test_sse_event_format():
    out = _sse("connected", {"unread_count": 3})
    assert out.startswith("event: connected\n")
    body = out.split("data: ", 1)[1].rsplit("\n\n", 1)[0]
    assert json.loads(body) == {"unread_count": 3}
    assert out.endswith("\n\n")

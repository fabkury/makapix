"""Tests for the standardized v1 error envelope (errors.py).

The v1 API serializes non-2xx responses as {"error": {"code","message","details"?}}.
Non-versioned surfaces keep FastAPI's default {"detail": ...} shape.
"""

from __future__ import annotations


def test_v1_not_found_uses_envelope(client):
    r = client.get("/v1/this-route-does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body, body
    assert body["error"]["code"] == "not_found"
    assert isinstance(body["error"]["message"], str)
    assert "detail" not in body


def test_non_v1_not_found_keeps_legacy_detail_shape(client):
    # Hardware/player and legacy surfaces must keep the default {detail} shape.
    r = client.get("/player/this-route-does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert body == {"detail": "Not Found"}


def test_v1_validation_error_uses_envelope(client):
    # Missing/invalid body on a v1 endpoint -> 422 with the envelope + details.
    r = client.post("/v1/auth/login", json={})
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "validation_error"
    assert "errors" in body["error"]["details"]


def test_legacy_root_validation_error_keeps_detail_shape(client):
    # The transition root mount keeps the legacy shape so existing web works.
    r = client.post("/auth/login", json={})
    assert r.status_code == 422
    assert "detail" in r.json()


def test_openapi_published_at_versioned_path_with_api_server(client):
    r = client.get("/v1/openapi.json")
    assert r.status_code == 200
    doc = r.json()
    assert doc["servers"] == [
        {"url": "/api", "description": "Public API base (Caddy strips /api)"}
    ]
    # App-facing routes are documented under /v1; legacy root copies are hidden.
    assert "/v1/auth/login" in doc["paths"]
    assert "/auth/login" not in doc["paths"]

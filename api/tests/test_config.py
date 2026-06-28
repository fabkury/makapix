"""Tests for the public /config endpoint (upload rules = single source of truth)."""

from __future__ import annotations

from app import vault


def test_config_upload_block_matches_vault(client):
    r = client.get("/v1/config")
    assert r.status_code == 200
    body = r.json()
    up = body["upload"]
    assert up["formats"] == list(vault.FORMAT_TO_EXT.keys())
    assert up["max_file_bytes"] == vault.MAX_FILE_SIZE_BYTES
    assert up["free_form_min"] == vault.FREE_FORM_MIN_SIZE == 128
    assert up["free_form_max"] == vault.MAX_CANVAS_SIZE == 256
    assert up["rotations_allowed"] is True
    # JSON turns tuples into lists; compare element-wise against the vault source.
    expected = [list(t) for t in vault.ALLOWED_SMALL_DIMENSIONS]
    assert up["small_whitelist"] == expected
    # Legacy allowed_dimensions is now sourced from the same vault constant.
    assert body["allowed_dimensions"] == expected


def test_config_etag_conditional_request(client):
    r1 = client.get("/v1/config")
    etag = r1.headers.get("ETag")
    assert etag
    assert r1.headers.get("Cache-Control") == "public, max-age=300"
    r2 = client.get("/v1/config", headers={"If-None-Match": etag})
    assert r2.status_code == 304


def test_config_available_on_legacy_root_during_transition(client):
    # The legacy root mount keeps working until web migrates to /api/v1.
    assert client.get("/config").status_code == 200

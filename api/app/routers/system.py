"""System endpoints (health, config)."""

from __future__ import annotations

import hashlib
import os
import time

from fastapi import APIRouter, Request, Response

from .. import schemas, vault

router = APIRouter(prefix="", tags=["System"])

# Global startup time for uptime calculation
_STARTUP_TIME = time.time()


@router.get("/health", response_model=schemas.HealthResponse)
def get_health() -> schemas.HealthResponse:
    """
    Liveness & minimal readiness check.
    """
    uptime_s = time.time() - _STARTUP_TIME
    return schemas.HealthResponse(status="ok", uptime_s=uptime_s)


def _build_config() -> schemas.Config:
    """Assemble the public client config from server-authoritative sources.

    Upload/conformance rules come straight from `vault.py`, so the app, web, and
    players read one source of truth and can never drift from what the server
    actually enforces (see change-request §6.1).
    """
    return schemas.Config(
        allowed_dimensions=list(vault.ALLOWED_SMALL_DIMENSIONS),
        max_art_file_bytes_default=vault.MAX_FILE_SIZE_BYTES,
        upload=schemas.UploadConfig(
            formats=list(vault.FORMAT_TO_EXT.keys()),
            max_file_bytes=vault.MAX_FILE_SIZE_BYTES,
            free_form_min=vault.FREE_FORM_MIN_SIZE,
            free_form_max=vault.MAX_CANVAS_SIZE,
            small_whitelist=list(vault.ALLOWED_SMALL_DIMENSIONS),
            rotations_allowed=True,
            # Capability advertisement for .mkpx layers-file attachments
            # (docs/mkpx-upload/): clients gate all mkpx UI on this block,
            # and its appearance on prod is the launch signal (deploy=flip).
            mkpx=schemas.MkpxUploadConfig(
                enabled=True,
                max_file_bytes=vault.MKPX_SIZE_LIMIT_BYTES,
            ),
        ),
        # UGC-safety capability block (docs/ugc-safety/API-CONTRACT.md §1):
        # its presence is the clients' feature gate, and its appearance on
        # prod is the launch signal (deploy=flip), like the mkpx block above.
        moderation=_build_moderation_config(),
    )


def _build_moderation_config() -> schemas.ModerationConfig:
    base_url = os.getenv("BASE_URL", "https://makapix.club").rstrip("/")
    return schemas.ModerationConfig(
        report_reasons=[
            schemas.ReportReasonEntry(code=code, label=label)
            for code, label in schemas.REPORT_REASONS
        ],
        contact_email=os.getenv("MODERATION_ALERT_EMAIL", "acme@makapix.club"),
        guidelines_url=f"{base_url}/about?tab=rules",
        moderation_policy_url=f"{base_url}/about?tab=moderation",
        max_blocks_per_user=1000,
    )


_CACHE_CONTROL = "public, max-age=300"


@router.get("/config", response_model=schemas.Config)
def get_public_config(request: Request, response: Response):
    """Public, cacheable configuration limits + upload rules for clients."""
    cfg = _build_config()
    etag = '"' + hashlib.sha256(cfg.model_dump_json().encode()).hexdigest()[:16] + '"'
    if request.headers.get("if-none-match") == etag:
        return Response(
            status_code=304,
            headers={"ETag": etag, "Cache-Control": _CACHE_CONTROL},
        )
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = _CACHE_CONTROL
    return cfg

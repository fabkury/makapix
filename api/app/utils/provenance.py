"""Artwork provenance: constants, validation and `_server` zone assembly.

Source of truth: docs/artwork-provenance/PLAN.md (§3–§5). Values are app-level
constants (no DB enums, like Post.kind) so future values are additive.

Semantics that must never regress:
- NULL means unknown, never "web" — absence of a declaration is not coerced.
- Clients can never write the reserved ``_server`` key; it is stripped from
  declared input and rebuilt server-side.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import status

from ..errors import AppError, ErrorCode
from .view_tracking import DeviceType, detect_device_type

# --- upload_channel -----------------------------------------------------------

UPLOAD_CHANNEL_WEB = "web"
UPLOAD_CHANNEL_APP = "app"
UPLOAD_CHANNEL_API = "api"

# --- creation_method ----------------------------------------------------------

CREATION_METHOD_EDITOR_HAND_DRAWN = "editor_hand_drawn"
CREATION_METHOD_EDITOR_IMPORT = "editor_import"
# Server-inferred only ("made in the editor, hand-drawn vs import unknown");
# clients must not send it — they know better.
CREATION_METHOD_EDITOR = "editor"
CREATION_METHOD_EXTERNAL_FILE = "external_file"

CLIENT_DECLARABLE_CREATION_METHODS = frozenset(
    {
        CREATION_METHOD_EDITOR_HAND_DRAWN,
        CREATION_METHOD_EDITOR_IMPORT,
        CREATION_METHOD_EXTERNAL_FILE,
    }
)

# --- source_details -----------------------------------------------------------

SOURCE_DETAILS_MAX_BYTES = 2048
# Upload devices (L7): the existing DeviceType enum minus "player" — players
# don't upload. No laptop/smartphone split: not honestly observable.
UPLOAD_DEVICE_TYPES = frozenset(
    {DeviceType.DESKTOP.value, DeviceType.MOBILE.value, DeviceType.TABLET.value}
)
EDITOR_PLATFORMS = frozenset({"ios", "android"})
SERVER_ZONE_KEY = "_server"

# Whitelisted client-declared keys -> validator (returns True when acceptable).
_DECLARED_KEY_VALIDATORS: dict[str, Any] = {
    "editor_version": lambda v: isinstance(v, str) and 0 < len(v) <= 64,
    "editor_platform": lambda v: v in EDITOR_PLATFORMS,
    # May be a comma list in first-use order, e.g. "png,gif" (app message
    # 0003 §"details worth confirming" — accepted 2026-08-14).
    "imported_format": lambda v: isinstance(v, str) and 0 < len(v) <= 64,
    "device_type": lambda v: v in UPLOAD_DEVICE_TYPES,
}

USER_AGENT_MAX_CHARS = 256

# NoDerivatives licenses legally forbid derivatives — such posts can never be
# Remixable (L5, ADR 0003). Keep in sync with scripts/relicense_bulk_import.py.
ND_LICENSE_IDENTIFIERS = frozenset({"CC-BY-ND-4.0", "CC-BY-NC-ND-4.0"})


def resolve_remixable(declared: str | None, license_identifier: str | None) -> bool:
    """Resolve the effective ``remixable`` value at upload (L4/L5).

    Effective default: false for ND licenses, true otherwise. An explicit
    ``true`` on an ND-licensed post is a contradiction → 422.
    """
    is_nd = license_identifier in ND_LICENSE_IDENTIFIERS
    if declared is None or declared == "":
        return not is_nd
    wants_remixable = declared.lower() in ("true", "1", "yes")
    if wants_remixable and is_nd:
        raise AppError(
            ErrorCode.remixable_conflicts_with_license,
            "A NoDerivatives-licensed work cannot be marked Remixable.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return wants_remixable


def _invalid_source_details(reason: str) -> AppError:
    return AppError(
        ErrorCode.invalid_source_details,
        f"Invalid source_details: {reason}",
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def map_client_to_channel(client: str | None) -> str | None:
    """Prefix-map the raw declared ``client`` string to an upload_channel.

    Unrecognized prefixes map to None (unknown) — the raw string is still
    recorded in ``_server.declared_client``. Absence ≠ web and absence ≠ api.
    """
    if not client:
        return None
    if client.startswith("web"):
        return UPLOAD_CHANNEL_WEB
    if client.startswith("app"):
        return UPLOAD_CHANNEL_APP
    if client.startswith("api"):
        return UPLOAD_CHANNEL_API
    return None


def validate_creation_method(creation_method: str | None) -> str | None:
    """Validate a client-declared creation_method (None passes through)."""
    if creation_method is None:
        return None
    if creation_method not in CLIENT_DECLARABLE_CREATION_METHODS:
        raise AppError(
            ErrorCode.invalid_creation_method,
            "creation_method must be one of: "
            + ", ".join(sorted(CLIENT_DECLARABLE_CREATION_METHODS)),
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return creation_method


def parse_declared_source_details(raw: str | None) -> dict[str, Any]:
    """Parse + whitelist the client-declared ``source_details`` form field.

    Unknown keys are dropped silently; keys starting with ``_`` are reserved
    for the server and always discarded; known keys with invalid values are a
    422 (contract drift should be caught, not swallowed).
    """
    if raw is None or raw == "":
        return {}
    if len(raw.encode("utf-8")) > SOURCE_DETAILS_MAX_BYTES:
        raise _invalid_source_details(f"exceeds {SOURCE_DETAILS_MAX_BYTES} bytes")
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        raise _invalid_source_details("not valid JSON")
    if not isinstance(parsed, dict):
        raise _invalid_source_details("must be a JSON object")

    declared: dict[str, Any] = {}
    for key, value in parsed.items():
        if not isinstance(key, str) or key.startswith("_"):
            continue  # server-reserved zone: silently discarded
        validator = _DECLARED_KEY_VALIDATORS.get(key)
        if validator is None:
            continue  # unknown keys: silently dropped
        if not validator(value):
            raise _invalid_source_details(f"invalid value for {key!r}")
        declared[key] = value
    return declared


def build_server_zone(
    *,
    declared_client: str | None,
    user_agent: str | None,
    mkpx_at_upload: bool,
    inferred: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the server-observed ``_server`` zone (D2: trust + record)."""
    zone: dict[str, Any] = {
        "declared_client": declared_client,
        "user_agent": user_agent[:USER_AGENT_MAX_CHARS] if user_agent else None,
        "mkpx_at_upload": mkpx_at_upload,
    }
    if user_agent:
        device = detect_device_type(user_agent)
        if device.value in UPLOAD_DEVICE_TYPES:
            # Cross-check signal for the client-declared device_type (L7).
            zone["device_type"] = device.value
    if inferred:
        zone["inferred"] = inferred
    return zone


def compose_source_details(
    declared: dict[str, Any], server_zone: dict[str, Any]
) -> dict[str, Any] | None:
    """Merge declared keys with the ``_server`` zone; None when both empty."""
    if not declared and not server_zone:
        return None
    result = dict(declared)
    if server_zone:
        result[SERVER_ZONE_KEY] = server_zone
    return result


def snapshot_replaced_provenance(post: Any) -> dict[str, Any]:
    """Snapshot pre-replace declared provenance for ``_server.replaced[]`` (D5)."""
    declared = {
        k: v for k, v in (post.source_details or {}).items() if k != SERVER_ZONE_KEY
    }
    return {
        "at": datetime.now(timezone.utc).isoformat(),
        "upload_channel": post.upload_channel,
        "creation_method": post.creation_method,
        "declared": declared,
    }

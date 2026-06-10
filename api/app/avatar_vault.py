"""Avatar image storage utility.

Avatars are stored in a sub-vault inside the regular vault under avatar/
using a hash-based folder structure derived from the avatar UUID.

We intentionally store the raw bytes as-uploaded (no re-encoding) so that
animated GIF/WEBP avatars remain animated.

Unlike artwork, avatars have no stored shard column — the stored
``users.avatar_url`` is the reference, and filesystem paths are derived from
the UUID at call time using the *current* canonical sharding scheme
(``vault.compute_storage_shard``). During the resharding dual-location
window (docs/vault-resharding/), saves mirror to the twin scheme's path and
deletes remove both, so either URL form stays consistent with disk.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from uuid import UUID

from .settings import vault_public_base_url
from .vault import (
    compute_storage_shard,
    derive_twin_shard,
    should_mirror_to_twin,
    write_file_atomic,
)

logger = logging.getLogger(__name__)

# Maximum avatar file size: 5 MB
MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024

# Allowed image MIME types (avatars)
ALLOWED_MIME_TYPES: dict[str, str] = {
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
}


def get_vault_location() -> Path:
    """Get the vault location from environment variable."""
    vault_path = os.environ.get("VAULT_LOCATION")
    if not vault_path:
        raise ValueError("VAULT_LOCATION environment variable is not set")
    return Path(vault_path)


def get_avatar_vault_location() -> Path:
    """Get the avatar sub-vault location."""
    return get_vault_location() / "avatar"


def hash_avatar_id(avatar_id: UUID) -> str:
    """Hash the avatar UUID using SHA256 for folder structure derivation."""
    return hashlib.sha256(str(avatar_id).encode()).hexdigest()


def get_avatar_folder_path(avatar_id: UUID) -> Path:
    """
    Get the canonical folder path for an avatar (current sharding scheme).
    """
    return get_avatar_vault_location() / compute_storage_shard(avatar_id)


def _candidate_file_paths(avatar_id: UUID, extension: str) -> list[Path]:
    """
    The avatar's file path under the canonical scheme followed by its twin
    (the other sharding scheme). Both are touched by writes and deletes
    during the dual-location window.
    """
    ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    name = f"{avatar_id}{ext}"
    base = get_avatar_vault_location()
    canonical_shard = compute_storage_shard(avatar_id)
    twin_shard = derive_twin_shard(avatar_id, canonical_shard)
    return [base / canonical_shard / name, base / twin_shard / name]


def save_avatar_image(avatar_id: UUID, file_content: bytes, mime_type: str) -> Path:
    """
    Save an avatar image to the vault (canonical location + twin mirror).

    Args:
        avatar_id: The UUID of the avatar image
        file_content: Raw bytes (stored as-is, preserving animation)
        mime_type: Content type (image/png, image/jpeg, image/gif, image/webp)
    """
    mime_type_lower = (mime_type or "").lower()
    if mime_type_lower == "image/jpg":
        mime_type_lower = "image/jpeg"

    if mime_type_lower not in ALLOWED_MIME_TYPES:
        raise ValueError(
            f"MIME type '{mime_type}' is not allowed. Allowed types: {list(ALLOWED_MIME_TYPES.keys())}"
        )

    if len(file_content) > MAX_AVATAR_SIZE_BYTES:
        max_mb = MAX_AVATAR_SIZE_BYTES / (1024 * 1024)
        actual_mb = len(file_content) / (1024 * 1024)
        raise ValueError(
            f"File size ({actual_mb:.2f} MB) exceeds maximum of {max_mb} MB"
        )

    extension = ALLOWED_MIME_TYPES[mime_type_lower]
    canonical, twin = _candidate_file_paths(avatar_id, extension)

    write_file_atomic(canonical, file_content)
    logger.info(f"Saved avatar {avatar_id} to {canonical}")

    try:
        canonical_shard = compute_storage_shard(avatar_id)
        if should_mirror_to_twin(avatar_id, canonical_shard, twin.parent):
            write_file_atomic(twin, file_content)
    except Exception as e:
        logger.error(f"Dual-write mirror failed for avatar {avatar_id}: {e}")

    return canonical


def get_avatar_url(avatar_id: UUID, extension: str) -> str:
    """
    Get the public URL for an avatar image (canonical sharding scheme).

    When VAULT_PUBLIC_BASE_URL is set, returns an absolute URL on the Caddy
    vault subdomain (e.g. https://vault.makapix.club/avatar/<...>). Otherwise
    returns /api/vault/avatar/<...>, served by FastAPI StaticFiles via the
    Caddy reverse proxy (which strips /api before forwarding).
    """
    ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    prefix = vault_public_base_url() or "/api/vault"
    shard = compute_storage_shard(avatar_id)
    return f"{prefix}/avatar/{shard}/{avatar_id}{ext}"


def try_delete_avatar_by_public_url(avatar_url: str | None) -> bool:
    """
    Best-effort delete of an avatar file referenced by its public URL.

    Accepts both URL prefixes (/api/vault/avatar/... and the vault subdomain)
    and both sharding depths (v1 <c1>/<c2>/<c3> and v2 <c1>/<c2>). Deletes
    the path literally encoded in the URL plus both scheme-derived candidate
    paths, so a replacement during the dual-location window never leaves a
    stale copy serving the old image.

    Returns True if at least one file was deleted.
    """
    if not avatar_url:
        return False

    try:
        from urllib.parse import urlparse

        # Accept absolute URLs as well; normalize to just the path.
        path = urlparse(avatar_url).path if "://" in avatar_url else avatar_url

        # Strip the legacy /api/vault prefix so both forms collapse to
        # /avatar/<shard components>/<filename>.
        if path.startswith("/api/vault/avatar/"):
            path = path[len("/api/vault") :]
        if not path.startswith("/avatar/"):
            return False

        # Path parts: ["", "avatar", <2 or 3 shard components>, filename]
        parts = [p for p in path.split("/") if p]
        if len(parts) not in (4, 5):  # avatar + 2|3 components + filename
            return False

        filename = parts[-1]
        if "." not in filename:
            return False

        uuid_str, ext = filename.rsplit(".", 1)
        avatar_id = UUID(uuid_str)

        candidates = _candidate_file_paths(avatar_id, f".{ext}")
        url_path = get_avatar_vault_location().joinpath(*parts[1:-1]) / filename
        if url_path not in candidates:
            candidates.append(url_path)

        deleted = False
        for candidate in candidates:
            try:
                candidate.unlink()
                deleted = True
            except FileNotFoundError:
                pass
        return deleted
    except Exception as e:
        logger.warning(f"Failed to delete avatar for url={avatar_url}: {e}")
        return False

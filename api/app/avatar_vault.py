"""Avatar image storage utility.

Avatars are stored in a sub-vault inside the regular vault under avatar/
using a hash-based folder structure derived from the avatar UUID.

We intentionally store the raw bytes as-uploaded (no re-encoding) so that
animated GIF/WEBP avatars remain animated.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from uuid import UUID

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
    Get the folder path for an avatar based on its hashed ID.

    Example:
        hash = "a1b2c3d4..."
        folder = VAULT_LOCATION/avatar/a1/b2/c3/
    """
    avatar_vault_location = get_avatar_vault_location()
    hash_value = hash_avatar_id(avatar_id)
    return avatar_vault_location / hash_value[0:2] / hash_value[2:4] / hash_value[4:6]


def save_avatar_image(avatar_id: UUID, file_content: bytes, mime_type: str) -> Path:
    """
    Save an avatar image to the vault.

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
    folder_path = get_avatar_folder_path(avatar_id)
    folder_path.mkdir(parents=True, exist_ok=True)
    file_path = folder_path / f"{avatar_id}{extension}"

    with open(file_path, "wb") as f:
        f.write(file_content)

    logger.info(f"Saved avatar {avatar_id} to {file_path}")
    return file_path


def get_avatar_url(avatar_id: UUID, extension: str) -> str:
    """
    Get the public URL path for accessing an avatar image.

    We return an /api/vault/... path because the reverse proxy strips /api and
    the FastAPI app mounts the vault at /vault.
    """
    hash_value = hash_avatar_id(avatar_id)
    chunk1 = hash_value[0:2]
    chunk2 = hash_value[2:4]
    chunk3 = hash_value[4:6]

    ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    return f"/api/vault/avatar/{chunk1}/{chunk2}/{chunk3}/{avatar_id}{ext}"


def try_delete_avatar_by_public_url(avatar_url: str | None) -> bool:
    """
    Best-effort delete of an avatar file referenced by its public URL.

    We only delete avatars that match our vault URL scheme:
        /api/vault/avatar/<xx>/<yy>/<zz>/<uuid>.<ext>

    Returns True if we deleted a file, False otherwise.
    """
    if not avatar_url:
        return False

    try:
        from urllib.parse import urlparse

        # Accept absolute URLs as well; normalize to just the path.
        path = urlparse(avatar_url).path if "://" in avatar_url else avatar_url
        if not path.startswith("/api/vault/avatar/"):
            return False

        # Path parts: /api/vault/avatar/{c1}/{c2}/{c3}/{filename}
        parts = path.split("/")
        if len(parts) < 8:
            return False

        c1, c2, c3 = parts[4], parts[5], parts[6]
        filename = parts[7]
        if "." not in filename:
            return False

        uuid_str, ext = filename.rsplit(".", 1)
        avatar_id = UUID(uuid_str)

        vault_file = get_avatar_vault_location() / c1 / c2 / c3 / f"{avatar_id}.{ext}"
        if vault_file.exists():
            vault_file.unlink()
            return True
        return False
    except Exception as e:
        logger.warning(f"Failed to delete avatar for url={avatar_url}: {e}")
        return False

"""Blog image storage utility.

Blog images are stored in a sub-vault inside the regular vault under blog_image/
using the same hash-based folder structure as artwork images.

Like avatars (and unlike artwork), blog images have no stored shard column —
the stored URLs (``blog_posts.image_urls[]`` and markdown embeds in
``blog_posts.body``) are the reference, and filesystem paths are derived from
the UUID at call time using the *current* canonical sharding scheme
(``vault.compute_storage_shard``). During the resharding dual-location
window (docs/vault-resharding/), saves mirror to the twin scheme's path and
deletes remove both.
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

# Maximum file size: 10 MB
MAX_BLOG_IMAGE_SIZE_BYTES = 10 * 1024 * 1024

# Maximum images per blog post
MAX_IMAGES_PER_POST = 10

# Allowed image MIME types
ALLOWED_MIME_TYPES = {
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


def get_blog_vault_location() -> Path:
    """Get the blog image sub-vault location."""
    return get_vault_location() / "blog_image"


def hash_image_id(image_id: UUID) -> str:
    """Hash the image ID using SHA256 for folder structure derivation."""
    return hashlib.sha256(str(image_id).encode()).hexdigest()


def get_blog_image_folder_path(image_id: UUID) -> Path:
    """
    Get the canonical folder path for a blog image (current sharding scheme).
    """
    return get_blog_vault_location() / compute_storage_shard(image_id)


def _candidate_file_paths(image_id: UUID, extension: str) -> list[Path]:
    """
    The image's file path under the canonical scheme followed by its twin
    (the other sharding scheme). Both are touched by writes and deletes
    during the dual-location window.
    """
    ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    name = f"{image_id}{ext}"
    base = get_blog_vault_location()
    canonical_shard = compute_storage_shard(image_id)
    twin_shard = derive_twin_shard(image_id, canonical_shard)
    return [base / canonical_shard / name, base / twin_shard / name]


def get_blog_image_file_path(image_id: UUID, extension: str) -> Path:
    """
    Get the canonical file path for a blog image.

    Args:
        image_id: The UUID of the image
        extension: The file extension (e.g., ".png", ".jpg", ".gif")

    Returns:
        Full path where the image file should be stored
    """
    return _candidate_file_paths(image_id, extension)[0]


def save_blog_image(
    image_id: UUID,
    file_content: bytes,
    mime_type: str,
) -> Path:
    """
    Save a blog image to the vault (canonical location + twin mirror).

    Args:
        image_id: The UUID of the image
        file_content: The raw bytes of the image file
        mime_type: The MIME type of the image (image/png, image/jpeg, image/gif, etc.)

    Returns:
        The canonical path where the file was saved

    Raises:
        ValueError: If the MIME type is not allowed or file size exceeds limit
        OSError: If there's an error writing the file
    """
    # Normalize MIME type
    mime_type_lower = mime_type.lower()
    if mime_type_lower == "image/jpg":
        mime_type_lower = "image/jpeg"

    if mime_type_lower not in ALLOWED_MIME_TYPES:
        raise ValueError(
            f"MIME type '{mime_type}' is not allowed. Allowed types: {list(ALLOWED_MIME_TYPES.keys())}"
        )

    # Validate file size
    file_size = len(file_content)
    if file_size > MAX_BLOG_IMAGE_SIZE_BYTES:
        max_mb = MAX_BLOG_IMAGE_SIZE_BYTES / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        raise ValueError(
            f"File size ({actual_mb:.2f} MB) exceeds maximum of {max_mb} MB"
        )

    extension = ALLOWED_MIME_TYPES[mime_type_lower]
    canonical, twin = _candidate_file_paths(image_id, extension)

    try:
        write_file_atomic(canonical, file_content)
        logger.info(f"Saved blog image {image_id} to {canonical}")
    except OSError as e:
        logger.error(f"Failed to save blog image {image_id}: {e}")
        raise

    try:
        canonical_shard = compute_storage_shard(image_id)
        if should_mirror_to_twin(image_id, canonical_shard, twin.parent):
            write_file_atomic(twin, file_content)
    except Exception as e:
        logger.error(f"Dual-write mirror failed for blog image {image_id}: {e}")

    return canonical


def delete_blog_image(image_id: UUID, extension: str) -> bool:
    """
    Delete a blog image from the vault (canonical location and its twin).

    Args:
        image_id: The UUID of the image
        extension: The file extension

    Returns:
        True if at least one copy was deleted
    """
    deleted = False
    for candidate in _candidate_file_paths(image_id, extension):
        try:
            candidate.unlink()
            logger.info(f"Deleted blog image {image_id} from {candidate}")
            deleted = True
        except FileNotFoundError:
            pass
        except OSError as e:
            logger.error(f"Failed to delete blog image {image_id}: {e}")
            raise
    if not deleted:
        logger.warning(f"Blog image {image_id} not found in either vault location")
    return deleted


def get_blog_image_url(image_id: UUID, extension: str) -> str:
    """
    Get the URL for accessing a blog image (canonical sharding scheme).

    When VAULT_PUBLIC_BASE_URL is set, returns an absolute URL on the Caddy
    vault subdomain. Otherwise returns /api/vault/blog_image/<...>, served by
    FastAPI StaticFiles via the Caddy reverse proxy.

    Args:
        image_id: The UUID of the image
        extension: The file extension

    Returns:
        URL like https://vault.makapix.club/blog_image/a1/b2/c3/<uuid>.png
        or       /api/vault/blog_image/a1/b2/<uuid>.png
    """
    ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    prefix = vault_public_base_url() or "/api/vault"
    shard = compute_storage_shard(image_id)
    return f"{prefix}/blog_image/{shard}/{image_id}{ext}"


def validate_blog_image_file_size(file_size: int) -> tuple[bool, str | None]:
    """
    Validate that the file size is within limits.

    Args:
        file_size: File size in bytes

    Returns:
        Tuple of (is_valid, error_message)
    """
    if file_size > MAX_BLOG_IMAGE_SIZE_BYTES:
        max_mb = MAX_BLOG_IMAGE_SIZE_BYTES / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        return False, f"File size ({actual_mb:.2f} MB) exceeds maximum of {max_mb} MB"

    return True, None

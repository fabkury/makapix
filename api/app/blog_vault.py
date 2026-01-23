"""Blog image storage utility.

Blog images are stored in a sub-vault inside the regular vault under blog_image/
using the same hash-based folder structure as artwork images.

Example:
    If the image ID is "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    and it hashes to "a1b2c3..."
    The file will be stored at: VAULT_LOCATION/blog_image/a1/b2/c3/a1b2c3d4-e5f6-7890-abcd-ef1234567890.png
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from uuid import UUID

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
    Get the folder path for a blog image based on its hashed ID.

    The first 6 characters of the hash are split into 3 chunks of 2 characters
    to create a folder structure.

    Example:
        hash = "a1b2c3d4..."
        folder = VAULT_LOCATION/blog_image/a1/b2/c3/
    """
    blog_vault_location = get_blog_vault_location()
    hash_value = hash_image_id(image_id)

    # Split first 6 characters into 3 chunks of 2
    chunk1 = hash_value[0:2]
    chunk2 = hash_value[2:4]
    chunk3 = hash_value[4:6]

    return blog_vault_location / chunk1 / chunk2 / chunk3


def get_blog_image_file_path(image_id: UUID, extension: str) -> Path:
    """
    Get the full file path for a blog image.

    Args:
        image_id: The UUID of the image
        extension: The file extension (e.g., ".png", ".jpg", ".gif")

    Returns:
        Full path where the image file should be stored
    """
    folder_path = get_blog_image_folder_path(image_id)
    # Ensure extension is lowercase and starts with a dot
    ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    return folder_path / f"{image_id}{ext}"


def save_blog_image(
    image_id: UUID,
    file_content: bytes,
    mime_type: str,
) -> Path:
    """
    Save a blog image to the vault.

    Args:
        image_id: The UUID of the image
        file_content: The raw bytes of the image file
        mime_type: The MIME type of the image (image/png, image/jpeg, image/gif, etc.)

    Returns:
        The path where the file was saved

    Raises:
        ValueError: If the MIME type is not allowed or file size exceeds limit
        IOError: If there's an error writing the file
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
    file_path = get_blog_image_file_path(image_id, extension)

    # Create the directory structure if it doesn't exist
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the file
    try:
        with open(file_path, "wb") as f:
            f.write(file_content)
        logger.info(f"Saved blog image {image_id} to {file_path}")
        return file_path
    except IOError as e:
        logger.error(f"Failed to save blog image {image_id}: {e}")
        raise


def delete_blog_image(image_id: UUID, extension: str) -> bool:
    """
    Delete a blog image from the vault.

    Args:
        image_id: The UUID of the image
        extension: The file extension

    Returns:
        True if the file was deleted, False if it didn't exist
    """
    file_path = get_blog_image_file_path(image_id, extension)

    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted blog image {image_id} from {file_path}")
            return True
        else:
            logger.warning(f"Blog image {image_id} not found at {file_path}")
            return False
    except IOError as e:
        logger.error(f"Failed to delete blog image {image_id}: {e}")
        raise


def get_blog_image_url(image_id: UUID, extension: str) -> str:
    """
    Get the URL path for accessing a blog image.

    This returns a relative URL path that can be served by the API.

    Args:
        image_id: The UUID of the image
        extension: The file extension

    Returns:
        URL path like /api/vault/blog_image/a1/b2/c3/image-id.png
    """
    hash_value = hash_image_id(image_id)
    chunk1 = hash_value[0:2]
    chunk2 = hash_value[2:4]
    chunk3 = hash_value[4:6]

    ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"

    return f"/api/vault/blog_image/{chunk1}/{chunk2}/{chunk3}/{image_id}{ext}"


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

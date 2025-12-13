"""Vault storage utility for artwork images.

The vault stores artwork images using a hash-based folder structure
derived from the artwork ID to ensure no single folder has too many files.

Example:
    If the artwork ID is "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    and it hashes to "a1b2c3..."
    The file will be stored at: VAULT_LOCATION/a1/b2/c3/a1b2c3d4-e5f6-7890-abcd-ef1234567890.png
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from uuid import UUID

from .settings import MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES

logger = logging.getLogger(__name__)

# Maximum file size for artwork assets (bytes)
MAX_FILE_SIZE_BYTES = MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES

# Maximum canvas dimensions: 256x256
MAX_CANVAS_SIZE = 256

# Allowed image MIME types
ALLOWED_MIME_TYPES = {
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def get_vault_location() -> Path:
    """Get the vault location from environment variable."""
    vault_path = os.environ.get("VAULT_LOCATION")
    if not vault_path:
        raise ValueError("VAULT_LOCATION environment variable is not set")
    return Path(vault_path)


def hash_artwork_id(artwork_id: UUID) -> str:
    """Hash the artwork ID using SHA256 for folder structure derivation."""
    return hashlib.sha256(str(artwork_id).encode()).hexdigest()


def get_artwork_folder_path(artwork_id: UUID) -> Path:
    """
    Get the folder path for an artwork based on its hashed ID.
    
    The first 6 characters of the hash are split into 3 chunks of 2 characters
    to create a folder structure.
    
    Example:
        hash = "a1b2c3d4..."
        folder = VAULT_LOCATION/a1/b2/c3/
    """
    vault_location = get_vault_location()
    hash_value = hash_artwork_id(artwork_id)
    
    # Split first 6 characters into 3 chunks of 2
    chunk1 = hash_value[0:2]
    chunk2 = hash_value[2:4]
    chunk3 = hash_value[4:6]
    
    return vault_location / chunk1 / chunk2 / chunk3


def get_artwork_file_path(artwork_id: UUID, extension: str) -> Path:
    """
    Get the full file path for an artwork.
    
    Args:
        artwork_id: The UUID of the artwork
        extension: The file extension (e.g., ".png", ".jpg", ".gif")
    
    Returns:
        Full path where the artwork file should be stored
    """
    folder_path = get_artwork_folder_path(artwork_id)
    # Ensure extension is lowercase and starts with a dot
    ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    return folder_path / f"{artwork_id}{ext}"


def save_artwork_to_vault(
    artwork_id: UUID,
    file_content: bytes,
    mime_type: str,
) -> Path:
    """
    Save an artwork image to the vault.
    
    Args:
        artwork_id: The UUID of the artwork (post ID)
        file_content: The raw bytes of the image file
        mime_type: The MIME type of the image (image/png, image/jpeg, image/gif)
    
    Returns:
        The path where the file was saved
    
    Raises:
        ValueError: If the MIME type is not allowed
        IOError: If there's an error writing the file
    """
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"MIME type '{mime_type}' is not allowed. Allowed types: {list(ALLOWED_MIME_TYPES.keys())}")
    
    extension = ALLOWED_MIME_TYPES[mime_type]
    file_path = get_artwork_file_path(artwork_id, extension)
    
    # Create the directory structure if it doesn't exist
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write the file
    try:
        with open(file_path, "wb") as f:
            f.write(file_content)
        logger.info(f"Saved artwork {artwork_id} to {file_path}")
        return file_path
    except IOError as e:
        logger.error(f"Failed to save artwork {artwork_id}: {e}")
        raise


def delete_artwork_from_vault(artwork_id: UUID, extension: str) -> bool:
    """
    Delete an artwork image from the vault.
    
    Args:
        artwork_id: The UUID of the artwork
        extension: The file extension
    
    Returns:
        True if the file was deleted, False if it didn't exist
    """
    file_path = get_artwork_file_path(artwork_id, extension)
    
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted artwork {artwork_id} from {file_path}")
            return True
        else:
            logger.warning(f"Artwork {artwork_id} not found at {file_path}")
            return False
    except IOError as e:
        logger.error(f"Failed to delete artwork {artwork_id}: {e}")
        raise


def get_artwork_url(artwork_id: UUID, extension: str) -> str:
    """
    Get the URL path for accessing an artwork.
    
    This returns a relative URL path that can be served by the API.
    
    Args:
        artwork_id: The UUID of the artwork
        extension: The file extension
    
    Returns:
        URL path like /api/vault/a1/b2/c3/artwork-id.png
    """
    hash_value = hash_artwork_id(artwork_id)
    chunk1 = hash_value[0:2]
    chunk2 = hash_value[2:4]
    chunk3 = hash_value[4:6]
    
    ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
    
    return f"/api/vault/{chunk1}/{chunk2}/{chunk3}/{artwork_id}{ext}"


def validate_image_dimensions(width: int, height: int) -> tuple[bool, str | None]:
    """
    Validate image dimensions according to Makapix Club size rules.
    
    Rules:
    - Under 128x128: Only specific sizes allowed (8x8, 8x16, 16x8, 16x16, 16x32, 32x16, 32x32, 32x64, 64x32, 64x64, 64x128, 128x64)
      All 90-degree rotations of these sizes are also allowed (e.g., 8x16 and 16x8 are both valid)
    - From 128x128 to 256x256 (inclusive): Any size allowed (square or rectangular)
    - Above 256x256: Not allowed
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if width < 1 or height < 1:
        return False, "Image dimensions must be at least 1x1"
    
    # Check if either dimension exceeds 256
    if width > 256 or height > 256:
        return False, f"Image dimensions exceed maximum of 256x256. Got {width}x{height}"
    
    # Define allowed sizes for dimensions under 128x128
    # Includes both orientations (e.g., 8x16 and 16x8 are both allowed)
    allowed_sizes = [
        (8, 8), (8, 16), (16, 8), (8, 32), (32, 8),
        (16, 16), (16, 32), (32, 16),
        (32, 32), (32, 64), (64, 32),
        (64, 64), (64, 128), (128, 64),
    ]
    
    # If both dimensions are >= 128, any size is allowed (up to 256x256)
    if width >= 128 and height >= 128:
        return True, None
    
    # Otherwise, check if the size is in the allowed list
    # This covers cases where at least one dimension is < 128
    if (width, height) not in allowed_sizes:
        # Create a sorted list for the error message (remove duplicates)
        unique_sizes = sorted(set(allowed_sizes))
        allowed_str = ", ".join([f"{w}x{h}" for w, h in unique_sizes])
        return False, f"Image size {width}x{height} is not allowed. Under 128x128, only these sizes are allowed (rotations included): {allowed_str}"
    
    return True, None


def validate_file_size(file_size: int) -> tuple[bool, str | None]:
    """
    Validate that the file size is within limits.
    
    Args:
        file_size: File size in bytes
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if file_size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        return False, f"File size ({actual_mb:.2f} MB) exceeds maximum of {max_mb} MB"
    
    return True, None


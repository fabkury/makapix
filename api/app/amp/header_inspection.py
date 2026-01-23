"""AMP Phase A: Header inspection for fail-fast validation.

Reads file headers before loading the full image with Pillow to validate:
- File extension
- File size
- Canvas dimensions (extracted from format-specific headers)
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from .constants import (
    ALLOWED_EXTENSIONS,
    ALLOWED_SMALL_SIZES,
    MAX_CANVAS_SIZE,
    MAX_FILE_SIZE_BYTES,
)


@dataclass
class HeaderResult:
    """Result of header inspection."""

    success: bool
    width: int | None = None
    height: int | None = None
    error_code: str | None = None
    error_message: str | None = None


def inspect_header(file_path: Path) -> HeaderResult:
    """
    Inspect file header for early validation before Pillow load.

    Validates:
    1. File extension
    2. File size
    3. Canvas dimensions (from header)

    Returns HeaderResult with success status and extracted dimensions or error.
    """
    # 1. Validate file extension (case-insensitive)
    extension = file_path.suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return HeaderResult(
            success=False,
            error_code="INVALID_EXTENSION",
            error_message=f"File extension '{extension}' is not allowed. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 2. Validate file size
    try:
        file_size = file_path.stat().st_size
    except OSError as e:
        return HeaderResult(
            success=False,
            error_code="FILE_NOT_FOUND",
            error_message=f"Could not read file: {e}",
        )

    if file_size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        return HeaderResult(
            success=False,
            error_code="FILE_TOO_LARGE",
            error_message=f"File size ({actual_mb:.2f} MB) exceeds maximum of {max_mb:.2f} MB",
        )

    # 3. Extract dimensions from header based on format
    try:
        if extension == ".png":
            width, height = _read_png_header(file_path)
        elif extension == ".gif":
            width, height = _read_gif_header(file_path)
        elif extension == ".webp":
            width, height = _read_webp_header(file_path)
        elif extension == ".bmp":
            width, height = _read_bmp_header(file_path)
        else:
            # Should never reach here due to extension validation
            return HeaderResult(
                success=False,
                error_code="UNSUPPORTED_FORMAT",
                error_message=f"Unsupported format: {extension}",
            )
    except Exception as e:
        return HeaderResult(
            success=False,
            error_code="HEADER_READ_FAILED",
            error_message=f"Failed to read {extension} header: {e}",
        )

    # 4. Validate canvas dimensions
    validation_error = _validate_dimensions(width, height)
    if validation_error:
        return HeaderResult(
            success=False,
            width=width,
            height=height,
            error_code="INVALID_DIMENSIONS",
            error_message=validation_error,
        )

    return HeaderResult(success=True, width=width, height=height)


def _read_png_header(file_path: Path) -> tuple[int, int]:
    """
    Read PNG header to extract width and height.

    PNG structure:
    - 8 bytes: PNG signature
    - 4 bytes: IHDR chunk length (should be 13)
    - 4 bytes: "IHDR" chunk type
    - 4 bytes: width (big-endian)
    - 4 bytes: height (big-endian)
    """
    with open(file_path, "rb") as f:
        # Read PNG signature (8 bytes)
        signature = f.read(8)
        if signature != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Invalid PNG signature")

        # Read IHDR chunk length (4 bytes)
        chunk_length = struct.unpack(">I", f.read(4))[0]
        if chunk_length != 13:
            raise ValueError(f"Invalid IHDR chunk length: {chunk_length}")

        # Read IHDR chunk type (4 bytes)
        chunk_type = f.read(4)
        if chunk_type != b"IHDR":
            raise ValueError(f"Expected IHDR chunk, got {chunk_type}")

        # Read width and height (4 bytes each, big-endian)
        width = struct.unpack(">I", f.read(4))[0]
        height = struct.unpack(">I", f.read(4))[0]

        return width, height


def _read_gif_header(file_path: Path) -> tuple[int, int]:
    """
    Read GIF header to extract width and height.

    GIF structure:
    - 6 bytes: GIF signature ("GIF87a" or "GIF89a")
    - 2 bytes: width (little-endian)
    - 2 bytes: height (little-endian)
    """
    with open(file_path, "rb") as f:
        # Read GIF signature (6 bytes)
        signature = f.read(6)
        if signature not in (b"GIF87a", b"GIF89a"):
            raise ValueError(f"Invalid GIF signature: {signature}")

        # Read width and height (2 bytes each, little-endian)
        width = struct.unpack("<H", f.read(2))[0]
        height = struct.unpack("<H", f.read(2))[0]

        return width, height


def _read_webp_header(file_path: Path) -> tuple[int, int]:
    """
    Read WebP header to extract width and height.

    WebP structure:
    - 4 bytes: "RIFF"
    - 4 bytes: file size - 8
    - 4 bytes: "WEBP"
    - Then chunks (VP8, VP8L, or VP8X)

    VP8X (extended format):
    - 4 bytes: "VP8X"
    - 4 bytes: chunk size
    - 1 byte: flags
    - 3 bytes: reserved
    - 3 bytes: canvas width - 1 (24-bit little-endian)
    - 3 bytes: canvas height - 1 (24-bit little-endian)

    VP8L (lossless):
    - 4 bytes: "VP8L"
    - 4 bytes: chunk size
    - 1 byte: signature (0x2f)
    - 4 bytes: packed bits with width/height

    VP8 (lossy):
    - 4 bytes: "VP8 "
    - 4 bytes: chunk size
    - Then key frame data with dimensions
    """
    with open(file_path, "rb") as f:
        # Read RIFF header
        riff_tag = f.read(4)
        if riff_tag != b"RIFF":
            raise ValueError("Invalid WebP: missing RIFF header")

        file_size = struct.unpack("<I", f.read(4))[0]

        webp_tag = f.read(4)
        if webp_tag != b"WEBP":
            raise ValueError("Invalid WebP: missing WEBP tag")

        # Read first chunk
        chunk_tag = f.read(4)
        chunk_size = struct.unpack("<I", f.read(4))[0]

        if chunk_tag == b"VP8X":
            # Extended format
            f.read(4)  # Skip flags and reserved bytes
            # Read 24-bit width and height (stored as width-1 and height-1)
            width_bytes = f.read(3) + b"\x00"
            height_bytes = f.read(3) + b"\x00"
            width = struct.unpack("<I", width_bytes)[0] + 1
            height = struct.unpack("<I", height_bytes)[0] + 1
            return width, height

        elif chunk_tag == b"VP8L":
            # Lossless format
            signature = f.read(1)
            if signature != b"\x2f":
                raise ValueError("Invalid VP8L signature")

            # Read 4 bytes containing packed width/height
            packed = struct.unpack("<I", f.read(4))[0]
            # Width is 14 bits, height is 14 bits
            width = (packed & 0x3FFF) + 1
            height = ((packed >> 14) & 0x3FFF) + 1
            return width, height

        elif chunk_tag == b"VP8 ":
            # Lossy format
            # Skip frame tag (3 bytes)
            frame_tag = f.read(3)
            if frame_tag != b"\x9d\x01\x2a":
                raise ValueError("Invalid VP8 frame tag")

            # Read width and height (2 bytes each, little-endian)
            size_bytes = f.read(4)
            width = struct.unpack("<H", size_bytes[0:2])[0] & 0x3FFF
            height = struct.unpack("<H", size_bytes[2:4])[0] & 0x3FFF
            return width, height

        else:
            raise ValueError(f"Unsupported WebP chunk type: {chunk_tag}")


def _read_bmp_header(file_path: Path) -> tuple[int, int]:
    """
    Read BMP header to extract width and height.

    BMP structure:
    - 2 bytes: "BM" signature
    - 4 bytes: file size
    - 4 bytes: reserved
    - 4 bytes: pixel data offset
    - 4 bytes: DIB header size (determines header version)
    - 4 bytes: width (signed 32-bit integer)
    - 4 bytes: height (signed 32-bit integer, can be negative for top-down)
    """
    with open(file_path, "rb") as f:
        # Read BMP signature (2 bytes)
        signature = f.read(2)
        if signature != b"BM":
            raise ValueError(f"Invalid BMP signature: {signature}")

        # Skip file size, reserved, and pixel data offset (12 bytes)
        f.read(12)

        # Read DIB header size (4 bytes)
        dib_header_size = struct.unpack("<I", f.read(4))[0]

        # BITMAPCOREHEADER (OS/2 1.x) has 12-byte header with 16-bit dimensions
        if dib_header_size == 12:
            width = struct.unpack("<H", f.read(2))[0]
            height = struct.unpack("<H", f.read(2))[0]
        else:
            # BITMAPINFOHEADER and later have 32-bit signed dimensions
            width = struct.unpack("<i", f.read(4))[0]
            height = struct.unpack("<i", f.read(4))[0]
            # Height can be negative for top-down DIBs
            height = abs(height)

        if width <= 0:
            raise ValueError(f"Invalid BMP width: {width}")

        return width, height


def _validate_dimensions(width: int, height: int) -> str | None:
    """
    Validate canvas dimensions according to Makapix Club rules.

    Returns None if valid, error message otherwise.
    """
    if width < 1 or height < 1:
        return "Image dimensions must be at least 1x1"

    # Check if either dimension exceeds 256
    if width > MAX_CANVAS_SIZE or height > MAX_CANVAS_SIZE:
        return f"Image dimensions exceed maximum of {MAX_CANVAS_SIZE}x{MAX_CANVAS_SIZE}. Got {width}x{height}"

    # If both dimensions are >= 128, any size is allowed (up to 256x256)
    if width >= 128 and height >= 128:
        return None

    # Otherwise, check if the size is in the allowed list
    if (width, height) not in ALLOWED_SMALL_SIZES:
        unique_sizes = sorted(set(ALLOWED_SMALL_SIZES))
        allowed_str = ", ".join([f"{w}x{h}" for w, h in unique_sizes])
        return f"Image size {width}x{height} is not allowed. Under 128x128, only these sizes are allowed: {allowed_str}"

    return None

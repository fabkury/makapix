"""AMP Phase B: Metadata extraction from Pillow-loaded images.

Extracts comprehensive metadata including:
- Dimensions and file format
- Animation frame data
- Unique colors
- Transparency metadata and actual transparency
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .constants import MAX_FRAMES_TO_SCAN


@dataclass
class AMPMetadata:
    """Complete AMP metadata for an artwork file."""

    # Dimensions
    width: int
    height: int
    base: int  # min(width, height)
    size: int  # max(width, height)
    file_bytes: int

    # Format
    file_format: str  # "png", "gif", "webp", "bmp"

    # Animation
    frame_count: int
    shortest_duration_ms: int | None  # None for static images
    longest_duration_ms: int | None  # None for static images

    # Colors
    unique_colors: int  # Max unique colors in any single frame

    # Transparency metadata (from file metadata)
    transparency_meta: bool  # File claims transparency capability
    alpha_meta: bool  # File claims alpha channel

    # Transparency actual (from pixel scanning)
    transparency_actual: bool  # Actual transparent pixels found
    alpha_actual: bool  # Actual semi-transparent pixels found


def extract_metadata(file_path: Path, img: Image.Image) -> AMPMetadata:
    """
    Extract all AMP metadata from a Pillow-loaded image.

    Args:
        file_path: Path to the image file (for file_bytes calculation)
        img: Pillow Image object (already loaded)

    Returns:
        AMPMetadata with all extracted fields
    """
    # Basic dimensions and file info
    width, height = img.size
    file_bytes = file_path.stat().st_size

    # File format (normalize to lowercase)
    file_format = _normalize_format(img.format)

    # Animation metadata
    frame_count = _get_frame_count(img)
    shortest_duration_ms, longest_duration_ms = _get_frame_durations(img, frame_count)

    # Unique colors (max across all frames)
    unique_colors = _get_max_unique_colors(img, frame_count)

    # Transparency metadata from file
    transparency_meta, alpha_meta = _get_transparency_metadata(img)

    # Transparency actual from pixel scanning
    # Only scan if metadata claims transparency/alpha support
    transparency_actual, alpha_actual = _get_transparency_actual(
        img, frame_count, transparency_meta, alpha_meta
    )

    # Compute derived dimension fields
    base = min(width, height)
    size = max(width, height)

    return AMPMetadata(
        width=width,
        height=height,
        base=base,
        size=size,
        file_bytes=file_bytes,
        file_format=file_format,
        frame_count=frame_count,
        shortest_duration_ms=shortest_duration_ms,
        longest_duration_ms=longest_duration_ms,
        unique_colors=unique_colors,
        transparency_meta=transparency_meta,
        alpha_meta=alpha_meta,
        transparency_actual=transparency_actual,
        alpha_actual=alpha_actual,
    )


def _normalize_format(fmt: str | None) -> str:
    """
    Normalize Pillow format to lowercase standard.

    Raises:
        ValueError: If format cannot be determined or is not supported.
    """
    if not fmt:
        raise ValueError("Cannot determine file format")
    fmt_lower = fmt.lower()
    # Map common variants
    if fmt_lower in ("png", "gif", "webp", "bmp"):
        return fmt_lower
    # BMP variants
    if fmt_lower in ("dib", "bitmap"):
        return "bmp"
    raise ValueError(f"Unsupported file format: {fmt}")


def _get_frame_count(img: Image.Image) -> int:
    """Get the number of frames in the image."""
    try:
        return getattr(img, "n_frames", 1)
    except Exception:
        return 1


def _get_frame_durations(
    img: Image.Image, frame_count: int
) -> tuple[int | None, int | None]:
    """
    Get shortest and longest frame durations in milliseconds.

    Returns (None, None) for static images.
    """
    if frame_count <= 1:
        return None, None

    try:
        durations = []
        original_frame = img.tell() if hasattr(img, "tell") else 0

        for frame_idx in range(frame_count):
            img.seek(frame_idx)
            duration = img.info.get("duration")
            if duration is not None and duration > 0:
                durations.append(duration)

        # Restore original frame
        img.seek(original_frame)

        if durations:
            return min(durations), max(durations)
        return None, None
    except Exception:
        return None, None


def _get_max_unique_colors(img: Image.Image, frame_count: int) -> int:
    """
    Get the maximum number of unique colors in any single frame.

    For static images, returns unique colors in the image.
    For animations, computes unique colors per frame and returns max.
    """
    try:
        if frame_count <= 1:
            # Static image
            return _count_unique_colors_in_frame(img)

        # Animation: find max unique colors across frames
        max_colors = 0
        original_frame = img.tell() if hasattr(img, "tell") else 0
        frames_to_check = min(frame_count, MAX_FRAMES_TO_SCAN)

        for frame_idx in range(frames_to_check):
            img.seek(frame_idx)
            colors = _count_unique_colors_in_frame(img)
            max_colors = max(max_colors, colors)

        # Restore original frame
        img.seek(original_frame)

        return max_colors
    except Exception:
        # If we can't count, return a safe default
        return 0


def _count_unique_colors_in_frame(img: Image.Image) -> int:
    """Count unique colors in a single frame."""
    try:
        # Convert to RGB/RGBA for consistent color counting
        if img.mode in ("RGBA", "LA", "PA"):
            frame = img.convert("RGBA")
        else:
            frame = img.convert("RGB")

        # Use getcolors with no limit to get all unique colors
        colors = frame.getcolors(maxcolors=frame.width * frame.height + 1)

        if colors is None:
            # getcolors returned None, meaning too many colors
            # Fall back to pixel-by-pixel counting (slower but accurate)
            pixels = set(frame.getdata())
            return len(pixels)

        return len(colors)
    except Exception:
        return 0


def _get_transparency_metadata(img: Image.Image) -> tuple[bool, bool]:
    """
    Determine transparency metadata from file metadata/format.

    Returns:
        (transparency_meta, alpha_meta)
        - transparency_meta: File format supports transparency
        - alpha_meta: File format supports alpha channel
    """
    mode = img.mode
    info = getattr(img, "info", {})

    # Modes with full alpha channel
    if mode in ("RGBA", "LA", "PA"):
        return True, True

    # Palette mode with transparency index
    if mode == "P" and "transparency" in info:
        # Palette with transparency index is considered transparency but not alpha
        # (since palette transparency is binary: transparent or opaque)
        return True, False

    # No transparency support
    return False, False


def _get_transparency_actual(
    img: Image.Image,
    frame_count: int,
    transparency_meta: bool,
    alpha_meta: bool,
) -> tuple[bool, bool]:
    """
    Determine actual transparency by scanning pixels.

    Only scans if metadata claims transparency/alpha support.
    Returns (transparency_actual, alpha_actual).

    Per AMP requirements:
    - If metadata claims no transparency, both are False (no scan needed)
    - If metadata claims no alpha, alpha_actual is False (no alpha scan needed)
    - transparency_actual: True if any pixel has alpha != 255
    - alpha_actual: True if any pixel has alpha not in {0, 255}
    """
    # If metadata claims no transparency, skip scanning
    if not transparency_meta:
        return False, False

    # If metadata claims no alpha channel, alpha_actual must be False
    # But we still need to check for binary transparency
    if not alpha_meta:
        transparency_actual = _scan_for_binary_transparency(img, frame_count)
        return transparency_actual, False

    # Full scan for both transparency and alpha
    return _scan_for_transparency_and_alpha(img, frame_count)


def _scan_for_binary_transparency(img: Image.Image, frame_count: int) -> bool:
    """
    Scan for binary transparency (fully transparent pixels).

    Used when file has transparency support but no alpha channel.
    """
    try:
        frames_to_scan = min(frame_count, MAX_FRAMES_TO_SCAN)
        original_frame = img.tell() if hasattr(img, "tell") else 0

        for frame_idx in range(frames_to_scan):
            if frame_count > 1:
                img.seek(frame_idx)

            # Convert to RGBA to get alpha channel
            rgba = img.convert("RGBA")
            alpha = rgba.getchannel("A")

            # Check if any pixel is not fully opaque
            a_min, a_max = alpha.getextrema()
            if a_min < 255:
                # Found at least one non-opaque pixel
                if frame_count > 1:
                    img.seek(original_frame)
                return True

        if frame_count > 1:
            img.seek(original_frame)
        return False
    except Exception:
        return False


def _scan_for_transparency_and_alpha(
    img: Image.Image, frame_count: int
) -> tuple[bool, bool]:
    """
    Scan for both transparency and alpha (semi-transparent pixels).

    Returns (transparency_actual, alpha_actual).
    """
    try:
        transparency_actual = False
        alpha_actual = False

        frames_to_scan = min(frame_count, MAX_FRAMES_TO_SCAN)
        original_frame = img.tell() if hasattr(img, "tell") else 0

        for frame_idx in range(frames_to_scan):
            if frame_count > 1:
                img.seek(frame_idx)

            # Convert to RGBA to get alpha channel
            rgba = img.convert("RGBA")
            alpha = rgba.getchannel("A")

            a_min, a_max = alpha.getextrema()

            # Fast path: fully opaque frame
            if a_min == 255 and a_max == 255:
                continue

            # At least one pixel is not fully opaque
            transparency_actual = True

            # If we already proved alpha_actual, we can stop
            if alpha_actual:
                break

            # Check for semi-transparent pixels (alpha in range 1-254)
            hist = alpha.histogram()
            if sum(hist[1:255]) > 0:
                alpha_actual = True
                # Both conditions met, can stop early
                break

        if frame_count > 1:
            img.seek(original_frame)

        return transparency_actual, alpha_actual
    except Exception:
        return False, False


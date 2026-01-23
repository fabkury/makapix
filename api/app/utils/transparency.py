"""Transparency metadata extraction for uploaded artworks.

Makapix Club defines "transparency-metadata" as:
- uses_transparency: True if any pixel anywhere has alpha != 255
- uses_alpha: True if any pixel anywhere has alpha not in {0, 255}

Notes:
- We do NOT trust file-reported "has transparency" to set these values to True.
  We only use file metadata to short-circuit the *negative* case:
  if metadata indicates the file has no transparency capability, we treat it as
  no-transparency/no-alpha without scanning pixels.
- We scan at most the first 256 frames for animated formats.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

MAX_FRAMES_TO_SCAN = 256


@dataclass(frozen=True)
class TransparencyMetadata:
    uses_alpha: bool
    uses_transparency: bool


def _metadata_claims_no_transparency(img: Image.Image) -> bool:
    """
    Return True if image metadata indicates the image cannot have transparency.

    Per product requirement: if metadata claims NO transparency/alpha, then the
    image is treated as NO transparency/alpha, without pixel scanning.
    """
    # Modes that carry an alpha channel.
    if img.mode in ("RGBA", "LA", "PA"):
        return False

    # Palette images can carry a transparency index in info (e.g. GIF/PNG paletted).
    if img.mode == "P" and "transparency" in getattr(img, "info", {}):
        return False

    # Other modes (RGB, L, CMYK, etc.) are treated as no transparency.
    return True


def compute_transparency_metadata(img: Image.Image) -> TransparencyMetadata:
    """
    Compute transparency metadata for an image by scanning pixels.

    If metadata indicates no transparency support, returns (False, False) without scanning.

    Raises:
        Exception: if Pillow cannot decode frames/pixels as expected.
        NOTE: This is intentionally not swallowed. Failure to compute this metadata
        should be treated as a serious issue; later we may mark uploads unhealthy
        or refuse them. For now we just fail the request path that calls this.
    """
    if _metadata_claims_no_transparency(img):
        return TransparencyMetadata(uses_alpha=False, uses_transparency=False)

    uses_transparency = False
    uses_alpha = False

    # Pillow animated images expose n_frames and require seek().
    n_frames = int(getattr(img, "n_frames", 1) or 1)
    frames_to_scan = min(n_frames, MAX_FRAMES_TO_SCAN)

    # Preserve caller's current frame position if possible.
    original_frame = getattr(img, "tell", lambda: 0)()
    try:
        for frame_idx in range(frames_to_scan):
            img.seek(frame_idx)

            # Convert to RGBA so we always have an alpha channel to examine.
            rgba = img.convert("RGBA")
            alpha = rgba.getchannel("A")

            a_min, a_max = alpha.getextrema()

            # Fast path: fully opaque frame.
            if a_min == 255 and a_max == 255:
                continue

            # At least one pixel is not fully opaque.
            uses_transparency = True

            # If we already proved uses_alpha earlier, we can stop.
            if uses_alpha:
                break

            # Detect any alpha value between 1..254 (semi-transparent).
            # Histogram is 256 bins (0..255). Any count in 1..254 implies uses_alpha.
            hist = alpha.histogram()
            if sum(hist[1:255]) > 0:
                uses_alpha = True
                # uses_alpha implies uses_transparency, so we can stop early.
                break

        return TransparencyMetadata(
            uses_alpha=uses_alpha, uses_transparency=uses_transparency
        )
    finally:
        # Best-effort restore original frame to avoid surprising callers.
        try:
            img.seek(original_frame)
        except Exception:
            pass

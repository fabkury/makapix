"""AMP validation constants and configuration."""

from __future__ import annotations

from ..settings import MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES

# Allowed file extensions (case-insensitive)
ALLOWED_EXTENSIONS = {".png", ".gif", ".webp", ".bmp"}

# Maximum file size for artwork assets (bytes)
MAX_FILE_SIZE_BYTES = MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES

# Maximum canvas dimensions: 256x256
MAX_CANVAS_SIZE = 256

# Allowed sizes for dimensions under 128x128
# Includes both orientations (e.g., 8x16 and 16x8 are both allowed)
ALLOWED_SMALL_SIZES = [
    (8, 8), (8, 16), (16, 8), (8, 32), (32, 8),
    (16, 16), (16, 32), (32, 16),
    (32, 32), (32, 64), (64, 32),
    (64, 64), (64, 128), (128, 64),
]

# Maximum number of frames to scan for transparency/color analysis
MAX_FRAMES_TO_SCAN = 1024


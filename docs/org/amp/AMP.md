# Artwork Metadata Platform (AMP)

The **Artwork Metadata Platform (AMP)** is Makapix Club's comprehensive system for file handling, validation, and metadata collection for every artwork uploaded to the platform.

## Overview

AMP serves two critical purposes:

1. **Safety and Sanitization**: Validates and rejects faulty, malicious, or non-conformant files before they enter the system
2. **Metadata Collection**: Extracts comprehensive metadata from artwork files to enable querying, filtering, and display optimization

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Artwork Upload                              │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AMP Inspector (amp_inspector.py)                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ PHASE A: Header Inspection (Fail-Fast)                      │   │
│  │  • File extension validation (case-insensitive)             │   │
│  │  • File size validation                                     │   │
│  │  • Header-based dimension extraction (before Pillow load)   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                   Validation Pass?                                  │
│                      │      │                                       │
│                    Yes      No ──────────► Reject with Error        │
│                      │                                              │
│                      ▼                                              │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ PHASE B: Metadata Extraction (Pillow-based)                 │   │
│  │  • Load image with Pillow                                   │   │
│  │  • Extract dimensions, format, bit depth                    │   │
│  │  • Count animation frames and durations                     │   │
│  │  • Count unique colors (per frame, keep max)                │   │
│  │  • Detect transparency metadata and actual transparency     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│                      JSON Output (success + metadata)               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Backend (posts.py)                               │
│  • Parse AMP JSON output                                            │
│  • Populate Post model with metadata                                │
│  • Save artwork to vault                                            │
│  • Create database record                                           │
└─────────────────────────────────────────────────────────────────────┘
```

## Supported File Formats

| Format | Extension | Animation Support | Transparency Support |
|--------|-----------|-------------------|---------------------|
| PNG    | `.png`    | APNG (via Pillow) | Yes (RGBA, palette) |
| GIF    | `.gif`    | Yes               | Yes (palette index) |
| WebP   | `.webp`   | Yes               | Yes (RGBA)          |
| BMP    | `.bmp`    | No                | Limited             |

## Components

### Phase A: Header Inspection

Located in `api/app/amp/header_inspection.py`

Header inspection performs fast, fail-early validation before loading the full image:

1. **Extension Validation**: Checks file extension against allowed list (case-insensitive)
2. **File Size Validation**: Ensures file doesn't exceed size limit
3. **Dimension Extraction**: Reads format-specific headers to extract canvas dimensions without loading the full image

#### Header Parsing by Format

| Format | Header Location | Dimension Fields |
|--------|-----------------|------------------|
| PNG    | IHDR chunk (bytes 16-23) | 4-byte width, 4-byte height (big-endian) |
| GIF    | Logical Screen Descriptor (bytes 6-9) | 2-byte width, 2-byte height (little-endian) |
| WebP   | VP8/VP8L/VP8X chunk | Varies by chunk type |
| BMP    | DIB header (after 14-byte file header) | 4-byte width, 4-byte height (little-endian, signed) |

### Phase B: Metadata Extraction

Located in `api/app/amp/metadata_extraction.py`

After header validation passes, the full image is loaded with Pillow to extract:

| Field | Description |
|-------|-------------|
| `width` | Canvas width in pixels |
| `height` | Canvas height in pixels |
| `file_bytes` | Exact file size in bytes |
| `file_format` | Normalized format (png, gif, webp, bmp) |
| `bit_depth` | Per-channel bit depth (e.g., 8, 16) |
| `frame_count` | Number of animation frames (1 for static) |
| `shortest_duration_ms` | Duration of shortest frame (animations only) |
| `longest_duration_ms` | Duration of longest frame (animations only) |
| `unique_colors` | Maximum unique colors in any single frame |
| `transparency_meta` | File format claims transparency support |
| `alpha_meta` | File format claims alpha channel support |
| `transparency_actual` | Actual transparent pixels found (alpha < 255) |
| `alpha_actual` | Actual semi-transparent pixels found (0 < alpha < 255) |
| `sha256` | SHA256 hash of the entire file |

### Main Inspector Script

Located in `api/app/amp/amp_inspector.py`

The CLI entry point that orchestrates both phases.

## Usage

### Command Line (Human Mode)

```bash
python -m app.amp.amp_inspector /path/to/image.png
```

Prints progress messages to stderr and JSON output to stdout:

```
Inspecting file: /path/to/image.png
Phase A: Header inspection...
  ✓ Extension: .png
  ✓ Dimensions: 64x64
  ✓ File size: 1,234 bytes
Phase B: Loading image with Pillow...
Phase B: Extracting metadata...

✓ Inspection complete!

Metadata:
{
  "success": true,
  "metadata": { ... }
}

JSON output:
{"success": true, "metadata": {...}}
```

### Backend Mode (Silent)

```bash
python -m app.amp.amp_inspector --backend /path/to/image.png
```

Only outputs JSON to stdout (no progress messages):

```json
{"success": true, "metadata": {"width": 64, "height": 64, ...}}
```

### CLI Options

| Option | Description |
|--------|-------------|
| `file_path` | Path to artwork file (required, positional) |
| `--backend` | Silent mode for backend integration |
| `--max-file-size N` | Override maximum file size in bytes |
| `--skip-pixel-scan` | Skip transparency/color pixel scanning |

## Output Format

### Success Response

```json
{
  "success": true,
  "metadata": {
    "width": 64,
    "height": 64,
    "file_bytes": 1234,
    "file_format": "png",
    "bit_depth": 8,
    "frame_count": 1,
    "shortest_duration_ms": null,
    "longest_duration_ms": null,
    "unique_colors": 42,
    "transparency_meta": true,
    "alpha_meta": true,
    "transparency_actual": false,
    "alpha_actual": false,
    "sha256": "e3b0c44298fc1c149afbf4c8996fb924..."
  }
}
```

### Error Response

```json
{
  "success": false,
  "error": {
    "code": "INVALID_EXTENSION",
    "message": "File extension '.bmp' is not allowed. Allowed: .gif, .png, .webp"
  }
}
```

## Error Codes

| Code | Description | Phase |
|------|-------------|-------|
| `FILE_NOT_FOUND` | File does not exist | Pre-validation |
| `NOT_A_FILE` | Path is not a file | Pre-validation |
| `INVALID_EXTENSION` | Extension not in allowed list | Phase A |
| `FILE_TOO_LARGE` | File exceeds size limit | Phase A |
| `INVALID_DIMENSIONS` | Canvas size not allowed | Phase A |
| `HEADER_READ_FAILED` | Could not read file header | Phase A |
| `PILLOW_LOAD_FAILED` | Pillow could not open file | Phase B |
| `METADATA_EXTRACTION_FAILED` | Error during extraction | Phase B |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Validation error (file rejected) |
| `2` | System error (unexpected exception) |

## Database Schema

AMP metadata is stored in the `posts` table:

```sql
-- Dimensions
width               INTEGER     -- Canvas width in pixels
height              INTEGER     -- Canvas height in pixels
file_bytes          INTEGER     -- Exact file size in bytes

-- Format
mime_type           VARCHAR(50) -- MIME type (image/png, etc.)

-- Animation
frame_count         INTEGER     -- Number of frames (default: 1)
min_frame_duration_ms INTEGER   -- Shortest frame duration (ms)
max_frame_duration_ms INTEGER   -- Longest frame duration (ms)

-- AMP metadata
bit_depth           INTEGER     -- Per-channel bit depth
unique_colors       INTEGER     -- Max unique colors in any frame

-- Transparency
transparency_meta   BOOLEAN     -- Format claims transparency support
alpha_meta          BOOLEAN     -- Format claims alpha channel
transparency_actual BOOLEAN     -- Transparent pixels actually found
alpha_actual        BOOLEAN     -- Semi-transparent pixels found
```

## Backend Integration

The backend calls AMP via subprocess in `api/app/routers/posts.py`:

```python
import subprocess
import json

# Save uploaded file to temp location
with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
    tmp_file.write(file_content)
    tmp_path = tmp_file.name

try:
    # Call AMP inspector
    result = subprocess.run(
        [sys.executable, "-m", "app.amp.amp_inspector", "--backend", tmp_path],
        capture_output=True,
        text=True,
        timeout=30,
    )
    
    amp_result = json.loads(result.stdout)
    
    if not amp_result["success"]:
        raise HTTPException(
            status_code=400,
            detail=amp_result["error"]["message"]
        )
    
    metadata = amp_result["metadata"]
    # Use metadata to populate Post fields...
finally:
    os.unlink(tmp_path)
```

## Transparency Detection

AMP distinguishes between **metadata claims** and **actual pixel data**:

### Transparency Metadata (`transparency_meta`, `alpha_meta`)

Determined from file format and mode:
- **RGBA, LA, PA modes**: Both `transparency_meta` and `alpha_meta` are True
- **Palette mode with transparency index**: `transparency_meta` is True, `alpha_meta` is False
- **RGB, L modes**: Both are False

### Actual Transparency (`transparency_actual`, `alpha_actual`)

Determined by scanning pixels (only if metadata claims support):
- **`transparency_actual`**: True if any pixel has alpha ≠ 255
- **`alpha_actual`**: True if any pixel has 0 < alpha < 255 (semi-transparent)

### Optimization

If metadata claims no transparency support, pixel scanning is skipped:
- Both `transparency_actual` and `alpha_actual` are set to False without scanning
- This significantly improves performance for RGB images

## Unique Colors Calculation

For animations, unique colors is calculated as the **maximum** unique colors in any single frame:

1. Iterate through each frame (up to `MAX_FRAMES_TO_SCAN`)
2. Count unique colors in that frame
3. Keep track of the maximum across all frames
4. Return the maximum

This approach ensures the value represents the most colorful frame, useful for palette optimization decisions.

## Canvas Size Rules

AMP validates canvas dimensions according to Makapix Club rules:

| Dimension Range | Rule |
|-----------------|------|
| Both ≥ 128 | Any size allowed up to 256×256 |
| Either < 128 | Only specific sizes allowed |

### Allowed Small Sizes

```
8×8, 8×16, 16×8, 8×32, 32×8
16×16, 16×32, 32×16
32×32, 32×64, 64×32
64×64, 64×128, 128×64
```

## Backfill Script

A backfill script exists at `api/scripts/backfill_amp_metadata.py` for populating AMP metadata on existing artworks:

```bash
# Dry run (preview changes)
python /workspace/api/scripts/backfill_amp_metadata.py --dry-run --limit 10

# Full backfill
python /workspace/api/scripts/backfill_amp_metadata.py

# Options
--dry-run       Preview without making changes
--limit N       Only process N posts
--offset N      Skip first N posts
--post-id ID    Process specific post ID
--delay N       Delay between posts (default: 0.5s)
```

## Future Extensions

AMP is designed to support future features:

1. **Query Filtering**: MQTT clients will be able to filter artworks by AMP metadata (e.g., "only animations with transparency")
2. **Display Optimization**: Players can optimize rendering based on transparency and color information
3. **Format Recommendations**: Suggest optimal formats based on artwork characteristics
4. **Conformance Scoring**: Rate artworks on pixel-art conformance using AMP data

## File Locations

| Component | Path |
|-----------|------|
| Constants | `api/app/amp/constants.py` |
| Header Inspection | `api/app/amp/header_inspection.py` |
| Metadata Extraction | `api/app/amp/metadata_extraction.py` |
| Main Inspector | `api/app/amp/amp_inspector.py` |
| Backfill Script | `api/scripts/backfill_amp_metadata.py` |
| This Documentation | `docs/amp/AMP.md` |


# Artwork Metadata Platform (AMP)

The Artwork Metadata Platform (AMP) is Makapix Club's comprehensive file handling and metadata collection system for artwork uploads.

## Overview

AMP performs two-phase inspection and validation:

1. **Phase A: Header Inspection** - Fast fail-fast validation before loading the full image
2. **Phase B: Metadata Extraction** - Comprehensive metadata extraction using Pillow

## Components

### `constants.py`
Defines all validation constants:
- Allowed file extensions (`.png`, `.gif`, `.webp`)
- Maximum file size (from settings)
- Canvas size restrictions
- Frame scanning limits

### `header_inspection.py`
Phase A: Reads file headers before Pillow loading to validate:
- File extension (case-insensitive)
- File size
- Canvas dimensions (extracted from format-specific headers)

Supports PNG, GIF, and WebP header parsing.

### `metadata_extraction.py`
Phase B: Extracts comprehensive metadata from Pillow-loaded images:
- **Dimensions**: width, height, file_bytes
- **Format**: file_format, bit_depth
- **Animation**: frame_count, shortest_duration_ms, longest_duration_ms
- **Colors**: unique_colors (max across all frames)
- **Transparency metadata**: transparency_meta, alpha_meta (from file metadata)
- **Transparency actual**: transparency_actual, alpha_actual (from pixel scanning)

### `amp_inspector.py`
Main CLI entry point that orchestrates both phases.

## Usage

### Command Line (Human Mode)
```bash
python -m app.amp.amp_inspector /path/to/image.png
```
Prints progress messages to stderr and JSON output to stdout.

### Backend Mode (Silent)
```bash
python -m app.amp.amp_inspector --backend /path/to/image.png
```
Only outputs JSON to stdout (no stderr messages).

### Output Format

**Success:**
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
    "alpha_actual": false
  }
}
```

**Error:**
```json
{
  "success": false,
  "error": {
    "code": "INVALID_EXTENSION",
    "message": "File extension '.bmp' is not allowed. Allowed: .gif, .png, .webp"
  }
}
```

## Supported Formats

- PNG (`.png`)
- GIF (`.gif`) - including animated GIFs
- WebP (`.webp`) - including animated WebP
- BMP (`.bmp`)

## Error Codes

- `FILE_NOT_FOUND`: File does not exist
- `NOT_A_FILE`: Path is not a file
- `INVALID_EXTENSION`: File extension not allowed
- `FILE_TOO_LARGE`: File exceeds size limit
- `INVALID_DIMENSIONS`: Canvas size not allowed
- `HEADER_READ_FAILED`: Could not read file header
- `PILLOW_LOAD_FAILED`: Pillow could not open the file
- `METADATA_EXTRACTION_FAILED`: Error during metadata extraction

## Exit Codes

- `0`: Success
- `1`: Validation error (file rejected)
- `2`: System error (unexpected exception)

## Integration

The backend calls AMP via subprocess in `app/routers/posts.py`:

```python
result = subprocess.run(
    [sys.executable, "-m", "app.amp.amp_inspector", "--backend", tmp_path],
    capture_output=True,
    text=True,
    timeout=30,
    check=False,
)
amp_result = json.loads(result.stdout)
```

## Database Fields

AMP populates the following Post model fields:
- `width`, `height`, `file_bytes`
- `frame_count`, `min_frame_duration_ms`, `max_frame_duration_ms`
- `bit_depth`, `unique_colors`
- `transparency_meta`, `alpha_meta`
- `transparency_actual`, `alpha_actual`

## Key Design Decisions

1. **Fail-fast validation**: Header inspection catches invalid files before expensive Pillow loading
2. **Metadata-driven optimization**: If file metadata claims no transparency, pixel scanning is skipped
3. **Standalone script**: All artwork processing is delegated to a CLI script that can be tested independently
4. **Frame-wise analysis**: Unique colors and transparency are computed per-frame for animations
5. **Bit depth accuracy**: Reports per-channel bit depth, not palette depth


# Displaying Artwork

Handle image formats, dimensions, and animations on your display device.

## Artwork Specifications

All artwork on Makapix follows strict specifications:

| Property | Requirement |
|----------|-------------|
| Dimensions | 8x8 to 256x256 pixels |
| Aspect Ratio | Perfect square (width = height) |
| Formats | PNG, GIF, WebP, BMP |
| Max File Size | 5 MB |

### Dimension Rules

Dimensions follow specific allowable sizes:

- **Under 128x128**: Only specific sizes (8, 16, 32, 64, and combinations)
- **128x128 to 256x256**: Any size allowed

Common sizes: 8x8, 16x16, 32x32, 64x64, 128x128, 256x256

## Fetching Images

Images are served from the vault via HTTPS:

```
https://makapix.club/api/vault/{storage_shard}/{storage_key}.{format}
```

For physical players over HTTP (no TLS overhead):

```
http://vault.makapix.club/{storage_shard}/{storage_key}.{format}
```

### URL Components

From the query response:

```json
{
  "storage_key": "abc123-def456-789",
  "storage_shard": "a1/b2/c3",
  "native_format": "png",
  "art_url": "https://makapix.club/api/vault/a1/b2/c3/abc123-def456-789.png"
}
```

You can use `art_url` directly, or construct the HTTP variant:

```
http://vault.makapix.club/a1/b2/c3/abc123-def456-789.png
```

## Image Formats

### PNG

- Best for static artwork with transparency
- Lossless compression
- Widest hardware support

### GIF

- Supports animation (multiple frames)
- 256 color palette per frame
- Binary transparency only (fully transparent or opaque)

### WebP

- Modern format with good compression
- Supports animation
- Supports full alpha transparency
- May require newer hardware/libraries

### BMP

- Uncompressed bitmap
- Largest file size
- Simplest to decode
- No native animation support

## Handling Animations

Animated images (frame_count > 1) require special handling.

### Frame Timing

Query response includes timing hints:

```json
{
  "frame_count": 12,
  "min_frame_duration_ms": 50,
  "max_frame_duration_ms": 100
}
```

| Field | Description |
|-------|-------------|
| `frame_count` | Total frames in animation |
| `min_frame_duration_ms` | Shortest frame delay |
| `max_frame_duration_ms` | Longest frame delay |

### GIF Frame Delays

GIF frame delays are embedded in the file. Libraries like PIL/Pillow, ImageMagick, or giflib can extract them:

```python
from PIL import Image

img = Image.open("animation.gif")
for frame in range(img.n_frames):
    img.seek(frame)
    duration_ms = img.info.get('duration', 100)
    # Display frame for duration_ms
```

### WebP Animation

WebP animations also embed frame delays. Use libwebp or similar to extract:

```c
// Using libwebp
WebPAnimDecoder* dec = WebPAnimDecoderNew(&webp_data, NULL);
WebPAnimInfo info;
WebPAnimDecoderGetInfo(dec, &info);

while (WebPAnimDecoderHasMoreFrames(dec)) {
    uint8_t* buf;
    int timestamp;
    WebPAnimDecoderGetNext(dec, &buf, &timestamp);
    // timestamp is cumulative milliseconds
}
```

## Display Scaling

Your display resolution may differ from artwork dimensions. Common approaches:

### Nearest Neighbor (Recommended)

Preserves pixel art crispness:

```python
from PIL import Image

img = Image.open("artwork.png")
scaled = img.resize((display_width, display_height), Image.NEAREST)
```

### Integer Scaling

Scale by whole numbers to maintain pixel alignment:

```
Display: 64x64
Artwork: 16x16
Scale factor: 4x (16 * 4 = 64)
```

### Centering Smaller Images

If artwork is smaller than display:

```python
# Center 32x32 artwork on 64x64 display
offset_x = (64 - 32) // 2  # 16
offset_y = (64 - 32) // 2  # 16
display.blit(artwork, (offset_x, offset_y))
```

## Transparency Handling

### Checking for Transparency

Query response indicates transparency:

```json
{
  "transparency_actual": true,
  "alpha_actual": false
}
```

| Field | Meaning |
|-------|---------|
| `transparency_actual` | Image has fully transparent pixels |
| `alpha_actual` | Image has semi-transparent pixels (0 < alpha < 255) |

### Background Color

For displays that don't support transparency, composite against a background:

```python
from PIL import Image

artwork = Image.open("transparent.png").convert("RGBA")
background = Image.new("RGBA", artwork.size, (0, 0, 0, 255))  # Black
composite = Image.alpha_composite(background, artwork)
display_image = composite.convert("RGB")
```

## Dwell Time

Each artwork has a suggested display duration:

```json
{
  "dwell_time_ms": 30000
}
```

Default is 30 seconds (30000 ms). Your player can:

1. Use the suggested time
2. Allow user configuration
3. Implement gestures/buttons to advance

For animations, consider:

- Show for at least one full loop
- Or show for `dwell_time_ms`, whichever is longer

## Memory Management

On constrained devices:

### Stream Large Images

Don't load entire file into RAM:

```c
// Decode row by row instead of entire image
while (has_more_rows) {
    decode_row(decoder, row_buffer);
    display_row(row_buffer);
}
```

### Cache Current/Next Only

Keep at most 2 images in memory:

```python
current_image = load_image(current_post)
next_image = load_image(next_post)  # Preload

# When advancing
current_image = next_image
next_image = load_image(upcoming_post)
```

### Use Native Format

Avoid format conversion when possible. If your display handles PNG directly, don't convert to BMP.

## Color Handling

### Unique Colors

The `unique_colors` field indicates color complexity:

```json
{
  "unique_colors": 16
}
```

Useful for:

- Filtering to match display capabilities
- Optimizing palette-based displays

### Color Depth

| Display Type | Recommended |
|--------------|-------------|
| 1-bit (monochrome) | Dither or threshold |
| 8-bit indexed | Use `unique_colors` <= 256 |
| 16-bit RGB565 | Direct conversion |
| 24-bit RGB | Full color support |

## Error Handling

### Network Failures

```python
def fetch_artwork(url, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.content
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
```

### Corrupt Images

Validate downloaded images before display:

```python
from PIL import Image
import io

def validate_image(data):
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()  # Check for corruption
        return True
    except Exception:
        return False
```

### Fallback Display

When image loading fails:

1. Display a placeholder/error image
2. Log the error
3. Advance to next artwork
4. Optionally report error to server

## ESP32 Example

```cpp
#include <HTTPClient.h>
#include <TJpg_Decoder.h>  // or PNG/GIF library

void displayArtwork(const char* url) {
    HTTPClient http;
    http.begin(url);

    int httpCode = http.GET();
    if (httpCode == HTTP_CODE_OK) {
        int len = http.getSize();
        uint8_t* buffer = (uint8_t*)malloc(len);

        WiFiClient* stream = http.getStreamPtr();
        stream->readBytes(buffer, len);

        // Decode and display
        decodeAndDisplay(buffer, len);

        free(buffer);
    }
    http.end();
}
```

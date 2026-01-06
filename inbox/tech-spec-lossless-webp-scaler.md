# Technical Specification: Browser-Based Lossless WEBP Image Scaler

**Version:** 1.0  
**Status:** Draft  
**Last Updated:** January 2025

---

## 1. Overview

### 1.1 Purpose

This document specifies the technical architecture for a browser-based tool that receives images in GIF, PNG, BMP, or WEBP format (including animated variants), scales them to user-specified dimensions, and outputs lossless WEBP files preserving animation where applicable.

### 1.2 Key Requirements

| Requirement | Description |
|-------------|-------------|
| Input Formats | GIF (static/animated), PNG (static/APNG), BMP, WEBP (static/animated) |
| Output Format | Lossless WEBP (static or animated, matching input) with full alpha channel |
| Scaling | Arbitrary dimensions; nearest-neighbor (default) or Lanczos3 resampling |
| Transparency | Full alpha channel preservation required throughout pipeline |
| Environment | Modern browsers (Chrome 90+, Firefox 90+, Safari 15+, Edge 90+) |
| Processing | Fully client-side, no server required |

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser Environment                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │   Decoder    │    │   Scaler     │    │  Encoder         │   │
│  │   Module     │───▶│   Module     │───▶│  Module          │   │
│  │              │    │              │    │  (WASM libwebp)  │   │
│  └──────────────┘    └──────────────┘    └──────────────────┘   │
│         │                   │                     │              │
│         ▼                   ▼                     ▼              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Frame Buffer Pool                     │    │
│  │           (RGBA pixel data + timing metadata)            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Specifications

### 3.1 Decoder Module

The decoder module extracts frames, timing information, and metadata from input files.

#### 3.1.1 GIF Decoder

**Recommended Library:** `gifuct-js` (MIT License)  
**NPM:** `npm install gifuct-js`

**Capabilities:**
- Extracts all frames from animated GIFs
- Provides frame delay timing (in milliseconds)
- Handles disposal methods (restore to background, restore to previous, etc.)
- Outputs raw RGBA pixel data per frame

**Frame Data Structure:**
```typescript
interface GifFrame {
  pixels: Uint8ClampedArray;  // RGBA data
  width: number;
  height: number;
  delay: number;              // Frame delay in ms
  disposalMethod: number;     // 0-3 per GIF89a spec
  left: number;               // Frame offset X
  top: number;                // Frame offset Y
}
```

**Implementation Notes:**
- GIF frames may be partial (smaller than canvas); composite onto full-size canvas before scaling
- Convert frame delays from centiseconds (GIF native) to milliseconds
- Handle edge case: delay of 0 should default to 100ms (per browser convention)

#### 3.1.2 PNG/APNG Decoder

**Recommended Library:** `upng-js` (MIT License)  
**NPM:** `npm install upng-js`

**Capabilities:**
- Decodes standard PNG to RGBA
- Decodes APNG (Animated PNG) with full frame extraction
- Provides frame timing and blend/dispose operations

**Frame Data Structure:**
```typescript
interface ApngFrame {
  data: Uint8Array;           // Raw RGBA
  width: number;
  height: number;
  delay: number;              // Delay in ms (derived from delay_num/delay_den)
  blendOp: number;            // 0 = source, 1 = over
  disposeOp: number;          // 0 = none, 1 = background, 2 = previous
  left: number;
  top: number;
}
```

#### 3.1.3 WEBP Decoder

**Recommended Library:** `libwebp` WASM (BSD License)  
**Source:** Compile from Google's libwebp or use pre-built `@aspect-build/aspect-cli`, `libwebp-wasm`, or similar

**Capabilities:**
- Decodes static WEBP (lossy and lossless)
- Decodes animated WEBP via WebPAnimDecoder API
- Extracts frame timing and metadata

**Required libwebp APIs:**
```c
// For static images
WebPDecodeRGBA(data, size, &width, &height)

// For animated images
WebPAnimDecoderNew(webp_data, &dec_options)
WebPAnimDecoderGetInfo(decoder, &anim_info)
WebPAnimDecoderGetNext(decoder, &buf, &timestamp)
```

**Frame Data Structure:**
```typescript
interface WebpFrame {
  rgba: Uint8Array;
  width: number;
  height: number;
  timestamp: number;          // Cumulative timestamp in ms
  duration: number;           // Derived: next_timestamp - this_timestamp
}
```

#### 3.1.4 BMP Decoder

**Recommended Approach:** Native browser decoding via `<canvas>`

**Implementation:**
```javascript
const img = new Image();
img.src = URL.createObjectURL(bmpBlob);
await img.decode();
ctx.drawImage(img, 0, 0);
const imageData = ctx.getImageData(0, 0, img.width, img.height);
```

BMP is always static; output as single-frame.

---

### 3.2 Unified Frame Representation

All decoders must normalize output to this common structure:

```typescript
interface DecodedImage {
  frames: Frame[];
  loopCount: number;          // 0 = infinite, N = loop N times
  originalFormat: 'gif' | 'png' | 'apng' | 'webp' | 'bmp';
  isAnimated: boolean;
}

interface Frame {
  rgba: Uint8ClampedArray;    // Full-canvas RGBA, pre-composited
  width: number;              // Canvas width (same for all frames)
  height: number;             // Canvas height (same for all frames)
  duration: number;           // Frame duration in milliseconds
}
```

**Critical:** All frames must be full-canvas, pre-composited RGBA. Partial frames (as in GIF/APNG) must be rendered onto a full canvas respecting disposal and blend operations before passing to the scaler.

---

### 3.3 Scaler Module

#### 3.3.1 Scaling Algorithms

The scaler supports two resampling algorithms, selectable by the user:

| Algorithm | Default | Best For | Characteristics |
|-----------|---------|----------|-----------------|
| **Nearest Neighbor** | ✓ Yes | Pixel art, sprites, retro graphics, sharp edges | Preserves hard edges, no interpolation, fastest performance |
| **Lanczos3** | No | Photographs, gradients, smooth artwork | High-quality interpolation, anti-aliased results, slower |

#### 3.3.2 Nearest Neighbor Implementation (Default)

**Implementation:** Native Canvas API with `imageSmoothingEnabled: false`

```javascript
async function scaleFrameNearestNeighbor(
  sourceRgba: Uint8ClampedArray,
  srcWidth: number,
  srcHeight: number,
  destWidth: number,
  destHeight: number
): Promise<Uint8ClampedArray> {
  
  // Create source canvas with original image
  const srcCanvas = new OffscreenCanvas(srcWidth, srcHeight);
  const srcCtx = srcCanvas.getContext('2d');
  srcCtx.putImageData(new ImageData(sourceRgba, srcWidth, srcHeight), 0, 0);
  
  // Create destination canvas
  const destCanvas = new OffscreenCanvas(destWidth, destHeight);
  const destCtx = destCanvas.getContext('2d');
  
  // CRITICAL: Disable smoothing for nearest neighbor
  destCtx.imageSmoothingEnabled = false;
  
  // Scale via drawImage
  destCtx.drawImage(srcCanvas, 0, 0, destWidth, destHeight);
  
  return destCtx.getImageData(0, 0, destWidth, destHeight).data;
}
```

**Nearest Neighbor Characteristics:**
- Preserves exact pixel colors (no color blending)
- Ideal for integer scale factors (2×, 3×, 4×, etc.)
- Non-integer scales may produce uneven pixel distribution
- Alpha channel values preserved exactly (no interpolation)

#### 3.3.3 Lanczos3 Implementation (Optional)

**Recommended Library:** `pica` (MIT License)  
**NPM:** `npm install pica`

```javascript
import Pica from 'pica';

const pica = new Pica();

async function scaleFrameLanczos(
  sourceRgba: Uint8ClampedArray,
  srcWidth: number,
  srcHeight: number,
  destWidth: number,
  destHeight: number
): Promise<Uint8ClampedArray> {
  
  const srcCanvas = new OffscreenCanvas(srcWidth, srcHeight);
  const srcCtx = srcCanvas.getContext('2d');
  srcCtx.putImageData(new ImageData(sourceRgba, srcWidth, srcHeight), 0, 0);
  
  const destCanvas = new OffscreenCanvas(destWidth, destHeight);
  
  await pica.resize(srcCanvas, destCanvas, {
    quality: 3,               // Max quality (Lanczos3)
    alpha: true,              // CRITICAL: Preserve alpha channel
    unsharpAmount: 0,         // Disable sharpening for lossless fidelity
    unsharpRadius: 0,
    unsharpThreshold: 0
  });
  
  const destCtx = destCanvas.getContext('2d');
  return destCtx.getImageData(0, 0, destWidth, destHeight).data;
}
```

#### 3.3.4 Unified Scaler Interface

```typescript
type ResamplingAlgorithm = 'nearest-neighbor' | 'lanczos3';

async function scaleFrame(
  sourceRgba: Uint8ClampedArray,
  srcWidth: number,
  srcHeight: number,
  destWidth: number,
  destHeight: number,
  algorithm: ResamplingAlgorithm = 'nearest-neighbor'  // Default
): Promise<Uint8ClampedArray> {
  
  switch (algorithm) {
    case 'nearest-neighbor':
      return scaleFrameNearestNeighbor(sourceRgba, srcWidth, srcHeight, destWidth, destHeight);
    case 'lanczos3':
      return scaleFrameLanczos(sourceRgba, srcWidth, srcHeight, destWidth, destHeight);
    default:
      throw new Error(`Unknown resampling algorithm: ${algorithm}`);
  }
}
```

#### 3.3.5 Scaling Considerations

| Consideration | Recommendation |
|---------------|----------------|
| Aspect Ratio | Preserve by default; offer crop/pad options |
| Upscaling (Nearest) | Clean integer multiples; non-integer may have uneven pixels |
| Upscaling (Lanczos) | Smooth results, but inherently soft; warn user |
| Downscaling (Nearest) | May lose detail; warn user for large reductions |
| Downscaling (Lanczos) | High quality; recommended for significant size reduction |
| **Alpha Channel** | **MUST be preserved with both algorithms** |
| Color Space | Work in sRGB; no color management required |

#### 3.3.6 Performance Optimization

- Process frames in parallel using Web Workers (pica does this automatically)
- For animations with >50 frames, process in batches of 10-20 to avoid memory pressure
- Release source frame memory after scaling each frame
- Consider streaming: scale and encode frames progressively

---

### 3.4 Encoder Module (WASM libwebp)

#### 3.4.1 WASM Build Requirements

**Source:** Google's libwebp (https://chromium.googlesource.com/webm/libwebp)  
**Minimum Version:** 1.3.0 (for latest encoder optimizations)  
**License:** BSD-3-Clause

**Required Compilation Flags:**
```bash
emcc \
  -O3 \
  -s WASM=1 \
  -s MODULARIZE=1 \
  -s EXPORT_ES6=1 \
  -s ALLOW_MEMORY_GROWTH=1 \
  -s EXPORTED_FUNCTIONS='[
    "_WebPEncodeLosslessRGBA",
    "_WebPAnimEncoderNew",
    "_WebPAnimEncoderAdd",
    "_WebPAnimEncoderAssemble",
    "_WebPAnimEncoderDelete",
    "_WebPDataClear",
    "_malloc",
    "_free"
  ]' \
  -s EXPORTED_RUNTIME_METHODS='["cwrap", "getValue", "setValue"]' \
  src/enc/*.c \
  src/dsp/*.c \
  src/utils/*.c \
  src/mux/*.c \
  -I . \
  -o libwebp.js
```

**Pre-built Alternative:** If build is not feasible, evaluate:
- `@aspect-build/aspect-cli` (includes WASM libwebp)
- `libwebp-wasm` npm package
- Build from aspect-build/aspect-cli source

#### 3.4.2 Static Image Encoding

For single-frame (non-animated) output:

```typescript
interface WebPEncoder {
  encodeLosslessRGBA(
    rgba: Uint8Array,
    width: number,
    height: number
  ): Uint8Array;
}

// libwebp C API being wrapped:
// size_t WebPEncodeLosslessRGBA(
//   const uint8_t* rgba, int width, int height, int stride,
//   uint8_t** output
// );
```

**JavaScript Wrapper:**
```javascript
function encodeLosslessWebP(rgba, width, height) {
  const stride = width * 4;
  const inputPtr = Module._malloc(rgba.length);
  Module.HEAPU8.set(rgba, inputPtr);
  
  const outputPtrPtr = Module._malloc(4);
  
  const size = Module._WebPEncodeLosslessRGBA(
    inputPtr,
    width,
    height,
    stride,
    outputPtrPtr
  );
  
  const outputPtr = Module.getValue(outputPtrPtr, 'i32');
  const output = new Uint8Array(Module.HEAPU8.buffer, outputPtr, size).slice();
  
  Module._free(inputPtr);
  Module._WebPFree(outputPtr);
  Module._free(outputPtrPtr);
  
  return output;
}
```

#### 3.4.3 Animated Image Encoding

For multi-frame (animated) output, use `WebPAnimEncoder`:

**Required C Structures:**
```c
typedef struct WebPAnimEncoderOptions {
  WebPMuxAnimParams anim_params;
  int minimize_size;
  int kmin;
  int kmax;
  int allow_mixed;
  int verbose;
  // ... padding
} WebPAnimEncoderOptions;

typedef struct WebPMuxAnimParams {
  uint32_t bgcolor;
  int loop_count;
} WebPMuxAnimParams;
```

**Encoding Flow:**
```javascript
async function encodeAnimatedLosslessWebP(frames, loopCount = 0) {
  // 1. Initialize encoder options
  const encOptions = createAnimEncoderOptions({
    bgcolor: 0x00000000,      // Transparent background
    loopCount: loopCount,     // 0 = infinite
    minimizeSize: 1,          // Optimize output size
    allowMixed: 0             // Force all frames lossless
  });
  
  // 2. Create encoder
  const encoder = WebPAnimEncoderNew(
    frames[0].width,
    frames[0].height,
    encOptions
  );
  
  // 3. Configure lossless encoding for each frame
  const frameConfig = createWebPConfig();
  frameConfig.lossless = 1;
  frameConfig.quality = 100;
  frameConfig.method = 6;     // Max compression effort
  
  // 4. Add frames
  let timestamp = 0;
  for (const frame of frames) {
    const picture = createWebPPicture(frame.rgba, frame.width, frame.height);
    WebPAnimEncoderAdd(encoder, picture, timestamp, frameConfig);
    timestamp += frame.duration;
    freePicture(picture);
  }
  
  // 5. Add final "null" frame to signal end
  WebPAnimEncoderAdd(encoder, null, timestamp, null);
  
  // 6. Assemble output
  const webpData = WebPAnimEncoderAssemble(encoder);
  
  // 7. Cleanup
  WebPAnimEncoderDelete(encoder);
  
  return webpData;
}
```

#### 3.4.4 Lossless Encoding Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `lossless` | 1 | Required for lossless output |
| `quality` | 100 | Maximum quality in lossless mode affects compression effort |
| `method` | 6 | Highest compression effort (slower but smaller files) |
| `exact` | 1 | Preserve RGB values in transparent areas |
| `near_lossless` | 100 | Disable near-lossless preprocessing |

**WebPConfig Setup:**
```c
WebPConfig config;
WebPConfigInit(&config);
config.lossless = 1;
config.quality = 100;
config.method = 6;
config.exact = 1;
```

---

## 4. Transparency and Alpha Channel Support

### 4.1 Core Requirement

**Full alpha channel preservation is mandatory throughout the entire pipeline.** The output lossless WEBP file MUST contain accurate alpha channel data matching the (scaled) input.

### 4.2 Alpha Support by Input Format

| Format | Alpha Support | Notes |
|--------|---------------|-------|
| GIF | 1-bit transparency | Single transparent color index; convert to full alpha (0 or 255) |
| PNG | 8/16-bit alpha | Full alpha channel; preserve exactly |
| APNG | 8/16-bit alpha | Full alpha channel per frame; preserve exactly |
| WEBP | 8-bit alpha | Full alpha channel; preserve exactly |
| BMP | 8-bit alpha (32-bit BMP) | If present, preserve; otherwise assume fully opaque |

### 4.3 Pipeline Alpha Handling

Each stage must explicitly preserve alpha:

#### 4.3.1 Decoding Stage

```javascript
// All decoders MUST output RGBA (4 channels), never RGB
interface Frame {
  rgba: Uint8ClampedArray;  // MUST be 4 bytes per pixel: R, G, B, A
  // ...
}

// Verify frame data integrity
function validateFrameData(frame: Frame): void {
  const expectedLength = frame.width * frame.height * 4;
  if (frame.rgba.length !== expectedLength) {
    throw new Error(`Invalid frame data: expected ${expectedLength} bytes (RGBA), got ${frame.rgba.length}`);
  }
}
```

#### 4.3.2 Compositing Stage (Animated Images)

GIF and APNG frames require careful alpha handling during compositing:

```javascript
// For APNG blend operations
function compositeWithAlpha(dest: ImageData, src: ImageData, blendOp: number) {
  if (blendOp === 0) {
    // APNG_BLEND_OP_SOURCE: Replace entirely, including alpha
    // Directly copy all RGBA values
    dest.data.set(src.data);
  } else {
    // APNG_BLEND_OP_OVER: Standard alpha compositing
    for (let i = 0; i < src.data.length; i += 4) {
      const srcAlpha = src.data[i + 3] / 255;
      const destAlpha = dest.data[i + 3] / 255;
      const outAlpha = srcAlpha + destAlpha * (1 - srcAlpha);
      
      if (outAlpha > 0) {
        dest.data[i]     = (src.data[i] * srcAlpha + dest.data[i] * destAlpha * (1 - srcAlpha)) / outAlpha;
        dest.data[i + 1] = (src.data[i + 1] * srcAlpha + dest.data[i + 1] * destAlpha * (1 - srcAlpha)) / outAlpha;
        dest.data[i + 2] = (src.data[i + 2] * srcAlpha + dest.data[i + 2] * destAlpha * (1 - srcAlpha)) / outAlpha;
      }
      dest.data[i + 3] = outAlpha * 255;
    }
  }
}
```

#### 4.3.3 Scaling Stage

**Nearest Neighbor:**
```javascript
// Alpha is copied exactly like any other channel
// No interpolation means alpha values are preserved precisely
destCtx.imageSmoothingEnabled = false;  // Affects all channels including alpha
```

**Lanczos3 (via pica):**
```javascript
await pica.resize(srcCanvas, destCanvas, {
  alpha: true,  // CRITICAL: Must be explicitly enabled
  // This ensures alpha channel is processed correctly and not premultiplied incorrectly
});
```

#### 4.3.4 Encoding Stage

libwebp lossless encoding with alpha:

```c
// WebPConfig for lossless with alpha
WebPConfig config;
WebPConfigInit(&config);
config.lossless = 1;
config.exact = 1;      // CRITICAL: Preserve RGB values in transparent areas

// WebPPicture setup
WebPPicture picture;
WebPPictureInit(&picture);
picture.use_argb = 1;  // Use ARGB format (includes alpha)
picture.width = width;
picture.height = height;

// Import RGBA data (WebP uses ARGB internally, but import handles conversion)
WebPPictureImportRGBA(&picture, rgba_data, stride);
```

**Critical Encoder Settings for Alpha:**

| Setting | Value | Purpose |
|---------|-------|---------|
| `config.exact` | 1 | Preserves RGB values even where alpha=0 (prevents green/black transparent pixels) |
| `picture.use_argb` | 1 | Enables ARGB mode which includes alpha channel |
| `anim_params.bgcolor` | 0x00000000 | Transparent background for animations |

### 4.4 Alpha Channel Validation

**Test Cases for Alpha Verification:**

```javascript
async function validateAlphaPreservation(inputBlob: Blob, outputBlob: Blob): Promise<boolean> {
  const inputFrames = await decode(inputBlob);
  const outputFrames = await decode(outputBlob);
  
  for (let f = 0; f < inputFrames.length; f++) {
    const inputFrame = inputFrames[f];
    const outputFrame = outputFrames[f];
    
    // Scale input frame to output dimensions for comparison
    const scaledInput = await scaleFrame(
      inputFrame.rgba,
      inputFrame.width, inputFrame.height,
      outputFrame.width, outputFrame.height
    );
    
    // Compare alpha channels
    for (let i = 3; i < scaledInput.length; i += 4) {
      if (scaledInput[i] !== outputFrame.rgba[i]) {
        console.error(`Alpha mismatch at pixel ${i/4}: expected ${scaledInput[i]}, got ${outputFrame.rgba[i]}`);
        return false;
      }
    }
  }
  return true;
}
```

### 4.5 Edge Cases

| Case | Handling |
|------|----------|
| Fully opaque image (no alpha) | Output WEBP still contains alpha channel (all 255) |
| Fully transparent image | Must preserve; output should have alpha=0 throughout |
| GIF transparency color | Convert to alpha=0; all other pixels alpha=255 |
| Semi-transparent pixels (PNG/WEBP) | Preserve exact alpha values (0-255 range) |
| Transparent pixels with non-zero RGB | `config.exact=1` preserves RGB data in transparent areas |
| Premultiplied vs straight alpha | Work in straight alpha throughout; do not premultiply |

---

## 5. Data Flow

### 5.1 Processing Pipeline

```
Input File (Blob)
       │
       ▼
┌──────────────────────┐
│  Format Detection    │  ← Magic bytes / MIME type
└──────────────────────┘
       │
       ▼
┌──────────────────────┐
│  Decoder Selection   │  ← Route to appropriate decoder
└──────────────────────┘
       │
       ▼
┌──────────────────────┐
│  Frame Extraction    │  ← Decode to Frame[] array
└──────────────────────┘
       │
       ▼
┌──────────────────────┐
│  Frame Compositing   │  ← Apply disposal/blend, full-canvas RGBA
└──────────────────────┘
       │
       ▼
┌──────────────────────┐
│  Parallel Scaling    │  ← Lanczos3 resize each frame
└──────────────────────┘
       │
       ▼
┌──────────────────────┐
│  WASM Encoding       │  ← libwebp lossless encoding
└──────────────────────┘
       │
       ▼
Output File (Uint8Array → Blob → Download)
```

### 5.2 Memory Management

**Estimated Memory Usage:**
```
Per Frame = Width × Height × 4 bytes (RGBA)

Example: 1920×1080 animation, 100 frames
- Source frames:  1920 × 1080 × 4 × 100 = ~830 MB
- Scaled frames:  (varies by output size)
- WASM heap:      ~50-100 MB overhead
```

**Mitigation Strategies:**

1. **Streaming Processing:** Don't decode all frames before scaling
   ```
   Decode Frame N → Scale Frame N → Encode Frame N → Free Frame N
   ```

2. **Frame Pooling:** Reuse ArrayBuffer allocations

3. **Chunked Processing:** For very long animations (>200 frames), process in chunks and warn user of memory requirements

4. **Memory Limits:** Check `performance.memory` (Chrome) or estimate, warn if approaching 2GB

---

## 6. API Specification

### 6.1 Public Interface

```typescript
type ResamplingAlgorithm = 'nearest-neighbor' | 'lanczos3';

interface ScalerOptions {
  width: number;                        // Target width in pixels
  height: number;                       // Target height in pixels
  resamplingAlgorithm?: ResamplingAlgorithm;    // Default: 'nearest-neighbor'
  maintainAspectRatio?: boolean;        // Default: true
  aspectRatioMode?: 'fit' | 'fill' | 'stretch';  // Default: 'fit'
  backgroundColor?: string;             // For 'fit' mode padding, default: transparent (preserves alpha)
}

interface ProgressCallback {
  (progress: {
    stage: 'decoding' | 'scaling' | 'encoding';
    current: number;
    total: number;
    percent: number;
  }): void;
}

interface ScalerResult {
  blob: Blob;                           // Output WEBP file
  width: number;                        // Actual output width
  height: number;                       // Actual output height
  frameCount: number;                   // Number of frames
  isAnimated: boolean;
  hasAlpha: boolean;                    // True if output contains non-opaque pixels
  fileSizeBytes: number;
}

async function scaleToLosslessWebP(
  input: File | Blob,
  options: ScalerOptions,
  onProgress?: ProgressCallback
): Promise<ScalerResult>;
```

### 6.2 Error Handling

```typescript
class ScalerError extends Error {
  code: 
    | 'UNSUPPORTED_FORMAT'
    | 'DECODE_FAILED'
    | 'INVALID_DIMENSIONS'
    | 'MEMORY_EXCEEDED'
    | 'ENCODE_FAILED'
    | 'WASM_INIT_FAILED';
  details?: string;
}
```

---

## 7. Browser Compatibility

### 7.1 Required Features

| Feature | Chrome | Firefox | Safari | Edge |
|---------|--------|---------|--------|------|
| WebAssembly | 57+ | 52+ | 11+ | 16+ |
| OffscreenCanvas | 69+ | 105+ | 16.4+ | 79+ |
| Web Workers | ✓ | ✓ | ✓ | ✓ |
| BigInt (WASM) | 67+ | 68+ | 14+ | 79+ |
| ES Modules | 61+ | 60+ | 11+ | 79+ |

### 7.2 Minimum Supported Versions

- Chrome 90+
- Firefox 105+ (for OffscreenCanvas)
- Safari 16.4+
- Edge 90+

### 7.3 Fallback Strategy

If OffscreenCanvas unavailable, fall back to main-thread canvas operations (with performance warning).

---

## 8. Testing Requirements

### 8.1 Test Matrix

| Input | Variants to Test |
|-------|------------------|
| GIF | Static, animated (2 frames), animated (100+ frames), transparent, interlaced |
| PNG | 8-bit, 16-bit, indexed, grayscale, with alpha, APNG animated |
| WEBP | Lossy, lossless, animated lossy, animated lossless, with alpha |
| BMP | 24-bit, 32-bit with alpha, various color depths |

### 8.2 Validation Criteria

1. **Lossless Verification:** Decode output WEBP, compare pixel-by-pixel with scaled source (must be identical)
2. **Animation Timing:** Frame durations must match input within 1ms tolerance
3. **Dimension Accuracy:** Output dimensions must exactly match requested dimensions
4. **Alpha Preservation:** Transparent pixels must remain fully transparent; semi-transparent pixels must retain exact alpha values
5. **Alpha Channel Presence:** Output WEBP must contain alpha channel data even for fully opaque inputs

### 8.3 Alpha-Specific Test Cases

| Test Case | Input | Expected Output |
|-----------|-------|-----------------|
| Fully opaque PNG | 100×100 red square, no transparency | WEBP with alpha channel (all 255) |
| PNG with alpha | Image with gradient alpha (0-255) | Exact alpha values preserved after scaling |
| GIF with transparency | GIF using color index 0 as transparent | WEBP with alpha=0 for transparent pixels |
| Animated WEBP with alpha | 10-frame animation with per-frame transparency | All frames preserve exact alpha |
| Transparent pixels with RGB data | PNG where transparent pixels have R=255 | Output preserves RGB values in transparent areas |

### 8.4 Performance Benchmarks

| Test Case | Target |
|-----------|--------|
| 1080p static PNG → 720p | < 500ms |
| 100-frame GIF (500×500) → 250×250 | < 10s |
| 4K static BMP → 1080p | < 2s |

---

## 9. Dependencies Summary

| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| libwebp (WASM) | ≥1.3.0 | Lossless WEBP encoding with alpha support | BSD-3-Clause |
| gifuct-js | ≥1.0.0 | GIF decoding with transparency | MIT |
| upng-js | ≥2.0.0 | PNG/APNG decoding with full alpha | MIT |
| pica | ≥9.0.0 | High-quality Lanczos scaling (optional algorithm) | MIT |

---

## 10. Delivery Artifacts

1. **Core Library:** ES module bundle (`lossless-webp-scaler.esm.js`)
2. **WASM Binary:** Compiled libwebp (`libwebp.wasm`)
3. **TypeScript Definitions:** Full type definitions (`index.d.ts`)
4. **Worker Script:** Web Worker for parallel processing (`scaler.worker.js`)
5. **Demo Application:** Reference implementation with UI

---

## 11. Open Questions / Decisions Needed

1. **APNG Support Priority:** Full APNG support adds complexity. Confirm if required.
2. **Maximum Animation Length:** Should we impose a frame count limit (e.g., 500 frames)?
3. **Compression Level UX:** Expose encoding `method` (1-6) to users for speed/size tradeoff?
4. **Algorithm Recommendation UI:** Should the UI suggest Lanczos for photographs and nearest-neighbor for pixel art?

---

## Appendix A: libwebp WASM Build Instructions

```bash
# Clone libwebp
git clone https://chromium.googlesource.com/webm/libwebp
cd libwebp

# Checkout stable version
git checkout v1.3.2

# Install Emscripten (if needed)
# See: https://emscripten.org/docs/getting_started/downloads.html

# Build WASM
mkdir build-wasm && cd build-wasm

emcmake cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DWEBP_BUILD_ANIM_UTILS=OFF \
  -DWEBP_BUILD_CWEBP=OFF \
  -DWEBP_BUILD_DWEBP=OFF \
  -DWEBP_BUILD_GIF2WEBP=OFF \
  -DWEBP_BUILD_IMG2WEBP=OFF \
  -DWEBP_BUILD_VWEBP=OFF \
  -DWEBP_BUILD_WEBPINFO=OFF \
  -DWEBP_BUILD_WEBPMUX=OFF \
  -DWEBP_BUILD_EXTRAS=OFF

emmake make

# Link final WASM module
emcc \
  -O3 \
  -s WASM=1 \
  -s MODULARIZE=1 \
  -s EXPORT_NAME="LibWebP" \
  -s ALLOW_MEMORY_GROWTH=1 \
  -s MAXIMUM_MEMORY=2GB \
  -s EXPORTED_FUNCTIONS='["_WebPEncodeLosslessRGBA", ...]' \
  -s EXPORTED_RUNTIME_METHODS='["cwrap", "getValue", "setValue", "addFunction"]' \
  libwebp.a libwebpmux.a libsharpyuv.a \
  -o libwebp.js
```

---

## Appendix B: Frame Compositing Reference

For GIF and APNG, frames may be partial with disposal methods:

```javascript
function compositeFrames(rawFrames, canvasWidth, canvasHeight) {
  const canvas = new OffscreenCanvas(canvasWidth, canvasHeight);
  const ctx = canvas.getContext('2d');
  const composited = [];
  
  let previousImageData = null;
  
  for (const frame of rawFrames) {
    // Handle disposal from PREVIOUS frame
    if (previousImageData && frame.disposalMethod === 'restoreToPrevious') {
      ctx.putImageData(previousImageData, 0, 0);
    } else if (frame.disposalMethod === 'restoreToBackground') {
      ctx.clearRect(0, 0, canvasWidth, canvasHeight);
    }
    // 'doNotDispose' = keep current canvas state
    
    // Save state before drawing (for future "restoreToPrevious")
    if (frame.disposalMethod === 'restoreToPrevious') {
      previousImageData = ctx.getImageData(0, 0, canvasWidth, canvasHeight);
    }
    
    // Draw current frame
    const frameImageData = new ImageData(
      new Uint8ClampedArray(frame.pixels),
      frame.width,
      frame.height
    );
    
    // Create temp canvas for frame
    const tempCanvas = new OffscreenCanvas(frame.width, frame.height);
    const tempCtx = tempCanvas.getContext('2d');
    tempCtx.putImageData(frameImageData, 0, 0);
    
    // Composite onto main canvas at offset
    ctx.drawImage(tempCanvas, frame.left, frame.top);
    
    // Capture full composited frame
    composited.push({
      rgba: ctx.getImageData(0, 0, canvasWidth, canvasHeight).data,
      width: canvasWidth,
      height: canvasHeight,
      duration: frame.delay
    });
  }
  
  return composited;
}
```

---

*End of Specification*

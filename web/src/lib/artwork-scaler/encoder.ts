/**
 * WebP Encoder
 * Handles encoding RGBA frames to lossless WebP (static and animated)
 */

import type { Frame, ProgressCallback } from './types';
import { ScalerError } from './types';

/**
 * Convert RGBA bytes to the format expected by webpxmux.
 *
 * webpxmux has a buggy RGBA-to-ARGB conversion in its C code (webpenc.c):
 *   *pixel = (((*pixel & 0xff) << 24) | (*pixel >> 8));
 *
 * This rotates bytes incorrectly. To compensate, we pre-transform our data
 * so that after webpxmux's transformation, the result is correct ARGB.
 *
 * Canvas RGBA bytes: [R, G, B, A] stored as 0xAABBGGRR (little-endian)
 * Required input for webpxmux: 0xRRGGBBAA (bytes [A, B, G, R] in little-endian)
 * After webpxmux transform: 0xAARRGGBB (correct ARGB for libwebp)
 */
function rgbaToWebpxmuxFormat(rgba: Uint8ClampedArray): Uint32Array {
  const pixelCount = rgba.length / 4;
  const result = new Uint32Array(pixelCount);
  for (let i = 0; i < pixelCount; i++) {
    const offset = i * 4;
    // Reverse byte order: RGBA [R,G,B,A] -> [A,B,G,R] for webpxmux
    // This produces 0xRRGGBBAA which webpxmux will transform to 0xAARRGGBB
    result[i] =
      (rgba[offset] << 24) | // R to high byte
      (rgba[offset + 1] << 16) | // G to byte 2
      (rgba[offset + 2] << 8) | // B to byte 1
      rgba[offset + 3]; // A to low byte
  }
  return result;
}

/**
 * Default lossless encoding options for @saschazar/wasm-webp
 */
const LOSSLESS_OPTIONS = {
  quality: 100,
  target_size: 0,
  target_PSNR: 0,
  method: 6, // Maximum compression effort
  sns_strength: 0,
  filter_strength: 0,
  filter_sharpness: 0,
  filter_type: 0,
  partitions: 0,
  segments: 1,
  pass: 1,
  show_compressed: 0,
  preprocessing: 0,
  autofilter: 0,
  partition_limit: 0,
  alpha_compression: 1,
  alpha_filtering: 1,
  alpha_quality: 100,
  lossless: 1, // CRITICAL: Lossless encoding
  exact: 1, // CRITICAL: Preserve RGB values in transparent areas
  image_hint: 0,
  emulate_jpeg_size: 0,
  thread_level: 0,
  low_memory: 0,
  near_lossless: 100,
  use_delta_palette: 0,
  use_sharp_yuv: 0,
};

/**
 * Encode a single frame to lossless WebP using @saschazar/wasm-webp
 */
export async function encodeStaticWebP(
  frame: Frame,
  onProgress?: ProgressCallback
): Promise<Uint8Array> {
  if (onProgress) {
    onProgress({ stage: 'encoding', current: 0, total: 1, percent: 0 });
  }

  const wasm_webp = (await import('@saschazar/wasm-webp')).default;

  try {
    // Initialize the WebAssembly module (Promise-based API in v3+)
    const webpModule = await wasm_webp({
      locateFile: (path: string) => {
        if (path.endsWith('.wasm')) {
          return '/wasm/wasm_webp.wasm';
        }
        return path;
      },
    });

    // Encode RGBA to lossless WebP
    const result = webpModule.encode(
      frame.rgba,
      frame.width,
      frame.height,
      4, // 4 channels (RGBA)
      LOSSLESS_OPTIONS
    );

    if (!result || result.length === 0) {
      throw new ScalerError('ENCODE_FAILED', 'WebP encoding returned empty result');
    }

    // Copy result before freeing (result is BufferSource, could be Uint8Array or ArrayBuffer)
    const output = result instanceof Uint8Array
      ? new Uint8Array(result)
      : new Uint8Array(result as ArrayBuffer);

    webpModule.free();

    if (onProgress) {
      onProgress({ stage: 'encoding', current: 1, total: 1, percent: 100 });
    }

    return output;
  } catch (err) {
    if (err instanceof ScalerError) {
      throw err;
    }
    throw new ScalerError('ENCODE_FAILED', `WebP encoding failed: ${err}`);
  }
}

/**
 * Encode multiple frames to animated lossless WebP using webpxmux
 */
export async function encodeAnimatedWebP(
  frames: Frame[],
  loopCount: number = 0,
  onProgress?: ProgressCallback
): Promise<Uint8Array> {
  if (frames.length === 0) {
    throw new ScalerError('ENCODE_FAILED', 'No frames to encode');
  }

  if (frames.length === 1) {
    // Single frame - use static encoder
    return encodeStaticWebP(frames[0], onProgress);
  }

  if (onProgress) {
    onProgress({ stage: 'encoding', current: 0, total: frames.length, percent: 0 });
  }

  const webpxmuxModule = await import('webpxmux');
  const createWebPXMux = webpxmuxModule.default;

  // Use absolute path - works in both main thread and worker contexts
  const wasmUrl = typeof window !== 'undefined'
    ? new URL('/wasm/webpxmux.wasm', window.location.href).toString()
    : '/wasm/webpxmux.wasm';
  const mux = createWebPXMux(wasmUrl);

  await mux.waitRuntime();

  // Convert frames to webpxmux format
  const width = frames[0].width;
  const height = frames[0].height;

  const webpFrames = frames.map((frame, i) => {
    if (onProgress) {
      onProgress({
        stage: 'encoding',
        current: i + 1,
        total: frames.length,
        percent: Math.round(((i + 1) / frames.length) * 100),
      });
    }

    // Convert RGBA bytes to webpxmux format with byte-order transformation
    // to compensate for webpxmux's buggy RGBA-to-ARGB conversion
    const rgba32 = rgbaToWebpxmuxFormat(frame.rgba);

    return {
      duration: frame.duration,
      isKeyframe: i === 0, // First frame is keyframe
      rgba: rgba32,
    };
  });

  const framesData = {
    frameCount: webpFrames.length,
    width,
    height,
    loopCount,
    bgColor: 0x00000000, // Transparent background
    frames: webpFrames,
  };

  try {
    const result = await mux.encodeFrames(framesData);

    if (!result || result.length === 0) {
      throw new ScalerError('ENCODE_FAILED', 'Animated WebP encoding returned empty result');
    }

    return result;
  } catch (err) {
    throw new ScalerError('ENCODE_FAILED', `Animated WebP encoding failed: ${err}`);
  }
}

/**
 * Main encode function - routes to static or animated encoder
 */
export async function encodeWebP(
  frames: Frame[],
  loopCount: number = 0,
  onProgress?: ProgressCallback
): Promise<Uint8Array> {
  if (frames.length === 1) {
    return encodeStaticWebP(frames[0], onProgress);
  } else {
    return encodeAnimatedWebP(frames, loopCount, onProgress);
  }
}

/**
 * Check if frames have any transparency (alpha < 255)
 */
export function framesHaveAlpha(frames: Frame[]): boolean {
  for (const frame of frames) {
    // Check every 4th byte (alpha channel)
    for (let i = 3; i < frame.rgba.length; i += 4) {
      if (frame.rgba[i] < 255) {
        return true;
      }
    }
  }
  return false;
}

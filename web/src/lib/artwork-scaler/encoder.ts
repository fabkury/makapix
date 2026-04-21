/**
 * WebP Encoder
 * Handles encoding RGBA frames to WebP (static and animated), losslessly or
 * lossily depending on the source format's own lossiness.
 */

import type { Frame, ProgressCallback } from './types';
import { ScalerError } from './types';
import type { WebPOptions } from '@saschazar/wasm-webp';

/**
 * Build the static-encoder config for @saschazar/wasm-webp.
 *
 * Lossless uses `exact: 1` so RGB values beneath fully-transparent pixels
 * survive the round-trip — important because Pixelc/Piskel layers sometimes
 * leave colored data under alpha-0 regions.
 */
function buildStaticWebpOptions(lossless: boolean): WebPOptions {
  return {
    quality: 100,
    target_size: 0,
    target_PSNR: 0,
    method: 6, // max compression effort
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
    // Lossy mode is only reached when the input was itself lossy WebP. Keep
    // quality high to avoid stacking generational loss on top of the source.
    lossless: lossless ? 1 : 0,
    // exact=1 preserves RGB values under fully-transparent pixels — matters for
    // pixel art with hidden colored layers under alpha-0 regions.
    exact: lossless ? 1 : 0,
    image_hint: 0,
    emulate_jpeg_size: 0,
    thread_level: 0,
    low_memory: 0,
    near_lossless: 100,
    use_delta_palette: 0,
    use_sharp_yuv: 0,
  };
}

/**
 * Encode a single frame to WebP using @saschazar/wasm-webp.
 */
export async function encodeStaticWebP(
  frame: Frame,
  lossless: boolean,
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

    const result = webpModule.encode(
      frame.rgba,
      frame.width,
      frame.height,
      4, // 4 channels (RGBA)
      buildStaticWebpOptions(lossless)
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

// Cache the wasm-webp Emscripten Module instance — it's expensive to
// instantiate and safe to share across calls.
let animatedWebpModulePromise: Promise<any> | null = null;

async function getAnimatedWebpModule(): Promise<any> {
  if (!animatedWebpModulePromise) {
    // Import the glue directly instead of the high-level wrapper so we can
    // pass `locateFile` — the wrapper calls Module() with no arguments, and
    // next.config disables webpack's asset-URL detection for this package, so
    // Emscripten's own `new URL('webp-wasm.wasm', import.meta.url)` fallback
    // won't resolve. We serve the WASM from /wasm/webp-wasm.wasm instead
    // (Dockerfile copies it from node_modules at build time).
    // @ts-expect-error: subpath import, no TS declarations
    const glueModule = await import('wasm-webp/dist/esm/webp-wasm.js');
    const factory = glueModule.default;
    animatedWebpModulePromise = factory({
      locateFile: (path: string) => {
        if (path.endsWith('.wasm')) {
          return '/wasm/webp-wasm.wasm';
        }
        return path;
      },
    });
  }
  return animatedWebpModulePromise;
}

/**
 * Encode multiple frames to animated WebP using wasm-webp
 * (libwebp's WebPAnimEncoder under the hood).
 */
export async function encodeAnimatedWebP(
  frames: Frame[],
  loopCount: number = 0,
  lossless: boolean,
  onProgress?: ProgressCallback
): Promise<Uint8Array> {
  if (frames.length === 0) {
    throw new ScalerError('ENCODE_FAILED', 'No frames to encode');
  }

  if (frames.length === 1) {
    return encodeStaticWebP(frames[0], lossless, onProgress);
  }

  if (onProgress) {
    onProgress({ stage: 'encoding', current: 0, total: frames.length, percent: 0 });
  }

  // loopCount is accepted for API symmetry with the old encoder but wasm-webp
  // 0.1.0 doesn't expose a loop-count knob — libwebp's default (infinite loop,
  // matching GIF and most source WebPs) is applied.
  void loopCount;

  const m = await getAnimatedWebpModule();

  const frameVector = new m.VectorWebPAnimationFrame();
  try {
    const config = {
      lossless: lossless ? 1 : 0,
      // Quality is ignored by libwebp when lossless = 1. For lossy we keep
      // quality high to minimize additional generational loss.
      quality: 100,
    };

    for (let i = 0; i < frames.length; i++) {
      const f = frames[i];
      // wasm-webp expects plain Uint8Array; Frame.rgba is Uint8ClampedArray.
      // Same memory; just reinterpret without copying.
      const data = new Uint8Array(f.rgba.buffer, f.rgba.byteOffset, f.rgba.byteLength);
      frameVector.push_back({
        duration: f.duration,
        data,
        config,
        has_config: true,
      });

      if (onProgress) {
        onProgress({
          stage: 'encoding',
          current: i + 1,
          total: frames.length,
          percent: Math.round(((i + 1) / frames.length) * 100),
        });
      }
    }

    // wasm-webp's C++ binding uses hasAlpha to set stride = hasAlpha ? 4*w : 3*w
    // and dispatches to WebPPictureImportRGBA / WebPPictureImportRGB accordingly.
    // Our frame data is always 4-byte-per-pixel RGBA (from canvas), so hasAlpha
    // must be true even when every pixel's alpha is 255; passing false would
    // make libwebp read 3 bytes per pixel and scramble the image.
    const result = m.encodeAnimation(frames[0].width, frames[0].height, true, frameVector);

    if (!result || result.length === 0) {
      throw new ScalerError('ENCODE_FAILED', 'Animated WebP encoding returned empty result');
    }

    return result instanceof Uint8Array ? new Uint8Array(result) : new Uint8Array(result);
  } catch (err) {
    if (err instanceof ScalerError) throw err;
    throw new ScalerError('ENCODE_FAILED', `Animated WebP encoding failed: ${err}`);
  } finally {
    if (typeof frameVector.delete === 'function') {
      frameVector.delete();
    }
  }
}

/**
 * Main encode function - routes to static or animated encoder
 */
export async function encodeWebP(
  frames: Frame[],
  loopCount: number = 0,
  lossless: boolean,
  onProgress?: ProgressCallback
): Promise<Uint8Array> {
  if (frames.length === 1) {
    return encodeStaticWebP(frames[0], lossless, onProgress);
  } else {
    return encodeAnimatedWebP(frames, loopCount, lossless, onProgress);
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

/**
 * Image Decoders
 * Handles decoding of GIF, PNG, BMP, and WebP images to raw RGBA frames
 */

import type { DecodedImage, Frame, InputFormat, ProgressCallback } from './types';
import { ScalerError, MAX_FRAMES } from './types';

/**
 * Decode a GIF image (static or animated) using gifuct-js
 */
export async function decodeGif(
  buffer: ArrayBuffer,
  onProgress?: ProgressCallback
): Promise<DecodedImage> {
  const { parseGIF, decompressFrames } = await import('gifuct-js');

  const gif = parseGIF(buffer);
  const rawFrames = decompressFrames(gif, true);

  if (rawFrames.length === 0) {
    throw new ScalerError('DECODE_FAILED', 'GIF contains no frames');
  }

  if (rawFrames.length > MAX_FRAMES) {
    throw new ScalerError(
      'TOO_MANY_FRAMES',
      `GIF has ${rawFrames.length} frames, maximum allowed is ${MAX_FRAMES}`
    );
  }

  // Get canvas dimensions from first frame or GIF header
  const canvasWidth = gif.lsd.width;
  const canvasHeight = gif.lsd.height;

  const frames: Frame[] = [];

  // Create a persistent canvas for compositing
  const canvas = new OffscreenCanvas(canvasWidth, canvasHeight);
  const ctx = canvas.getContext('2d')!;

  // Previous frame data for disposal method handling
  let previousImageData: ImageData | null = null;

  for (let i = 0; i < rawFrames.length; i++) {
    const rawFrame = rawFrames[i];

    if (onProgress) {
      onProgress({
        stage: 'decoding',
        current: i + 1,
        total: rawFrames.length,
        percent: Math.round(((i + 1) / rawFrames.length) * 100),
      });
    }

    // Handle disposal from PREVIOUS frame before drawing current
    const disposalMethod = rawFrame.disposalType;

    // Create ImageData for this frame's patch
    const frameWidth = rawFrame.dims.width;
    const frameHeight = rawFrame.dims.height;
    const frameLeft = rawFrame.dims.left;
    const frameTop = rawFrame.dims.top;

    // gifuct-js provides RGBA patch data
    const patchData = new Uint8ClampedArray(rawFrame.patch);

    // Draw frame patch onto canvas
    if (patchData.length === frameWidth * frameHeight * 4) {
      const patchImageData = new ImageData(patchData, frameWidth, frameHeight);

      // Create temp canvas for the patch
      const tempCanvas = new OffscreenCanvas(frameWidth, frameHeight);
      const tempCtx = tempCanvas.getContext('2d')!;
      tempCtx.putImageData(patchImageData, 0, 0);

      // Draw patch onto main canvas at offset
      ctx.drawImage(tempCanvas, frameLeft, frameTop);
    }

    // Capture full composited frame
    const composited = ctx.getImageData(0, 0, canvasWidth, canvasHeight);
    frames.push({
      rgba: new Uint8ClampedArray(composited.data),
      width: canvasWidth,
      height: canvasHeight,
      // GIF delays are in centiseconds, convert to milliseconds
      // Minimum of 20ms (browsers default 0 to 100ms, we use 20ms for smoother animation)
      duration: Math.max(rawFrame.delay * 10, 20),
    });

    // Handle disposal method for next frame
    if (disposalMethod === 2) {
      // Restore to background (clear the frame area)
      ctx.clearRect(frameLeft, frameTop, frameWidth, frameHeight);
    } else if (disposalMethod === 3 && previousImageData) {
      // Restore to previous
      ctx.putImageData(previousImageData, 0, 0);
    }

    // Save state for potential "restore to previous"
    if (disposalMethod !== 3) {
      previousImageData = ctx.getImageData(0, 0, canvasWidth, canvasHeight);
    }
  }

  return {
    frames,
    loopCount: 0, // GIF typically loops infinitely
    originalFormat: 'gif',
    isAnimated: frames.length > 1,
  };
}

/**
 * Decode a PNG image (static only, APNG treated as static)
 */
export async function decodePng(
  buffer: ArrayBuffer,
  onProgress?: ProgressCallback
): Promise<DecodedImage> {
  const UPNG = await import('upng-js');

  if (onProgress) {
    onProgress({ stage: 'decoding', current: 0, total: 1, percent: 0 });
  }

  // Decode PNG
  const img = UPNG.decode(buffer);

  // Convert to RGBA (handles all PNG color types)
  const rgba = UPNG.toRGBA8(img);

  if (rgba.length === 0) {
    throw new ScalerError('DECODE_FAILED', 'PNG decode returned no data');
  }

  // For static PNG, use first buffer (APNG would have multiple)
  const frameData = new Uint8ClampedArray(rgba[0]);

  if (onProgress) {
    onProgress({ stage: 'decoding', current: 1, total: 1, percent: 100 });
  }

  return {
    frames: [{
      rgba: frameData,
      width: img.width,
      height: img.height,
      duration: 0, // Static image
    }],
    loopCount: 0,
    originalFormat: 'png',
    isAnimated: false,
  };
}

/**
 * Decode a BMP image using native browser canvas
 */
export async function decodeBmp(
  buffer: ArrayBuffer,
  onProgress?: ProgressCallback
): Promise<DecodedImage> {
  if (onProgress) {
    onProgress({ stage: 'decoding', current: 0, total: 1, percent: 0 });
  }

  // Create blob URL for the BMP
  const blob = new Blob([buffer], { type: 'image/bmp' });
  const url = URL.createObjectURL(blob);

  try {
    // Load image via browser
    const img = await loadImage(url);

    // Draw to canvas and extract RGBA
    const canvas = new OffscreenCanvas(img.width, img.height);
    const ctx = canvas.getContext('2d')!;
    ctx.drawImage(img, 0, 0);

    const imageData = ctx.getImageData(0, 0, img.width, img.height);

    if (onProgress) {
      onProgress({ stage: 'decoding', current: 1, total: 1, percent: 100 });
    }

    return {
      frames: [{
        rgba: new Uint8ClampedArray(imageData.data),
        width: img.width,
        height: img.height,
        duration: 0,
      }],
      loopCount: 0,
      originalFormat: 'bmp',
      isAnimated: false,
    };
  } finally {
    URL.revokeObjectURL(url);
  }
}

/**
 * Decode a WebP image (static or animated) using webpxmux
 */
export async function decodeWebp(
  buffer: ArrayBuffer,
  onProgress?: ProgressCallback
): Promise<DecodedImage> {
  // Try ImageDecoder API first (Chrome/Firefox/Edge)
  if (typeof window !== 'undefined' && 'ImageDecoder' in window) {
    try {
      return await decodeWebpWithImageDecoder(buffer, onProgress);
    } catch (err) {
      console.warn('ImageDecoder failed, falling back to WASM:', err);
    }
  }

  // Fall back to webpxmux WASM
  return decodeWebpWithWasm(buffer, onProgress);
}

/**
 * Decode WebP using native ImageDecoder API
 */
async function decodeWebpWithImageDecoder(
  buffer: ArrayBuffer,
  onProgress?: ProgressCallback
): Promise<DecodedImage> {
  const ImageDecoderClass = (window as any).ImageDecoder;

  const isSupported = await ImageDecoderClass.isTypeSupported('image/webp');
  if (!isSupported) {
    throw new Error('ImageDecoder does not support WebP');
  }

  const decoder = new ImageDecoderClass({
    data: buffer,
    type: 'image/webp',
  });

  await decoder.tracks.ready;
  const track = decoder.tracks.selectedTrack;

  if (!track) {
    decoder.close();
    throw new Error('No image track found');
  }

  const frameCount = track.frameCount;

  if (frameCount > MAX_FRAMES) {
    decoder.close();
    throw new ScalerError(
      'TOO_MANY_FRAMES',
      `WebP has ${frameCount} frames, maximum allowed is ${MAX_FRAMES}`
    );
  }

  const frames: Frame[] = [];

  try {
    for (let i = 0; i < frameCount; i++) {
      if (onProgress) {
        onProgress({
          stage: 'decoding',
          current: i + 1,
          total: frameCount,
          percent: Math.round(((i + 1) / frameCount) * 100),
        });
      }

      const result = await decoder.decode({ frameIndex: i });
      const frame = result.image as any;

      const w = frame.displayWidth ?? frame.codedWidth ?? frame.width;
      const h = frame.displayHeight ?? frame.codedHeight ?? frame.height;

      // Convert to RGBA via canvas (OffscreenCanvas for worker compatibility)
      const canvas = new OffscreenCanvas(w, h);
      const ctx = canvas.getContext('2d')!;
      ctx.drawImage(frame, 0, 0);

      const imageData = ctx.getImageData(0, 0, w, h);
      const durationMs = frame.duration ? frame.duration / 1000 : 100;

      frames.push({
        rgba: new Uint8ClampedArray(imageData.data),
        width: w,
        height: h,
        duration: durationMs,
      });

      if (typeof frame.close === 'function') {
        frame.close();
      }
    }
  } finally {
    decoder.close();
  }

  return {
    frames,
    loopCount: 0,
    originalFormat: 'webp',
    isAnimated: frameCount > 1,
  };
}

/**
 * Decode WebP using webpxmux WASM
 */
async function decodeWebpWithWasm(
  buffer: ArrayBuffer,
  onProgress?: ProgressCallback
): Promise<DecodedImage> {
  const webpxmuxModule = await import('webpxmux');
  const createWebPXMux = webpxmuxModule.default;

  // Use absolute path - works in both main thread and worker contexts
  const wasmUrl = typeof window !== 'undefined'
    ? new URL('/wasm/webpxmux.wasm', window.location.href).toString()
    : '/wasm/webpxmux.wasm';
  const mux = createWebPXMux(wasmUrl);

  await mux.waitRuntime();

  if (onProgress) {
    onProgress({ stage: 'decoding', current: 0, total: 1, percent: 0 });
  }

  const uint8Array = new Uint8Array(buffer);
  const info = await mux.decodeFrames(uint8Array);

  if (!info || !info.frames || info.frames.length === 0) {
    throw new ScalerError('DECODE_FAILED', 'webpxmux returned no frames');
  }

  if (info.frames.length > MAX_FRAMES) {
    throw new ScalerError(
      'TOO_MANY_FRAMES',
      `WebP has ${info.frames.length} frames, maximum allowed is ${MAX_FRAMES}`
    );
  }

  const frames: Frame[] = [];

  for (let i = 0; i < info.frames.length; i++) {
    if (onProgress) {
      onProgress({
        stage: 'decoding',
        current: i + 1,
        total: info.frames.length,
        percent: Math.round(((i + 1) / info.frames.length) * 100),
      });
    }

    const frame = info.frames[i];

    // frame.rgba is Uint32Array, convert to Uint8ClampedArray
    // Must respect byteOffset in case frame.rgba is a view into a larger buffer
    const rgbaBytes = new Uint8ClampedArray(
      frame.rgba.buffer.slice(
        frame.rgba.byteOffset,
        frame.rgba.byteOffset + frame.rgba.byteLength
      )
    );

    frames.push({
      rgba: rgbaBytes,
      width: info.width,
      height: info.height,
      duration: frame.duration || 100,
    });
  }

  return {
    frames,
    loopCount: info.loopCount || 0,
    originalFormat: 'webp',
    isAnimated: info.frames.length > 1,
  };
}

/**
 * Helper to load an image element
 */
function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Failed to load image'));
    img.src = url;
  });
}

/**
 * Detect input format from buffer magic bytes
 */
export function detectFormat(buffer: ArrayBuffer): InputFormat | null {
  const view = new DataView(buffer);

  if (buffer.byteLength < 12) return null;

  // GIF: "GIF87a" or "GIF89a"
  if (
    view.getUint8(0) === 0x47 &&
    view.getUint8(1) === 0x49 &&
    view.getUint8(2) === 0x46
  ) {
    return 'gif';
  }

  // PNG: 0x89 "PNG" 0x0D 0x0A 0x1A 0x0A
  if (
    view.getUint8(0) === 0x89 &&
    view.getUint8(1) === 0x50 &&
    view.getUint8(2) === 0x4E &&
    view.getUint8(3) === 0x47
  ) {
    return 'png';
  }

  // WebP: "RIFF" + size + "WEBP"
  if (
    view.getUint32(0, false) === 0x52494646 && // "RIFF"
    view.getUint32(8, false) === 0x57454250    // "WEBP"
  ) {
    return 'webp';
  }

  // BMP: "BM"
  if (view.getUint8(0) === 0x42 && view.getUint8(1) === 0x4D) {
    return 'bmp';
  }

  return null;
}

/**
 * Main decode function - routes to appropriate decoder
 */
export async function decode(
  buffer: ArrayBuffer,
  format?: InputFormat,
  onProgress?: ProgressCallback
): Promise<DecodedImage> {
  const detectedFormat = format || detectFormat(buffer);

  if (!detectedFormat) {
    throw new ScalerError('UNSUPPORTED_FORMAT', 'Could not detect image format');
  }

  switch (detectedFormat) {
    case 'gif':
      return decodeGif(buffer, onProgress);
    case 'png':
      return decodePng(buffer, onProgress);
    case 'webp':
      return decodeWebp(buffer, onProgress);
    case 'bmp':
      return decodeBmp(buffer, onProgress);
    default:
      throw new ScalerError('UNSUPPORTED_FORMAT', `Unsupported format: ${detectedFormat}`);
  }
}

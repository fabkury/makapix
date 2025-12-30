/**
 * WebP Animation Decoder
 * 
 * Hybrid approach that uses native ImageDecoder API when available,
 * falling back to webpxmux WASM for Safari and when ImageDecoder fails.
 */

export interface DecodedFrame {
  rgba: ArrayBuffer; // RGBA bytes (width*height*4). Sent via postMessage transferables.
  duration: number; // Frame duration in milliseconds
}

export interface DecodedAnimation {
  frames: DecodedFrame[];
  width: number;
  height: number;
  frameCount: number;
  averageFps: number;
  isAnimated: boolean;
}

export interface DecodingProgress {
  current: number;
  total: number;
  phase: 'fetching' | 'decoding' | 'converting';
}

export type ProgressCallback = (progress: DecodingProgress) => void;

/**
 * Check if the browser supports ImageDecoder API for WebP
 */
export function supportsImageDecoder(): boolean {
  return typeof window !== 'undefined' && 'ImageDecoder' in window;
}

/**
 * Detect if a WebP file is animated (has multiple frames)
 * @deprecated Use decodeWebPAnimation instead - it handles detection internally
 */
export async function isAnimatedWebP(url: string): Promise<boolean> {
  try {
    const response = await fetch(url);
    const buffer = await response.arrayBuffer();
    return checkForAnimChunk(buffer);
  } catch {
    return false;
  }
}

/**
 * Check for ANIM chunk in WebP buffer (indicates it might be animated)
 */
function checkForAnimChunk(buffer: ArrayBuffer): boolean {
  try {
    const view = new DataView(buffer);
    
    // Verify RIFF header
    if (buffer.byteLength < 12) return false;
    if (view.getUint32(0, false) !== 0x52494646) return false; // "RIFF"
    
    // Verify WEBP signature
    if (view.getUint32(8, false) !== 0x57454250) return false; // "WEBP"
    
    // Look for ANIM chunk (indicates animation)
    let offset = 12;
    while (offset < buffer.byteLength - 8) {
      const chunkType = view.getUint32(offset, false);
      const chunkSize = view.getUint32(offset + 4, true);
      
      // 0x414E494D = "ANIM"
      if (chunkType === 0x414E494D) {
        return true;
      }
      
      offset += 8 + chunkSize + (chunkSize % 2); // Chunks are padded to even length
    }
    
    return false;
  } catch {
    return false;
  }
}

/**
 * Helper to load an image and return its dimensions
 */
function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = url;
  });
}

/**
 * Extract detailed error message from various error types
 */
function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  if (error instanceof Event) {
    // ImageDecoder often rejects with Event objects
    const target = (error as any).target;
    if (target?.error) {
      return `Event error: ${target.error.message || target.error}`;
    }
    return `Event: ${error.type || 'unknown event'}`;
  }
  if (typeof error === 'object' && error !== null) {
    // Try to extract useful info from object
    const obj = error as Record<string, unknown>;
    if ('message' in obj) return String(obj.message);
    if ('error' in obj) return String(obj.error);
    return JSON.stringify(error);
  }
  return String(error);
}

/**
 * Decode WebP animation using native ImageDecoder API (Chrome/Firefox/Edge)
 */
async function decodeWithImageDecoder(
  buffer: ArrayBuffer,
  onProgress?: ProgressCallback
): Promise<DecodedAnimation> {
  if (!('ImageDecoder' in window)) {
    throw new Error('ImageDecoder API not available');
  }

  const ImageDecoderClass = (window as any).ImageDecoder;
  
  // Check if WebP is supported by ImageDecoder
  let isSupported = false;
  try {
    isSupported = await ImageDecoderClass.isTypeSupported('image/webp');
  } catch (err) {
    throw new Error(`ImageDecoder.isTypeSupported failed: ${getErrorMessage(err)}`);
  }
  
  if (!isSupported) {
    throw new Error('ImageDecoder does not support WebP format');
  }

  let decoder: any;
  try {
    decoder = new ImageDecoderClass({
      data: buffer,
      type: 'image/webp',
    });
  } catch (err) {
    throw new Error(`ImageDecoder constructor failed: ${getErrorMessage(err)}`);
  }

  // Wait for tracks to be ready with timeout
  try {
    await Promise.race([
      decoder.tracks.ready,
      new Promise((_, reject) => 
        setTimeout(() => reject(new Error('ImageDecoder tracks.ready timed out after 10s')), 10000)
      )
    ]);
  } catch (err) {
    decoder.close();
    throw new Error(`ImageDecoder tracks.ready failed: ${getErrorMessage(err)}`);
  }

  const track = decoder.tracks.selectedTrack;
  
  if (!track) {
    decoder.close();
    throw new Error('ImageDecoder: No image track found in WebP file');
  }
  
  const frameCount = track.frameCount;
  console.log(`ImageDecoder: Found ${frameCount} frame(s) in WebP`);

  // If only 1 frame, it's not really animated
  if (frameCount <= 1) {
    decoder.close();
    return {
      frames: [],
      width: 0,
      height: 0,
      frameCount: 1,
      averageFps: 0,
      isAnimated: false,
    };
  }

  if (onProgress) {
    onProgress({ current: 0, total: frameCount, phase: 'decoding' });
  }

  const frames: DecodedFrame[] = [];
  const durations: number[] = [];
  let width = 0;
  let height = 0;

  try {
    for (let i = 0; i < frameCount; i++) {
      let result;
      try {
        result = await decoder.decode({ frameIndex: i });
      } catch (err) {
        throw new Error(`ImageDecoder.decode() failed at frame ${i}: ${getErrorMessage(err)}`);
      }
      
      // Some browsers return ImageBitmap, others return VideoFrame-like objects.
      // Both are valid sources for drawImage.
      const frame: any = result.image;
      const w = frame.displayWidth ?? frame.codedWidth ?? frame.width;
      const h = frame.displayHeight ?? frame.codedHeight ?? frame.height;
      if (!w || !h) {
        throw new Error(`ImageDecoder returned frame without dimensions at index ${i}`);
      }
      
      // Store dimensions from first frame
      if (i === 0) {
        width = w;
        height = h;
      }
      
      // Convert frame to RGBA bytes via canvas
      const canvas = document.createElement('canvas');
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext('2d');
      
      if (!ctx) {
        throw new Error('Failed to create canvas context');
      }

      ctx.drawImage(frame, 0, 0);
      
      // Get duration in milliseconds (ImageDecoder returns microseconds)
      const durationMs = (result.image as any).duration ? (result.image as any).duration / 1000 : 100;
      durations.push(durationMs);
      
      const imgData = ctx.getImageData(0, 0, w, h);
      // Copy to a standalone ArrayBuffer so it can be transferred safely.
      const rgba = imgData.data.buffer.slice(0);
      frames.push({
        rgba,
        duration: durationMs,
      });

      // Close underlying resources if supported (ImageBitmap / VideoFrame)
      try {
        if (typeof frame.close === 'function') frame.close();
      } catch {
        // ignore
      }

      if (onProgress) {
        onProgress({ current: i + 1, total: frameCount, phase: 'converting' });
      }
    }
  } finally {
    decoder.close();
  }

  // Calculate average FPS from frame durations
  const totalDuration = durations.reduce((sum, d) => sum + d, 0);
  const averageFps = totalDuration > 0 ? Math.round((frameCount * 1000) / totalDuration) : 10;

  console.log(`ImageDecoder: Successfully decoded ${frames.length} frames at ~${averageFps} FPS`);

  return {
    frames,
    width,
    height,
    frameCount,
    averageFps,
    isAnimated: frameCount > 1,
  };
}

/**
 * Decode WebP animation using WASM fallback (webpxmux)
 * Used for Safari and when ImageDecoder fails
 */
async function decodeWithWasm(
  buffer: ArrayBuffer,
  onProgress?: ProgressCallback
): Promise<DecodedAnimation> {
  console.log('WASM: Loading webpxmux library...');
  
  // Lazy-load webpxmux - it's a default export factory function
  const webpxmuxModule = await import('webpxmux');
  const createWebPXMux = webpxmuxModule.default;
  
  // Create decoder instance with an explicit wasm path.
  // We serve this file from Next.js public assets at /wasm/webpxmux.wasm
  const wasmUrl = new URL('/wasm/webpxmux.wasm', window.location.href).toString();
  const mux = createWebPXMux(wasmUrl);
  
  // Wait for WASM runtime to initialize
  await mux.waitRuntime();
  
  if (onProgress) {
    onProgress({ current: 0, total: 1, phase: 'decoding' });
  }

  // Decode the WebP file
  const uint8Array = new Uint8Array(buffer);
  let info;
  try {
    info = await mux.decodeFrames(uint8Array);
  } catch (err) {
    throw new Error(`webpxmux decodeFrames failed: ${getErrorMessage(err)}`);
  }
  
  if (!info || !info.frames || info.frames.length === 0) {
    throw new Error('webpxmux returned no frames');
  }

  console.log(`WASM: Found ${info.frames.length} frame(s), ${info.width}x${info.height}`);

  const frames: DecodedFrame[] = [];
  const frameCount = info.frames.length;

  for (let i = 0; i < frameCount; i++) {
    const frame = info.frames[i];
    
    // Create canvas from frame RGBA data
    const canvas = document.createElement('canvas');
    canvas.width = info.width;
    canvas.height = info.height;
    const ctx = canvas.getContext('2d');
    
    if (!ctx) {
      throw new Error('Failed to create canvas context');
    }

    // frame.rgba is Uint32Array - convert to Uint8ClampedArray for ImageData
    // Each Uint32 contains RGBA packed as a single 32-bit value
    // Copy to a new ArrayBuffer to ensure it's not a SharedArrayBuffer
    const byteLength = frame.rgba.byteLength;
    const newBuffer = new ArrayBuffer(byteLength);
    new Uint8Array(newBuffer).set(new Uint8Array(frame.rgba.buffer));
    const rgbaBytes = new Uint8ClampedArray(newBuffer);
    const imageData = new ImageData(rgbaBytes, info.width, info.height);
    ctx.putImageData(imageData, 0, 0);
    
    // Duration is in milliseconds
    const duration = frame.duration || 100;
    
    // Extract RGBA bytes and copy to standalone buffer for transfer
    const imgData = ctx.getImageData(0, 0, info.width, info.height);
    const rgba = imgData.data.buffer.slice(0);

    frames.push({
      rgba,
      duration,
    });

    if (onProgress) {
      onProgress({ current: i + 1, total: frameCount, phase: 'converting' });
    }
  }

  // Calculate average FPS from frame durations
  const totalDuration = frames.reduce((sum, f) => sum + f.duration, 0);
  const averageFps = totalDuration > 0 ? Math.round((frameCount * 1000) / totalDuration) : 10;

  console.log(`WASM: Successfully decoded ${frames.length} frames at ~${averageFps} FPS`);

  return {
    frames,
    width: info.width,
    height: info.height,
    frameCount,
    averageFps,
    isAnimated: frameCount > 1,
  };
}

/**
 * Main entry point: Decode WebP animation with proper fallback chain
 * 
 * Fallback order:
 * 1. ImageDecoder API (Chrome/Edge/Firefox - fast, native)
 * 2. WASM via webpxmux (Safari, or when ImageDecoder fails)
 * 3. Single frame (last resort)
 */
export async function decodeWebPAnimation(
  url: string,
  onProgress?: ProgressCallback
): Promise<DecodedAnimation> {
  // Fetch the file
  if (onProgress) {
    onProgress({ current: 0, total: 1, phase: 'fetching' });
  }

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch artwork: ${response.statusText}`);
  }

  const buffer = await response.arrayBuffer();

  // Check if it might be animated (has ANIM chunk)
  const mightBeAnimated = checkForAnimChunk(buffer);
  
  if (!mightBeAnimated) {
    console.log('WebP does not have ANIM chunk - treating as static image');
    return {
      frames: [],
      width: 0,
      height: 0,
      frameCount: 1,
      averageFps: 0,
      isAnimated: false,
    };
  }

  console.log('WebP has ANIM chunk - attempting to decode animation...');

  // FALLBACK 1: Try ImageDecoder first (Chrome/Edge/Firefox)
  if (supportsImageDecoder()) {
    try {
      console.log('Trying ImageDecoder API...');
      const result = await decodeWithImageDecoder(buffer, onProgress);
      
      if (result.isAnimated && result.frames.length > 1) {
        return result;
      }
      console.log('ImageDecoder returned single frame, trying WASM...');
    } catch (error) {
      console.warn('ImageDecoder failed:', getErrorMessage(error));
      console.log('Falling back to WASM decoder...');
    }
  } else {
    console.log('ImageDecoder not available, trying WASM decoder...');
  }

  // FALLBACK 2: Try WASM decoder (webpxmux)
  try {
    const result = await decodeWithWasm(buffer, onProgress);
    
    if (result.isAnimated && result.frames.length > 1) {
      return result;
    }
    console.log('WASM decoder returned single frame');
  } catch (error) {
    console.warn('WASM decoder failed:', getErrorMessage(error));
  }

  // FALLBACK 3: Give up and return as non-animated
  console.warn('All decoders failed - falling back to single frame mode');
  return {
    frames: [],
    width: 0,
    height: 0,
    frameCount: 1,
    averageFps: 0,
    isAnimated: false,
  };
}

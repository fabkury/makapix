/**
 * Artwork Scaler Types
 * Common types for the browser-based lossless WebP image scaler
 */

export type ResamplingAlgorithm = 'nearest-neighbor' | 'lanczos3';

export type InputFormat = 'gif' | 'png' | 'webp' | 'bmp';

export interface Frame {
  /** Full-canvas RGBA pixel data (width * height * 4 bytes) */
  rgba: Uint8ClampedArray;
  /** Canvas width in pixels */
  width: number;
  /** Canvas height in pixels */
  height: number;
  /** Frame duration in milliseconds */
  duration: number;
}

export interface DecodedImage {
  /** Array of frames (single frame for static images) */
  frames: Frame[];
  /** Loop count: 0 = infinite, N = loop N times */
  loopCount: number;
  /** Original input format */
  originalFormat: InputFormat;
  /** Whether the image is animated (multiple frames) */
  isAnimated: boolean;
}

export interface ScalerOptions {
  /** Target width in pixels */
  width: number;
  /** Target height in pixels */
  height: number;
  /** Resampling algorithm (default: 'nearest-neighbor') */
  resamplingAlgorithm?: ResamplingAlgorithm;
  /** Maintain aspect ratio (default: true) */
  maintainAspectRatio?: boolean;
  /** Aspect ratio mode when maintaining ratio (default: 'fit') */
  aspectRatioMode?: 'fit' | 'fill' | 'stretch';
}

export interface ProgressInfo {
  /** Current processing stage */
  stage: 'decoding' | 'scaling' | 'encoding';
  /** Current item being processed (e.g., frame number) */
  current: number;
  /** Total items to process */
  total: number;
  /** Progress percentage (0-100) */
  percent: number;
}

export type ProgressCallback = (progress: ProgressInfo) => void;

export interface ScalerResult {
  /** Output file as Blob */
  blob: Blob;
  /** Actual output width */
  width: number;
  /** Actual output height */
  height: number;
  /** Number of frames in output */
  frameCount: number;
  /** Whether output is animated */
  isAnimated: boolean;
  /** Whether output has transparency */
  hasAlpha: boolean;
  /** Output file size in bytes */
  fileSizeBytes: number;
  /** Output format (webp or original) */
  format: 'webp' | InputFormat;
}

export type ScalerErrorCode =
  | 'UNSUPPORTED_FORMAT'
  | 'DECODE_FAILED'
  | 'INVALID_DIMENSIONS'
  | 'MEMORY_EXCEEDED'
  | 'ENCODE_FAILED'
  | 'WASM_INIT_FAILED'
  | 'TOO_MANY_FRAMES';

export class ScalerError extends Error {
  code: ScalerErrorCode;
  details?: string;

  constructor(code: ScalerErrorCode, message: string, details?: string) {
    super(message);
    this.name = 'ScalerError';
    this.code = code;
    this.details = details;
  }
}

/** Maximum allowed frames for animated images */
export const MAX_FRAMES = 1024;

/** Supported input MIME types */
export const SUPPORTED_MIME_TYPES = [
  'image/gif',
  'image/png',
  'image/webp',
  'image/bmp',
  'image/x-ms-bmp',
] as const;

/** Map MIME type to InputFormat */
export function mimeToFormat(mimeType: string): InputFormat | null {
  switch (mimeType) {
    case 'image/gif':
      return 'gif';
    case 'image/png':
      return 'png';
    case 'image/webp':
      return 'webp';
    case 'image/bmp':
    case 'image/x-ms-bmp':
      return 'bmp';
    default:
      return null;
  }
}

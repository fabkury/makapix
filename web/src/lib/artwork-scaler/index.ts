/**
 * Artwork Scaler - Browser-based Lossless WebP Image Scaler
 *
 * A client-side tool for scaling images (GIF, PNG, BMP, WebP) and encoding
 * to lossless WebP format with full alpha channel preservation.
 *
 * @module artwork-scaler
 */

// Types
export type {
  ResamplingAlgorithm,
  InputFormat,
  Frame,
  DecodedImage,
  ScalerOptions,
  ProgressInfo,
  ProgressCallback,
  ScalerResult,
  ScalerErrorCode,
} from './types';

export { ScalerError, MAX_FRAMES, SUPPORTED_MIME_TYPES, mimeToFormat } from './types';

// Decoders
export { decode, detectFormat } from './decoders';

// Scaler
export {
  scaleFrame,
  scaleFrames,
  calculateOutputDimensions,
  calculateDimensionsByRatio,
} from './scaler';

// Encoder
export { encodeWebP, encodeStaticWebP, encodeAnimatedWebP, framesHaveAlpha } from './encoder';

// Main Processor
export type { ProcessOptions } from './processor';
export { processImage, previewScale, getImageInfo } from './processor';

// React Hook
export { useArtworkScaler } from './useArtworkScaler';
export type { UseArtworkScalerOptions, ImageInfo, ScalerState, ScalerActions } from './useArtworkScaler';

/**
 * Main entry point - scale an image to lossless WebP
 *
 * @example
 * ```typescript
 * import { scaleToLosslessWebP } from '@/lib/artwork-scaler';
 *
 * const result = await scaleToLosslessWebP(file, {
 *   width: 128,
 *   height: 128,
 *   resamplingAlgorithm: 'nearest-neighbor',
 * });
 *
 * // result.blob contains the lossless WebP file
 * ```
 */
export { processImage as scaleToLosslessWebP } from './processor';

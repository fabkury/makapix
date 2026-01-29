/**
 * Image Processor
 * Main processing pipeline for the artwork scaler
 */

import type {
  DecodedImage,
  Frame,
  InputFormat,
  ProgressCallback,
  ScalerOptions,
  ScalerResult,
} from './types';
import { ScalerError, mimeToFormat } from './types';
import { decode, detectFormat } from './decoders';
import { scaleFrames, calculateOutputDimensions, calculateDimensionsByRatio } from './scaler';
import { encodeWebP, framesHaveAlpha } from './encoder';

export interface ProcessOptions extends ScalerOptions {
  /** Scale by percentage instead of absolute dimensions */
  scalePercent?: number;
  /** Force output format (default: webp if scaling, original if not) */
  forceWebP?: boolean;
}

/**
 * Process an image file through the scaling pipeline
 *
 * @param input - File or Blob to process
 * @param options - Processing options
 * @param onProgress - Progress callback
 * @returns Processed result
 */
export async function processImage(
  input: File | Blob,
  options: ProcessOptions,
  onProgress?: ProgressCallback
): Promise<ScalerResult> {
  // Determine input format
  const format = mimeToFormat(input.type);
  if (!format && input.type !== '') {
    throw new ScalerError('UNSUPPORTED_FORMAT', `Unsupported file type: ${input.type}`);
  }

  // Read file to buffer
  const buffer = await input.arrayBuffer();

  // Detect format from magic bytes if not determined from MIME
  const detectedFormat = format || detectFormat(buffer);
  if (!detectedFormat) {
    throw new ScalerError('UNSUPPORTED_FORMAT', 'Could not detect image format');
  }

  // Decode the image
  const decoded = await decode(buffer, detectedFormat, onProgress);

  // Calculate output dimensions
  let outputWidth: number;
  let outputHeight: number;

  if (options.scalePercent !== undefined && options.scalePercent !== 100) {
    // Scale by percentage
    const dims = calculateDimensionsByRatio(
      decoded.frames[0].width,
      decoded.frames[0].height,
      options.scalePercent
    );
    outputWidth = dims.width;
    outputHeight = dims.height;
  } else if (options.width && options.height) {
    // Scale to specific dimensions
    const dims = calculateOutputDimensions(
      decoded.frames[0].width,
      decoded.frames[0].height,
      options.width,
      options.height,
      options.maintainAspectRatio ?? true,
      options.aspectRatioMode ?? 'fit'
    );
    outputWidth = dims.width;
    outputHeight = dims.height;
  } else {
    // No scaling - keep original dimensions
    outputWidth = decoded.frames[0].width;
    outputHeight = decoded.frames[0].height;
  }

  // Check if scaling is needed
  const needsScaling =
    outputWidth !== decoded.frames[0].width ||
    outputHeight !== decoded.frames[0].height;

  // Determine if we should convert to WebP
  const shouldConvertToWebP = options.forceWebP || needsScaling;

  // Scale frames if needed
  let processedFrames: Frame[];
  if (needsScaling) {
    processedFrames = await scaleFrames(
      decoded.frames,
      outputWidth,
      outputHeight,
      options.resamplingAlgorithm ?? 'nearest-neighbor',
      onProgress
    );
  } else {
    processedFrames = decoded.frames;
  }

  // Encode to WebP or return original format
  let outputBlob: Blob;
  let outputFormat: 'webp' | InputFormat;

  if (shouldConvertToWebP) {
    // Encode to lossless WebP
    const webpData = await encodeWebP(processedFrames, decoded.loopCount, onProgress);
    // Create Blob with a copy of the data to ensure proper ArrayBuffer type
    outputBlob = new Blob([new Uint8Array(webpData)], { type: 'image/webp' });
    outputFormat = 'webp';
  } else {
    // Return original file (no processing needed)
    outputBlob = input;
    outputFormat = detectedFormat;
  }

  // Check if output has alpha
  const hasAlpha = framesHaveAlpha(processedFrames);

  return {
    blob: outputBlob,
    width: outputWidth,
    height: outputHeight,
    frameCount: processedFrames.length,
    isAnimated: processedFrames.length > 1,
    hasAlpha,
    fileSizeBytes: outputBlob.size,
    format: outputFormat,
  };
}

/**
 * Quick preview scaling (for UI preview without full encoding)
 */
export async function previewScale(
  input: File | Blob,
  options: ProcessOptions,
  onProgress?: ProgressCallback
): Promise<{
  previewUrl: string;
  width: number;
  height: number;
  frameCount: number;
  isAnimated: boolean;
}> {
  const format = mimeToFormat(input.type);
  const buffer = await input.arrayBuffer();
  const detectedFormat = format || detectFormat(buffer);

  if (!detectedFormat) {
    throw new ScalerError('UNSUPPORTED_FORMAT', 'Could not detect image format');
  }

  // Decode
  const decoded = await decode(buffer, detectedFormat, onProgress);

  // Calculate dimensions
  let outputWidth: number;
  let outputHeight: number;

  if (options.scalePercent !== undefined && options.scalePercent !== 100) {
    const dims = calculateDimensionsByRatio(
      decoded.frames[0].width,
      decoded.frames[0].height,
      options.scalePercent
    );
    outputWidth = dims.width;
    outputHeight = dims.height;
  } else if (options.width && options.height) {
    const dims = calculateOutputDimensions(
      decoded.frames[0].width,
      decoded.frames[0].height,
      options.width,
      options.height,
      options.maintainAspectRatio ?? true,
      options.aspectRatioMode ?? 'fit'
    );
    outputWidth = dims.width;
    outputHeight = dims.height;
  } else {
    outputWidth = decoded.frames[0].width;
    outputHeight = decoded.frames[0].height;
  }

  // Scale first frame only for preview
  const scaledFrame = (await scaleFrames(
    [decoded.frames[0]],
    outputWidth,
    outputHeight,
    options.resamplingAlgorithm ?? 'nearest-neighbor'
  ))[0];

  // Create preview canvas
  const canvas = new OffscreenCanvas(scaledFrame.width, scaledFrame.height);
  const ctx = canvas.getContext('2d')!;
  // Create ImageData with a fresh Uint8ClampedArray backed by new ArrayBuffer
  const rgbaBuffer = new ArrayBuffer(scaledFrame.rgba.byteLength);
  const rgba = new Uint8ClampedArray(rgbaBuffer);
  rgba.set(scaledFrame.rgba);
  const imageData = new ImageData(rgba, scaledFrame.width, scaledFrame.height);
  ctx.putImageData(imageData, 0, 0);

  // Convert to blob URL
  const previewBlob = await canvas.convertToBlob({ type: 'image/png' });
  const previewUrl = URL.createObjectURL(previewBlob);

  return {
    previewUrl,
    width: outputWidth,
    height: outputHeight,
    frameCount: decoded.frames.length,
    isAnimated: decoded.isAnimated,
  };
}

/**
 * Get image info without processing
 */
export async function getImageInfo(
  input: File | Blob
): Promise<{
  width: number;
  height: number;
  frameCount: number;
  isAnimated: boolean;
  format: InputFormat;
  totalDuration: number;
  averageFps: number;
}> {
  const format = mimeToFormat(input.type);
  const buffer = await input.arrayBuffer();
  const detectedFormat = format || detectFormat(buffer);

  if (!detectedFormat) {
    throw new ScalerError('UNSUPPORTED_FORMAT', 'Could not detect image format');
  }

  const decoded = await decode(buffer, detectedFormat);

  const totalDuration = decoded.frames.reduce((sum, f) => sum + f.duration, 0);
  const averageFps = decoded.isAnimated && totalDuration > 0
    ? Math.round((decoded.frames.length * 1000) / totalDuration)
    : 0;

  return {
    width: decoded.frames[0].width,
    height: decoded.frames[0].height,
    frameCount: decoded.frames.length,
    isAnimated: decoded.isAnimated,
    format: detectedFormat,
    totalDuration,
    averageFps,
  };
}

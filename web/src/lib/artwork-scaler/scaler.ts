/**
 * Image Scaler
 * Handles nearest-neighbor and Lanczos3 scaling of RGBA frames
 */

import type { Frame, ResamplingAlgorithm, ProgressCallback } from './types';

/**
 * Scale a single frame using nearest-neighbor algorithm
 * Uses browser canvas with imageSmoothingEnabled = false
 */
async function scaleFrameNearestNeighbor(
  frame: Frame,
  destWidth: number,
  destHeight: number
): Promise<Frame> {
  // Create source canvas
  const srcCanvas = new OffscreenCanvas(frame.width, frame.height);
  const srcCtx = srcCanvas.getContext('2d')!;
  // Create ImageData with a fresh Uint8ClampedArray backed by new ArrayBuffer
  const srcBuffer = new ArrayBuffer(frame.rgba.byteLength);
  const srcRgba = new Uint8ClampedArray(srcBuffer);
  srcRgba.set(frame.rgba);
  const srcImageData = new ImageData(srcRgba, frame.width, frame.height);
  srcCtx.putImageData(srcImageData, 0, 0);

  // Create destination canvas
  const destCanvas = new OffscreenCanvas(destWidth, destHeight);
  const destCtx = destCanvas.getContext('2d')!;

  // CRITICAL: Disable smoothing for nearest-neighbor
  destCtx.imageSmoothingEnabled = false;

  // Scale via drawImage
  destCtx.drawImage(srcCanvas, 0, 0, destWidth, destHeight);

  // Extract scaled RGBA data
  const destImageData = destCtx.getImageData(0, 0, destWidth, destHeight);

  return {
    rgba: new Uint8ClampedArray(destImageData.data),
    width: destWidth,
    height: destHeight,
    duration: frame.duration,
  };
}

/**
 * Scale a single frame using Lanczos3 algorithm via pica
 */
async function scaleFrameLanczos(
  frame: Frame,
  destWidth: number,
  destHeight: number
): Promise<Frame> {
  const Pica = (await import('pica')).default;
  const pica = new Pica();

  // Create source canvas
  const srcCanvas = new OffscreenCanvas(frame.width, frame.height);
  const srcCtx = srcCanvas.getContext('2d')!;
  // Create ImageData with a fresh Uint8ClampedArray backed by new ArrayBuffer
  const srcBuffer = new ArrayBuffer(frame.rgba.byteLength);
  const srcRgba = new Uint8ClampedArray(srcBuffer);
  srcRgba.set(frame.rgba);
  const srcImageData = new ImageData(srcRgba, frame.width, frame.height);
  srcCtx.putImageData(srcImageData, 0, 0);

  // Create destination canvas
  const destCanvas = new OffscreenCanvas(destWidth, destHeight);

  // Resize with pica (Lanczos3)
  await pica.resize(srcCanvas as any, destCanvas as any, {
    quality: 3, // Max quality (Lanczos3)
    alpha: true, // CRITICAL: Preserve alpha channel
    unsharpAmount: 0, // Disable sharpening for lossless fidelity
    unsharpRadius: 0,
    unsharpThreshold: 0,
  });

  // Extract scaled RGBA data
  const destCtx = destCanvas.getContext('2d')!;
  const destImageData = destCtx.getImageData(0, 0, destWidth, destHeight);

  return {
    rgba: new Uint8ClampedArray(destImageData.data),
    width: destWidth,
    height: destHeight,
    duration: frame.duration,
  };
}

/**
 * Scale a single frame using the specified algorithm
 */
export async function scaleFrame(
  frame: Frame,
  destWidth: number,
  destHeight: number,
  algorithm: ResamplingAlgorithm = 'nearest-neighbor'
): Promise<Frame> {
  // No scaling needed if dimensions match
  if (frame.width === destWidth && frame.height === destHeight) {
    return {
      ...frame,
      rgba: new Uint8ClampedArray(frame.rgba),
    };
  }

  switch (algorithm) {
    case 'nearest-neighbor':
      return scaleFrameNearestNeighbor(frame, destWidth, destHeight);
    case 'lanczos3':
      return scaleFrameLanczos(frame, destWidth, destHeight);
    default:
      throw new Error(`Unknown resampling algorithm: ${algorithm}`);
  }
}

/**
 * Scale all frames in an animation
 */
export async function scaleFrames(
  frames: Frame[],
  destWidth: number,
  destHeight: number,
  algorithm: ResamplingAlgorithm = 'nearest-neighbor',
  onProgress?: ProgressCallback
): Promise<Frame[]> {
  const scaledFrames: Frame[] = [];

  for (let i = 0; i < frames.length; i++) {
    if (onProgress) {
      onProgress({
        stage: 'scaling',
        current: i + 1,
        total: frames.length,
        percent: Math.round(((i + 1) / frames.length) * 100),
      });
    }

    const scaled = await scaleFrame(frames[i], destWidth, destHeight, algorithm);
    scaledFrames.push(scaled);
  }

  return scaledFrames;
}

/**
 * Calculate output dimensions based on input and options
 */
export function calculateOutputDimensions(
  inputWidth: number,
  inputHeight: number,
  targetWidth: number,
  targetHeight: number,
  maintainAspectRatio: boolean = true,
  aspectRatioMode: 'fit' | 'fill' | 'stretch' = 'fit'
): { width: number; height: number } {
  if (!maintainAspectRatio || aspectRatioMode === 'stretch') {
    return { width: targetWidth, height: targetHeight };
  }

  const inputRatio = inputWidth / inputHeight;
  const targetRatio = targetWidth / targetHeight;

  if (aspectRatioMode === 'fit') {
    // Fit inside target bounds (letterbox)
    if (inputRatio > targetRatio) {
      // Input is wider - constrain by width
      return {
        width: targetWidth,
        height: Math.round(targetWidth / inputRatio),
      };
    } else {
      // Input is taller - constrain by height
      return {
        width: Math.round(targetHeight * inputRatio),
        height: targetHeight,
      };
    }
  } else {
    // Fill target bounds (crop)
    if (inputRatio > targetRatio) {
      return {
        width: Math.round(targetHeight * inputRatio),
        height: targetHeight,
      };
    } else {
      return {
        width: targetWidth,
        height: Math.round(targetWidth / inputRatio),
      };
    }
  }
}

/**
 * Calculate dimensions when scaling by percentage
 */
export function calculateDimensionsByRatio(
  inputWidth: number,
  inputHeight: number,
  scalePercent: number
): { width: number; height: number } {
  const ratio = scalePercent / 100;
  return {
    width: Math.round(inputWidth * ratio),
    height: Math.round(inputHeight * ratio),
  };
}

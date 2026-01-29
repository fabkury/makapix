/**
 * Artwork Scaler Web Worker
 *
 * Runs image processing off the main thread to keep UI responsive.
 * Communicates via postMessage with structured commands and responses.
 */

import type { ProcessOptions } from './processor';
import type { ProgressInfo, ScalerResult, ScalerErrorCode } from './types';

// Worker message types
export interface WorkerCommand {
  id: string;
  type: 'process' | 'preview' | 'getInfo' | 'cancel';
  file?: File;
  options?: ProcessOptions;
}

export interface WorkerResponse {
  id: string;
  type: 'progress' | 'result' | 'error' | 'preview' | 'info';
  progress?: ProgressInfo;
  result?: ScalerResult;
  preview?: {
    previewUrl: string;
    width: number;
    height: number;
    frameCount: number;
    isAnimated: boolean;
  };
  info?: {
    width: number;
    height: number;
    frameCount: number;
    isAnimated: boolean;
    format: string;
    totalDuration: number;
    averageFps: number;
  };
  error?: {
    code: ScalerErrorCode;
    message: string;
    details?: string;
  };
}

// Track active operations for cancellation
const activeOperations = new Map<string, { cancelled: boolean }>();

/**
 * Handle incoming messages from main thread
 */
self.onmessage = async (event: MessageEvent<WorkerCommand>) => {
  const { id, type, file, options } = event.data;

  if (type === 'cancel') {
    const op = activeOperations.get(id);
    if (op) {
      op.cancelled = true;
    }
    return;
  }

  // Create operation tracker
  const operation = { cancelled: false };
  activeOperations.set(id, operation);

  try {
    // Dynamic import to avoid loading processing code until needed
    const { processImage, previewScale, getImageInfo } = await import('./processor');
    const { ScalerError } = await import('./types');

    const progressCallback = (progress: ProgressInfo) => {
      if (operation.cancelled) return;
      self.postMessage({
        id,
        type: 'progress',
        progress,
      } as WorkerResponse);
    };

    if (type === 'process' && file && options) {
      const result = await processImage(file, options, progressCallback);

      if (operation.cancelled) return;

      self.postMessage({
        id,
        type: 'result',
        result,
      } as WorkerResponse);
    } else if (type === 'preview' && file && options) {
      const preview = await previewScale(file, options, progressCallback);

      if (operation.cancelled) return;

      self.postMessage({
        id,
        type: 'preview',
        preview,
      } as WorkerResponse);
    } else if (type === 'getInfo' && file) {
      const info = await getImageInfo(file);

      if (operation.cancelled) return;

      self.postMessage({
        id,
        type: 'info',
        info,
      } as WorkerResponse);
    }
  } catch (err) {
    if (operation.cancelled) return;

    const { ScalerError } = await import('./types');

    if (err instanceof ScalerError) {
      self.postMessage({
        id,
        type: 'error',
        error: {
          code: err.code,
          message: err.message,
          details: err.details,
        },
      } as WorkerResponse);
    } else {
      self.postMessage({
        id,
        type: 'error',
        error: {
          code: 'ENCODE_FAILED',
          message: err instanceof Error ? err.message : 'Unknown error',
        },
      } as WorkerResponse);
    }
  } finally {
    activeOperations.delete(id);
  }
};

// Export for TypeScript module detection
export {};

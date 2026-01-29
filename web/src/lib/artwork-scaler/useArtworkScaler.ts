/**
 * useArtworkScaler Hook
 *
 * React hook for processing images with the artwork scaler.
 * Uses Web Worker when available for better performance, with main-thread fallback.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import type { ProcessOptions } from './processor';
import type { ProgressInfo, ScalerResult, ScalerErrorCode } from './types';
import type { WorkerCommand, WorkerResponse } from './worker';

export interface UseArtworkScalerOptions {
  /** Whether to use Web Worker (default: true) */
  useWorker?: boolean;
}

export interface ImageInfo {
  width: number;
  height: number;
  frameCount: number;
  isAnimated: boolean;
  format: string;
  totalDuration: number;
  averageFps: number;
}

export interface ScalerState {
  /** Whether processing is in progress */
  isProcessing: boolean;
  /** Current progress info */
  progress: ProgressInfo | null;
  /** Processing result */
  result: ScalerResult | null;
  /** Error if processing failed */
  error: { code: ScalerErrorCode; message: string; details?: string } | null;
  /** Preview data */
  preview: {
    previewUrl: string;
    width: number;
    height: number;
    frameCount: number;
    isAnimated: boolean;
  } | null;
  /** Image info */
  imageInfo: ImageInfo | null;
}

export interface ScalerActions {
  /** Process an image file */
  process: (file: File, options: ProcessOptions) => Promise<ScalerResult | null>;
  /** Generate a preview */
  generatePreview: (file: File, options: ProcessOptions) => Promise<void>;
  /** Get image info without processing */
  getInfo: (file: File) => Promise<ImageInfo | null>;
  /** Cancel current operation */
  cancel: () => void;
  /** Reset state */
  reset: () => void;
}

const initialState: ScalerState = {
  isProcessing: false,
  progress: null,
  result: null,
  error: null,
  preview: null,
  imageInfo: null,
};

/**
 * Hook for artwork scaling operations
 */
export function useArtworkScaler(
  options: UseArtworkScalerOptions = {}
): [ScalerState, ScalerActions] {
  const { useWorker = true } = options;

  const [state, setState] = useState<ScalerState>(initialState);
  const workerRef = useRef<Worker | null>(null);
  const operationIdRef = useRef<string | null>(null);

  // Initialize worker on mount
  useEffect(() => {
    if (!useWorker || typeof window === 'undefined') return;

    try {
      // Create worker using dynamic import
      const worker = new Worker(
        new URL('./worker.ts', import.meta.url),
        { type: 'module' }
      );

      worker.onmessage = (event: MessageEvent<WorkerResponse>) => {
        const { id, type, progress, result, preview, info, error } = event.data;

        // Ignore responses for old operations
        if (id !== operationIdRef.current) return;

        switch (type) {
          case 'progress':
            if (progress) {
              setState((prev) => ({ ...prev, progress }));
            }
            break;
          case 'result':
            if (result) {
              setState((prev) => ({
                ...prev,
                isProcessing: false,
                result,
                progress: null,
              }));
            }
            break;
          case 'preview':
            if (preview) {
              setState((prev) => ({
                ...prev,
                isProcessing: false,
                preview,
                progress: null,
              }));
            }
            break;
          case 'info':
            if (info) {
              setState((prev) => ({
                ...prev,
                isProcessing: false,
                imageInfo: info,
                progress: null,
              }));
            }
            break;
          case 'error':
            if (error) {
              setState((prev) => ({
                ...prev,
                isProcessing: false,
                error,
                progress: null,
              }));
            }
            break;
        }
      };

      worker.onerror = (err) => {
        console.error('Worker error:', err);
        setState((prev) => ({
          ...prev,
          isProcessing: false,
          error: {
            code: 'WASM_INIT_FAILED',
            message: 'Worker failed to initialize',
            details: err.message,
          },
        }));
      };

      workerRef.current = worker;

      return () => {
        worker.terminate();
        workerRef.current = null;
      };
    } catch (err) {
      console.warn('Failed to create worker, will use main thread:', err);
    }
  }, [useWorker]);

  // Generate unique operation ID
  const generateId = useCallback(() => {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }, []);

  // Process image
  const process = useCallback(
    async (file: File, processOptions: ProcessOptions): Promise<ScalerResult | null> => {
      const id = generateId();
      operationIdRef.current = id;

      setState((prev) => ({
        ...prev,
        isProcessing: true,
        error: null,
        result: null,
        progress: { stage: 'decoding', current: 0, total: 1, percent: 0 },
      }));

      // Try worker first
      if (workerRef.current) {
        return new Promise((resolve) => {
          const handleResult = (event: MessageEvent<WorkerResponse>) => {
            if (event.data.id !== id) return;

            if (event.data.type === 'result') {
              workerRef.current?.removeEventListener('message', handleResult);
              resolve(event.data.result || null);
            } else if (event.data.type === 'error') {
              workerRef.current?.removeEventListener('message', handleResult);
              resolve(null);
            }
          };

          workerRef.current!.addEventListener('message', handleResult);
          workerRef.current!.postMessage({
            id,
            type: 'process',
            file,
            options: processOptions,
          } as WorkerCommand);
        });
      }

      // Fallback to main thread
      try {
        const { processImage } = await import('./processor');
        const result = await processImage(file, processOptions, (progress) => {
          if (operationIdRef.current === id) {
            setState((prev) => ({ ...prev, progress }));
          }
        });

        if (operationIdRef.current === id) {
          setState((prev) => ({
            ...prev,
            isProcessing: false,
            result,
            progress: null,
          }));
        }

        return result;
      } catch (err) {
        const { ScalerError } = await import('./types');

        if (operationIdRef.current === id) {
          if (err instanceof ScalerError) {
            setState((prev) => ({
              ...prev,
              isProcessing: false,
              error: { code: err.code, message: err.message, details: err.details },
              progress: null,
            }));
          } else {
            setState((prev) => ({
              ...prev,
              isProcessing: false,
              error: {
                code: 'ENCODE_FAILED',
                message: err instanceof Error ? err.message : 'Unknown error',
              },
              progress: null,
            }));
          }
        }

        return null;
      }
    },
    [generateId]
  );

  // Generate preview
  const generatePreview = useCallback(
    async (file: File, processOptions: ProcessOptions): Promise<void> => {
      const id = generateId();
      operationIdRef.current = id;

      setState((prev) => ({
        ...prev,
        isProcessing: true,
        error: null,
        preview: null,
      }));

      if (workerRef.current) {
        workerRef.current.postMessage({
          id,
          type: 'preview',
          file,
          options: processOptions,
        } as WorkerCommand);
        return;
      }

      // Fallback to main thread
      try {
        const { previewScale } = await import('./processor');
        const preview = await previewScale(file, processOptions);

        if (operationIdRef.current === id) {
          setState((prev) => ({
            ...prev,
            isProcessing: false,
            preview,
          }));
        }
      } catch (err) {
        const { ScalerError } = await import('./types');

        if (operationIdRef.current === id) {
          if (err instanceof ScalerError) {
            setState((prev) => ({
              ...prev,
              isProcessing: false,
              error: { code: err.code, message: err.message, details: err.details },
            }));
          } else {
            setState((prev) => ({
              ...prev,
              isProcessing: false,
              error: {
                code: 'ENCODE_FAILED',
                message: err instanceof Error ? err.message : 'Unknown error',
              },
            }));
          }
        }
      }
    },
    [generateId]
  );

  // Get image info
  const getInfo = useCallback(
    async (file: File): Promise<ImageInfo | null> => {
      const id = generateId();
      operationIdRef.current = id;

      setState((prev) => ({
        ...prev,
        isProcessing: true,
        error: null,
        imageInfo: null,
      }));

      if (workerRef.current) {
        return new Promise((resolve) => {
          const handleResult = (event: MessageEvent<WorkerResponse>) => {
            if (event.data.id !== id) return;

            if (event.data.type === 'info') {
              workerRef.current?.removeEventListener('message', handleResult);
              resolve(event.data.info || null);
            } else if (event.data.type === 'error') {
              workerRef.current?.removeEventListener('message', handleResult);
              resolve(null);
            }
          };

          workerRef.current!.addEventListener('message', handleResult);
          workerRef.current!.postMessage({
            id,
            type: 'getInfo',
            file,
          } as WorkerCommand);
        });
      }

      // Fallback to main thread
      try {
        const { getImageInfo } = await import('./processor');
        const info = await getImageInfo(file);

        if (operationIdRef.current === id) {
          setState((prev) => ({
            ...prev,
            isProcessing: false,
            imageInfo: info,
          }));
        }

        return info;
      } catch (err) {
        const { ScalerError } = await import('./types');

        if (operationIdRef.current === id) {
          if (err instanceof ScalerError) {
            setState((prev) => ({
              ...prev,
              isProcessing: false,
              error: { code: err.code, message: err.message, details: err.details },
            }));
          } else {
            setState((prev) => ({
              ...prev,
              isProcessing: false,
              error: {
                code: 'ENCODE_FAILED',
                message: err instanceof Error ? err.message : 'Unknown error',
              },
            }));
          }
        }

        return null;
      }
    },
    [generateId]
  );

  // Cancel current operation
  const cancel = useCallback(() => {
    if (operationIdRef.current && workerRef.current) {
      workerRef.current.postMessage({
        id: operationIdRef.current,
        type: 'cancel',
      } as WorkerCommand);
    }
    operationIdRef.current = null;
    setState((prev) => ({ ...prev, isProcessing: false, progress: null }));
  }, []);

  // Reset state
  const reset = useCallback(() => {
    operationIdRef.current = null;
    // Revoke any preview URLs
    if (state.preview?.previewUrl) {
      URL.revokeObjectURL(state.preview.previewUrl);
    }
    setState(initialState);
  }, [state.preview?.previewUrl]);

  return [state, { process, generatePreview, getInfo, cancel, reset }];
}

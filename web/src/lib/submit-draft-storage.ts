/**
 * Submit Draft Storage System
 *
 * Persists submit artwork page state to sessionStorage so users don't lose
 * their work when navigating away. Uses sessionStorage for tab-specific drafts.
 */

export interface ImageInfo {
  width: number;
  height: number;
  frameCount: number;
  isAnimated: boolean;
  format: string;
  totalDuration: number;
  averageFps: number;
}

export interface SubmitDraftData {
  version: 1;
  savedAt: number;
  // Image data (File objects can't be serialized, so use data URL)
  imageDataUrl: string | null;
  imageName: string | null;
  imageMimeType: string | null;
  imageInfo: ImageInfo | null;
  // Form fields
  title: string;
  description: string;
  hashtags: string;
  postAsHidden: boolean;
  allowEdit: boolean;
  // Scaling options
  showScalingOptions: boolean;
  scalePercent: number;
  scaleAlgorithm: 'nearest-neighbor' | 'lanczos3';
  scalingMode: 'ratio' | 'dimensions';
  customWidth: string;
  customHeight: string;
  maintainAspectRatio: boolean;
}

const STORAGE_KEY = 'makapix_submit_draft';
const DRAFT_EXPIRY_MS = 24 * 60 * 60 * 1000; // 24 hours

/**
 * Check if draft is expired
 */
function isDraftExpired(draft: SubmitDraftData): boolean {
  const age = Date.now() - draft.savedAt;
  return age > DRAFT_EXPIRY_MS;
}

/**
 * Save draft to sessionStorage
 * Handles QuotaExceededError by saving form fields without image data
 */
export function saveDraft(draft: SubmitDraftData): boolean {
  if (typeof window === 'undefined') return false;

  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
    return true;
  } catch (err) {
    if (err instanceof DOMException && err.name === 'QuotaExceededError') {
      // Try saving without image data
      console.warn('Storage quota exceeded, saving draft without image data');
      try {
        const reducedDraft: SubmitDraftData = {
          ...draft,
          imageDataUrl: null,
        };
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(reducedDraft));
        return true;
      } catch (innerErr) {
        console.error('Failed to save reduced draft:', innerErr);
        return false;
      }
    }
    console.error('Failed to save draft:', err);
    return false;
  }
}

/**
 * Load draft from sessionStorage
 * Returns null if no draft, expired, or corrupted
 */
export function loadDraft(): SubmitDraftData | null {
  if (typeof window === 'undefined') return null;

  try {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (!stored) return null;

    const draft: SubmitDraftData = JSON.parse(stored);

    // Version check
    if (draft.version !== 1) {
      console.warn('Draft version mismatch, clearing');
      clearDraft();
      return null;
    }

    // Expiry check
    if (isDraftExpired(draft)) {
      console.log('Draft expired, clearing');
      clearDraft();
      return null;
    }

    return draft;
  } catch (err) {
    console.error('Failed to load draft:', err);
    clearDraft();
    return null;
  }
}

/**
 * Clear draft from sessionStorage
 */
export function clearDraft(): void {
  if (typeof window === 'undefined') return;

  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch (err) {
    console.warn('Failed to clear draft:', err);
  }
}

/**
 * Convert File to base64 data URL
 */
export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        resolve(reader.result);
      } else {
        reject(new Error('FileReader result is not a string'));
      }
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

/**
 * Convert data URL back to File
 */
export function dataUrlToFile(
  dataUrl: string,
  fileName: string,
  mimeType: string
): File {
  const byteString = atob(dataUrl.split(',')[1]);
  const arrayBuffer = new ArrayBuffer(byteString.length);
  const uint8Array = new Uint8Array(arrayBuffer);
  for (let i = 0; i < byteString.length; i++) {
    uint8Array[i] = byteString.charCodeAt(i);
  }
  const blob = new Blob([arrayBuffer], { type: mimeType });
  return new File([blob], fileName, { type: mimeType });
}

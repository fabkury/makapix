import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import Layout from '../components/Layout';
import { authenticatedFetch, clearTokens, getMe } from '../lib/api';
import PostReviewNotice from '../components/PostReviewNotice';
import {
  IconUpload,
  IconAlertTriangle,
  IconAlertCircle,
  IconCheckCircle,
  IconX,
} from '../components/kit/icons';
import Button from '../components/kit/Button';
import Field from '../components/kit/Field';
import Notice from '../components/kit/Notice';
import Dialog from '../components/kit/Dialog';
import Disclosure from '../components/kit/Disclosure';
import { ensureCompatibleArtUrl } from '../utils/imageCompat';
import {
  saveDraft,
  loadDraft,
  clearDraft,
  fileToDataUrl,
  dataUrlToFile,
  SubmitDraftData,
} from '../lib/submit-draft-storage';

interface ImageInfo {
  width: number;
  height: number;
  frameCount: number;
  isAnimated: boolean;
  format: string;
  totalDuration: number;
  averageFps: number;
}

interface UploadedArtwork {
  id: number;
  public_sqid: string;
  title: string;
  art_url: string;
  width: number;
  height: number;
  public_visibility: boolean;
  created_at: string;
}

interface ValidationError {
  type: 'size' | 'dimensions' | 'format';
  message: string;
}

interface License {
  id: number;
  identifier: string;
  title: string;
  canonical_url: string;
  badge_path: string;
}

type ResamplingAlgorithm = 'nearest-neighbor' | 'lanczos3';

interface CachedScaledPreview {
  blob: Blob;
  url: string;
  width: number;
  height: number;
  algorithm: ResamplingAlgorithm;
  sourceFile: File;
  isAnimated: boolean;
  frameCount: number;
}

const MAX_UPLOAD_SIZE_BYTES = (() => {
  const raw = process.env.NEXT_PUBLIC_MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES || '5242880';
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : 5242880;
})();

const MAX_LOAD_SIZE_BYTES = 256 * 1024 * 1024;

function formatMiB(bytes: number): string {
  const mib = bytes / (1024 * 1024);
  if (Math.abs(mib - Math.round(mib)) < 1e-9) return `${Math.round(mib)} MiB`;
  return `${mib.toFixed(2)} MiB`;
}

const ALLOWED_TYPES = ['image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/x-ms-bmp'];

// Allowed sizes for dimensions under 128x128
const ALLOWED_SMALL_SIZES: [number, number][] = [
  [8, 8], [8, 16], [16, 8], [8, 32], [32, 8],
  [16, 16], [16, 32], [32, 16],
  [32, 32], [32, 64], [64, 32],
  [64, 64], [64, 128], [128, 64],
];

/**
 * Check if dimensions are valid according to Makapix size rules
 */
function isValidSize(width: number, height: number): boolean {
  if (width < 1 || height < 1) return false;
  if (width > 256 || height > 256) return false;
  if (width >= 128 && height >= 128) return true;
  return ALLOWED_SMALL_SIZES.some(([w, h]) => width === w && height === h);
}

/**
 * Find the nearest valid size for a given input size
 * Prefers sizes that maintain aspect ratio as closely as possible
 */
function findNearestValidSize(width: number, height: number): { width: number; height: number } {
  // If already valid, return as-is
  if (isValidSize(width, height)) {
    return { width, height };
  }

  // If over 256, clamp to 256
  if (width > 256 || height > 256) {
    const scale = Math.min(256 / width, 256 / height);
    const newWidth = Math.round(width * scale);
    const newHeight = Math.round(height * scale);
    // Clamp to 128-256 range
    return {
      width: Math.max(128, Math.min(256, newWidth)),
      height: Math.max(128, Math.min(256, newHeight)),
    };
  }

  // If both dimensions >= 128, they're already valid (handled above)
  // Otherwise, find nearest allowed small size

  const aspectRatio = width / height;
  let bestMatch = ALLOWED_SMALL_SIZES[0];
  let bestScore = Infinity;

  for (const [w, h] of ALLOWED_SMALL_SIZES) {
    const sizeAspectRatio = w / h;
    // Score based on aspect ratio similarity and size proximity
    const aspectDiff = Math.abs(aspectRatio - sizeAspectRatio);
    const sizeDiff = Math.abs(width - w) + Math.abs(height - h);
    // Prefer sizes that are larger than the input (to avoid downscaling and losing detail)
    const sizePenalty = (w < width || h < height) ? 100 : 0;
    const score = aspectDiff * 50 + sizeDiff + sizePenalty;

    if (score < bestScore) {
      bestScore = score;
      bestMatch = [w, h];
    }
  }

  return { width: bestMatch[0], height: bestMatch[1] };
}

function validateDimensions(width: number, height: number): ValidationError[] {
  const errors: ValidationError[] = [];

  if (width < 1 || height < 1) {
    errors.push({ type: 'dimensions', message: 'Image dimensions must be at least 1x1' });
    return errors;
  }

  if (width > 256 || height > 256) {
    errors.push({
      type: 'dimensions',
      message: `Image dimensions exceed maximum of 256x256. Got ${width}x${height}`,
    });
    return errors;
  }

  if (width >= 128 && height >= 128) {
    return errors;
  }

  const isAllowed = ALLOWED_SMALL_SIZES.some(([w, h]) => width === w && height === h);

  if (!isAllowed) {
    const sizeSet = new Set<string>();
    ALLOWED_SMALL_SIZES.forEach(([w, h]) => sizeSet.add(`${w}x${h}`));
    const allowedStr = Array.from(sizeSet).sort().join(', ');
    errors.push({
      type: 'dimensions',
      message: `Image size ${width}x${height} is not allowed. Under 128x128, only these sizes are allowed: ${allowedStr}`,
    });
  }

  return errors;
}

// Inner component that uses the artwork scaler hook
function SubmitPageContent() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Dynamically import hook only on client side
  const [scalerModule, setScalerModule] = useState<any>(null);

  useEffect(() => {
    import('../lib/artwork-scaler').then((module) => {
      setScalerModule(module);
    }).catch((err) => {
      console.error('Failed to load artwork scaler:', err);
    });
  }, []);

  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageInfo, setImageInfo] = useState<ImageInfo | null>(null);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [isDragging, setIsDragging] = useState(false);

  // Form inputs
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [hashtags, setHashtags] = useState('');
  const [postAsHidden, setPostAsHidden] = useState(false);
  // Remixable (docs/artwork-provenance/ L4): default allow; ND licenses force
  // it off (L5, mirrored server-side).
  const [remixable, setRemixable] = useState(true);

  // Scaling options
  const [showScalingOptions, setShowScalingOptions] = useState(false);
  const [scalePercent, setScalePercent] = useState(100);
  const [scaleAlgorithm, setScaleAlgorithm] = useState<ResamplingAlgorithm>('nearest-neighbor');
  const [scalingMode, setScalingMode] = useState<'ratio' | 'dimensions'>('ratio');
  const [customWidth, setCustomWidth] = useState<string>('');
  const [customHeight, setCustomHeight] = useState<string>('');
  const [maintainAspectRatio, setMaintainAspectRatio] = useState(true);
  const [previewScaling, setPreviewScaling] = useState(false);
  const [scaledPreview, setScaledPreview] = useState<CachedScaledPreview | null>(null);

  // Upload state
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadedArtwork, setUploadedArtwork] = useState<UploadedArtwork | null>(null);
  const [showClearDialog, setShowClearDialog] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);

  // License state
  const [licenses, setLicenses] = useState<License[]>([]);
  const [selectedLicenseId, setSelectedLicenseId] = useState<number | null>(null);
  const [showLicenseOptions, setShowLicenseOptions] = useState(false);

  // ND licenses legally forbid derivatives, so they force Remixable off
  // (docs/artwork-provenance/ L5; the server 422s contradictory combos).
  const ndLicenseSelected = licenses.some(
    (l) => l.id === selectedLicenseId && l.identifier.includes('-ND-')
  );
  useEffect(() => {
    setRemixable(!ndLicenseSelected);
  }, [ndLicenseSelected]);

  // Processing state (managed locally since we use direct function calls)
  const [processingState, setProcessingState] = useState<{
    isProcessing: boolean;
    progress: { stage: string; current: number; total: number; percent: number } | null;
    error: { code: string; message: string } | null;
  }>({
    isProcessing: false,
    progress: null,
    error: null,
  });

  const API_BASE_URL = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/auth');
    } else {
      setIsAuthenticated(true);
    }
  }, [router]);

  // Trust status (capabilities.can_post_public): null until known. Untrusted
  // users get a heads-up that their post will be reviewed before release.
  const [canPostPublic, setCanPostPublic] = useState<boolean | null>(null);
  useEffect(() => {
    if (!isAuthenticated) return;
    getMe()
      .then((me) => setCanPostPublic(!!me.capabilities?.can_post_public))
      .catch(() => setCanPostPublic(null));
  }, [isAuthenticated]);

  // Fetch available licenses on mount
  useEffect(() => {
    const fetchLicenses = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/license`);
        if (response.ok) {
          const data = await response.json();
          setLicenses(data.items || []);
          // Default to "No license / All rights reserved" (null)
        }
      } catch (err) {
        console.error('Failed to fetch licenses:', err);
      }
    };
    fetchLicenses();
  }, [API_BASE_URL]);

  // Track if we've attempted the initial draft restore
  const [draftRestoreProcessed, setDraftRestoreProcessed] = useState(false);

  // Draft persistence state
  const [imageDataUrl, setImageDataUrl] = useState<string | null>(null);
  const [initComplete, setInitComplete] = useState(false);

  // Get image info when file is selected
  const handleFileSelect = useCallback(async (file: File) => {
    // Validate file type
    if (!ALLOWED_TYPES.includes(file.type)) {
      setValidationErrors([{
        type: 'format',
        message: 'File format not supported. Please upload PNG, GIF, WebP, or BMP.',
      }]);
      return;
    }

    // Reject files that exceed the loading limit outright
    if (file.size > MAX_LOAD_SIZE_BYTES) {
      setValidationErrors([{
        type: 'size',
        message: `File size (${formatMiB(file.size)}) exceeds the loading limit of ${formatMiB(MAX_LOAD_SIZE_BYTES)}.`,
      }]);
      return;
    }

    setSelectedFile(file);
    setValidationErrors([]);
    setUploadError(null);
    setUploadedArtwork(null);
    setPreviewScaling(false);
    setScaledPreview(prev => {
      if (prev) URL.revokeObjectURL(prev.url);
      return null;
    });

    // Create preview URL
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);

    // Convert file to data URL for draft persistence (async, non-blocking)
    fileToDataUrl(file)
      .then((dataUrl) => setImageDataUrl(dataUrl))
      .catch((err) => console.warn('Failed to convert file to data URL:', err));

    // Get detailed image info using the scaler module (if available)
    if (scalerModule?.getImageInfo) {
      try {
        const info = await scalerModule.getImageInfo(file);
        if (info) {
          setImageInfo(info);

          // Set default title from filename
          if (!title) {
            const nameWithoutExt = file.name.replace(/\.[^/.]+$/, '');
            setTitle(nameWithoutExt);
          }

          // Check if input size is valid - if not, auto-enable scaling to nearest valid size
          const inputIsValid = isValidSize(info.width, info.height);
          if (!inputIsValid) {
            const nearestValid = findNearestValidSize(info.width, info.height);
            setCustomWidth(nearestValid.width.toString());
            setCustomHeight(nearestValid.height.toString());
            setScalingMode('dimensions');
            setShowScalingOptions(true);
          } else {
            // Initialize custom dimensions to original size
            setCustomWidth(info.width.toString());
            setCustomHeight(info.height.toString());
          }
        }
      } catch (err) {
        console.error('Failed to get image info:', err);
        // Fallback to basic info
        fallbackImageInfo(file, objectUrl);
      }
    } else {
      fallbackImageInfo(file, objectUrl);
    }
  }, [title, scalerModule]);

  // Restore state from a saved draft
  const restoreFromDraft = useCallback(async (draft: SubmitDraftData) => {
    // Restore form fields
    setTitle(draft.title);
    setDescription(draft.description);
    setHashtags(draft.hashtags);
    setPostAsHidden(draft.postAsHidden);
    setRemixable(draft.remixable ?? true);

    // Restore scaling options
    setShowScalingOptions(draft.showScalingOptions);
    setScalePercent(draft.scalePercent);
    setScaleAlgorithm(draft.scaleAlgorithm);
    setScalingMode(draft.scalingMode);
    setCustomWidth(draft.customWidth);
    setCustomHeight(draft.customHeight);
    setMaintainAspectRatio(draft.maintainAspectRatio);

    // Restore license selection (older drafts may not have this field)
    setSelectedLicenseId(draft.selectedLicenseId ?? null);

    // Restore image info
    if (draft.imageInfo) {
      setImageInfo(draft.imageInfo);
    }

    // Restore image data URL and convert back to File
    if (draft.imageDataUrl && draft.imageName && draft.imageMimeType) {
      setImageDataUrl(draft.imageDataUrl);
      const file = dataUrlToFile(draft.imageDataUrl, draft.imageName, draft.imageMimeType);
      setSelectedFile(file);
      const objectUrl = URL.createObjectURL(file);
      setPreviewUrl(objectUrl);
      setScaledPreview(prev => {
        if (prev) URL.revokeObjectURL(prev.url);
        return null;
      });
    }
  }, []);

  // Restore saved draft on first load
  useEffect(() => {
    if (draftRestoreProcessed) return;
    if (!router.isReady) return;

    const draft = loadDraft();
    if (draft) {
      restoreFromDraft(draft);
    }

    setDraftRestoreProcessed(true);
    setInitComplete(true);
  }, [router.isReady, draftRestoreProcessed, restoreFromDraft]);

  // Fallback for image info when scaler is not available
  const fallbackImageInfo = useCallback((file: File, objectUrl: string) => {
    const img = new Image();
    img.onload = () => {
      const info: ImageInfo = {
        width: img.naturalWidth,
        height: img.naturalHeight,
        frameCount: 1,
        isAnimated: false,
        format: file.type.split('/')[1]?.toUpperCase() || 'UNKNOWN',
        totalDuration: 0,
        averageFps: 0,
      };
      setImageInfo(info);

      if (!title) {
        const nameWithoutExt = file.name.replace(/\.[^/.]+$/, '');
        setTitle(nameWithoutExt);
      }

      // Check if input size is valid - if not, auto-enable scaling to nearest valid size
      const inputIsValid = isValidSize(info.width, info.height);
      if (!inputIsValid) {
        const nearestValid = findNearestValidSize(info.width, info.height);
        setCustomWidth(nearestValid.width.toString());
        setCustomHeight(nearestValid.height.toString());
        setScalingMode('dimensions');
        setShowScalingOptions(true);
      } else {
        setCustomWidth(info.width.toString());
        setCustomHeight(info.height.toString());
      }
    };
    img.src = objectUrl;
  }, [title]);

  // Auto-save draft when state changes (debounced)
  useEffect(() => {
    // Only save after initialization is complete and we have an image
    if (!initComplete || !selectedFile) return;

    const timeoutId = setTimeout(() => {
      const draft: SubmitDraftData = {
        version: 1,
        savedAt: Date.now(),
        imageDataUrl,
        imageName: selectedFile.name,
        imageMimeType: selectedFile.type,
        imageInfo,
        title,
        description,
        hashtags,
        postAsHidden,
        remixable,
        showScalingOptions,
        scalePercent,
        scaleAlgorithm,
        scalingMode,
        customWidth,
        customHeight,
        maintainAspectRatio,
        selectedLicenseId,
      };
      saveDraft(draft);
    }, 500); // 500ms debounce

    return () => clearTimeout(timeoutId);
  }, [
    initComplete,
    selectedFile,
    imageDataUrl,
    imageInfo,
    title,
    description,
    hashtags,
    postAsHidden,
    remixable,
    showScalingOptions,
    scalePercent,
    scaleAlgorithm,
    scalingMode,
    customWidth,
    customHeight,
    maintainAspectRatio,
    selectedLicenseId,
  ]);

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  }, [handleFileSelect]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileSelect(file);
    }
  }, [handleFileSelect]);

  // Calculate output dimensions based on scaling mode
  const getOutputDimensions = useCallback(() => {
    if (!imageInfo) return null;

    if (scalingMode === 'ratio') {
      return {
        width: Math.round(imageInfo.width * scalePercent / 100),
        height: Math.round(imageInfo.height * scalePercent / 100),
      };
    } else {
      const w = parseInt(customWidth) || imageInfo.width;
      const h = parseInt(customHeight) || imageInfo.height;
      return { width: w, height: h };
    }
  }, [imageInfo, scalingMode, scalePercent, customWidth, customHeight]);

  const outputDimensions = getOutputDimensions();
  const needsScaling = outputDimensions && imageInfo && (
    outputDimensions.width !== imageInfo.width ||
    outputDimensions.height !== imageInfo.height
  );

  const isPreviewStale = useMemo(() => {
    if (!scaledPreview || !outputDimensions || !selectedFile) return false;
    return (
      scaledPreview.sourceFile !== selectedFile ||
      scaledPreview.width !== outputDimensions.width ||
      scaledPreview.height !== outputDimensions.height ||
      scaledPreview.algorithm !== scaleAlgorithm
    );
  }, [scaledPreview, selectedFile, outputDimensions, scaleAlgorithm]);

  useEffect(() => {
    const url = scaledPreview?.url;
    if (!url) return;
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [scaledPreview?.url]);

  // Handle scale slider change
  const handleScaleSliderChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value);
    setScalePercent(value);

    if (imageInfo) {
      setCustomWidth(Math.round(imageInfo.width * value / 100).toString());
      setCustomHeight(Math.round(imageInfo.height * value / 100).toString());
    }
  }, [imageInfo]);

  // Handle scale input change
  const handleScaleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value);
    if (!isNaN(value) && value >= 3.125 && value <= 300) {
      setScalePercent(value);

      if (imageInfo) {
        setCustomWidth(Math.round(imageInfo.width * value / 100).toString());
        setCustomHeight(Math.round(imageInfo.height * value / 100).toString());
      }
    }
  }, [imageInfo]);

  // Handle width change with aspect ratio
  const handleWidthChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setCustomWidth(value);

    if (imageInfo && value && maintainAspectRatio) {
      const numValue = parseInt(value);
      if (!isNaN(numValue) && numValue > 0) {
        const aspectRatio = imageInfo.width / imageInfo.height;
        const newHeight = Math.round(numValue / aspectRatio);
        setCustomHeight(newHeight.toString());

        const newScale = (numValue / imageInfo.width) * 100;
        setScalePercent(Math.min(300, Math.max(3.125, newScale)));
      }
    }
  }, [imageInfo, maintainAspectRatio]);

  const handleHeightChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setCustomHeight(value);

    if (imageInfo && value && maintainAspectRatio) {
      const numValue = parseInt(value);
      if (!isNaN(numValue) && numValue > 0) {
        const aspectRatio = imageInfo.width / imageInfo.height;
        const newWidth = Math.round(numValue * aspectRatio);
        setCustomWidth(newWidth.toString());

        const newScale = (numValue / imageInfo.height) * 100;
        setScalePercent(Math.min(300, Math.max(3.125, newScale)));
      }
    }
  }, [imageInfo, maintainAspectRatio]);

  const clearSelection = useCallback(() => {
    setSelectedFile(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setScaledPreview(prev => {
      if (prev) URL.revokeObjectURL(prev.url);
      return null;
    });
    setImageInfo(null);
    setImageDataUrl(null);
    setValidationErrors([]);
    setTitle('');
    setDescription('');
    setHashtags('');
    setPostAsHidden(false);
    setRemixable(true);
    setScalePercent(100);
    setCustomWidth('');
    setCustomHeight('');
    setUploadError(null);
    setUploadedArtwork(null);
    setShowScalingOptions(false);
    setPreviewScaling(false);
    setShowLicenseOptions(false);
    // Reset license to default (No license / All rights reserved)
    setSelectedLicenseId(null);
    setProcessingState({ isProcessing: false, progress: null, error: null });
    clearDraft();
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [previewUrl, licenses]);

  const handleClearAll = useCallback(() => {
    clearSelection();
    setShowClearDialog(false);
  }, [clearSelection]);

  const handleGeneratePreview = async () => {
    if (!selectedFile || !outputDimensions) return;
    if (!isValidSize(outputDimensions.width, outputDimensions.height)) return;

    if (!needsScaling) {
      // No scaling: show the original at max size in the pixelated square.
      if (scaledPreview) {
        URL.revokeObjectURL(scaledPreview.url);
        setScaledPreview(null);
      }
      setPreviewScaling(true);
      return;
    }

    if (!scalerModule?.processImage) return;

    setUploadError(null);
    setProcessingState({ isProcessing: true, progress: null, error: null });

    try {
      const result = await scalerModule.processImage(
        selectedFile,
        {
          width: outputDimensions.width,
          height: outputDimensions.height,
          resamplingAlgorithm: scaleAlgorithm,
          maintainAspectRatio: false,
        },
        (progress: { stage: string; current: number; total: number; percent: number }) => {
          setProcessingState(prev => ({ ...prev, progress }));
        }
      );

      if (!result) throw new Error('Image processing failed');

      const url = URL.createObjectURL(result.blob);
      setScaledPreview(prev => {
        if (prev) URL.revokeObjectURL(prev.url);
        return {
          blob: result.blob,
          url,
          width: outputDimensions.width,
          height: outputDimensions.height,
          algorithm: scaleAlgorithm,
          sourceFile: selectedFile,
          isAnimated: result.isAnimated,
          frameCount: result.frameCount,
        };
      });
      setPreviewScaling(true);
    } catch (error) {
      console.error('Preview generation error:', error);
      setUploadError(error instanceof Error ? error.message : 'Preview generation failed');
    } finally {
      setProcessingState(prev => ({ ...prev, isProcessing: false, progress: null }));
    }
  };

  const handleSubmit = async () => {
    if (!selectedFile || !title.trim()) return;

    // Validate output dimensions before submitting
    if (!outputDimensions || !isValidSize(outputDimensions.width, outputDimensions.height)) {
      setUploadError('Output dimensions are not valid. Please adjust scaling.');
      return;
    }

    setUploading(true);
    setUploadError(null);
    setProcessingState({ isProcessing: true, progress: null, error: null });

    try {
      let fileToUpload: File | Blob = selectedFile;

      // Process image if scaling is needed
      if (needsScaling && outputDimensions && scalerModule?.processImage) {
        const cacheHit =
          scaledPreview &&
          scaledPreview.sourceFile === selectedFile &&
          scaledPreview.width === outputDimensions.width &&
          scaledPreview.height === outputDimensions.height &&
          scaledPreview.algorithm === scaleAlgorithm;

        if (cacheHit) {
          fileToUpload = scaledPreview.blob;
        } else {
          const result = await scalerModule.processImage(
            selectedFile,
            {
              width: outputDimensions.width,
              height: outputDimensions.height,
              resamplingAlgorithm: scaleAlgorithm,
              maintainAspectRatio: false,
            },
            (progress: { stage: string; current: number; total: number; percent: number }) => {
              setProcessingState(prev => ({ ...prev, progress }));
            }
          );

          if (!result) {
            throw new Error('Image processing failed');
          }

          fileToUpload = result.blob;
        }
      }

      // Create FormData
      const formData = new FormData();
      // If we scaled the image, it's now a WebP blob without a filename
      // We need to provide a filename with the correct extension
      if (fileToUpload instanceof Blob && !(fileToUpload instanceof File)) {
        // Scaled image is always WebP
        formData.append('image', fileToUpload, 'scaled-artwork.webp');
      } else {
        formData.append('image', fileToUpload);
      }
      formData.append('title', title.trim() || selectedFile.name.replace(/\.[^/.]+$/, ''));
      formData.append('description', description.trim());
      formData.append('hashtags', hashtags.trim());
      formData.append('hidden_by_user', postAsHidden.toString());
      if (selectedLicenseId !== null) {
        formData.append('license_id', selectedLicenseId.toString());
      }
      // Provenance (docs/artwork-provenance/ §5.1): a website upload is by
      // definition a file from outside the editor pipeline. Device type is
      // server-inferred from the User-Agent.
      formData.append('client', 'web');
      formData.append('creation_method', 'external_file');
      formData.append('remixable', remixable.toString());

      const response = await authenticatedFetch(`${API_BASE_URL}/api/post/upload`, {
        method: 'POST',
        body: formData,
      });

      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(errorData.detail || 'Upload failed');
      }

      const data = await response.json();
      setUploadedArtwork({
        id: data.post.id,
        public_sqid: data.post.public_sqid,
        title: data.post.title,
        art_url: data.post.art_url,
        width: data.post.width,
        height: data.post.height,
        public_visibility: data.post.public_visibility,
        created_at: data.post.created_at,
      });

      // Clear draft after successful upload
      clearDraft();

    } catch (error) {
      console.error('Upload error:', error);
      setUploadError(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setUploading(false);
      setProcessingState(prev => ({ ...prev, isProcessing: false, progress: null }));
    }
  };

  // Copy the new post's permalink (success screen, both variants)
  const copyPostLink = useCallback(async () => {
    if (!uploadedArtwork) return;
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/p/${uploadedArtwork.public_sqid}`);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 2000);
    } catch {
      // Clipboard unavailable (e.g. insecure context) — ignore silently
    }
  }, [uploadedArtwork]);

  // Validate output dimensions (not input) - this is what will actually be uploaded
  const outputIsValid = outputDimensions ? isValidSize(outputDimensions.width, outputDimensions.height) : false;
  const isValid = selectedFile && outputIsValid && title.trim().length > 0;
  const isProcessing = processingState.isProcessing || uploading;

  const displayedPreviewUrl =
    previewScaling && scaledPreview ? scaledPreview.url : previewUrl;


  // Compact meta line for the loaded artwork (docs/newpost-ui-appraisal/ F13)
  const metaLine = imageInfo
    ? [
        imageInfo.format.toUpperCase(),
        `${imageInfo.width} × ${imageInfo.height} px`,
        imageInfo.isAnimated
          ? `${imageInfo.frameCount} frames @ ${imageInfo.averageFps.toFixed(1)} FPS`
          : 'static',
      ].join(' · ')
    : null;

  // Collapsed-state summaries for the disclosure sections (F15)
  const scalingSummary = !imageInfo
    ? undefined
    : !outputIsValid
      ? 'Required'
      : needsScaling && outputDimensions
        ? `${outputDimensions.width} × ${outputDimensions.height} px`
        : 'None';
  const licenseSummary = selectedLicenseId
    ? licenses.find((l) => l.id === selectedLicenseId)?.identifier || 'Selected'
    : 'No license';

  if (!isAuthenticated) {
    return (
      <Layout title="New post" description="Post your pixel art">
        <div className="submit-container">
          <div className="loading-state">Loading...</div>
        </div>
        <style jsx>{`
          .submit-container { max-width: 800px; margin: 0 auto; padding: 24px; }
          .loading-state { text-align: center; padding: 48px; color: var(--text-muted); }
        `}</style>
      </Layout>
    );
  }

  return (
    <Layout title="New post" description="Post your pixel art">
      <div className="submit-container">
        {!uploadedArtwork && <h1 className="page-title">New post</h1>}

        {!uploadedArtwork && canPostPublic === false && (
          <div className="pre-upload-notice">
            <PostReviewNotice variant="pre-upload" />
          </div>
        )}

        {uploadedArtwork ? (
          <div className="success-container">
            <div className="success-card">
              <p className="success-eyebrow">Your artwork is posted</p>
              <Link href={`/p/${uploadedArtwork.public_sqid}`} legacyBehavior>
                <a className="success-preview">
                  <img
                    src={ensureCompatibleArtUrl(`${API_BASE_URL}${uploadedArtwork.art_url}`)}
                    alt={uploadedArtwork.title}
                    className="success-image"
                  />
                </a>
              </Link>
              <h2 className="success-name">{uploadedArtwork.title}</h2>

              {uploadedArtwork.public_visibility ? (
                <p className="success-status">
                  <IconCheckCircle size={16} /> Live — visible to the whole community
                </p>
              ) : (
                <PostReviewNotice variant="pending" />
              )}

              <div className="success-buttons">
                <Button variant="primary" onClick={() => router.push(`/p/${uploadedArtwork.public_sqid}`)}>
                  View post
                </Button>
                <Button variant="secondary" onClick={copyPostLink}>
                  {linkCopied ? 'Link copied' : 'Copy link'}
                </Button>
                <Button variant="ghost" onClick={clearSelection}>
                  Post another
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div className="upload-grid">
            {/* Left Column */}
            <div className="upload-column">
              {previewUrl ? (
                <div
                  className="preview-card"
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/png,image/gif,image/webp,image/bmp"
                    onChange={handleFileInputChange}
                    className="file-input"
                  />
                  <div className={`preview-frame ${isDragging ? 'dragging' : ''}`}>
                    <img src={displayedPreviewUrl ?? previewUrl} alt="Preview" className="preview-image" />
                  </div>
                  {metaLine && (
                    <p className="preview-meta">
                      {metaLine}
                      {needsScaling && outputDimensions && outputIsValid && (
                        <span className="preview-meta-output">
                          {' '}→ posts at {outputDimensions.width} × {outputDimensions.height} px
                        </span>
                      )}
                    </p>
                  )}
                  {previewScaling && scaledPreview && !isPreviewStale && (
                    <div className="scaled-preview-badge">Scaled preview active</div>
                  )}
                  {previewScaling && scaledPreview && isPreviewStale && (
                    <div className="scaled-preview-stale">Parameters changed — preview is out of date</div>
                  )}
                  <div className="preview-actions">
                    <Button variant="secondary" onClick={() => fileInputRef.current?.click()}>
                      Replace
                    </Button>
                    <Button variant="secondary" onClick={clearSelection}>
                      <IconX size={14} /> Remove
                    </Button>
                  </div>
                </div>
              ) : (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  className={`upload-area ${isDragging ? 'dragging' : ''}`}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/png,image/gif,image/webp,image/bmp"
                    onChange={handleFileInputChange}
                    className="file-input"
                  />
                  <div className="upload-placeholder">
                    <div className="upload-icon"><IconUpload size={26} /></div>
                    <p className="upload-text">Drop your artwork here</p>
                    <p className="upload-subtext">or click to browse</p>
                    <p className="upload-formats">
                      PNG, GIF, WebP, or BMP · max {formatMiB(MAX_UPLOAD_SIZE_BYTES)} ·{' '}
                      <Link
                        href="/size_rules"
                        className="upload-formats-link"
                        onClick={(e) => e.stopPropagation()}
                      >
                        size rules
                      </Link>
                    </p>
                    <p className="upload-formats-note">
                      Larger files (up to {formatMiB(MAX_LOAD_SIZE_BYTES)}) can be resized before posting
                    </p>
                  </div>
                </div>
              )}

              {validationErrors.length > 0 && (
                <Notice tone="danger" icon={<IconAlertCircle size={18} />}>
                  <p>{validationErrors.map(e => e.message).join(' ')}</p>
                </Notice>
              )}

              {selectedFile && selectedFile.size > MAX_UPLOAD_SIZE_BYTES && (
                <Notice tone="warning" icon={<IconAlertTriangle size={18} />}>
                  <p>
                    File size {formatMiB(selectedFile.size)} exceeds the {formatMiB(MAX_UPLOAD_SIZE_BYTES)} upload limit.
                    Resize or compress this artwork before posting.
                  </p>
                </Notice>
              )}
            </div>

            {/* Right Column — inactive until an image is loaded (F7) */}
            <div className={`form-column ${!selectedFile ? 'inactive' : ''}`} aria-disabled={!selectedFile}>
              <Field id="title" label="Title" count={{ value: title.length, max: 128 }}>
                <input id="title" type="text" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={128} className="form-input" />
              </Field>

              <Field id="description" label="Description" optional count={{ value: description.length, max: 5000 }}>
                <textarea id="description" value={description} onChange={(e) => setDescription(e.target.value)} rows={4} maxLength={5000} className="form-textarea" />
              </Field>

              <Field
                id="hashtags"
                label="Hashtags"
                optional
                helper={
                  <>
                    Some tags are moderated —{' '}
                    <Link href="/about?tab=rules#monitored-hashtags">tag rules</Link>
                  </>
                }
              >
                <input id="hashtags" type="text" value={hashtags} onChange={(e) => setHashtags(e.target.value)} placeholder="pixel, retro, game (comma separated)" className="form-input" />
              </Field>

              {imageInfo && !isValidSize(imageInfo.width, imageInfo.height) && (
                <Notice tone="warning" icon={<IconAlertTriangle size={18} />}>
                  <p>Input size {imageInfo.width}×{imageInfo.height} is non-standard. Scaling to a valid size is required.</p>
                </Notice>
              )}

              <Disclosure
                title={`Image scaling${imageInfo && !isValidSize(imageInfo.width, imageInfo.height) ? ' (required)' : ''}`}
                summary={scalingSummary}
                open={showScalingOptions}
                onToggle={() => setShowScalingOptions(!showScalingOptions)}
              >
                {!imageInfo ? (
                  <div className="no-image-notice">
                    <p className="help-text center">Load an image to configure scaling options</p>
                  </div>
                ) : (
                  <>
                    <div className="tabs">
                      <button className={`tab ${scalingMode === 'ratio' ? 'active' : ''}`} onClick={() => setScalingMode('ratio')}>By ratio</button>
                      <button className={`tab ${scalingMode === 'dimensions' ? 'active' : ''}`} onClick={() => setScalingMode('dimensions')}>By dimensions</button>
                    </div>

                    {scalingMode === 'ratio' ? (
                      <div className="scaling-ratio">
                        <p className="original-size-label">Original: {imageInfo.width} × {imageInfo.height} px</p>

                        <div className="ratio-input-row">
                          <label className="form-label">Scaling ratio</label>
                          <div className="ratio-input-group">
                            <input type="number" value={scalePercent} onChange={handleScaleInputChange} min={3.125} max={300} step={0.1} className="ratio-input" />
                            <span className="ratio-suffix">%</span>
                          </div>
                        </div>
                        <p className="help-text">Adjust the slider or enter a percentage to scale both dimensions uniformly</p>

                        <div className="slider-container">
                          <input type="range" min={3.125} max={300} step={0.1} value={scalePercent} onChange={handleScaleSliderChange} className="scale-slider" />
                          <div className="slider-labels"><span>3.1%</span><span>100%</span><span>300%</span></div>
                        </div>

                        {scalePercent !== 100 ? (
                          <div className="scale-preview">New size: {Math.round(imageInfo.width * scalePercent / 100)} × {Math.round(imageInfo.height * scalePercent / 100)} px</div>
                        ) : (
                          <div className="scale-preview muted">No scaling applied</div>
                        )}
                        {outputDimensions && !outputIsValid && (
                          <div className="scale-preview-error">Output size {outputDimensions.width} × {outputDimensions.height} px is not a valid Makapix size. Please adjust scaling.</div>
                        )}
                      </div>
                    ) : (
                      <div className="scaling-dimensions">
                        <p className="original-size-label">Original: {imageInfo.width} × {imageInfo.height} px</p>

                        <div className="aspect-ratio-toggle">
                          <label className="form-label">Maintain aspect ratio</label>
                          <button className={`toggle ${maintainAspectRatio ? 'on' : ''}`} onClick={() => setMaintainAspectRatio(!maintainAspectRatio)}><span className="toggle-handle"></span></button>
                        </div>
                        <p className="help-text">{maintainAspectRatio ? 'Specify one dimension, the other will be calculated automatically' : 'Specify both dimensions independently'}</p>

                        <div className="dimension-inputs">
                          <div className="dimension-input-group">
                            <label className="form-label">Width (px)</label>
                            <input type="number" value={customWidth} onChange={handleWidthChange} placeholder={imageInfo.width.toString()} className="form-input mono" />
                          </div>
                          <div className="dimension-input-group">
                            <label className="form-label">Height (px)</label>
                            <input type="number" value={customHeight} onChange={handleHeightChange} placeholder={imageInfo.height.toString()} className="form-input mono" />
                          </div>
                        </div>

                        {customWidth && customHeight && (() => {
                          const outW = parseInt(customWidth) || imageInfo.width;
                          const outH = parseInt(customHeight) || imageInfo.height;
                          const scaleW = ((outW / imageInfo.width) * 100).toFixed(1);
                          const scaleH = ((outH / imageInfo.height) * 100).toFixed(1);
                          const isSameScale = scaleW === scaleH;
                          const isNoChange = outW === imageInfo.width && outH === imageInfo.height;

                          if (isNoChange) {
                            return <div className="scale-preview muted">No scaling (original size)</div>;
                          } else if (isSameScale) {
                            return <div className="scale-preview">Output: {outW} × {outH} px ({scaleW}%)</div>;
                          } else {
                            return <div className="scale-preview">Output: {outW} × {outH} px (W: {scaleW}%, H: {scaleH}%)</div>;
                          }
                        })()}
                        {outputDimensions && !outputIsValid && (
                          <div className="scale-preview-error">Output size {outputDimensions.width} × {outputDimensions.height} px is not a valid Makapix size. Please adjust scaling.</div>
                        )}
                      </div>
                    )}

                    <div className="algorithm-section">
                      <label className="form-label">Scaling style</label>
                      <div className="radio-group">
                        <label className="radio-option"><input type="radio" name="algorithm" checked={scaleAlgorithm === 'nearest-neighbor'} onChange={() => setScaleAlgorithm('nearest-neighbor')} /><span className="radio-label">Crisp</span></label>
                        <p className="radio-description">Best for pixel art — sharp edges, no blurring (nearest neighbor)</p>
                        <label className="radio-option"><input type="radio" name="algorithm" checked={scaleAlgorithm === 'lanczos3'} onChange={() => setScaleAlgorithm('lanczos3')} /><span className="radio-label">Smooth</span></label>
                        <p className="radio-description">Best for photos — smooth gradients (Lanczos3)</p>
                      </div>
                    </div>

                    {needsScaling && (
                      <div className="preview-scaling-section">
                        {(() => {
                          const genDisabled = !selectedFile || isProcessing || !outputIsValid;
                          const toggleDisabled = isProcessing;

                          if (!scaledPreview) {
                            return (
                              <>
                                <Button variant="secondary" fullWidth onClick={handleGeneratePreview} disabled={genDisabled}>
                                  Preview scaling
                                </Button>
                                <p className="help-text center">Click to generate a real scaled preview</p>
                              </>
                            );
                          }

                          if (isPreviewStale) {
                            return (
                              <>
                                <Button variant="secondary" fullWidth onClick={handleGeneratePreview} disabled={genDisabled}>
                                  Regenerate preview
                                </Button>
                                {previewScaling && (
                                  <Button variant="secondary" fullWidth onClick={() => setPreviewScaling(false)} disabled={toggleDisabled}>
                                    Show original
                                  </Button>
                                )}
                                <p className="help-text center">Scaling parameters changed — click to regenerate</p>
                              </>
                            );
                          }

                          if (previewScaling) {
                            return (
                              <>
                                <Button variant="secondary" fullWidth onClick={() => setPreviewScaling(false)} disabled={toggleDisabled}>
                                  Show original
                                </Button>
                                <p className="help-text center">Click to view original size</p>
                              </>
                            );
                          }

                          return (
                            <>
                              <Button variant="secondary" fullWidth onClick={() => setPreviewScaling(true)} disabled={toggleDisabled}>
                                Show scaled preview
                              </Button>
                              <p className="help-text center">Click to view the scaled preview</p>
                            </>
                          );
                        })()}
                      </div>
                    )}
                  </>
                )}
              </Disclosure>

              <Disclosure
                title="License"
                summary={licenseSummary}
                open={showLicenseOptions}
                onToggle={() => setShowLicenseOptions(!showLicenseOptions)}
              >
                <div className="license-section">
                  <label className="form-label">Select license</label>
                  <div className="license-radio-group">
                    <label className="license-radio-option">
                      <input
                        type="radio"
                        name="license"
                        checked={selectedLicenseId === null}
                        onChange={() => setSelectedLicenseId(null)}
                      />
                      <div className="license-option-content">
                        <div className="license-option-text">
                          <span className="license-option-identifier">No license</span>
                          <span className="license-option-title">All rights reserved</span>
                        </div>
                      </div>
                    </label>

                    {licenses.map((license) => (
                      <label key={license.id} className="license-radio-option">
                        <input
                          type="radio"
                          name="license"
                          checked={selectedLicenseId === license.id}
                          onChange={() => setSelectedLicenseId(license.id)}
                        />
                        <div className="license-option-content">
                          <img src={license.badge_path} alt={license.identifier} className="license-option-badge" />
                          <div className="license-option-text">
                            <span className="license-option-identifier">{license.identifier}</span>
                            <span className="license-option-title">{license.title}</span>
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>

                  {selectedLicenseId && (() => {
                    const selected = licenses.find((l) => l.id === selectedLicenseId);
                    if (!selected) return null;
                    return (
                      <a href={selected.canonical_url} target="_blank" rel="noopener noreferrer" className="license-learn-more">
                        Learn more about this license
                      </a>
                    );
                  })()}
                </div>
              </Disclosure>

              <Field
                id="visibility"
                label="Visibility"
                helper={postAsHidden ? 'Hidden posts are visible only to you and anyone you share the link with.' : undefined}
              >
                <select
                  id="visibility"
                  className="form-select"
                  value={postAsHidden ? 'hidden' : 'public'}
                  onChange={(e) => setPostAsHidden(e.target.value === 'hidden')}
                >
                  <option value="public">Public</option>
                  <option value="hidden">Hidden</option>
                </select>
              </Field>

              <label className="checkbox-option" title={ndLicenseSelected ? 'NoDerivatives license — this work cannot be marked Remixable' : 'Turning this off stops others from remixing this artwork'}>
                <input type="checkbox" checked={remixable} disabled={ndLicenseSelected} onChange={(e) => setRemixable(e.target.checked)} />
                <span className="checkbox-label">Remixable — others may remix this artwork</span>
              </label>

              {processingState.progress && (
                <div className="progress-container">
                  <div className="progress-header"><span className="progress-stage">{processingState.progress.stage}...</span><span className="progress-percent">{processingState.progress.percent}%</span></div>
                  <div className="progress-bar"><div className="progress-fill" style={{ width: `${processingState.progress.percent}%` }}></div></div>
                </div>
              )}

              {(uploadError || processingState.error) && (
                <Notice tone="danger" icon={<IconAlertCircle size={18} />}>
                  <p>{uploadError || processingState.error?.message}</p>
                </Notice>
              )}

              <div className="action-buttons">
                <Button variant="primary" className="action-post" onClick={handleSubmit} disabled={!isValid || isProcessing}>
                  {isProcessing ? 'Posting…' : 'Post'}
                </Button>
                <Button variant="secondary" onClick={() => setShowClearDialog(true)} disabled={isProcessing}>
                  Clear all
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>

      {showClearDialog && (
        <Dialog
          title="Clear all fields?"
          onClose={() => setShowClearDialog(false)}
          actions={
            <>
              <Button variant="secondary" onClick={() => setShowClearDialog(false)}>Cancel</Button>
              <Button variant="danger" onClick={handleClearAll}>Clear all</Button>
            </>
          }
        >
          <p>This action will remove all your inputs including the loaded artwork. This cannot be undone.</p>
        </Dialog>
      )}

      <style jsx>{`
        .submit-container { max-width: 900px; margin: 0 auto; padding: 24px; }
        .page-title { font-size: 1.75rem; font-weight: 700; color: var(--text-primary); margin-bottom: 28px; }
        .upload-grid { display: grid; grid-template-columns: 1fr; gap: 32px; }
        @media (min-width: 768px) { .upload-grid { grid-template-columns: 1fr 1fr; } }
        .upload-column, .form-column { display: flex; flex-direction: column; }
        .upload-column > :global(* + *), .form-column > :global(* + *) { margin-top: 20px; }
        .form-column.inactive { opacity: 0.45; pointer-events: none; }
        .upload-area { border: 2px dashed var(--bg-tertiary); border-radius: 12px; padding: 48px 24px; cursor: pointer; transition: all var(--transition-fast); min-height: 250px; display: flex; align-items: center; justify-content: center; }
        .upload-area:hover { border-color: var(--accent-cyan); background: rgba(0, 212, 255, 0.05); }
        .upload-area.dragging { border-color: var(--accent-cyan); background: rgba(0, 212, 255, 0.08); }
        .file-input { display: none; }
        .upload-placeholder { text-align: center; }
        .upload-icon { width: 56px; height: 56px; border-radius: 50%; background: var(--bg-tertiary); color: var(--text-secondary); display: flex; align-items: center; justify-content: center; margin: 0 auto 16px; }
        .upload-text { font-size: 1.1rem; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
        .upload-subtext { color: var(--text-secondary); margin-bottom: 12px; }
        .upload-formats { font-size: 0.8rem; color: var(--text-muted); }
        .upload-formats :global(a) { font-size: 0.8rem; }
        .upload-formats-note { font-size: 0.75rem; color: var(--text-muted); margin-top: 4px; }
        .preview-card { display: flex; flex-direction: column; align-items: center; width: 100%; background: var(--bg-secondary); border: 1px solid var(--bg-tertiary); border-radius: 12px; padding: 20px; }
        .preview-card > :global(* + *) { margin-top: 14px; }
        .preview-frame { width: min(384px, 100%); aspect-ratio: 1 / 1; display: flex; align-items: center; justify-content: center; background: var(--bg-primary); border: 1px solid var(--bg-tertiary); border-radius: 8px; overflow: hidden; }
        .preview-frame.dragging { border-color: var(--accent-cyan); }
        .preview-image { width: 100%; height: 100%; object-fit: contain; image-rendering: -webkit-optimize-contrast; image-rendering: -moz-crisp-edges; image-rendering: crisp-edges; image-rendering: pixelated; }
        .preview-meta { font-size: 0.85rem; color: var(--text-secondary); margin: 0; text-align: center; }
        .preview-meta-output { color: var(--accent-cyan); }
        .preview-actions { display: flex; gap: 12px; }
        .scaled-preview-badge { font-size: 0.75rem; color: var(--text-secondary); background: var(--bg-primary); padding: 6px 12px; border-radius: 6px; border: 1px solid var(--bg-tertiary); }
        .scaled-preview-stale { font-size: 0.75rem; color: var(--warning); background: rgba(240, 191, 104, 0.1); padding: 6px 12px; border-radius: 6px; border: 1px solid rgba(240, 191, 104, 0.3); }
        .form-input, .form-textarea, .form-select { background: var(--bg-tertiary); border: 1px solid var(--bg-tertiary); color: var(--text-primary); border-radius: 8px; padding: 12px 16px; font-size: 1rem; transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
        .form-input:focus, .form-textarea:focus, .form-select:focus { outline: none; border-color: var(--accent-cyan); box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.15); }
        .form-input.mono { font-family: monospace; }
        .form-textarea { resize: vertical; min-height: 100px; }
        .form-select { appearance: auto; width: 100%; }
        .form-label { font-size: 0.9rem; color: var(--text-secondary); }
        .tabs { display: flex; border-radius: 8px; overflow: hidden; border: 1px solid var(--bg-tertiary); }
        .tab { flex: 1; padding: 10px 16px; background: transparent; color: var(--text-secondary); font-size: 0.9rem; cursor: pointer; transition: all var(--transition-fast); }
        .tab:hover { background: rgba(255, 255, 255, 0.05); }
        .tab.active { background: var(--accent-cyan); color: var(--bg-primary); }
        .scaling-ratio, .scaling-dimensions { display: flex; flex-direction: column; min-width: 260px; }
        .scaling-ratio > :global(* + *), .scaling-dimensions > :global(* + *) { margin-top: 12px; }
        .ratio-input-row { display: flex; justify-content: space-between; align-items: center; }
        .ratio-input-group { display: flex; align-items: center; }
        .ratio-input-group > :global(* + *) { margin-left: 8px; }
        .ratio-input { width: 100px; padding: 8px 12px; text-align: center; font-family: monospace; background: var(--bg-tertiary); border: 1px solid var(--bg-tertiary); color: var(--text-primary); border-radius: 6px; }
        .ratio-input:focus { outline: none; border-color: var(--accent-cyan); }
        .ratio-suffix { color: var(--text-secondary); }
        .slider-container { margin-top: 8px; }
        .scale-slider { width: 100%; height: 8px; border-radius: 4px; background: var(--bg-tertiary); -webkit-appearance: none; appearance: none; cursor: pointer; }
        .scale-slider::-webkit-slider-thumb { -webkit-appearance: none; width: 20px; height: 20px; border-radius: 50%; background: var(--accent-cyan); cursor: pointer; border: none; }
        .scale-slider::-moz-range-thumb { width: 20px; height: 20px; border-radius: 50%; background: var(--accent-cyan); cursor: pointer; border: none; }
        .slider-labels { display: flex; justify-content: space-between; margin-top: 4px; font-size: 0.7rem; color: var(--text-muted); }
        .scale-preview { padding: 12px; background: rgba(0, 212, 255, 0.08); border: 1px solid rgba(0, 212, 255, 0.25); border-radius: 6px; font-size: 0.85rem; color: var(--accent-cyan); }
        .scale-preview.muted { background: rgba(255, 255, 255, 0.04); border-color: rgba(255, 255, 255, 0.08); color: var(--text-secondary); }
        .scale-preview-error { padding: 12px; background: rgba(242, 85, 90, 0.1); border: 1px solid rgba(242, 85, 90, 0.3); border-radius: 6px; font-size: 0.85rem; color: var(--danger); }
        .help-text { font-size: 0.8rem; color: var(--text-muted); }
        .help-text.center { text-align: center; }
        .no-image-notice { padding: 24px 16px; }
        .original-size-label { font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 12px; padding: 8px 12px; background: rgba(255, 255, 255, 0.04); border-radius: 6px; }
        .aspect-ratio-toggle { display: flex; justify-content: space-between; align-items: center; }
        .toggle { width: 44px; height: 24px; border-radius: 12px; background: var(--bg-tertiary); border: none; cursor: pointer; position: relative; transition: background var(--transition-fast); }
        .toggle.on { background: var(--accent-cyan); }
        .toggle-handle { position: absolute; top: 2px; left: 2px; width: 20px; height: 20px; border-radius: 50%; background: white; transition: left var(--transition-fast); }
        .toggle.on .toggle-handle { left: 22px; }
        .dimension-inputs { display: grid; grid-template-columns: 120px 120px; gap: 12px; }
        .dimension-input-group { display: flex; flex-direction: column; }
        .dimension-input-group > :global(* + *) { margin-top: 6px; }
        .algorithm-section { padding-top: 16px; border-top: 1px solid var(--bg-tertiary); }
        .radio-group { display: flex; flex-direction: column; margin-top: 12px; }
        .radio-group > :global(* + *) { margin-top: 8px; }
        .radio-option { display: flex; align-items: center; cursor: pointer; }
        .radio-option > :global(* + *) { margin-left: 8px; }
        .radio-option input[type="radio"] { width: 18px; height: 18px; accent-color: var(--accent-cyan); }
        .radio-label { color: var(--text-primary); font-weight: 500; }
        .radio-description { font-size: 0.8rem; color: var(--text-muted); margin-left: 26px; margin-top: -4px; }
        .preview-scaling-section { padding-top: 16px; border-top: 1px solid var(--bg-tertiary); display: flex; flex-direction: column; }
        .preview-scaling-section > :global(* + *) { margin-top: 10px; }
        .license-section { display: flex; flex-direction: column; }
        .license-section > :global(* + *) { margin-top: 12px; }
        .license-radio-group { display: flex; flex-direction: column; margin-top: 12px; }
        .license-radio-group > :global(* + *) { margin-top: 8px; }
        .license-radio-option { display: flex; align-items: flex-start; cursor: pointer; padding: 12px; border: 1px solid var(--bg-tertiary); border-radius: 8px; transition: all var(--transition-fast); }
        .license-radio-option > :global(* + *) { margin-left: 12px; }
        .license-radio-option:hover { border-color: var(--accent-cyan); background: rgba(0, 212, 255, 0.05); }
        .license-radio-option:has(input:checked) { border-color: var(--accent-cyan); background: rgba(0, 212, 255, 0.1); }
        .license-radio-option input[type="radio"] { width: 18px; height: 18px; accent-color: var(--accent-cyan); flex-shrink: 0; margin-top: 2px; }
        .license-option-content { display: flex; align-items: flex-start; flex: 1; min-width: 0; }
        .license-option-content > :global(* + *) { margin-left: 12px; }
        .license-option-badge { width: 88px; height: 31px; flex-shrink: 0; }
        .license-option-text { display: flex; flex-direction: column; min-width: 0; }
        .license-option-text > :global(* + *) { margin-top: 2px; }
        .license-option-identifier { font-size: 0.85rem; font-weight: 500; color: var(--text-primary); }
        .license-option-title { font-size: 0.8rem; color: var(--text-secondary); line-height: 1.3; }
        .license-learn-more { font-size: 0.8rem; color: var(--accent-cyan); margin-top: 8px; display: inline-block; }
        .license-learn-more:hover { text-decoration: underline; }
        .checkbox-option { display: flex; align-items: center; cursor: pointer; }
        .checkbox-option > :global(* + *) { margin-left: 10px; }
        .checkbox-option input[type="checkbox"] { width: 18px; height: 18px; accent-color: var(--accent-cyan); }
        .checkbox-label { color: var(--text-primary); font-size: 0.9rem; }
        .progress-container { display: flex; flex-direction: column; }
        .progress-container > :global(* + *) { margin-top: 8px; }
        .progress-header { display: flex; justify-content: space-between; font-size: 0.9rem; }
        .progress-stage { color: var(--text-secondary); text-transform: capitalize; }
        .progress-percent { color: var(--accent-cyan); }
        .progress-bar { height: 8px; background: rgba(255, 255, 255, 0.1); border-radius: 4px; overflow: hidden; }
        .progress-fill { height: 100%; background: var(--accent-cyan); transition: width 0.3s ease; }
        .action-buttons { display: flex; gap: 12px; padding-top: 8px; }
        .action-buttons :global(.action-post) { flex: 1; }
        .success-container { max-width: 448px; margin: 48px auto 0; }
        .success-card { display: flex; flex-direction: column; align-items: center; padding: 32px; background: var(--bg-card); border: 1px solid var(--bg-tertiary); border-radius: 16px; }
        .success-card > :global(* + *) { margin-top: 16px; }
        .success-eyebrow { font-size: 0.9rem; color: var(--text-secondary); margin: 0; }
        .success-preview { width: 384px; max-width: 100%; aspect-ratio: 1 / 1; background: var(--bg-primary); border-radius: 12px; display: flex; align-items: center; justify-content: center; overflow: hidden; cursor: pointer; }
        .success-image { width: 100%; height: 100%; object-fit: contain; image-rendering: -webkit-optimize-contrast; image-rendering: -moz-crisp-edges; image-rendering: crisp-edges; image-rendering: pixelated; }
        .success-name { font-size: 1.25rem; font-weight: 600; color: var(--text-primary); margin: 0; }
        .success-status { display: inline-flex; align-items: center; gap: 8px; font-size: 0.9rem; color: var(--success); margin: 0; }
        .pre-upload-notice { margin-bottom: 24px; }
        .success-buttons { display: flex; gap: 12px; margin-top: 8px; width: 100%; }
        .success-buttons > :global(*) { flex: 1; }
        .loading-state { text-align: center; padding: 48px; color: var(--text-muted); }
        @media (max-width: 480px) { .submit-container { padding: 16px; } .page-title { font-size: 1.5rem; } .action-buttons { flex-direction: column; } .success-buttons { flex-direction: column; width: 100%; } }
      `}</style>
    </Layout>
  );
}

// Export with SSR disabled to avoid "window is not defined" errors
export default dynamic(() => Promise.resolve(SubmitPageContent), {
  ssr: false,
  loading: () => (
    <Layout title="New post" description="Post your pixel art">
      <div style={{ maxWidth: '800px', margin: '0 auto', padding: '24px', textAlign: 'center' }}>
        <p style={{ color: 'var(--text-muted)' }}>Loading…</p>
      </div>
    </Layout>
  ),
});

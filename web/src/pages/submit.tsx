import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import Layout from '../components/Layout';
import { authenticatedFetch, clearTokens } from '../lib/api';
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
  canvas: string;
  width: number;
  height: number;
  public_visibility: boolean;
}

interface ValidationError {
  type: 'size' | 'dimensions' | 'format';
  message: string;
}

type ResamplingAlgorithm = 'nearest-neighbor' | 'lanczos3';

const MAX_FILE_SIZE_BYTES = (() => {
  const raw = process.env.NEXT_PUBLIC_MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES || '5242880';
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : 5242880;
})();

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
  const [allowEdit, setAllowEdit] = useState(true);

  // Scaling options
  const [showScalingOptions, setShowScalingOptions] = useState(false);
  const [scalePercent, setScalePercent] = useState(100);
  const [scaleAlgorithm, setScaleAlgorithm] = useState<ResamplingAlgorithm>('nearest-neighbor');
  const [scalingMode, setScalingMode] = useState<'ratio' | 'dimensions'>('ratio');
  const [customWidth, setCustomWidth] = useState<string>('');
  const [customHeight, setCustomHeight] = useState<string>('');
  const [maintainAspectRatio, setMaintainAspectRatio] = useState(true);
  const [previewScaling, setPreviewScaling] = useState(false);

  // Upload state
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadedArtwork, setUploadedArtwork] = useState<UploadedArtwork | null>(null);
  const [showClearDialog, setShowClearDialog] = useState(false);

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

  // Track if we've processed Piskel/Pixelc import
  const [editorImportProcessed, setEditorImportProcessed] = useState(false);

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

    // Validate file size
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setValidationErrors([{
        type: 'size',
        message: `File size (${formatMiB(file.size)}) exceeds maximum of ${formatMiB(MAX_FILE_SIZE_BYTES)}`,
      }]);
      return;
    }

    setSelectedFile(file);
    setValidationErrors([]);
    setUploadError(null);
    setUploadedArtwork(null);
    setPreviewScaling(false);

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
            setMaintainAspectRatio(false); // Allow changing to target dimensions
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
    setAllowEdit(draft.allowEdit);

    // Restore scaling options
    setShowScalingOptions(draft.showScalingOptions);
    setScalePercent(draft.scalePercent);
    setScaleAlgorithm(draft.scaleAlgorithm);
    setScalingMode(draft.scalingMode);
    setCustomWidth(draft.customWidth);
    setCustomHeight(draft.customHeight);
    setMaintainAspectRatio(draft.maintainAspectRatio);

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
    }
  }, []);

  // Handle imports from Piskel or Pixelc editors, or restore saved draft
  useEffect(() => {
    if (editorImportProcessed) return;
    if (!router.isReady) return;

    const from = router.query.from as string | undefined;
    const hasEditorImport = from === 'piskel' || from === 'pixelc';

    if (hasEditorImport) {
      const storageKey = from === 'piskel' ? 'piskel_export' : 'pixelc_export';
      const exportData = sessionStorage.getItem(storageKey);

      if (exportData) {
        // New artwork from editor takes priority - clear any saved draft
        clearDraft();

        try {
          const data = JSON.parse(exportData);

          // Get the data URL - both Piskel and Pixelc use 'imageData'
          const dataUrl = data.imageData;

          if (!dataUrl || typeof dataUrl !== 'string') {
            console.error(`Invalid ${from} export data: missing data URL`);
            setEditorImportProcessed(true);
            setInitComplete(true);
            return;
          }

          // Convert data URL to File
          const byteString = atob(dataUrl.split(',')[1]);
          const mimeMatch = dataUrl.match(/^data:([^;]+);/);
          const mimeType = mimeMatch ? mimeMatch[1] : 'image/png';
          const arrayBuffer = new ArrayBuffer(byteString.length);
          const uint8Array = new Uint8Array(arrayBuffer);
          for (let i = 0; i < byteString.length; i++) {
            uint8Array[i] = byteString.charCodeAt(i);
          }
          const blob = new Blob([arrayBuffer], { type: mimeType });

          // Generate filename
          const extension = mimeType === 'image/gif' ? 'gif' : mimeType === 'image/webp' ? 'webp' : 'png';
          const fileName = from === 'pixelc' && data.name
            ? `${data.name}.${extension}`
            : `${from}-export.${extension}`;

          const file = new File([blob], fileName, { type: mimeType });

          // Store data URL for draft persistence
          setImageDataUrl(dataUrl);

          // Pre-fill title from Pixelc name if available
          if (from === 'pixelc' && data.name) {
            setTitle(data.name);
          }

          // Process the file
          handleFileSelect(file);

          // Clear the editor export from sessionStorage
          sessionStorage.removeItem(storageKey);

          setEditorImportProcessed(true);
          setInitComplete(true);
          return;
        } catch (err) {
          console.error(`Failed to process ${from} export:`, err);
          setEditorImportProcessed(true);
          setInitComplete(true);
          return;
        }
      }
    }

    // No editor import - try to restore saved draft
    const draft = loadDraft();
    if (draft) {
      restoreFromDraft(draft);
    }

    setEditorImportProcessed(true);
    setInitComplete(true);
  }, [router.isReady, router.query.from, editorImportProcessed, handleFileSelect, restoreFromDraft]);

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
        setMaintainAspectRatio(false);
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
        allowEdit,
        showScalingOptions,
        scalePercent,
        scaleAlgorithm,
        scalingMode,
        customWidth,
        customHeight,
        maintainAspectRatio,
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
    allowEdit,
    showScalingOptions,
    scalePercent,
    scaleAlgorithm,
    scalingMode,
    customWidth,
    customHeight,
    maintainAspectRatio,
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
    setImageInfo(null);
    setImageDataUrl(null);
    setValidationErrors([]);
    setTitle('');
    setDescription('');
    setHashtags('');
    setPostAsHidden(false);
    setAllowEdit(true);
    setScalePercent(100);
    setCustomWidth('');
    setCustomHeight('');
    setUploadError(null);
    setUploadedArtwork(null);
    setShowScalingOptions(false);
    setPreviewScaling(false);
    setProcessingState({ isProcessing: false, progress: null, error: null });
    clearDraft();
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [previewUrl]);

  const handleClearAll = useCallback(() => {
    clearSelection();
    setShowClearDialog(false);
  }, [clearSelection]);

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
        canvas: data.post.canvas,
        width: data.post.width,
        height: data.post.height,
        public_visibility: data.post.public_visibility,
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

  // Validate output dimensions (not input) - this is what will actually be uploaded
  const outputIsValid = outputDimensions ? isValidSize(outputDimensions.width, outputDimensions.height) : false;
  const isValid = selectedFile && outputIsValid && title.trim().length > 0;
  const isProcessing = processingState.isProcessing || uploading;

  // Compute scaled preview dimensions
  const scaledPreviewStyle = previewScaling && imageInfo && outputDimensions ? {
    width: `${outputDimensions.width}px`,
    height: `${outputDimensions.height}px`,
    imageRendering: scaleAlgorithm === 'nearest-neighbor' ? 'pixelated' as const : 'auto' as const,
  } : undefined;

  if (!isAuthenticated) {
    return (
      <Layout title="Submit Artwork" description="Upload your pixel art">
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
    <Layout title="Submit Artwork" description="Upload your pixel art">
      <div className="submit-container">
        <h1 className="page-title">Upload Artwork</h1>
        <div className="title-underline"></div>

        {uploadedArtwork ? (
          <div className="success-container">
            <div className="success-card">
              <div className="success-icon">✅</div>
              <h2 className="success-title">Artwork Uploaded!</h2>
              <div className="success-preview">
                <img
                  src={`${API_BASE_URL}${uploadedArtwork.art_url}`}
                  alt={uploadedArtwork.title}
                  className="success-image"
                />
              </div>
              <p className="success-name">{uploadedArtwork.title}</p>
              <p className="success-canvas">{uploadedArtwork.canvas}</p>

              {!uploadedArtwork.public_visibility && (
                <div className="pending-notice">
                  <span className="pending-icon">⏳</span>
                  <p className="pending-text">Your artwork is awaiting moderator approval.</p>
                </div>
              )}

              <div className="success-buttons">
                <button onClick={() => router.push(`/p/${uploadedArtwork.public_sqid}`)} className="btn btn-primary">View Artwork</button>
                <button onClick={clearSelection} className="btn btn-primary">Upload Another</button>
              </div>
            </div>
          </div>
        ) : (
          <div className="upload-grid">
            {/* Left Column */}
            <div className="upload-column">
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`upload-area ${isDragging ? 'dragging' : ''} ${previewUrl ? 'has-preview' : ''}`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/png,image/gif,image/webp,image/bmp"
                  onChange={handleFileInputChange}
                  className="file-input"
                />

                {previewUrl ? (
                  <div className="preview-container">
                    <img src={previewUrl} alt="Preview" className="preview-image" style={scaledPreviewStyle} />
                    {previewScaling && <div className="scaled-preview-badge">Scaled preview active</div>}
                    <button onClick={(e) => { e.stopPropagation(); clearSelection(); }} className="remove-btn">✕ Remove</button>
                  </div>
                ) : (
                  <div className="upload-placeholder">
                    <div className="upload-icon">📁</div>
                    <p className="upload-text">Drop your artwork here</p>
                    <p className="upload-subtext">or click to browse</p>
                    <p className="upload-formats">PNG, GIF, WebP, or BMP • Max {formatMiB(MAX_FILE_SIZE_BYTES)}</p>
                  </div>
                )}
              </div>

              <div className="size-rules-link-container">
                <Link href="/size_rules" className="size-rules-link">See size rules</Link>
              </div>

              <div className="monitored-hashtags-link-container">
                <Link href="/about?tab=rules#monitored-hashtags" className="monitored-hashtags-link">
                  See mandatory monitored hashtags rules
                </Link>
              </div>

              {imageInfo && (
                <div className="info-card">
                  <h3 className="info-title">Artwork Information</h3>
                  <div className="info-grid">
                    <div className="info-item"><p className="info-label">Original Size</p><p className="info-value">{imageInfo.width} × {imageInfo.height} px</p></div>
                    <div className="info-item"><p className="info-label">Format</p><p className="info-value">{imageInfo.format.toUpperCase()}</p></div>
                    <div className="info-item"><p className="info-label">Frames</p><p className="info-value">{imageInfo.frameCount}</p></div>
                    <div className="info-item"><p className="info-label">Frame Rate</p><p className="info-value">{imageInfo.isAnimated ? `${imageInfo.averageFps.toFixed(1)} FPS` : 'N/A'}</p></div>
                    {needsScaling && outputDimensions && (
                      <div className="info-item full-width"><p className="info-label">Output Size</p><p className="info-value highlight">{outputDimensions.width} × {outputDimensions.height} px</p></div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Right Column */}
            <div className="form-column">
              <div className="form-group">
                <label htmlFor="title" className="form-label">Artwork Title *</label>
                <input id="title" type="text" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Enter artwork title..." maxLength={200} className="form-input" />
                <span className="char-count">{title.length}/200</span>
              </div>

              <div className="form-group">
                <label htmlFor="description" className="form-label">Description</label>
                <textarea id="description" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Describe your artwork..." rows={4} maxLength={5000} className="form-textarea" />
                <span className="char-count">{description.length}/5000</span>
              </div>

              <div className="form-group">
                <label htmlFor="hashtags" className="form-label">Hashtags</label>
                <input id="hashtags" type="text" value={hashtags} onChange={(e) => setHashtags(e.target.value)} placeholder="pixel, retro, game (comma separated)" className="form-input" />
              </div>

              <div className="accordion">
                {/* Show warning if input size is non-standard */}
                {imageInfo && !isValidSize(imageInfo.width, imageInfo.height) && (
                  <div className="scaling-required-notice">
                    <span className="notice-icon">⚠️</span>
                    <span>Input size {imageInfo.width}x{imageInfo.height} is non-standard. Scaling to a valid size is required.</span>
                  </div>
                )}
                <button className={`accordion-trigger ${showScalingOptions ? 'open' : ''}`} onClick={() => setShowScalingOptions(!showScalingOptions)}>
                  <span className="accordion-title">Image Scaling {imageInfo && !isValidSize(imageInfo.width, imageInfo.height) ? '(Required)' : ''}</span>
                  <span className="accordion-icon">{showScalingOptions ? '▲' : '▼'}</span>
                </button>

                {showScalingOptions && (
                  <div className="accordion-content">
                    {!imageInfo ? (
                      <div className="no-image-notice">
                        <p className="help-text center">Load an image to configure scaling options</p>
                      </div>
                    ) : (
                      <>
                        <div className="tabs">
                          <button className={`tab ${scalingMode === 'ratio' ? 'active' : ''}`} onClick={() => setScalingMode('ratio')}>By Ratio</button>
                          <button className={`tab ${scalingMode === 'dimensions' ? 'active' : ''}`} onClick={() => setScalingMode('dimensions')}>By Dimensions</button>
                        </div>

                        {scalingMode === 'ratio' ? (
                          <div className="scaling-ratio">
                            <div className="ratio-input-row">
                              <label className="form-label">Scaling Ratio</label>
                              <div className="ratio-input-group">
                                <input type="number" value={scalePercent} onChange={handleScaleInputChange} min={3.125} max={300} step={0.1} className="ratio-input" />
                                <span className="ratio-suffix">%</span>
                              </div>
                            </div>

                            <div className="slider-container">
                              <input type="range" min={3.125} max={300} step={0.1} value={scalePercent} onChange={handleScaleSliderChange} className="scale-slider" />
                              <div className="slider-labels"><span>3.125%</span><span>100%</span><span>300%</span></div>
                            </div>

                            {scalePercent !== 100 ? (
                              <div className="scale-preview">New size: {Math.round(imageInfo.width * scalePercent / 100)} × {Math.round(imageInfo.height * scalePercent / 100)} px</div>
                            ) : (
                              <div className="scale-preview muted">Original size: {imageInfo.width} × {imageInfo.height} px (no scaling)</div>
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
                          </div>
                        )}

                        <div className="algorithm-section">
                          <label className="form-label">Scaling Algorithm</label>
                          <div className="radio-group">
                            <label className="radio-option"><input type="radio" name="algorithm" checked={scaleAlgorithm === 'nearest-neighbor'} onChange={() => setScaleAlgorithm('nearest-neighbor')} /><span className="radio-label">Nearest Neighbor (NN)</span></label>
                            <p className="radio-description">Best for pixel art - sharp edges, no blurring</p>
                            <label className="radio-option"><input type="radio" name="algorithm" checked={scaleAlgorithm === 'lanczos3'} onChange={() => setScaleAlgorithm('lanczos3')} /><span className="radio-label">Lanczos3 (LZ3)</span></label>
                            <p className="radio-description">Best for photographs - smooth gradients</p>
                          </div>
                        </div>

                        <div className="preview-scaling-section">
                          <button onClick={() => setPreviewScaling(!previewScaling)} disabled={!selectedFile} className={`btn preview-scaling-btn ${previewScaling ? 'active' : ''}`}>
                            {previewScaling ? 'Reset Preview' : 'Preview Scaling'}
                          </button>
                          <p className="help-text center">{previewScaling ? 'Click to view original size' : 'Click to preview scaled image'}</p>
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>

              <div className="options-card">
                <h3 className="options-title">Upload Options</h3>
                <div className="checkbox-group">
                  <label className="checkbox-option"><input type="checkbox" checked={postAsHidden} onChange={(e) => setPostAsHidden(e.target.checked)} /><span className="checkbox-label">Post as hidden</span></label>
                  <label className="checkbox-option"><input type="checkbox" checked={allowEdit} onChange={(e) => setAllowEdit(e.target.checked)} /><span className="checkbox-label">Allow others to edit</span></label>
                </div>
              </div>

              {processingState.progress && (
                <div className="progress-container">
                  <div className="progress-header"><span className="progress-stage">{processingState.progress.stage}...</span><span className="progress-percent">{processingState.progress.percent}%</span></div>
                  <div className="progress-bar"><div className="progress-fill" style={{ width: `${processingState.progress.percent}%` }}></div></div>
                </div>
              )}

              {(uploadError || processingState.error) && (
                <div className="error-box"><span className="error-icon">❌</span><p>{uploadError || processingState.error?.message}</p></div>
              )}

              {/* Show error if output dimensions are invalid */}
              {outputDimensions && !outputIsValid && (
                <div className="error-box">
                  <span className="error-icon">❌</span>
                  <p>Output size {outputDimensions.width}x{outputDimensions.height} is not a valid Makapix size. Please adjust scaling.</p>
                </div>
              )}

              <div className="action-buttons">
                <button onClick={handleSubmit} disabled={!isValid || isProcessing} className="btn btn-primary">{isProcessing ? 'Processing...' : '🚀 Submit'}</button>
                <button onClick={() => setShowClearDialog(true)} className="btn btn-secondary" disabled={isProcessing}>Clear All</button>
              </div>
            </div>
          </div>
        )}
      </div>

      {showClearDialog && (
        <div className="dialog-overlay" onClick={() => setShowClearDialog(false)}>
          <div className="dialog" onClick={(e) => e.stopPropagation()}>
            <h2 className="dialog-title">Clear all fields?</h2>
            <p className="dialog-description">This action will remove all your inputs including the uploaded artwork. This cannot be undone.</p>
            <div className="dialog-buttons">
              <button onClick={() => setShowClearDialog(false)} className="btn btn-secondary">Cancel</button>
              <button onClick={handleClearAll} className="btn btn-danger">Clear All</button>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .submit-container { max-width: 900px; margin: 0 auto; padding: 24px; }
        .page-title { font-size: 2rem; font-weight: 700; color: var(--text-primary); margin-bottom: 8px; }
        .title-underline { height: 3px; width: 80px; background: linear-gradient(90deg, var(--accent-cyan), var(--accent-pink)); margin-bottom: 32px; }
        .upload-grid { display: grid; grid-template-columns: 1fr; gap: 32px; }
        @media (min-width: 768px) { .upload-grid { grid-template-columns: 1fr 1fr; } }
        .upload-column, .form-column { display: flex; flex-direction: column; gap: 20px; }
        .upload-area { border: 2px dashed var(--bg-tertiary); border-radius: 12px; padding: 48px 24px; cursor: pointer; transition: all var(--transition-fast); min-height: 250px; display: flex; align-items: center; justify-content: center; }
        .upload-area:hover { border-color: var(--accent-cyan); background: rgba(0, 212, 255, 0.05); }
        .upload-area.dragging { border-color: var(--accent-pink); background: rgba(255, 110, 180, 0.1); }
        .upload-area.has-preview { padding: 24px; min-height: auto; }
        .file-input { display: none; }
        .upload-placeholder { text-align: center; }
        .upload-icon { width: 64px; height: 64px; border-radius: 50%; background: linear-gradient(135deg, var(--accent-cyan), var(--accent-pink)); display: flex; align-items: center; justify-content: center; font-size: 28px; margin: 0 auto 16px; }
        .upload-text { font-size: 1.1rem; font-weight: 600; color: var(--text-primary); margin-bottom: 4px; }
        .upload-subtext { color: var(--text-secondary); margin-bottom: 12px; }
        .upload-formats { font-size: 0.8rem; color: var(--text-muted); }
        .preview-container { display: flex; flex-direction: column; align-items: center; gap: 16px; }
        .preview-image { max-width: 100%; max-height: 400px; object-fit: contain; border: 1px solid var(--bg-tertiary); border-radius: 8px; }
        .scaled-preview-badge { font-size: 0.75rem; color: var(--accent-pink); font-family: monospace; background: rgba(255, 110, 180, 0.1); padding: 6px 12px; border-radius: 6px; border: 1px solid rgba(255, 110, 180, 0.3); }
        .remove-btn { padding: 8px 16px; background: transparent; border: 1px solid var(--bg-tertiary); color: var(--text-secondary); border-radius: 6px; cursor: pointer; transition: all var(--transition-fast); }
        .remove-btn:hover { border-color: var(--accent-pink); color: var(--accent-pink); }
        .size-rules-link-container { text-align: center; }
        .size-rules-link { color: var(--accent-cyan); font-size: 0.9rem; }
        .size-rules-link:hover { text-decoration: underline; }
        .monitored-hashtags-link-container { text-align: center; margin-top: 4px; }
        .monitored-hashtags-link { color: #ff6b6b; font-size: 0.85rem; }
        .monitored-hashtags-link:hover { text-decoration: underline; color: #ff8888; }
        .error-box { padding: 16px; background: rgba(255, 100, 100, 0.1); border: 1px solid rgba(255, 100, 100, 0.3); border-radius: 8px; }
        .error-box p { margin: 0; color: #ff6b6b; }
        .error-item { display: flex; align-items: center; gap: 8px; color: #ff6b6b; font-size: 0.9rem; }
        .scaling-required-notice { display: flex; align-items: center; gap: 8px; padding: 12px 16px; background: rgba(255, 200, 100, 0.15); border: 1px solid rgba(255, 200, 100, 0.3); border-radius: 8px; margin-bottom: 8px; color: #ffc864; font-size: 0.9rem; }
        .notice-icon { flex-shrink: 0; font-size: 1.1rem; }
        .error-icon { flex-shrink: 0; }
        .info-card { background: var(--bg-secondary); border: 1px solid var(--bg-tertiary); border-radius: 12px; padding: 20px; }
        .info-title { color: var(--accent-cyan); font-size: 1rem; font-weight: 600; margin-bottom: 16px; }
        .info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .info-item { display: flex; flex-direction: column; gap: 4px; }
        .info-item.full-width { grid-column: span 2; }
        .info-label { font-size: 0.8rem; color: var(--text-secondary); }
        .info-value { font-family: monospace; color: var(--text-primary); }
        .info-value.highlight { color: var(--accent-pink); }
        .form-group { display: flex; flex-direction: column; gap: 6px; }
        .form-label { font-size: 0.9rem; color: var(--text-secondary); }
        .form-input, .form-textarea { background: var(--bg-tertiary); border: 1px solid var(--bg-tertiary); color: var(--text-primary); border-radius: 8px; padding: 12px 16px; font-size: 1rem; transition: border-color var(--transition-fast), box-shadow var(--transition-fast); }
        .form-input:focus, .form-textarea:focus { outline: none; border-color: var(--accent-cyan); box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.15); }
        .form-input.mono { font-family: monospace; }
        .form-textarea { resize: vertical; min-height: 100px; }
        .char-count { font-size: 0.75rem; color: var(--text-muted); text-align: right; }
        .accordion { border: 1px solid var(--bg-tertiary); border-radius: 12px; overflow: hidden; background: var(--bg-secondary); }
        .accordion-trigger { width: 100%; display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; background: transparent; color: var(--accent-cyan); font-weight: 600; cursor: pointer; transition: background var(--transition-fast); }
        .accordion-trigger:hover { background: rgba(0, 212, 255, 0.05); }
        .accordion-icon { font-size: 0.8rem; color: var(--text-secondary); }
        .accordion-content { padding: 0 20px 20px; display: flex; flex-direction: column; gap: 20px; }
        .tabs { display: flex; border-radius: 8px; overflow: hidden; border: 1px solid var(--bg-tertiary); }
        .tab { flex: 1; padding: 10px 16px; background: transparent; color: var(--text-secondary); font-size: 0.9rem; cursor: pointer; transition: all var(--transition-fast); }
        .tab:hover { background: rgba(255, 255, 255, 0.05); }
        .tab.active { background: var(--accent-cyan); color: var(--bg-primary); }
        .scaling-ratio, .scaling-dimensions { display: flex; flex-direction: column; gap: 12px; }
        .ratio-input-row { display: flex; justify-content: space-between; align-items: center; }
        .ratio-input-group { display: flex; align-items: center; gap: 8px; }
        .ratio-input { width: 100px; padding: 8px 12px; text-align: center; font-family: monospace; background: var(--bg-tertiary); border: 1px solid var(--bg-tertiary); color: var(--text-primary); border-radius: 6px; }
        .ratio-input:focus { outline: none; border-color: var(--accent-cyan); }
        .ratio-suffix { color: var(--text-secondary); }
        .slider-container { margin-top: 8px; }
        .scale-slider { width: 100%; height: 8px; border-radius: 4px; background: var(--bg-tertiary); -webkit-appearance: none; appearance: none; cursor: pointer; }
        .scale-slider::-webkit-slider-thumb { -webkit-appearance: none; width: 20px; height: 20px; border-radius: 50%; background: linear-gradient(135deg, var(--accent-cyan), var(--accent-pink)); cursor: pointer; border: none; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3); }
        .scale-slider::-moz-range-thumb { width: 20px; height: 20px; border-radius: 50%; background: linear-gradient(135deg, var(--accent-cyan), var(--accent-pink)); cursor: pointer; border: none; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3); }
        .slider-labels { display: flex; justify-content: space-between; margin-top: 4px; font-size: 0.7rem; color: var(--text-muted); }
        .scale-preview { padding: 12px; background: rgba(0, 212, 255, 0.1); border: 1px solid rgba(0, 212, 255, 0.3); border-radius: 6px; font-family: monospace; font-size: 0.85rem; color: var(--accent-cyan); }
        .scale-preview.muted { background: rgba(255, 255, 255, 0.05); border-color: rgba(255, 255, 255, 0.1); color: var(--text-secondary); }
        .help-text { font-size: 0.8rem; color: var(--text-muted); }
        .help-text.center { text-align: center; }
        .no-image-notice { padding: 24px 16px; }
        .original-size-label { font-size: 0.85rem; color: var(--text-secondary); font-family: monospace; margin-bottom: 12px; padding: 8px 12px; background: rgba(255, 255, 255, 0.05); border-radius: 6px; }
        .aspect-ratio-toggle { display: flex; justify-content: space-between; align-items: center; }
        .toggle { width: 44px; height: 24px; border-radius: 12px; background: var(--bg-tertiary); border: none; cursor: pointer; position: relative; transition: background var(--transition-fast); }
        .toggle.on { background: var(--accent-cyan); }
        .toggle-handle { position: absolute; top: 2px; left: 2px; width: 20px; height: 20px; border-radius: 50%; background: white; transition: left var(--transition-fast); }
        .toggle.on .toggle-handle { left: 22px; }
        .dimension-inputs { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .dimension-input-group { display: flex; flex-direction: column; gap: 6px; }
        .algorithm-section { padding-top: 16px; border-top: 1px solid var(--bg-tertiary); }
        .radio-group { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }
        .radio-option { display: flex; align-items: center; gap: 8px; cursor: pointer; }
        .radio-option input[type="radio"] { width: 18px; height: 18px; accent-color: var(--accent-cyan); }
        .radio-label { font-family: monospace; color: var(--text-primary); }
        .radio-description { font-size: 0.8rem; color: var(--text-muted); margin-left: 26px; margin-top: -4px; }
        .preview-scaling-section { padding-top: 16px; border-top: 1px solid var(--bg-tertiary); }
        .preview-scaling-btn { width: 100%; padding: 12px; font-weight: 600; background: linear-gradient(135deg, var(--accent-cyan), var(--accent-pink)); color: var(--bg-primary); }
        .preview-scaling-btn:hover:not(:disabled) { box-shadow: 0 0 20px rgba(0, 212, 255, 0.4); }
        .preview-scaling-btn.active { background: var(--accent-pink); }
        .options-card { background: var(--bg-secondary); border: 1px solid var(--bg-tertiary); border-radius: 12px; padding: 20px; }
        .options-title { color: var(--accent-pink); font-size: 1rem; font-weight: 600; margin-bottom: 16px; }
        .checkbox-group { display: flex; flex-direction: column; gap: 12px; }
        .checkbox-option { display: flex; align-items: center; gap: 10px; cursor: pointer; }
        .checkbox-option input[type="checkbox"] { width: 18px; height: 18px; accent-color: var(--accent-cyan); }
        .checkbox-label { color: var(--text-primary); font-size: 0.9rem; }
        .progress-container { display: flex; flex-direction: column; gap: 8px; }
        .progress-header { display: flex; justify-content: space-between; font-size: 0.9rem; }
        .progress-stage { color: var(--text-secondary); text-transform: capitalize; }
        .progress-percent { color: var(--accent-cyan); }
        .progress-bar { height: 8px; background: rgba(255, 255, 255, 0.1); border-radius: 4px; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, var(--accent-cyan), var(--accent-pink)); transition: width 0.3s ease; }
        .action-buttons { display: flex; gap: 12px; padding-top: 8px; }
        .btn { padding: 12px 24px; border-radius: 8px; font-size: 1rem; font-weight: 600; cursor: pointer; transition: all var(--transition-fast); border: none; text-decoration: none; display: inline-flex; align-items: center; justify-content: center; }
        .btn-primary { flex: 1; background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple)); color: white; }
        .btn-primary:hover:not(:disabled) { box-shadow: var(--glow-cyan); transform: translateY(-1px); }
        .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
        .btn-secondary { background: transparent; border: 1px solid var(--bg-tertiary); color: var(--text-secondary); }
        .btn-secondary:hover:not(:disabled) { border-color: var(--accent-cyan); color: var(--accent-cyan); }
        .btn-danger { background: rgba(255, 100, 100, 0.2); border: 1px solid rgba(255, 100, 100, 0.4); color: #ff6b6b; }
        .btn-danger:hover { background: rgba(255, 100, 100, 0.3); }
        .success-container { max-width: 400px; margin: 0 auto; }
        .success-card { display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 32px; background: rgba(255, 255, 255, 0.05); border: 1px solid var(--bg-tertiary); border-radius: 16px; }
        .success-icon { font-size: 3rem; }
        .success-title { font-size: 1.25rem; font-weight: 600; color: var(--text-primary); }
        .success-preview { width: 176px; height: 176px; background: rgba(0, 0, 0, 0.3); border-radius: 12px; display: flex; align-items: center; justify-content: center; overflow: hidden; }
        .success-image { max-width: 100%; max-height: 100%; object-fit: contain; image-rendering: pixelated; }
        .success-name { font-weight: 600; color: var(--text-primary); }
        .success-canvas { font-size: 0.9rem; color: var(--text-secondary); }
        .pending-notice { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 16px; background: rgba(255, 200, 100, 0.1); border: 1px solid rgba(255, 200, 100, 0.3); border-radius: 12px; text-align: center; }
        .pending-icon { font-size: 1.5rem; }
        .pending-text { font-size: 0.9rem; color: var(--text-primary); }
        .success-buttons { display: flex; gap: 12px; margin-top: 8px; }
        .dialog-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.8); display: flex; align-items: center; justify-content: center; z-index: 100; padding: 24px; }
        .dialog { background: var(--bg-primary); border: 1px solid var(--bg-tertiary); border-radius: 16px; padding: 24px; max-width: 400px; width: 100%; }
        .dialog-title { font-size: 1.25rem; font-weight: 600; color: var(--text-primary); margin-bottom: 12px; }
        .dialog-description { color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 24px; }
        .dialog-buttons { display: flex; gap: 12px; justify-content: flex-end; }
        .loading-state { text-align: center; padding: 48px; color: var(--text-muted); }
        @media (max-width: 480px) { .submit-container { padding: 16px; } .page-title { font-size: 1.5rem; } .action-buttons { flex-direction: column; } .success-buttons { flex-direction: column; width: 100%; } .success-buttons .btn { width: 100%; } }
      `}</style>
    </Layout>
  );
}

// Export with SSR disabled to avoid "window is not defined" errors
export default dynamic(() => Promise.resolve(SubmitPageContent), {
  ssr: false,
  loading: () => (
    <Layout title="Submit Artwork" description="Upload your pixel art">
      <div style={{ maxWidth: '800px', margin: '0 auto', padding: '24px', textAlign: 'center' }}>
        <p style={{ color: 'var(--text-muted)' }}>Loading upload tool...</p>
      </div>
    </Layout>
  ),
});

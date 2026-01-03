import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Layout from '../components/Layout';
import { authenticatedFetch, clearTokens } from '../lib/api';

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

const MAX_FILE_SIZE_BYTES = (() => {
  const raw = process.env.NEXT_PUBLIC_MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES || '5242880';
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : 5242880;
})();

function formatMiB(bytes: number): string {
  const mib = bytes / (1024 * 1024);
  // If it’s effectively an integer, render without decimals.
  if (Math.abs(mib - Math.round(mib)) < 1e-9) return `${Math.round(mib)} MiB`;
  return `${mib.toFixed(2)} MiB`;
}

const MAX_CANVAS_SIZE = 256;
const ALLOWED_TYPES = ['image/png', 'image/gif', 'image/webp', 'image/bmp', 'image/x-ms-bmp'];

export default function SubmitPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageDimensions, setImageDimensions] = useState<{ width: number; height: number } | null>(null);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [fromPiskel, setFromPiskel] = useState(false);
  
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [hashtags, setHashtags] = useState('');
  
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadedArtwork, setUploadedArtwork] = useState<UploadedArtwork | null>(null);
  
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

  const validateFile = useCallback((file: File): ValidationError[] => {
    const errors: ValidationError[] = [];
    
    // Check file size
    if (file.size > MAX_FILE_SIZE_BYTES) {
      const sizeMiB = formatMiB(file.size);
      errors.push({
        type: 'size',
        message: `File size (${sizeMiB}) exceeds maximum of ${formatMiB(MAX_FILE_SIZE_BYTES)}`,
      });
    }
    
    // Check file type
    if (!ALLOWED_TYPES.includes(file.type)) {
      errors.push({
        type: 'format',
        message: 'Invalid format. Please use PNG, GIF, WebP, or BMP',
      });
    }
    
    return errors;
  }, []);

  const validateImageDimensions = useCallback((width: number, height: number): ValidationError[] => {
    const errors: ValidationError[] = [];
    
    // Check minimum size
    if (width < 1 || height < 1) {
      errors.push({
        type: 'dimensions',
        message: 'Image dimensions must be at least 1x1',
      });
      return errors;
    }
    
    // Check if either dimension exceeds 256
    if (width > 256 || height > 256) {
      errors.push({
        type: 'dimensions',
        message: `Image dimensions exceed maximum of 256x256. Got ${width}x${height}`,
      });
      return errors;
    }
    
    // Define allowed sizes for dimensions under 128x128
    // Includes both orientations (e.g., 8x16 and 16x8 are both allowed)
    const allowedSizes = [
      [8, 8], [8, 16], [16, 8], [8, 32], [32, 8],
      [16, 16], [16, 32], [32, 16],
      [32, 32], [32, 64], [64, 32],
      [64, 64], [64, 128], [128, 64],
    ];
    
    // If both dimensions are >= 128, any size is allowed (up to 256x256)
    if (width >= 128 && height >= 128) {
      return errors;
    }
    
    // Otherwise, check if the size is in the allowed list
    // This covers cases where at least one dimension is < 128
    const isAllowed = allowedSizes.some(([w, h]) => 
      width === w && height === h
    );
    
    if (!isAllowed) {
      // Show unique sizes in error message (group by min/max to show both orientations)
      const sizeSet = new Set<string>();
      allowedSizes.forEach(([w, h]) => {
        sizeSet.add(`${w}x${h}`);
      });
      const allowedStr = Array.from(sizeSet).sort().join(', ');
      errors.push({
        type: 'dimensions',
        message: `Image size ${width}x${height} is not allowed. Under 128x128, only these sizes are allowed (rotations included): ${allowedStr}`,
      });
    }
    
    return errors;
  }, []);

  // Check for Piskel export data (after validation functions are defined)
  useEffect(() => {
    if (router.query.from !== 'piskel') return;
    
    try {
      const exportDataStr = sessionStorage.getItem('piskel_export');
      if (!exportDataStr) return;
      
      const exportData = JSON.parse(exportDataStr);
      
      // Check if data is recent (within 5 minutes)
      if (Date.now() - exportData.timestamp > 5 * 60 * 1000) {
        sessionStorage.removeItem('piskel_export');
        return;
      }
      
      setFromPiskel(true);
      
      // Convert base64 back to File
      const byteString = atob(exportData.imageData.split(',')[1]);
      const mimeType = exportData.imageData.split(',')[0].split(':')[1].split(';')[0];
      const ab = new ArrayBuffer(byteString.length);
      const ia = new Uint8Array(ab);
      for (let i = 0; i < byteString.length; i++) {
        ia[i] = byteString.charCodeAt(i);
      }
      const blob = new Blob([ab], { type: mimeType });
      const file = new File([blob], `${exportData.name || 'artwork'}.gif`, { type: mimeType });
      
      // Set file and preview
      setSelectedFile(file);
      setPreviewUrl(exportData.imageData);
      setImageDimensions({ width: exportData.width, height: exportData.height });
      setTitle(exportData.name || '');
      
      // Validate
      const fileErrors = validateFile(file);
      const dimErrors = validateImageDimensions(exportData.width, exportData.height);
      setValidationErrors([...fileErrors, ...dimErrors]);
      
      // Clear the stored data
      sessionStorage.removeItem('piskel_export');
    } catch (err) {
      console.error('Failed to load Piskel export:', err);
    }
  }, [router.query.from, validateFile, validateImageDimensions]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    // Reset state
    setUploadError(null);
    setUploadedArtwork(null);
    
    // Validate file
    const fileErrors = validateFile(file);
    
    // Load image to check dimensions
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);
    
    img.onload = () => {
      const dimensionErrors = validateImageDimensions(img.width, img.height);
      const allErrors = [...fileErrors, ...dimensionErrors];
      
      setSelectedFile(file);
      setPreviewUrl(objectUrl);
      setImageDimensions({ width: img.width, height: img.height });
      setValidationErrors(allErrors);
      
      // Set default title from filename if empty
      if (!title) {
        const nameWithoutExt = file.name.replace(/\.[^/.]+$/, '');
        setTitle(nameWithoutExt);
      }
    };
    
    img.onerror = () => {
      setValidationErrors([{
        type: 'format',
        message: 'Could not read image file. Please ensure it is a valid image.',
      }]);
      URL.revokeObjectURL(objectUrl);
    };
    
    img.src = objectUrl;
  }, [title, validateFile, validateImageDimensions]);

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    
    const file = e.dataTransfer.files[0];
    if (file && fileInputRef.current) {
      // Create a DataTransfer object to set files
      const dt = new DataTransfer();
      dt.items.add(file);
      fileInputRef.current.files = dt.files;
      
      // Trigger the change handler
      const event = { target: fileInputRef.current } as React.ChangeEvent<HTMLInputElement>;
      handleFileSelect(event);
    }
  }, [handleFileSelect]);

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedFile(null);
    setPreviewUrl(null);
    setImageDimensions(null);
    setValidationErrors([]);
    setTitle('');
    setDescription('');
    setHashtags('');
    setUploadError(null);
    setUploadedArtwork(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  const handleSubmit = async () => {
    if (!selectedFile || validationErrors.length > 0) return;
    
    setUploading(true);
    setUploadError(null);
    
    try {
      const formData = new FormData();
      formData.append('image', selectedFile);
      formData.append('title', title.trim() || selectedFile.name.replace(/\.[^/.]+$/, ''));
      formData.append('description', description.trim());
      formData.append('hashtags', hashtags.trim());
      
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
      
    } catch (error) {
      console.error('Upload error:', error);
      setUploadError(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const isValid = selectedFile && validationErrors.length === 0 && title.trim().length > 0;

  if (!isAuthenticated) {
    return (
      <Layout title="Submit Artwork" description="Upload your pixel art">
        <div className="submit-container">
          <div className="loading-state">Loading...</div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title="Submit Artwork" description="Upload your pixel art">
      <div className="submit-container">
        <h1 className="page-title">
          {fromPiskel ? '🖌️ Publish Artwork' : 'Submit Artwork'}
        </h1>
        
        {fromPiskel && (
          <div className="piskel-notice">
            <span>✨ Artwork from Piskel ready to publish!</span>
          </div>
        )}

        {uploadedArtwork ? (
          <div className="success-state">
            <div className="success-icon">✅</div>
            <h2>Artwork Uploaded!</h2>
            <div className="uploaded-preview">
              <img 
                src={`${API_BASE_URL}${uploadedArtwork.art_url}`}
                alt={uploadedArtwork.title}
                className="preview-image pixel-art"
              />
            </div>
            <p className="artwork-title">{uploadedArtwork.title}</p>
            <p className="artwork-canvas">{uploadedArtwork.canvas}</p>
            
            {!uploadedArtwork.public_visibility && (
              <div className="pending-notice">
                <span className="pending-icon">⏳</span>
                <p>Your artwork is awaiting moderator approval for public visibility.</p>
                <p className="pending-hint">It will appear on your profile, but not in Recent Artworks until approved.</p>
              </div>
            )}
            
            <div className="success-actions">
              <button onClick={() => router.push(`/p/${uploadedArtwork.public_sqid}`)} className="btn-primary">
                View Artwork
              </button>
              <button onClick={clearSelection} className="btn-secondary">
                Upload Another
              </button>
            </div>
          </div>
        ) : (
          <>
            {/* Upload Zone */}
            <div 
              className={`upload-zone ${selectedFile ? 'has-file' : ''} ${validationErrors.length > 0 ? 'has-errors' : ''}`}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/gif,image/webp,image/bmp"
                onChange={handleFileSelect}
                className="file-input"
                id="file-upload"
              />
              
              {selectedFile && previewUrl ? (
                <div className="file-preview">
                  <div className="preview-container">
                    <img 
                      src={previewUrl}
                      alt="Preview"
                      className="preview-image pixel-art"
                    />
                  </div>
                  <div className="file-info">
                    <span className="file-name">{selectedFile.name}</span>
                    {imageDimensions && (
                      <span className="file-dimensions">{imageDimensions.width}x{imageDimensions.height}</span>
                    )}
                    <span className="file-size">{(selectedFile.size / 1024).toFixed(1)} KB</span>
                  </div>
                  <button onClick={clearSelection} className="clear-btn" type="button">
                    ✕ Clear
                  </button>
                </div>
              ) : (
                <label htmlFor="file-upload" className="upload-label">
                  <span className="upload-icon">📁</span>
                  <span className="upload-text">Drop image here or click to select</span>
                  <span className="upload-hint">PNG, GIF, WebP, or BMP • Max {formatMiB(MAX_FILE_SIZE_BYTES)}</span>
                </label>
              )}
            </div>

            <div className="size-rules-link">
              <Link href="/size_rules">See size rules</Link>
            </div>

            {/* Validation Errors */}
            {validationErrors.length > 0 && (
              <div className="validation-errors">
                {validationErrors.map((error, index) => (
                  <div key={index} className="error-item">
                    <span className="error-icon">⚠️</span>
                    <span>{error.message}</span>
                  </div>
                ))}
              </div>
            )}
            
            {/* Form Fields */}
            {selectedFile && validationErrors.length === 0 && (
              <div className="form-section">
                <div className="form-field">
                  <label htmlFor="title">Title *</label>
                  <input
                    id="title"
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Give your artwork a title"
                    maxLength={200}
                    required
                  />
                  <span className="char-count">{title.length}/200</span>
                </div>
                
                <div className="form-field">
                  <label htmlFor="description">Description</label>
                  <textarea
                    id="description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Describe your artwork (optional)"
                    maxLength={5000}
                    rows={3}
                  />
                  <span className="char-count">{description.length}/5000</span>
                </div>
                
                <div className="form-field">
                  <label htmlFor="hashtags">Hashtags</label>
                  <input
                    id="hashtags"
                    type="text"
                    value={hashtags}
                    onChange={(e) => setHashtags(e.target.value)}
                    placeholder="pixel, retro, game (comma separated)"
                  />
                  <span className="field-hint">Separate hashtags with commas</span>
                </div>
                
                {uploadError && (
                  <div className="upload-error">
                    <span className="error-icon">❌</span>
                    <span>{uploadError}</span>
                  </div>
                )}
                
                <button
                  onClick={handleSubmit}
                  disabled={!isValid || uploading}
                  className="submit-btn"
                >
                  {uploading ? 'Uploading...' : '🚀 Submit Artwork'}
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <style jsx>{`
        .submit-container {
          max-width: 600px;
          margin: 0 auto;
          padding: 24px;
        }

        .page-title {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          margin-bottom: 24px;
          text-align: center;
        }

        .piskel-notice {
          text-align: center;
          margin-bottom: 20px;
          padding: 12px 16px;
          background: linear-gradient(135deg, rgba(255, 110, 180, 0.15), rgba(180, 78, 255, 0.15));
          border: 1px solid rgba(255, 110, 180, 0.3);
          border-radius: 12px;
          color: var(--accent-pink);
          font-weight: 500;
        }

        .loading-state {
          text-align: center;
          padding: 48px;
          color: var(--text-muted);
        }

        /* Upload Zone */
        .upload-zone {
          position: relative;
          border: 2px dashed var(--bg-tertiary);
          border-radius: 16px;
          padding: 32px;
          text-align: center;
          transition: all var(--transition-fast);
          background: var(--bg-secondary);
        }

        .upload-zone:hover,
        .upload-zone:focus-within {
          border-color: var(--accent-cyan);
          background: rgba(0, 212, 255, 0.05);
        }

        .upload-zone.has-file {
          border-style: solid;
          border-color: var(--accent-cyan);
        }

        .upload-zone.has-errors {
          border-color: #ef4444;
        }

        .file-input {
          position: absolute;
          inset: 0;
          opacity: 0;
          cursor: pointer;
        }

        .upload-zone.has-file .file-input {
          pointer-events: none;
        }

        .upload-label {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
          cursor: pointer;
          padding: 24px;
        }

        .upload-icon {
          font-size: 3rem;
        }

        .upload-text {
          font-size: 1.1rem;
          color: var(--text-secondary);
        }

        .upload-hint {
          font-size: 0.85rem;
          color: var(--text-muted);
        }

        .size-rules-link {
          text-align: center;
          margin-top: 12px;
        }

        .size-rules-link :global(a) {
          color: var(--accent-cyan);
          text-decoration: none;
          font-size: 0.9rem;
        }

        .size-rules-link :global(a:hover) {
          text-decoration: underline;
        }

        /* File Preview */
        .file-preview {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 16px;
          width: 100%;
        }

        .preview-container {
          width: 100%;
          background: var(--bg-tertiary);
          border-radius: 12px;
          overflow: hidden;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .preview-image {
          width: 100%;
          height: auto;
          display: block;
          image-rendering: -webkit-optimize-contrast !important;
          image-rendering: -moz-crisp-edges !important;
          image-rendering: crisp-edges !important;
          image-rendering: pixelated !important;
          -ms-interpolation-mode: nearest-neighbor !important;
        }

        .file-info {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          justify-content: center;
          color: var(--text-secondary);
          font-size: 0.9rem;
        }

        .file-name {
          font-weight: 500;
          color: var(--text-primary);
        }

        .file-dimensions,
        .file-size {
          background: var(--bg-tertiary);
          padding: 2px 8px;
          border-radius: 4px;
        }

        .clear-btn {
          padding: 8px 16px;
          background: var(--bg-tertiary);
          color: var(--text-secondary);
          border-radius: 8px;
          font-size: 0.9rem;
          transition: all var(--transition-fast);
        }

        .clear-btn:hover {
          background: rgba(239, 68, 68, 0.2);
          color: #ef4444;
        }

        /* Validation Errors */
        .validation-errors {
          margin-top: 16px;
          padding: 16px;
          background: rgba(239, 68, 68, 0.1);
          border: 1px solid rgba(239, 68, 68, 0.3);
          border-radius: 12px;
        }

        .error-item {
          display: flex;
          align-items: center;
          gap: 8px;
          color: #ef4444;
          font-size: 0.9rem;
        }

        .error-item + .error-item {
          margin-top: 8px;
        }

        /* Form Section */
        .form-section {
          margin-top: 24px;
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .form-field {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .form-field label {
          font-size: 0.9rem;
          font-weight: 500;
          color: var(--text-secondary);
        }

        .form-field input,
        .form-field textarea {
          padding: 12px 16px;
          font-size: 1rem;
          background: var(--bg-secondary);
          border: 1px solid var(--bg-tertiary);
          border-radius: 10px;
          color: var(--text-primary);
          transition: all var(--transition-fast);
        }

        .form-field input:focus,
        .form-field textarea:focus {
          outline: none;
          border-color: var(--accent-cyan);
          box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.1);
        }

        .form-field textarea {
          resize: vertical;
          min-height: 80px;
        }

        .char-count,
        .field-hint {
          font-size: 0.75rem;
          color: var(--text-muted);
          text-align: right;
        }

        .field-hint {
          text-align: left;
        }

        /* Upload Error */
        .upload-error {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px 16px;
          background: rgba(239, 68, 68, 0.1);
          border: 1px solid rgba(239, 68, 68, 0.3);
          border-radius: 10px;
          color: #ef4444;
          font-size: 0.9rem;
        }

        /* Submit Button */
        .submit-btn {
          width: 100%;
          padding: 16px;
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          font-size: 1.1rem;
          font-weight: 600;
          border-radius: 12px;
          transition: all var(--transition-fast);
        }

        .submit-btn:hover:not(:disabled) {
          box-shadow: 0 0 30px rgba(255, 110, 180, 0.4);
          transform: translateY(-2px);
        }

        .submit-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        /* Success State */
        .success-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 16px;
          padding: 32px;
          background: var(--bg-secondary);
          border-radius: 16px;
          text-align: center;
        }

        .success-icon {
          font-size: 3rem;
        }

        .success-state h2 {
          font-size: 1.5rem;
          color: var(--text-primary);
          margin: 0;
        }

        .uploaded-preview {
          width: 180px;
          height: 180px;
          background: var(--bg-tertiary);
          border-radius: 12px;
          overflow: hidden;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .artwork-title {
          font-size: 1.1rem;
          font-weight: 500;
          color: var(--text-primary);
          margin: 0;
        }

        .artwork-canvas {
          font-size: 0.9rem;
          color: var(--text-muted);
          margin: 0;
        }

        .pending-notice {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 8px;
          padding: 16px 24px;
          background: rgba(245, 158, 11, 0.1);
          border: 1px solid rgba(245, 158, 11, 0.3);
          border-radius: 12px;
          max-width: 100%;
        }

        .pending-icon {
          font-size: 1.5rem;
        }

        .pending-notice p {
          margin: 0;
          color: var(--text-secondary);
          font-size: 0.9rem;
        }

        .pending-hint {
          color: var(--text-muted) !important;
          font-size: 0.8rem !important;
        }

        .success-actions {
          display: flex;
          gap: 12px;
          margin-top: 8px;
        }

        .btn-primary,
        .btn-secondary {
          padding: 12px 24px;
          font-size: 1rem;
          font-weight: 500;
          border-radius: 10px;
          transition: all var(--transition-fast);
        }

        .btn-primary {
          background: var(--accent-cyan);
          color: var(--bg-primary);
        }

        .btn-primary:hover {
          box-shadow: var(--glow-cyan);
        }

        .btn-secondary {
          background: var(--bg-tertiary);
          color: var(--text-secondary);
        }

        .btn-secondary:hover {
          background: var(--accent-purple);
          color: white;
        }

        @media (max-width: 480px) {
          .submit-container {
            padding: 16px;
          }

          .page-title {
            font-size: 1.5rem;
          }

          .upload-zone {
            padding: 24px 16px;
          }

          .success-actions {
            flex-direction: column;
            width: 100%;
          }

          .btn-primary,
          .btn-secondary {
            width: 100%;
          }
        }
      `}</style>
    </Layout>
  );
}


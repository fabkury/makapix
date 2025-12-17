import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';
import { authenticatedFetch, authenticatedRequestJson, clearTokens, getAccessToken } from '../lib/api';

interface User {
  id: number;
  user_key: string;
  public_sqid: string | null;
  handle: string;
  bio?: string;
  avatar_url?: string;
  email: string;
  welcome_completed: boolean;
}

interface HandleCheckResponse {
  handle: string;
  available: boolean;
  message: string;
}

export default function NewAccountWelcomePage() {
  const router = useRouter();
  
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Form state
  const [editHandle, setEditHandle] = useState('');
  const [editBio, setEditBio] = useState('');
  const [pendingAvatarUrl, setPendingAvatarUrl] = useState<string | null>(null);
  const [removeAvatar, setRemoveAvatar] = useState(false);
  
  // Handle availability check
  const [handleStatus, setHandleStatus] = useState<'idle' | 'checking' | 'available' | 'taken' | 'invalid'>('idle');
  const [handleMessage, setHandleMessage] = useState<string>('');
  
  // Save state
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  
  // Avatar upload state
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);
  const [avatarUploadError, setAvatarUploadError] = useState<string | null>(null);
  const [isAvatarDragOver, setIsAvatarDragOver] = useState(false);
  const avatarInputRef = useRef<HTMLInputElement>(null);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Fetch current user
  useEffect(() => {
    const fetchUser = async () => {
      // Check if user is logged in
      const token = getAccessToken();
      if (!token) {
        router.push('/auth');
        return;
      }
      
      try {
        const response = await authenticatedFetch(`${API_BASE_URL}/api/auth/me`);
        
        if (response.status === 401) {
          clearTokens();
          router.push('/auth');
          return;
        }
        
        if (!response.ok) {
          throw new Error('Failed to fetch user data');
        }
        
        const data = await response.json();
        const userData = data.user as User;
        
        // If user has already completed welcome, redirect to their profile
        if (userData.welcome_completed) {
          router.push(`/u/${userData.public_sqid}`);
          return;
        }
        
        setUser(userData);
        setEditHandle(userData.handle);
        setEditBio(userData.bio || '');
        setPendingAvatarUrl(userData.avatar_url || null);
        setLoading(false);
      } catch (err) {
        console.error('Error fetching user:', err);
        setError('Failed to load your account. Please try logging in again.');
        setLoading(false);
      }
    };

    fetchUser();
  }, [router, API_BASE_URL]);

  // Check handle availability
  const checkHandleAvailability = async () => {
    if (!editHandle.trim()) {
      setHandleStatus('invalid');
      setHandleMessage('Handle cannot be empty');
      return;
    }
    
    setHandleStatus('checking');
    setHandleMessage('');
    
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/auth/check-handle-availability`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ handle: editHandle.trim() }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to check handle availability');
      }
      
      const data: HandleCheckResponse = await response.json();
      
      if (data.available) {
        setHandleStatus('available');
        setHandleMessage(data.message);
      } else {
        setHandleStatus(data.message.includes('Invalid') ? 'invalid' : 'taken');
        setHandleMessage(data.message);
      }
    } catch (err) {
      console.error('Error checking handle:', err);
      setHandleStatus('invalid');
      setHandleMessage('Failed to check availability');
    }
  };

  // Handle avatar upload
  const uploadAvatarFile = async (file: File) => {
    if (!user) return;
    
    setIsUploadingAvatar(true);
    setAvatarUploadError(null);
    
    // Validate file type
    const allowedTypes = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      setAvatarUploadError('Please upload a PNG, JPEG, GIF, or WebP image');
      setIsUploadingAvatar(false);
      return;
    }
    
    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      setAvatarUploadError('Image must be less than 5MB');
      setIsUploadingAvatar(false);
      return;
    }
    
    try {
      const formData = new FormData();
      formData.append('image', file);
      
      const response = await authenticatedFetch(`${API_BASE_URL}/api/user/${user.user_key}/avatar`, {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to upload avatar');
      }
      
      const updatedUser = await response.json();
      setPendingAvatarUrl(updatedUser.avatar_url);
      setRemoveAvatar(false);
    } catch (err) {
      console.error('Error uploading avatar:', err);
      setAvatarUploadError(err instanceof Error ? err.message : 'Failed to upload avatar');
    } finally {
      setIsUploadingAvatar(false);
    }
  };

  const handleAvatarDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsAvatarDragOver(false);
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      uploadAvatarFile(files[0]);
    }
  };

  const handleAvatarSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      uploadAvatarFile(files[0]);
    }
  };

  const handleRemoveAvatar = async () => {
    if (!user) return;
    
    setIsUploadingAvatar(true);
    setAvatarUploadError(null);
    
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/user/${user.user_key}/avatar`, {
        method: 'DELETE',
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to remove avatar');
      }
      
      setPendingAvatarUrl(null);
      setRemoveAvatar(true);
    } catch (err) {
      console.error('Error removing avatar:', err);
      setAvatarUploadError(err instanceof Error ? err.message : 'Failed to remove avatar');
    } finally {
      setIsUploadingAvatar(false);
    }
  };

  // Skip for now - just mark welcome as completed and redirect
  const handleSkip = async () => {
    if (!user) return;
    
    try {
      await authenticatedFetch(`${API_BASE_URL}/api/auth/complete-welcome`, {
        method: 'POST',
      });
      
      router.push(`/u/${user.public_sqid}`);
    } catch (err) {
      console.error('Error completing welcome:', err);
      // Still redirect even if marking complete fails
      router.push(`/u/${user.public_sqid}`);
    }
  };

  // Save changes and mark welcome as completed
  const handleSave = async () => {
    if (!user) return;
    
    setIsSaving(true);
    setSaveError(null);
    
    try {
      const payload: { handle?: string; bio?: string } = {};
      
      // Only include handle if it changed
      const trimmedHandle = editHandle.trim();
      if (trimmedHandle !== user.handle) {
        // If handle is different, check availability first
        if (handleStatus !== 'available' && trimmedHandle.toLowerCase() !== user.handle.toLowerCase()) {
          setSaveError('Please use the "Check" button to verify your handle is available');
          setIsSaving(false);
          return;
        }
        payload.handle = trimmedHandle;
      }
      
      // Only include bio if it changed
      if (editBio !== (user.bio || '')) {
        payload.bio = editBio;
      }
      
      // If there are changes to save
      if (Object.keys(payload).length > 0) {
        const response = await authenticatedFetch(`${API_BASE_URL}/api/user/${user.user_key}`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        });
        
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          if (response.status === 409) {
            setSaveError('This handle is already taken. Please use the "Check" button to verify availability.');
            setIsSaving(false);
            return;
          } else if (response.status === 400) {
            setSaveError(errorData.detail || 'Invalid handle format');
            setIsSaving(false);
            return;
          }
          throw new Error(errorData.detail || 'Failed to save changes');
        }
      }
      
      // Mark welcome as completed
      await authenticatedFetch(`${API_BASE_URL}/api/auth/complete-welcome`, {
        method: 'POST',
      });
      
      // Redirect to profile
      router.push(`/u/${user.public_sqid}`);
    } catch (err) {
      console.error('Error saving:', err);
      setSaveError(err instanceof Error ? err.message : 'Failed to save changes');
      setIsSaving(false);
    }
  };

  // Reset handle status when handle changes
  useEffect(() => {
    if (user && editHandle !== user.handle) {
      setHandleStatus('idle');
      setHandleMessage('');
    }
  }, [editHandle, user]);

  const getAvatarUrl = (url: string | null | undefined): string => {
    if (!url) return '';
    if (url.startsWith('http://') || url.startsWith('https://')) return url;
    return `${API_BASE_URL}${url.startsWith('/') ? '' : '/'}${url}`;
  };

  if (loading) {
    return (
      <Layout title="Welcome to Makapix">
        <div className="page-container">
          <div className="loading-card">
            <div className="spinner">⏳</div>
            <p>Loading your account...</p>
          </div>
        </div>
        <style jsx>{`
          .page-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - var(--header-offset));
            padding: 24px;
          }
          .loading-card {
            text-align: center;
            color: var(--text-secondary);
          }
          .spinner {
            font-size: 3rem;
            animation: pulse 1.5s ease-in-out infinite;
          }
          @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
          }
        `}</style>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout title="Welcome to Makapix">
        <div className="page-container">
          <div className="error-card">
            <div className="icon">❌</div>
            <h2>Something went wrong</h2>
            <p>{error}</p>
            <button onClick={() => router.push('/auth')} className="primary-button">
              Go to Login
            </button>
          </div>
        </div>
        <style jsx>{`
          .page-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - var(--header-offset));
            padding: 24px;
          }
          .error-card {
            text-align: center;
            background: var(--bg-secondary);
            border-radius: 16px;
            padding: 40px 32px;
            max-width: 450px;
          }
          .icon {
            font-size: 3rem;
            margin-bottom: 16px;
          }
          h2 {
            color: var(--text-primary);
            margin-bottom: 12px;
          }
          p {
            color: var(--text-secondary);
            margin-bottom: 24px;
          }
          .primary-button {
            padding: 14px 32px;
            background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
            color: white;
            font-size: 1rem;
            font-weight: 600;
            border-radius: 10px;
            border: none;
            cursor: pointer;
          }
        `}</style>
      </Layout>
    );
  }

  return (
    <Layout title="Welcome to Makapix">
      <div className="page-container">
        <div className="welcome-card">
          <div className="header">
            <div className="icon">🎨</div>
            <h1>Welcome to Makapix!</h1>
            <p className="subtitle">Let&apos;s set up your profile. You can always change these later.</p>
          </div>

          <div className="form-section">
            {/* Avatar */}
            <div className="field-group">
              <label>Profile Picture</label>
              <div 
                className={`avatar-upload ${isAvatarDragOver ? 'drag-over' : ''} ${isUploadingAvatar ? 'uploading' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setIsAvatarDragOver(true); }}
                onDragLeave={() => setIsAvatarDragOver(false)}
                onDrop={handleAvatarDrop}
                onClick={() => avatarInputRef.current?.click()}
              >
                {pendingAvatarUrl ? (
                  <img 
                    src={getAvatarUrl(pendingAvatarUrl)} 
                    alt="Avatar" 
                    className="avatar-preview"
                  />
                ) : (
                  <div className="avatar-placeholder">
                    <span>📷</span>
                    <span className="hint">Click or drag to upload</span>
                  </div>
                )}
                {isUploadingAvatar && (
                  <div className="upload-overlay">
                    <span>Uploading...</span>
                  </div>
                )}
              </div>
              <input
                ref={avatarInputRef}
                type="file"
                accept="image/png,image/jpeg,image/gif,image/webp"
                onChange={handleAvatarSelect}
                style={{ display: 'none' }}
              />
              {pendingAvatarUrl && (
                <button 
                  type="button" 
                  className="remove-avatar-btn"
                  onClick={(e) => { e.stopPropagation(); handleRemoveAvatar(); }}
                  disabled={isUploadingAvatar}
                >
                  Remove avatar
                </button>
              )}
              {avatarUploadError && (
                <p className="field-error">{avatarUploadError}</p>
              )}
            </div>

            {/* Handle */}
            <div className="field-group">
              <label htmlFor="handle">Handle</label>
              <div className="handle-input-row">
                <div className="handle-input-wrapper">
                  <span className="handle-prefix">@</span>
                  <input
                    id="handle"
                    type="text"
                    value={editHandle}
                    onChange={(e) => setEditHandle(e.target.value)}
                    placeholder="your-handle"
                    maxLength={32}
                    className={handleStatus === 'available' ? 'valid' : handleStatus === 'taken' || handleStatus === 'invalid' ? 'invalid' : ''}
                  />
                </div>
                <button 
                  type="button" 
                  className="check-btn"
                  onClick={checkHandleAvailability}
                  disabled={handleStatus === 'checking' || !editHandle.trim()}
                >
                  {handleStatus === 'checking' ? '...' : 'Check'}
                </button>
              </div>
              {handleMessage && (
                <p className={`field-message ${handleStatus === 'available' ? 'success' : 'error'}`}>
                  {handleStatus === 'available' ? '✓' : '✗'} {handleMessage}
                </p>
              )}
              <p className="field-hint">
                Your handle can contain any characters (letters, emoji, etc.) up to 32 characters.
              </p>
            </div>

            {/* Bio */}
            <div className="field-group">
              <label htmlFor="bio">Bio</label>
              <textarea
                id="bio"
                value={editBio}
                onChange={(e) => setEditBio(e.target.value)}
                placeholder="Tell us about yourself..."
                maxLength={1000}
                rows={4}
              />
              <p className="field-hint">{editBio.length}/1000 characters</p>
            </div>

            {saveError && (
              <div className="save-error">
                {saveError}
              </div>
            )}
          </div>

          <div className="actions">
            <button 
              type="button" 
              className="skip-btn"
              onClick={handleSkip}
              disabled={isSaving}
            >
              Skip for now
            </button>
            <button 
              type="button" 
              className="save-btn"
              onClick={handleSave}
              disabled={isSaving}
            >
              {isSaving ? 'Saving...' : 'Save changes'}
            </button>
          </div>
        </div>
      </div>

      <style jsx>{`
        .page-container {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: calc(100vh - var(--header-offset));
          padding: 24px;
        }

        .welcome-card {
          width: 100%;
          max-width: 520px;
          background: var(--bg-secondary);
          border-radius: 20px;
          padding: 40px 32px;
        }

        .header {
          text-align: center;
          margin-bottom: 32px;
        }

        .header .icon {
          font-size: 4rem;
          margin-bottom: 16px;
        }

        .header h1 {
          font-size: 1.75rem;
          color: var(--text-primary);
          margin: 0 0 8px 0;
        }

        .header .subtitle {
          color: var(--text-secondary);
          margin: 0;
          font-size: 1rem;
        }

        .form-section {
          display: flex;
          flex-direction: column;
          gap: 24px;
          margin-bottom: 32px;
        }

        .field-group {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .field-group label {
          font-weight: 600;
          color: var(--text-primary);
          font-size: 0.95rem;
        }

        .avatar-upload {
          width: 120px;
          height: 120px;
          border-radius: 50%;
          border: 3px dashed var(--border-color);
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: all 0.2s ease;
          overflow: hidden;
          position: relative;
        }

        .avatar-upload:hover {
          border-color: var(--accent-pink);
          background: rgba(255, 110, 180, 0.05);
        }

        .avatar-upload.drag-over {
          border-color: var(--accent-pink);
          background: rgba(255, 110, 180, 0.1);
        }

        .avatar-preview {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }

        .avatar-placeholder {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
          color: var(--text-muted);
        }

        .avatar-placeholder span:first-child {
          font-size: 2rem;
        }

        .avatar-placeholder .hint {
          font-size: 0.7rem;
          text-align: center;
        }

        .upload-overlay {
          position: absolute;
          inset: 0;
          background: rgba(0, 0, 0, 0.7);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-size: 0.9rem;
        }

        .remove-avatar-btn {
          width: 120px;
          padding: 6px 12px;
          background: transparent;
          border: 1px solid var(--border-color);
          border-radius: 6px;
          color: var(--text-secondary);
          font-size: 0.8rem;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .remove-avatar-btn:hover:not(:disabled) {
          border-color: #f87171;
          color: #f87171;
        }

        .remove-avatar-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .handle-input-row {
          display: flex;
          gap: 8px;
        }

        .handle-input-wrapper {
          flex: 1;
          display: flex;
          align-items: center;
          background: var(--bg-tertiary);
          border-radius: 10px;
          border: 2px solid transparent;
          transition: border-color 0.2s ease;
        }

        .handle-input-wrapper:focus-within {
          border-color: var(--accent-pink);
        }

        .handle-prefix {
          padding-left: 14px;
          color: var(--text-muted);
          font-size: 1rem;
        }

        .handle-input-wrapper input {
          flex: 1;
          padding: 12px 14px 12px 4px;
          background: transparent;
          border: none;
          color: var(--text-primary);
          font-size: 1rem;
          outline: none;
        }

        .handle-input-wrapper input.valid {
          color: #4ade80;
        }

        .handle-input-wrapper input.invalid {
          color: #f87171;
        }

        .check-btn {
          padding: 12px 20px;
          background: var(--bg-tertiary);
          border: 2px solid var(--border-color);
          border-radius: 10px;
          color: var(--text-primary);
          font-size: 0.95rem;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
          white-space: nowrap;
        }

        .check-btn:hover:not(:disabled) {
          border-color: var(--accent-pink);
          color: var(--accent-pink);
        }

        .check-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .field-message {
          font-size: 0.85rem;
          margin: 0;
        }

        .field-message.success {
          color: #4ade80;
        }

        .field-message.error {
          color: #f87171;
        }

        .field-hint {
          font-size: 0.8rem;
          color: var(--text-muted);
          margin: 0;
        }

        .field-error {
          font-size: 0.85rem;
          color: #f87171;
          margin: 0;
        }

        textarea {
          padding: 14px;
          background: var(--bg-tertiary);
          border: 2px solid transparent;
          border-radius: 10px;
          color: var(--text-primary);
          font-size: 1rem;
          resize: vertical;
          min-height: 100px;
          font-family: inherit;
        }

        textarea:focus {
          outline: none;
          border-color: var(--accent-pink);
        }

        textarea::placeholder {
          color: var(--text-muted);
        }

        .save-error {
          background: rgba(248, 113, 113, 0.1);
          border: 1px solid rgba(248, 113, 113, 0.3);
          border-radius: 10px;
          padding: 12px 16px;
          color: #f87171;
          font-size: 0.9rem;
        }

        .actions {
          display: flex;
          justify-content: space-between;
          gap: 16px;
        }

        .skip-btn {
          padding: 14px 24px;
          background: transparent;
          border: 2px solid var(--border-color);
          border-radius: 10px;
          color: var(--text-secondary);
          font-size: 1rem;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .skip-btn:hover:not(:disabled) {
          border-color: var(--text-secondary);
          color: var(--text-primary);
        }

        .skip-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .save-btn {
          padding: 14px 32px;
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          border: none;
          border-radius: 10px;
          color: white;
          font-size: 1rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .save-btn:hover:not(:disabled) {
          box-shadow: 0 0 20px rgba(255, 110, 180, 0.4);
        }

        .save-btn:disabled {
          opacity: 0.7;
          cursor: not-allowed;
        }

        @media (max-width: 480px) {
          .welcome-card {
            padding: 32px 20px;
          }

          .actions {
            flex-direction: column-reverse;
          }

          .skip-btn, .save-btn {
            width: 100%;
          }
        }
      `}</style>
    </Layout>
  );
}


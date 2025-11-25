import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import JSZip from 'jszip';
import Layout from '../components/Layout';

interface Artwork {
  filename: string;
  title: string;
  canvas: string;
  file_kb: number;
  blob: File;
  description?: string;
}

export default function PublishPage() {
  const router = useRouter();
  const [artworks, setArtworks] = useState<Artwork[]>([]);
  const [uploading, setUploading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string>('');
  const [jobError, setJobError] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userInfo, setUserInfo] = useState<any>(null);
  const [githubAppInstalled, setGithubAppInstalled] = useState(false);
  const [githubAppInstallUrl, setGithubAppInstallUrl] = useState<string>('');
  const [validationError, setValidationError] = useState<{error?: string, details?: string, install_url?: string, app_slug?: string} | null>(null);
  const [repositories, setRepositories] = useState<Array<{name: string, full_name: string, html_url: string}>>([]);
  const [selectedRepository, setSelectedRepository] = useState<string>('');
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [installationId, setInstallationId] = useState<number | null>(null);
  const expiredAlertShownRef = useRef(false);

  const [API_BASE_URL, setAPI_BASE_URL] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      return process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost';
    }
    return '';
  });

  const fetchRepositories = async (token: string, baseUrl: string) => {
    try {
      setLoadingRepos(true);
      const response = await fetch(`${baseUrl}/api/relay/repositories`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setRepositories(data.repositories || []);
        if (data.repositories && data.repositories.length > 0 && !selectedRepository) {
          setSelectedRepository(data.repositories[0].name);
        }
      }
    } catch (error) {
      console.error('Error fetching repositories:', error);
    } finally {
      setLoadingRepos(false);
    }
  };

  useEffect(() => {
    const baseUrl = typeof window !== 'undefined' 
      ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
      : '';
    
    if (baseUrl && baseUrl !== API_BASE_URL) {
      setAPI_BASE_URL(baseUrl);
    }

    const checkAuth = () => {
      const accessToken = localStorage.getItem('access_token');
      const userHandle = localStorage.getItem('user_handle');
      const userDisplayName = localStorage.getItem('user_display_name');

      if (!accessToken) {
        router.push('/auth');
        return;
      }

      if (accessToken && userHandle) {
        setIsAuthenticated(true);
        setUserInfo({
          handle: userHandle,
          displayName: userDisplayName
        });

        const urlToUse = baseUrl || API_BASE_URL;
        if (urlToUse) {
          checkGithubAppStatus(accessToken, urlToUse);
        }
      }
    };

    const checkGithubAppStatus = async (token: string, baseUrl: string) => {
      try {
        const statusUrl = `${baseUrl}/api/auth/github-app/status`;
        const response = await fetch(statusUrl, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        if (response.ok) {
          const data = await response.json();
          
          if (data.installed) {
            setValidationError(null);
            setInstallationId(data.installation_id || null);
            fetchRepositories(token, baseUrl);
          }
          
          setGithubAppInstalled(data.installed);
          setGithubAppInstallUrl(data.install_url || '');
        } else if (response.status === 401) {
          localStorage.clear();
          setIsAuthenticated(false);
          setUserInfo(null);
          router.push('/auth');
        }
      } catch (error) {
        console.error('Error checking GitHub App status:', error);
      }
    };

    checkAuth();
    
    const handleFocus = () => {
      const accessToken = localStorage.getItem('access_token');
      const baseUrl = typeof window !== 'undefined' 
        ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
        : '';
      
      if (accessToken && baseUrl) {
        checkGithubAppStatus(accessToken, baseUrl);
      }
    };
    
    window.addEventListener('focus', handleFocus);

    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'OAUTH_SUCCESS') {
        const { tokens } = event.data;

        localStorage.setItem('access_token', tokens.access_token);
        localStorage.setItem('refresh_token', tokens.refresh_token);
        localStorage.setItem('user_id', tokens.user_id);
        localStorage.setItem('user_handle', tokens.user_handle);
        localStorage.setItem('user_display_name', tokens.user_display_name);

        setIsAuthenticated(true);
        setUserInfo({
          handle: tokens.user_handle,
          displayName: tokens.user_display_name
        });
        
        expiredAlertShownRef.current = false;

        const currentApiUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost';
        checkGithubAppStatus(tokens.access_token, currentApiUrl);
      }
    };

    window.addEventListener('message', handleMessage);

    return () => {
      window.removeEventListener('message', handleMessage);
      window.removeEventListener('focus', handleFocus);
    };
  }, []);

  const loadImage = (file: File): Promise<HTMLImageElement> => {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = URL.createObjectURL(file);
    });
  };

  const handleArtworkUpdate = (index: number, field: 'title' | 'description', value: string) => {
    setArtworks(prev => prev.map((artwork, i) => 
      i === index ? { ...artwork, [field]: value } : artwork
    ));
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    
    const processedArtworks = await Promise.all(
      files.map(async (file) => {
        const img = await loadImage(file);
        const existing = artworks.find(a => a.filename === file.name);
        return {
          filename: file.name,
          title: existing?.title || file.name.replace(/\.[^/.]+$/, ""),
          canvas: `${img.width}x${img.height}`,
          file_kb: Math.round(file.size / 1024),
          blob: file,
          description: existing?.description || ""
        };
      })
    );
    
    setArtworks(processedArtworks);
  };

  const pollJobStatus = async (jobId: string) => {
    const poll = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/relay/jobs/${jobId}`);
        const job = await response.json();
        setJobStatus(job.status);
        setJobError(job.error || null);
        
        if (job.status === 'queued' || job.status === 'running') {
          setTimeout(poll, 2000);
        }
      } catch (error) {
        console.error('Error polling job status:', error);
      }
    };
    poll();
  };

  const handlePublish = async () => {
    setUploading(true);
    setJobError(null);
    setJobId(null);
    setJobStatus('');
    
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        alert('Please log in first.');
        setUploading(false);
        return;
      }
      
      const zip = new JSZip();
      
      const manifest = {
        version: "1.0",
        artworks: artworks.map(a => ({
          filename: a.filename,
          title: a.title,
          canvas: a.canvas,
          file_kb: a.file_kb,
          hashtags: [],
          description: a.description || ""
        }))
      };
      zip.file("manifest.json", JSON.stringify(manifest, null, 2));
      
      for (const artwork of artworks) {
        zip.file(artwork.filename, artwork.blob);
      }
      
      const zipBlob = await zip.generateAsync({ type: "blob" });
      
      const formData = new FormData();
      formData.append("bundle", zipBlob, "bundle.zip");
      formData.append("commit_message", "Update via Makapix");
      
      if (!selectedRepository) {
        alert('Please select a repository before publishing.');
        setUploading(false);
        return;
      }
      
      formData.append("repository", selectedRepository);
      
      const uploadUrl = `${API_BASE_URL}/api/relay/pages/upload`;
      
      const response = await fetch(uploadUrl, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${accessToken}`
        },
        body: formData
      });
      
      if (!response.ok) {
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const contentType = response.headers.get('content-type');
          if (contentType && contentType.includes('application/json')) {
            const errorData = await response.json();
            errorMessage = errorData.detail || errorData.error || errorMessage;
          }
        } catch (parseError) {
          console.error('Failed to parse error response:', parseError);
        }

        if (response.status === 401) {
          localStorage.clear();
          if (!expiredAlertShownRef.current) {
            expiredAlertShownRef.current = true;
            alert(`${errorMessage}. Please log in again.`);
          }
          setIsAuthenticated(false);
          setUserInfo(null);
          setUploading(false);
          return;
        }

        throw new Error(errorMessage);
      }
      
      const result = await response.json();
      
      if (result.status === "queued") {
        setJobId(result.job_id);
        pollJobStatus(result.job_id);
      } else if (result.status === "failed") {
        alert(`Upload failed: ${result.error}`);
      }
    } catch (error: any) {
      console.error('Upload error:', error);
      alert(`Upload failed: ${error.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleInstallGithubApp = async () => {
    const accessToken = localStorage.getItem('access_token');
    const baseUrl = typeof window !== 'undefined' 
      ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
      : '';
    
    if (accessToken && baseUrl) {
      try {
        const statusUrl = `${baseUrl}/api/auth/github-app/status`;
        const statusResponse = await fetch(statusUrl, {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        });
        
        if (statusResponse.ok) {
          const statusData = await statusResponse.json();
          const freshInstallUrl = statusData.install_url;
          
          if (freshInstallUrl) {
            window.open(freshInstallUrl, 'github-app-install', 'width=800,height=700,scrollbars=yes,resizable=yes');
          } else {
            alert('GitHub App installation URL is not available. Please refresh the page.');
          }
        }
      } catch (error) {
        console.error('Error getting fresh status:', error);
        alert('Error checking GitHub App status. Please refresh the page.');
      }
    }
  };

  return (
    <Layout title="Publish Artwork" description="Upload and publish your pixel art">
      <div className="publish-container">
        {/* Authentication Status */}
        {isAuthenticated && (
          <div className="status-card success">
            <span className="status-icon">✓</span>
            <div className="status-content">
              <strong>Authenticated as {userInfo?.displayName || userInfo?.handle}</strong>
              <span>Ready to publish artwork</span>
            </div>
            <button 
              onClick={() => {
                localStorage.clear();
                window.location.reload();
              }}
              className="logout-button"
            >
              Logout
            </button>
          </div>
        )}

        {/* GitHub App Status */}
        {isAuthenticated && !githubAppInstalled && (
          <div className="status-card warning">
            <span className="status-icon">⚠️</span>
            <div className="status-content">
              <strong>GitHub App Required</strong>
              <span>Install the Makapix GitHub App to publish artwork</span>
            </div>
            <button onClick={handleInstallGithubApp} className="install-button">
              Install GitHub App
            </button>
          </div>
        )}

        {isAuthenticated && githubAppInstalled && (
          <div className="status-card success">
            <span className="status-icon">✓</span>
            <div className="status-content">
              <strong>GitHub App Connected</strong>
              <span>Ready to publish to GitHub Pages</span>
            </div>
            {installationId && (
              <a 
                href={`https://github.com/settings/installations/${installationId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="manage-link"
              >
                Manage →
              </a>
            )}
          </div>
        )}

        {/* Repository Selection */}
        {isAuthenticated && githubAppInstalled && (
          <div className="section-card">
            <h2>Select Repository</h2>
            
            {loadingRepos ? (
              <div className="loading-repos">Loading repositories...</div>
            ) : (
              <div className="repo-selection">
                <select
                  value={selectedRepository}
                  onChange={(e) => setSelectedRepository(e.target.value)}
                  className="repo-select"
                >
                  <option value="">-- Select repository --</option>
                  {repositories.map((repo) => (
                    <option key={repo.name} value={repo.name}>
                      {repo.full_name}
                    </option>
                  ))}
                </select>
                
                <div className="repo-actions">
                  <button
                    onClick={async () => {
                      const accessToken = localStorage.getItem('access_token');
                      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost';
                      if (accessToken && baseUrl) {
                        await fetchRepositories(accessToken, baseUrl);
                      }
                    }}
                    disabled={loadingRepos}
                    className="refresh-button"
                  >
                    🔄 Refresh
                  </button>
                  <a 
                    href="https://github.com/new" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="create-repo-link"
                  >
                    Create on GitHub →
                  </a>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Upload Section */}
        <div className="section-card">
          <h2>Upload Images</h2>
          <div className="upload-zone">
            <input 
              type="file" 
              multiple 
              accept="image/png,image/jpeg,image/gif" 
              onChange={handleFileSelect}
              className="file-input"
              id="file-upload"
            />
            <label htmlFor="file-upload" className="upload-label">
              <span className="upload-icon">📁</span>
              <span>Click to select images or drag & drop</span>
              <span className="upload-hint">PNG, JPEG, GIF supported</span>
            </label>
          </div>
        </div>

        {/* Artwork Preview */}
        {artworks.length > 0 && (
          <div className="section-card">
            <h2>Artworks ({artworks.length})</h2>
            <div className="artwork-list">
              {artworks.map((artwork, index) => (
                <div key={index} className="artwork-item">
                  <div className="artwork-preview">
                    <img 
                      src={URL.createObjectURL(artwork.blob)} 
                      alt={artwork.title}
                      className="preview-image pixel-art"
                    />
                  </div>
                  <div className="artwork-form">
                    <div className="form-field">
                      <label>Title</label>
                      <input
                        type="text"
                        value={artwork.title}
                        onChange={(e) => handleArtworkUpdate(index, 'title', e.target.value)}
                        maxLength={200}
                      />
                    </div>
                    <div className="form-field">
                      <label>Description</label>
                      <textarea
                        value={artwork.description || ''}
                        onChange={(e) => handleArtworkUpdate(index, 'description', e.target.value)}
                        maxLength={5000}
                        placeholder="Describe your artwork..."
                      />
                      <span className="char-count">{(artwork.description || '').length}/5000</span>
                    </div>
                    <div className="artwork-meta">
                      {artwork.canvas} • {artwork.file_kb} KB
                    </div>
                  </div>
                </div>
              ))}
            </div>
            
            <button
              onClick={handlePublish}
              disabled={uploading || !isAuthenticated || !githubAppInstalled || !selectedRepository}
              className="publish-button"
            >
              {!isAuthenticated ? "Please log in first" :
               !githubAppInstalled ? "Install GitHub App first" :
               !selectedRepository ? "Select a repository" :
               uploading ? "Publishing..." : "🚀 Publish to GitHub Pages"}
            </button>
          </div>
        )}

        {/* Job Status */}
        {jobId && (
          <div className="section-card">
            <h2>Publishing Status</h2>
            <div className="job-status">
              <div className="status-row">
                <span className="status-label">Job ID:</span>
                <code>{jobId}</code>
              </div>
              <div className="status-row">
                <span className="status-label">Status:</span>
                <span className={`status-badge ${jobStatus}`}>{jobStatus}</span>
              </div>
              
              {jobStatus === 'committed' && (
                <div className="success-message">
                  <span className="success-icon">✅</span>
                  <div>
                    <strong>Successfully published!</strong>
                    <a 
                      href={`https://${userInfo?.handle || 'your-username'}.github.io/${selectedRepository}/`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="view-link"
                    >
                      View your artwork →
                    </a>
                    <span className="deploy-note">May take 1-2 minutes for GitHub Pages to deploy</span>
                  </div>
                </div>
              )}
              
              {jobStatus === 'failed' && (
                <div className="error-message">
                  <span className="error-icon">❌</span>
                  <div>
                    <strong>Publishing failed</strong>
                    {jobError && <span className="error-detail">{jobError}</span>}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        .publish-container {
          max-width: 800px;
          margin: 0 auto;
          padding: 24px;
        }

        .status-card {
          display: flex;
          align-items: center;
          gap: 16px;
          padding: 16px 20px;
          border-radius: 12px;
          margin-bottom: 16px;
        }

        .status-card.success {
          background: rgba(16, 185, 129, 0.15);
          border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .status-card.warning {
          background: rgba(245, 158, 11, 0.15);
          border: 1px solid rgba(245, 158, 11, 0.3);
        }

        .status-icon {
          font-size: 1.5rem;
        }

        .status-content {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .status-content strong {
          color: var(--text-primary);
        }

        .status-content span {
          font-size: 0.85rem;
          color: var(--text-muted);
        }

        .logout-button,
        .install-button {
          padding: 8px 16px;
          border-radius: 8px;
          font-size: 0.9rem;
          font-weight: 500;
          transition: all var(--transition-fast);
        }

        .logout-button {
          background: var(--bg-tertiary);
          color: var(--text-secondary);
        }

        .logout-button:hover {
          background: rgba(239, 68, 68, 0.2);
          color: #ef4444;
        }

        .install-button {
          background: var(--accent-cyan);
          color: var(--bg-primary);
        }

        .install-button:hover {
          box-shadow: var(--glow-cyan);
        }

        .manage-link {
          color: var(--accent-cyan);
          font-size: 0.9rem;
        }

        .section-card {
          background: var(--bg-secondary);
          border-radius: 12px;
          padding: 24px;
          margin-bottom: 16px;
        }

        .section-card h2 {
          font-size: 1.1rem;
          color: var(--text-primary);
          margin-bottom: 16px;
        }

        .loading-repos {
          color: var(--text-muted);
          padding: 16px;
          text-align: center;
        }

        .repo-selection {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .repo-select {
          width: 100%;
          padding: 12px 16px;
          font-size: 1rem;
        }

        .repo-actions {
          display: flex;
          gap: 12px;
          align-items: center;
        }

        .refresh-button {
          padding: 8px 16px;
          background: var(--bg-tertiary);
          color: var(--text-secondary);
          border-radius: 8px;
          font-size: 0.9rem;
        }

        .refresh-button:hover:not(:disabled) {
          background: var(--accent-cyan);
          color: var(--bg-primary);
        }

        .create-repo-link {
          color: var(--accent-cyan);
          font-size: 0.9rem;
        }

        .upload-zone {
          position: relative;
          border: 2px dashed var(--bg-tertiary);
          border-radius: 12px;
          padding: 40px;
          text-align: center;
          transition: all var(--transition-fast);
        }

        .upload-zone:hover {
          border-color: var(--accent-cyan);
          background: rgba(0, 212, 255, 0.05);
        }

        .file-input {
          position: absolute;
          inset: 0;
          opacity: 0;
          cursor: pointer;
        }

        .upload-label {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 8px;
          pointer-events: none;
        }

        .upload-icon {
          font-size: 2.5rem;
        }

        .upload-label span {
          color: var(--text-secondary);
        }

        .upload-hint {
          font-size: 0.85rem;
          color: var(--text-muted);
        }

        .artwork-list {
          display: flex;
          flex-direction: column;
          gap: 16px;
          margin-bottom: 24px;
        }

        .artwork-item {
          display: flex;
          gap: 16px;
          padding: 16px;
          background: var(--bg-tertiary);
          border-radius: 10px;
        }

        @media (max-width: 600px) {
          .artwork-item {
            flex-direction: column;
          }
        }

        .artwork-preview {
          flex-shrink: 0;
          width: 100px;
          height: 100px;
          background: var(--bg-primary);
          border-radius: 8px;
          overflow: hidden;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .preview-image {
          max-width: 100%;
          max-height: 100%;
          object-fit: contain;
          image-rendering: pixelated;
        }

        .artwork-form {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .form-field {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .form-field label {
          font-size: 0.85rem;
          color: var(--text-muted);
        }

        .form-field input,
        .form-field textarea {
          padding: 10px 12px;
          font-size: 0.95rem;
        }

        .form-field textarea {
          min-height: 60px;
          resize: vertical;
        }

        .char-count {
          font-size: 0.75rem;
          color: var(--text-muted);
          text-align: right;
        }

        .artwork-meta {
          font-size: 0.8rem;
          color: var(--text-muted);
        }

        .publish-button {
          width: 100%;
          padding: 16px;
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          font-size: 1.1rem;
          font-weight: 600;
          border-radius: 10px;
          transition: all var(--transition-fast);
        }

        .publish-button:hover:not(:disabled) {
          box-shadow: 0 0 30px rgba(255, 110, 180, 0.4);
          transform: translateY(-2px);
        }

        .publish-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .job-status {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .status-row {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .status-label {
          color: var(--text-muted);
          font-size: 0.9rem;
        }

        .status-row code {
          font-family: 'SF Mono', monospace;
          font-size: 0.85rem;
          color: var(--text-secondary);
          background: var(--bg-tertiary);
          padding: 4px 8px;
          border-radius: 4px;
        }

        .status-badge {
          padding: 4px 12px;
          border-radius: 12px;
          font-size: 0.85rem;
          font-weight: 500;
        }

        .status-badge.queued,
        .status-badge.running {
          background: rgba(245, 158, 11, 0.2);
          color: #f59e0b;
        }

        .status-badge.committed {
          background: rgba(16, 185, 129, 0.2);
          color: #10b981;
        }

        .status-badge.failed {
          background: rgba(239, 68, 68, 0.2);
          color: #ef4444;
        }

        .success-message,
        .error-message {
          display: flex;
          gap: 12px;
          padding: 16px;
          border-radius: 10px;
          margin-top: 12px;
        }

        .success-message {
          background: rgba(16, 185, 129, 0.1);
          border: 1px solid rgba(16, 185, 129, 0.2);
        }

        .error-message {
          background: rgba(239, 68, 68, 0.1);
          border: 1px solid rgba(239, 68, 68, 0.2);
        }

        .success-icon,
        .error-icon {
          font-size: 1.5rem;
        }

        .success-message div,
        .error-message div {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .view-link {
          color: var(--accent-cyan);
          font-size: 0.95rem;
        }

        .deploy-note,
        .error-detail {
          font-size: 0.85rem;
          color: var(--text-muted);
        }
      `}</style>
    </Layout>
  );
}

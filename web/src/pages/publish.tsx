import { useState, useEffect } from 'react';
import Head from 'next/head';
import JSZip from 'jszip';

interface Artwork {
  filename: string;
  title: string;
  canvas: string;
  file_kb: number;
  blob: File;
}

export default function PublishPage() {
  const [artworks, setArtworks] = useState<Artwork[]>([]);
  const [uploading, setUploading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string>('');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userInfo, setUserInfo] = useState<any>(null);
  
  // Get API base URL from environment or use current origin
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : 'http://localhost';

  // Check authentication status on component mount
  useEffect(() => {
    const checkAuth = () => {
      const accessToken = localStorage.getItem('access_token');
      const userHandle = localStorage.getItem('user_handle');
      const userDisplayName = localStorage.getItem('user_display_name');
      
      // Debug: log what's in localStorage
      console.log('LocalStorage contents:', {
        accessToken: accessToken ? 'present' : 'missing',
        userHandle: userHandle || 'missing',
        userDisplayName: userDisplayName || 'missing',
        allKeys: Object.keys(localStorage)
      });
      
      if (accessToken && userHandle) {
        setIsAuthenticated(true);
        setUserInfo({
          handle: userHandle,
          displayName: userDisplayName
        });
      }
    };

    // Check auth immediately
    checkAuth();

    // Listen for OAuth success messages from popup
    const handleMessage = (event: MessageEvent) => {
      if (event.data?.type === 'OAUTH_SUCCESS') {
        console.log('Received OAuth success message:', event.data);
        const { tokens } = event.data;
        
        // Store tokens in localStorage
        localStorage.setItem('access_token', tokens.access_token);
        localStorage.setItem('refresh_token', tokens.refresh_token);
        localStorage.setItem('user_id', tokens.user_id);
        localStorage.setItem('user_handle', tokens.user_handle);
        localStorage.setItem('user_display_name', tokens.user_display_name);
        
        // Update state
        setIsAuthenticated(true);
        setUserInfo({
          handle: tokens.user_handle,
          displayName: tokens.user_display_name
        });
        
        console.log('Tokens stored from postMessage');
      }
    };

    window.addEventListener('message', handleMessage);

    // Cleanup
    return () => {
      window.removeEventListener('message', handleMessage);
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

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    
    // Process each image
    const processedArtworks = await Promise.all(
      files.map(async (file) => {
        const img = await loadImage(file);
        return {
          filename: file.name,
          title: file.name.replace(/\.[^/.]+$/, ""),
          canvas: `${img.width}x${img.height}`,
          file_kb: Math.round(file.size / 1024),
          blob: file
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
        
        if (job.status === 'queued' || job.status === 'running') {
          setTimeout(poll, 2000); // Poll every 2 seconds
        }
      } catch (error) {
        console.error('Error polling job status:', error);
      }
    };
    poll();
  };

  const handlePublish = async () => {
    setUploading(true);
    
    try {
      // Check if user is authenticated
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        alert(`Please log in first. Go to ${API_BASE_URL}/api/auth/github/login to authenticate.`);
        setUploading(false);
        return;
      }
      
      // Create ZIP bundle
      const zip = new JSZip();
      
      // Add manifest
      const manifest = {
        version: "1.0",
        artworks: artworks.map(a => ({
          filename: a.filename,
          title: a.title,
          canvas: a.canvas,
          file_kb: a.file_kb,
          hashtags: []
        }))
      };
      zip.file("manifest.json", JSON.stringify(manifest, null, 2));
      
      // Add artwork files
      for (const artwork of artworks) {
        zip.file(artwork.filename, artwork.blob);
      }
      
      // Generate ZIP blob
      const zipBlob = await zip.generateAsync({ type: "blob" });
      
      // Upload to server
      const formData = new FormData();
      formData.append("bundle", zipBlob, "bundle.zip");
      formData.append("commit_message", "Update via Makapix");
      
      // Use the API base URL
      const uploadUrl = `${API_BASE_URL}/api/relay/pages/upload`;
      console.log('Uploading to:', uploadUrl);
      
      console.log('Making request to:', uploadUrl);
      console.log('Request headers:', {
        "Authorization": `Bearer ${accessToken.substring(0, 20)}...`
      });
      
      const response = await fetch(uploadUrl, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${accessToken}`
        },
        body: formData
      });
      
      console.log('Response received:', response.status, response.statusText);
      
      if (!response.ok) {
        // Read error response once
        const errorData = await response.json();
        
        // Handle token expiration
        if (response.status === 401 && errorData.detail && errorData.detail.includes("expired")) {
          // Clear expired tokens
          localStorage.clear();
          alert("Your session has expired. Please log in again.");
          setIsAuthenticated(false);
          setUserInfo(null);
          setUploading(false);
          return;
        }
        
        throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
      }
      
      const result = await response.json();
      console.log('Response data:', result);
      
      if (result.status === "queued") {
        setJobId(result.job_id);
        pollJobStatus(result.job_id);
      } else if (result.status === "failed") {
        alert(`Upload failed: ${result.error}`);
      }
    } catch (error) {
      console.error('Upload error:', error);
      alert(`Upload failed: ${error.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <>
      <Head>
        <title>Publish Artwork - Makapix</title>
      </Head>
      <main className="container">
        <h1>Publish Artwork</h1>
        
        {/* Authentication Status */}
        <div className="auth-status" style={{ 
          padding: '10px', 
          marginBottom: '20px', 
          borderRadius: '6px',
          backgroundColor: isAuthenticated ? '#d1fae5' : '#fef3c7',
          border: `1px solid ${isAuthenticated ? '#10b981' : '#f59e0b'}`
        }}>
          {isAuthenticated ? (
            <div>
              ✅ <strong>Authenticated as {userInfo?.displayName || userInfo?.handle}</strong>
              <br />
              <small>Ready to publish artwork to GitHub Pages</small>
            </div>
               ) : (
                 <div>
                   ⚠️ <strong>Not authenticated</strong>
                   <br />
                   <small>
                    Please <a 
                      href={`${API_BASE_URL}/api/auth/github/login`}
                      target="_blank" 
                      rel="noopener noreferrer"
                      onClick={(e) => {
                        e.preventDefault();
                        window.open(`${API_BASE_URL}/api/auth/github/login`, 'oauth', 'width=600,height=700,scrollbars=yes,resizable=yes');
                      }}
                    >log in with GitHub</a> first.
                <br />
                <button 
                  onClick={() => {
                    localStorage.clear();
                    window.location.reload();
                  }}
                  style={{ marginTop: '5px', padding: '5px 10px', fontSize: '12px' }}
                >
                  Clear localStorage & Refresh
                </button>
              </small>
            </div>
          )}
        </div>
        
        <div className="upload-section">
          <h2>Select Images</h2>
          <input 
            type="file" 
            multiple 
            accept="image/png,image/jpeg,image/gif" 
            onChange={handleFileSelect}
            className="file-input"
          />
        </div>

        {artworks.length > 0 && (
          <div className="artworks-section">
            <h2>Selected Artworks ({artworks.length})</h2>
            <div className="artwork-list">
              {artworks.map((artwork, index) => (
                <div key={index} className="artwork-item">
                  <div className="artwork-preview">
                    <img 
                      src={URL.createObjectURL(artwork.blob)} 
                      alt={artwork.title}
                      style={{ maxWidth: '100px', maxHeight: '100px' }}
                    />
                  </div>
                  <div className="artwork-details">
                    <h3>{artwork.title}</h3>
                    <p>Canvas: {artwork.canvas}</p>
                    <p>Size: {artwork.file_kb} KB</p>
                  </div>
                </div>
              ))}
            </div>
            
            <button 
              onClick={handlePublish} 
              disabled={uploading || !isAuthenticated}
              className="publish-button"
              style={{
                opacity: !isAuthenticated ? 0.5 : 1,
                cursor: !isAuthenticated ? 'not-allowed' : 'pointer'
              }}
            >
              {!isAuthenticated ? "Please log in first" : 
               uploading ? "Publishing..." : "Publish to GitHub Pages"}
            </button>
          </div>
        )}

        {jobId && (
          <div className="job-status">
            <h2>Publishing Status</h2>
            <p>Job ID: {jobId}</p>
            <p>Status: {jobStatus}</p>
            {jobStatus === 'committed' && (
              <div style={{ marginTop: '20px' }}>
                <p className="success">✅ Successfully published to GitHub Pages!</p>
                <div style={{ 
                  background: '#f0fdf4', 
                  border: '2px solid #22c55e', 
                  borderRadius: '8px', 
                  padding: '20px',
                  marginTop: '15px'
                }}>
                  <p style={{ fontWeight: 'bold', marginBottom: '10px', fontSize: '16px' }}>🌐 Your artwork is live!</p>
                  <a 
                    href={`https://${userInfo?.handle || 'your-username'}.github.io/makapix-user/`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      color: '#0070f3',
                      fontSize: '18px',
                      fontWeight: '600',
                      textDecoration: 'none',
                      display: 'block',
                      marginBottom: '10px',
                      wordBreak: 'break-all'
                    }}
                  >
                    {`https://${userInfo?.handle || 'your-username'}.github.io/makapix-user/`} →
                  </a>
                  <p style={{ fontSize: '14px', color: '#666', marginTop: '10px' }}>
                    📝 Note: It may take 1-2 minutes for GitHub Pages to deploy your site.
                  </p>
                  <p style={{ fontSize: '13px', color: '#ea580c', marginTop: '10px', padding: '10px', background: '#fff7ed', borderRadius: '4px' }}>
                    ⚠️ If you get a 404 error, enable GitHub Pages once:<br/>
                    Go to <a href={`https://github.com/${userInfo?.handle || 'your-username'}/makapix-user/settings/pages`} target="_blank" rel="noopener noreferrer" style={{color: '#0070f3'}}>Repository Settings → Pages</a> and set Source to "main" branch, "/" folder.
                  </p>
                </div>
              </div>
            )}
            {jobStatus === 'failed' && (
              <p className="error">❌ Publishing failed. Check the logs for details.</p>
            )}
          </div>
        )}
      </main>
      
      <style jsx>{`
        .container {
          max-width: 800px;
          margin: 2rem auto;
          padding: 0 1rem;
          font-family: system-ui, sans-serif;
        }
        
        .upload-section {
          margin-bottom: 2rem;
          padding: 1rem;
          border: 2px dashed #ccc;
          border-radius: 8px;
          text-align: center;
        }
        
        .file-input {
          margin-top: 1rem;
          padding: 0.5rem;
        }
        
        .artworks-section {
          margin-bottom: 2rem;
        }
        
        .artwork-list {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
          gap: 1rem;
          margin: 1rem 0;
        }
        
        .artwork-item {
          border: 1px solid #ddd;
          border-radius: 8px;
          padding: 1rem;
          display: flex;
          flex-direction: column;
          align-items: center;
        }
        
        .artwork-preview {
          margin-bottom: 0.5rem;
        }
        
        .artwork-details h3 {
          margin: 0 0 0.5rem 0;
          font-size: 1rem;
        }
        
        .artwork-details p {
          margin: 0.25rem 0;
          font-size: 0.875rem;
          color: #666;
        }
        
        .publish-button {
          background: #0070f3;
          color: white;
          border: none;
          padding: 1rem 2rem;
          border-radius: 8px;
          font-size: 1rem;
          cursor: pointer;
          margin-top: 1rem;
        }
        
        .publish-button:disabled {
          background: #ccc;
          cursor: not-allowed;
        }
        
        .job-status {
          padding: 1rem;
          background: #f5f5f5;
          border-radius: 8px;
          margin-top: 1rem;
        }
        
        .success {
          color: #22c55e;
          font-weight: bold;
        }
        
        .error {
          color: #ef4444;
          font-weight: bold;
        }
      `}</style>
    </>
  );
}

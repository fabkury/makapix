import { useState, useEffect, useRef } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import JSZip from 'jszip';

interface Artwork {
  filename: string;
  title: string;
  canvas: string;
  file_kb: number;
  blob: File;
  description?: string;
}

export default function PublishPage() {
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

  // Get API base URL - must be computed inside the component to ensure it runs client-side
  // Initialize with http://localhost as fallback to prevent issues when accessing directly on port 3000
  const [API_BASE_URL, setAPI_BASE_URL] = useState<string>(() => {
    if (typeof window !== 'undefined') {
      // Use env var if set, otherwise use http://localhost (not window.location.origin)
      // This ensures API calls work whether accessed via proxy (localhost) or directly (localhost:3000)
      return process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost';
    }
    return '';
  });

  // Fetch repositories function (defined before useEffect so it can be called inside)
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
        console.log('Repositories fetched:', data.repositories?.length || 0, 'repositories');
        console.log('Repository data:', data.repositories);
        setRepositories(data.repositories || []);
        // Auto-select first repository if available
        if (data.repositories && data.repositories.length > 0 && !selectedRepository) {
          setSelectedRepository(data.repositories[0].name);
        }
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('Failed to fetch repositories:', response.status, response.statusText, errorData);
        alert(`Failed to fetch repositories: ${errorData.detail || errorData.error || response.statusText}`);
      }
    } catch (error) {
      console.error('Error fetching repositories:', error);
      alert(`Error fetching repositories: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setLoadingRepos(false);
    }
  };

  // Check authentication status on component mount
  useEffect(() => {
    // Ensure API_BASE_URL is set correctly
    const baseUrl = typeof window !== 'undefined' 
      ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
      : '';
    
    if (baseUrl && baseUrl !== API_BASE_URL) {
      setAPI_BASE_URL(baseUrl);
    }

    // Log API_BASE_URL for debugging
    console.log('API Base URL:', {
      fromEnv: process.env.NEXT_PUBLIC_API_BASE_URL,
      fallback: typeof window !== 'undefined' ? window.location.origin : 'N/A',
      current: baseUrl || API_BASE_URL
    });

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

        // Check GitHub App installation status - use computed baseUrl
        const urlToUse = baseUrl || API_BASE_URL;
        if (urlToUse) {
          checkGithubAppStatus(accessToken, urlToUse);
        } else {
          console.error('API_BASE_URL is not available');
        }
      }
    };

    // Check if GitHub App is installed and validate it works
    const checkGithubAppStatus = async (token: string, baseUrl: string) => {
      try {
        const statusUrl = `${baseUrl}/api/auth/github-app/status`;
        console.log('Checking GitHub App status at:', statusUrl);
        console.log('Using token:', token.substring(0, 20) + '...');
        console.log('Base URL:', baseUrl);
        
        const response = await fetch(statusUrl, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        console.log('GitHub App status response:', response.status, response.statusText);

        if (response.ok) {
          const data = await response.json();
          console.log('GitHub App status data:', data);
          
          // If installed, validate that it actually works
          if (data.installed) {
            try {
              const validationResult = await validateGithubAppInstallation(token, baseUrl);
              if (!validationResult.valid) {
                // Only show errors if validation actually failed (not skipped due to network error)
                if (validationResult.error && validationResult.error !== 'Configuration error') {
                  console.error('GitHub App installation is invalid:', validationResult);
                  setGithubAppInstalled(false);
                  // Use install_url from validation result if available, otherwise use status install_url
                  setGithubAppInstallUrl(validationResult.install_url || data.install_url || '');
                  // Store validation error for display
                  setValidationError({
                    error: validationResult.error,
                    details: validationResult.details,
                    install_url: validationResult.install_url || data.install_url,
                    app_slug: validationResult.app_slug
                  });
                  if (validationResult.error) {
                    console.error('Validation error:', validationResult.error);
                    console.error('Validation details:', validationResult.details);
                  }
                  return;
                }
              }
              
              // Clear validation error if validation succeeds or was skipped
              setValidationError(null);
              // Store installation_id from validation result
              if (validationResult.installation_id) {
                setInstallationId(validationResult.installation_id);
              }
              // Fetch repositories when GitHub App is installed
              fetchRepositories(token, baseUrl);
            } catch (error: any) {
              // If validation throws an error, log it but don't block the UI
              console.warn('Validation check failed (non-critical):', error);
              // Still set the installation as valid based on status check
              setValidationError(null);
              setInstallationId(data.installation_id || null);
              fetchRepositories(token, baseUrl);
            }
          } else {
            // Clear validation error if not installed
            setValidationError(null);
          }
          
          setGithubAppInstalled(data.installed);
          setGithubAppInstallUrl(data.install_url || '');
          setInstallationId(data.installation_id || null);
          console.log('Install URL set to:', data.install_url);
          console.log('githubAppInstalled state:', data.installed);
          console.log('githubAppInstallUrl state:', data.install_url || '');
          console.log('installationId:', data.installation_id);
        } else {
          console.error('GitHub App status failed:', response.status, response.statusText);
          const errorData = await response.json().catch(() => ({}));
          console.error('Error details:', errorData);
          
          // Handle token expiration
          if (response.status === 401) {
            console.error('Authentication error - token may be expired');
            // Clear expired tokens and redirect to login
            localStorage.clear();
            setIsAuthenticated(false);
            setUserInfo(null);
            // Only show alert if not already shown
            if (!expiredAlertShownRef.current) {
              expiredAlertShownRef.current = true;
              alert('Your session has expired. Please log in again.');
            }
            return;
          } else if (response.status === 500) {
            console.error('Server error - check if GITHUB_APP_SLUG is configured in environment');
          }
          // Don't set any fallback URL - let the system fail properly
        }
      } catch (error) {
        console.error('Error checking GitHub App status:', error);
        console.error('Error details:', error.message);
        console.error('Error stack:', error.stack);
        // Don't set any fallback URL - let the system fail properly
      }
    };

    // Validate that GitHub App installation actually works
    const validateGithubAppInstallation = async (token: string, baseUrl: string): Promise<{valid: boolean, error?: string, details?: string, install_url?: string, app_slug?: string, installation_id?: number}> => {
      // Only validate if we have a valid baseUrl
      if (!baseUrl || baseUrl === '') {
        console.warn('Cannot validate GitHub App: baseUrl is empty');
        return {
          valid: false,
          error: 'Configuration error',
          details: 'API base URL is not configured'
        };
      }

      try {
        const validateUrl = `${baseUrl}/api/auth/github-app/validate`;
        console.log('Validating GitHub App installation at:', validateUrl);
        
        const response = await fetch(validateUrl, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });

        console.log('GitHub App validation response:', response.status, response.statusText);

        if (response.ok) {
          const data = await response.json();
          console.log('GitHub App validation data:', data);
          return {
            valid: data.valid === true,
            error: data.error,
            details: data.details,
            install_url: data.install_url,
            app_slug: data.app_slug,
            installation_id: data.installation_id
          };
        } else {
          console.error('GitHub App validation failed:', response.status, response.statusText);
          const errorData = await response.json().catch(() => ({}));
          console.error('Validation error details:', errorData);
          return {
            valid: false,
            error: errorData.error || 'Validation failed',
            details: errorData.details || errorData.message || 'Unknown error',
            install_url: errorData.install_url,
            app_slug: errorData.app_slug
          };
        }
      } catch (error: any) {
        // Network errors shouldn't be treated as validation failures
        // They might be due to CORS, network issues, or SSR
        console.warn('Error validating GitHub App installation (may be network/CORS issue):', error);
        
        // If it's a network error, don't fail validation - just skip it
        if (error.name === 'TypeError' && error.message.includes('NetworkError')) {
          console.warn('Network error detected - skipping validation (will retry on next check)');
          // Return valid: true to prevent blocking the UI, but mark that validation was skipped
          return {
            valid: true,
            error: undefined,
            details: undefined,
            install_url: undefined,
            app_slug: undefined
          };
        }
        
        return {
          valid: false,
          error: 'Validation error',
          details: error.message || 'Unknown error'
        };
      }
    };

        // Check auth immediately
    checkAuth();
    
    // Also check GitHub App status on page focus (in case user installed app in another tab)
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
        
        // Reset expired alert flag when user logs in successfully
        expiredAlertShownRef.current = false;

        // Check GitHub App installation status
        const currentApiUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost';
        checkGithubAppStatus(tokens.access_token, currentApiUrl);

        console.log('Tokens stored from postMessage');
      }
    };

    window.addEventListener('message', handleMessage);

    // Cleanup
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
    
    // Process each image
    const processedArtworks = await Promise.all(
      files.map(async (file) => {
        const img = await loadImage(file);
        // Check if we already have this artwork (by filename) to preserve title/description
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
    setJobError(null); // Clear any previous errors
    setJobId(null); // Clear previous job ID
    setJobStatus(''); // Clear previous status
    
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
          hashtags: [],
          description: a.description || ""
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
      
      // Repository name is required
      if (!selectedRepository) {
        alert('Please select a repository before publishing.');
        setUploading(false);
        return;
      }
      
      formData.append("repository", selectedRepository);
      console.log('Uploading to repository:', selectedRepository);
      
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
        // Try to read error response as JSON, but handle non-JSON responses
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const contentType = response.headers.get('content-type');
          if (contentType && contentType.includes('application/json')) {
            const errorData = await response.json();
            errorMessage = errorData.detail || errorData.error || errorMessage;
          } else {
            // If not JSON, read as text
            const errorText = await response.text();
            errorMessage = errorText || errorMessage;
          }
        } catch (parseError) {
          // If parsing fails, use the default error message
          console.error('Failed to parse error response:', parseError);
        }

        // Handle authentication errors (expired token, user not found, etc.)
        if (response.status === 401) {
          // Clear invalid/expired tokens
          localStorage.clear();
          // Only show alert if not already shown
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
      <div style={{
        minHeight: '100vh',
        backgroundColor: '#f5f5f5',
      }}>
        <header style={{
          backgroundColor: '#fff',
          borderBottom: '1px solid #e0e0e0',
          padding: '1rem 2rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <h1 style={{
            fontSize: '1.5rem',
            fontWeight: 'bold',
            margin: 0,
            color: '#333',
          }}>Makapix</h1>
          <nav style={{
            display: 'flex',
            gap: '1.5rem',
          }}>
            <Link href="/" style={{
              color: '#666',
              textDecoration: 'none',
              fontSize: '0.9rem',
            }}>Home</Link>
            <Link href="/recent" style={{
              color: '#666',
              textDecoration: 'none',
              fontSize: '0.9rem',
            }}>Recent</Link>
            <Link href="/search" style={{
              color: '#666',
              textDecoration: 'none',
              fontSize: '0.9rem',
            }}>Search</Link>
            <Link href="/publish" style={{
              color: '#666',
              textDecoration: 'none',
              fontSize: '0.9rem',
            }}>Publish</Link>
          </nav>
        </header>
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
              <br />
              <button 
                onClick={() => {
                  localStorage.clear();
                  window.location.reload();
                }}
                style={{ marginTop: '5px', padding: '5px 10px', fontSize: '12px' }}
              >
                Logout & Refresh
              </button>
            </div>
          ) : (
                 <div>
                   ⚠️ <strong>Not authenticated</strong>
                   <br />
                   <small>
                    Please                     <a
                      href="/api/auth/github/login"
                      target="_blank" 
                      rel="noopener noreferrer"
                      onClick={(e) => {
                        e.preventDefault();
                        const apiBaseUrl = typeof window !== 'undefined' 
                          ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
                          : '';
                        window.open(`${apiBaseUrl}/api/auth/github/login`, 'oauth', 'width=600,height=700,scrollbars=yes,resizable=yes');
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

        {/* GitHub App Installation Status */}
        {isAuthenticated && !githubAppInstalled && (
          <div className="github-app-status" style={{
            padding: '15px',
            marginBottom: '20px',
            borderRadius: '6px',
            backgroundColor: validationError?.error === 'Installation belongs to wrong GitHub App' ? '#fee2e2' : '#fef3c7',
            border: `2px solid ${validationError?.error === 'Installation belongs to wrong GitHub App' ? '#dc2626' : '#f59e0b'}`
          }}>
            <div>
              ⚠️ <strong>GitHub App Not Installed or Invalid</strong>
              <br />
              
              {validationError && validationError.error && (
                <div style={{
                  marginTop: '10px',
                  padding: '10px',
                  backgroundColor: '#fff',
                  borderRadius: '4px',
                  border: '1px solid #ddd'
                }}>
                  <strong style={{ color: '#dc2626', display: 'block', marginBottom: '5px' }}>
                    {validationError.error}
                  </strong>
                  {validationError.details && (
                    <div style={{ 
                      marginTop: '5px', 
                      fontSize: '13px', 
                      color: '#666',
                      whiteSpace: 'pre-wrap'
                    }}>
                      {validationError.details}
                    </div>
                  )}
                </div>
              )}
              
              {!validationError && (
                <small>To publish artwork, you need to install the Makapix GitHub App on your account. The system will validate that the installation is working properly before allowing uploads.</small>
              )}
              
              {validationError?.install_url && (
                <div style={{ marginTop: '15px' }}>
                  <a 
                    href={validationError.install_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      display: 'inline-block',
                      padding: '10px 20px',
                      backgroundColor: '#0070f3',
                      color: 'white',
                      textDecoration: 'none',
                      borderRadius: '6px',
                      fontSize: '14px',
                      fontWeight: 'bold'
                    }}
                  >
                    Install Correct GitHub App
                  </a>
                </div>
              )}
              
              {!validationError && (
                <>
                  <small style={{ color: '#dc2626', fontWeight: 'bold', display: 'block', marginTop: '10px' }}>
                    ⚠️ IMPORTANT: If you're being redirected to a GitHub settings page (like github.com/settings/installations/92158250), 
                    you need to uninstall the app from GitHub first, then reinstall it.
                  </small>
                  <br />
                  <a 
                    href="https://github.com/settings/installations/92158250" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    style={{
                      display: 'inline-block',
                      marginTop: '10px',
                      padding: '8px 16px',
                      backgroundColor: '#dc2626',
                      color: 'white',
                      textDecoration: 'none',
                      borderRadius: '6px',
                      fontSize: '14px',
                      fontWeight: 'bold'
                    }}
                  >
                    ⚠️ Uninstall from GitHub First
                  </a>
                  <br />
                </>
              )}
              <button
                onClick={async () => {
                  console.log('Install button clicked!');
                  console.log('Current githubAppInstallUrl:', githubAppInstallUrl);
                  
                  // Force refresh the GitHub App status before proceeding
                  const accessToken = localStorage.getItem('access_token');
                  const baseUrl = typeof window !== 'undefined' 
                    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
                    : '';
                  
                  if (accessToken && baseUrl) {
                    try {
                      console.log('Force refreshing GitHub App status...');
                      const statusUrl = `${baseUrl}/api/auth/github-app/status`;
                      const statusResponse = await fetch(statusUrl, {
                        headers: {
                          'Authorization': `Bearer ${accessToken}`
                        }
                      });
                      
                      if (statusResponse.ok) {
                        const statusData = await statusResponse.json();
                        console.log('Fresh status data:', statusData);
                        
                        // Update the install URL from the fresh data
                        const freshInstallUrl = statusData.install_url;
                        console.log('Fresh install URL:', freshInstallUrl);
                        
                        if (statusData.installed && statusData.installation_id) {
                          // There's an installation - check if it's valid
                          const validateUrl = `${baseUrl}/api/auth/github-app/validate`;
                          const validateResponse = await fetch(validateUrl, {
                            headers: {
                              'Authorization': `Bearer ${accessToken}`
                            }
                          });
                          
                          if (validateResponse.ok) {
                            const validateData = await validateResponse.json();
                            if (!validateData.valid) {
                              // Installation exists but is invalid - check if it's wrong app
                              if (validateData.error === 'Installation belongs to wrong GitHub App') {
                                // Show the correct install URL from validation response
                                if (validateData.install_url) {
                                  alert(`You have installed the wrong GitHub App. Please install the correct one from:\n\n${validateData.install_url}\n\nYou may need to uninstall the incorrect installation first.`);
                                  window.open(validateData.install_url, '_blank');
                                  return;
                                }
                              }
                              
                              // Installation exists but is invalid - guide user to uninstall first
                              const confirmMsg = `You have an existing GitHub App installation (ID: ${statusData.installation_id}) that is invalid.\n\n` +
                                `You need to:\n` +
                                `1. Uninstall the app from GitHub first\n` +
                                `2. Then reinstall it\n\n` +
                                `Open GitHub settings to uninstall?`;
                              
                              if (confirm(confirmMsg)) {
                                window.open(`https://github.com/settings/installations/${statusData.installation_id}`, '_blank');
                                
                                // After user confirms they've uninstalled, clear from database
                                const clearConfirm = confirm('Have you uninstalled the GitHub App from GitHub?\n\nClick OK to clear the invalid installation from our system, then you can reinstall.');
                                if (clearConfirm) {
                                  try {
                                    const clearUrl = `${baseUrl}/api/auth/github-app/clear-installation`;
                                    const clearResponse = await fetch(clearUrl, {
                                      method: 'POST',
                                      headers: {
                                        'Authorization': `Bearer ${accessToken}`
                                      }
                                    });
                                    
                                    if (clearResponse.ok) {
                                      const clearData = await clearResponse.json();
                                      alert(clearData.message || 'Invalid installation cleared. You can now reinstall the GitHub App.');
                                      window.location.reload();
                                    } else {
                                      alert('Failed to clear installation. Please try again.');
                                    }
                                  } catch (error) {
                                    console.error('Error clearing installation:', error);
                                    alert('Error clearing installation. Please refresh the page and try again.');
                                  }
                                }
                                return;
                              }
                            } else {
                              // Installation is valid - this shouldn't happen if we're showing the install button
                              alert('GitHub App is already installed and working. Please refresh the page.');
                              return;
                            }
                          }
                        }
                        
                        // Use the fresh install URL
                        if (freshInstallUrl) {
                          console.log('Opening fresh install URL:', freshInstallUrl);
                          window.open(freshInstallUrl, 'github-app-install', 'width=800,height=700,scrollbars=yes,resizable=yes');
                        } else {
                          alert('GitHub App installation URL is not available. Please refresh the page and try again.');
                        }
                      } else {
                        console.error('Failed to get fresh status:', statusResponse.status);
                        alert('Failed to get GitHub App status. Please refresh the page and try again.');
                      }
                    } catch (error) {
                      console.error('Error getting fresh status:', error);
                      alert('Error checking GitHub App status. Please refresh the page and try again.');
                    }
                  } else {
                    alert('You are not logged in. Please log in first.');
                  }
                }}
                style={{
                  marginTop: '10px',
                  padding: '10px 20px',
                  backgroundColor: '#0070f3',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontWeight: 'bold'
                }}
              >
                Install GitHub App
              </button>
              <br />
              <button
                onClick={async () => {
                  console.log('Debug button clicked - testing API call...');
                  const accessToken = localStorage.getItem('access_token');
                  const baseUrl = typeof window !== 'undefined' 
                    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
                    : '';
                  
                  console.log('Debug info:', {
                    accessToken: accessToken ? 'present' : 'missing',
                    baseUrl: baseUrl,
                    githubAppInstallUrl: githubAppInstallUrl
                  });
                  
                  if (accessToken && baseUrl) {
                    try {
                      const statusUrl = `${baseUrl}/api/auth/github-app/status`;
                      console.log('Testing API call to:', statusUrl);
                      const response = await fetch(statusUrl, {
                        headers: {
                          'Authorization': `Bearer ${accessToken}`
                        }
                      });
                      console.log('Debug API response:', response.status, response.statusText);
                      const data = await response.json();
                      console.log('Debug API data:', data);
                      
                      if (response.status === 401) {
                        // Only show alert if not already shown
                        if (!expiredAlertShownRef.current) {
                          expiredAlertShownRef.current = true;
                          alert(`Debug: Token expired (401). Please log in again.`);
                        }
                        // Clear expired tokens
                        localStorage.clear();
                        window.location.reload();
                      } else {
                        alert(`Debug: API returned status ${response.status}.\n\nData: ${JSON.stringify(data, null, 2)}\n\nCheck console for full details.`);
                      }
                    } catch (error) {
                      console.error('Debug API error:', error);
                      alert(`Debug: API call failed. Check console for details.`);
                    }
                  } else {
                    alert('Debug: Missing access token or base URL. Check console for details.');
                  }
                }}
                style={{
                  marginTop: '5px',
                  padding: '5px 10px',
                  backgroundColor: '#666',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                Debug API Call
              </button>
              <br />
              <button
                onClick={() => {
                  console.log('Refresh button clicked - reloading page...');
                  window.location.reload();
                }}
                style={{
                  marginTop: '5px',
                  padding: '5px 10px',
                  backgroundColor: '#10b981',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                Refresh Page
              </button>
              <br />
              <button
                onClick={async () => {
                  console.log('Force Install URL button clicked');
                  
                  // First, try to clear any existing installation from our database
                  const accessToken = localStorage.getItem('access_token');
                  const baseUrl = typeof window !== 'undefined' 
                    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
                    : '';
                  
                  if (accessToken && baseUrl) {
                    try {
                      // Check if there's an installation in our database
                      const statusUrl = `${baseUrl}/api/auth/github-app/status`;
                      const statusResponse = await fetch(statusUrl, {
                        headers: {
                          'Authorization': `Bearer ${accessToken}`
                        }
                      });
                      
                      if (statusResponse.ok) {
                        const statusData = await statusResponse.json();
                        if (statusData.installed && statusData.installation_id) {
                          // Clear it from our database
                          const clearUrl = `${baseUrl}/api/auth/github-app/clear-installation`;
                          const clearResponse = await fetch(clearUrl, {
                            method: 'POST',
                            headers: {
                              'Authorization': `Bearer ${accessToken}`
                            }
                          });
                          
                          if (clearResponse.ok) {
                            console.log('Cleared installation from database');
                          }
                        }
                      }
                    } catch (error) {
                      console.error('Error clearing installation:', error);
                    }
                  }
                  
                  // Now open the install URL with cache busting
                  const freshUrl = 'https://github.com/apps/makapix-club-local-development/installations/new';
                  console.log('Opening fresh URL directly:', freshUrl);
                  
                  // Use a new window name to avoid cache issues
                  const windowName = `github-app-install-${Date.now()}`;
                  window.open(freshUrl, windowName, 'width=800,height=700,scrollbars=yes,resizable=yes');
                }}
                style={{
                  marginTop: '5px',
                  padding: '5px 10px',
                  backgroundColor: '#f59e0b',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '12px'
                }}
              >
                Force Install URL
              </button>
              <br />
              <small style={{ marginTop: '10px', display: 'block', color: '#666' }}>
                After installation, refresh this page to continue.
              </small>
            </div>
          </div>
        )}

        {isAuthenticated && githubAppInstalled && (
          <div className="github-app-status" style={{
            padding: '10px',
            marginBottom: '20px',
            borderRadius: '6px',
            backgroundColor: '#d1fae5',
            border: '1px solid #10b981'
          }}>
            <div>
              ✅ <strong>GitHub App Installed</strong>
              <br />
              <small>Your artwork will be published to your GitHub Pages repository</small>
              <div style={{ marginTop: '10px', fontSize: '0.875rem' }}>
                {installationId && (
                  <a 
                    href={`https://github.com/settings/installations/${installationId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      color: '#0070f3',
                      textDecoration: 'none'
                    }}
                  >
                    Manage Installation →
                  </a>
                )}
              </div>
            </div>
          </div>
        )}

        {isAuthenticated && githubAppInstalled && (
          <div className="repository-selection" style={{
            padding: '15px',
            marginBottom: '20px',
            borderRadius: '6px',
            backgroundColor: '#fff',
            border: '1px solid #ddd'
          }}>
            <h2 style={{ marginTop: 0, marginBottom: '15px', fontSize: '1.2rem' }}>Select Repository</h2>
            
            {loadingRepos ? (
              <p>Loading repositories...</p>
            ) : (
              <>
                <div style={{ marginBottom: '15px' }}>
                  <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.5rem', fontSize: '0.9rem' }}>
                    Choose an existing repository:
                  </label>
                  <select
                    value={selectedRepository}
                    onChange={(e) => {
                      setSelectedRepository(e.target.value);
                    }}
                    style={{
                      width: '100%',
                      padding: '0.5rem',
                      fontSize: '1rem',
                      border: '1px solid #ddd',
                      borderRadius: '4px',
                      boxSizing: 'border-box'
                    }}
                  >
                    <option value="">-- Select repository --</option>
                    {repositories.map((repo) => (
                      <option key={repo.name} value={repo.name}>
                        {repo.full_name}
                      </option>
                    ))}
                  </select>
                  {repositories.length === 0 && (
                    <div style={{ fontSize: '0.875rem', color: '#666', marginTop: '0.5rem' }}>
                      <p style={{ marginBottom: '0.5rem' }}>No repositories found.</p>
                      <p style={{ marginTop: '0.5rem' }}>Use "Manage Installation" above to change repository access, or create a repository on GitHub using the button below.</p>
                    </div>
                  )}
                </div>

                <div style={{ marginTop: '10px', marginBottom: '15px' }}>
                  <button
                    onClick={async () => {
                      const accessToken = localStorage.getItem('access_token');
                      const baseUrl = typeof window !== 'undefined' 
                        ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
                        : '';
                      if (accessToken && baseUrl) {
                        await fetchRepositories(accessToken, baseUrl);
                      }
                    }}
                    disabled={loadingRepos}
                    style={{
                      padding: '0.5rem 1rem',
                      backgroundColor: '#10b981',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: loadingRepos ? 'not-allowed' : 'pointer',
                      opacity: loadingRepos ? 0.5 : 1,
                      fontSize: '0.875rem'
                    }}
                  >
                    {loadingRepos ? 'Loading...' : '🔄 Refresh Repository List'}
                  </button>
                  <a 
                    href="https://github.com/new" 
                    target="_blank" 
                    rel="noopener noreferrer"
                    style={{
                      marginLeft: '10px',
                      padding: '0.5rem 1rem',
                      backgroundColor: '#24292e',
                      color: 'white',
                      textDecoration: 'none',
                      borderRadius: '4px',
                      fontSize: '0.875rem',
                      display: 'inline-block'
                    }}
                  >
                    Create on GitHub →
                  </a>
                </div>
              </>
            )}
          </div>
        )}

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
                    <div style={{ marginBottom: '0.5rem' }}>
                      <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.25rem', fontSize: '0.9rem' }}>
                        Title:
                      </label>
                      <input
                        type="text"
                        value={artwork.title}
                        onChange={(e) => handleArtworkUpdate(index, 'title', e.target.value)}
                        style={{
                          width: '100%',
                          padding: '0.5rem',
                          fontSize: '1rem',
                          border: '1px solid #ddd',
                          borderRadius: '4px',
                          boxSizing: 'border-box'
                        }}
                        maxLength={200}
                      />
                    </div>
                    <div style={{ marginBottom: '0.5rem' }}>
                      <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '0.25rem', fontSize: '0.9rem' }}>
                        Description:
                      </label>
                      <textarea
                        value={artwork.description || ''}
                        onChange={(e) => handleArtworkUpdate(index, 'description', e.target.value)}
                        style={{
                          width: '100%',
                          padding: '0.5rem',
                          fontSize: '0.9rem',
                          border: '1px solid #ddd',
                          borderRadius: '4px',
                          minHeight: '80px',
                          resize: 'vertical',
                          fontFamily: 'inherit',
                          boxSizing: 'border-box'
                        }}
                        maxLength={5000}
                        placeholder="Describe your artwork..."
                      />
                      <div style={{ fontSize: '0.75rem', color: '#666', marginTop: '0.25rem', textAlign: 'right' }}>
                        {(artwork.description || '').length} / 5000
                      </div>
                    </div>
                    <p style={{ fontSize: '0.875rem', color: '#666', marginTop: '0.5rem' }}>
                      Canvas: {artwork.canvas} • Size: {artwork.file_kb} KB
                    </p>
                  </div>
                </div>
              ))}
            </div>
            
            <button
              onClick={handlePublish}
              disabled={uploading || !isAuthenticated || !githubAppInstalled || !selectedRepository}
              className="publish-button"
              style={{
                opacity: (!isAuthenticated || !githubAppInstalled || !selectedRepository) ? 0.5 : 1,
                cursor: (!isAuthenticated || !githubAppInstalled || !selectedRepository) ? 'not-allowed' : 'pointer'
              }}
            >
              {!isAuthenticated ? "Please log in first" :
               !githubAppInstalled ? "Install GitHub App first" :
               !selectedRepository ? "Select a repository" :
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
                    href={`https://${userInfo?.handle || 'your-username'}.github.io/${selectedRepository || 'makapix-user'}/`}
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
                    {`https://${userInfo?.handle || 'your-username'}.github.io/${selectedRepository || 'makapix-user'}/`} →
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
              <div className="error">
                <p>❌ Publishing failed.</p>
                {jobError && (
                  <p style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: '#d32f2f' }}>
                    Error: {jobError}
                  </p>
                )}
                {!jobError && (
                  <p style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: '#666' }}>
                    Check the logs for details.
                  </p>
                )}
              </div>
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
      </div>
    </>
  );
}

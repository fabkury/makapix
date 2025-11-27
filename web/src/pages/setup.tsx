import { useState, useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

export default function GitHubAppSetupPage() {
  const router = useRouter();
  const [status, setStatus] = useState<string>('loading');
  const [message, setMessage] = useState<string>('Processing GitHub App installation...');
  const [installationId, setInstallationId] = useState<string>('');
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  useEffect(() => {
    // Check for installation_id in URL params
    const { installation_id, setup_action } = router.query;
    
    if (installation_id && typeof installation_id === 'string') {
      setInstallationId(installation_id);
      
      if (setup_action === 'install') {
        // Process the installation
        handleInstallation(installation_id);
      } else {
        setStatus('error');
        setMessage(`Invalid setup action: ${setup_action}`);
      }
    } else {
      setStatus('error');
      setMessage('No installation ID found in URL parameters');
    }
  }, [router.query]);

  const handleInstallation = async (instId: string) => {
    setStatus('loading');
    setMessage('Processing GitHub App installation...');

    const accessToken = localStorage.getItem('access_token');
    const userHandle = localStorage.getItem('user_handle');
    
    if (!accessToken || !userHandle) {
      // User not authenticated, redirect to OAuth with installation_id preserved
      setStatus('redirecting');
      setMessage('Redirecting to authentication...');
      
      // Redirect to OAuth with installation_id as query parameter
      const oauthUrl = `${API_BASE_URL}/api/auth/github/login?installation_id=${instId}`;
      window.location.href = oauthUrl;
      return;
    }

    // User is authenticated, bind the installation
    try {
      setMessage('Binding GitHub App installation to your account...');
      
      const response = await fetch(`${API_BASE_URL}/api/profiles/bind-github-app`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify({
          installation_id: parseInt(instId)
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to bind installation');
      }

      const result = await response.json();
      setStatus('success');
      setMessage(`GitHub App installed successfully! Installation ID: ${result.installation_id}`);
      
      // Redirect to submit page after 2 seconds
      setTimeout(() => {
        router.push('/submit');
      }, 2000);
      
    } catch (error: any) {
      setStatus('error');
      setMessage(`Error: ${error.message}`);
    }
  };

  return (
    <>
      <Head>
        <title>GitHub App Installation - Makapix</title>
      </Head>
      <main className="container">
        <h1>GitHub App Installation</h1>
        
        <div className={`status-box ${status}`}>
          {status === 'loading' && (
            <>
              <div className="spinner"></div>
              <h2>Processing Installation</h2>
              <p>{message}</p>
              <div className="debug">
                <p>Installation ID: {installationId}</p>
              </div>
            </>
          )}
          
          {status === 'redirecting' && (
            <>
              <div className="spinner"></div>
              <h2>Redirecting to Authentication</h2>
              <p>{message}</p>
              <p>You will be redirected to GitHub to complete authentication...</p>
            </>
          )}
          
          {status === 'success' && (
            <>
              <div className="success-icon">✅</div>
              <h2>Success!</h2>
              <p>{message}</p>
              <p>Redirecting to submit page...</p>
              <a href="/submit" className="button primary">
                Go to Submit Page
              </a>
            </>
          )}
          
          {status === 'error' && (
            <>
              <div className="error-icon">❌</div>
              <h2>Error</h2>
              <p>{message}</p>
              <div className="actions">
                <button onClick={() => window.location.reload()} className="button">
                  Try Again
                </button>
                <a href="/submit" className="button secondary">
                  Back to Submit Page
                </a>
              </div>
            </>
          )}
        </div>
        
        <div className="help">
          <h3>What's happening?</h3>
          <p>
            This page handles the completion of your GitHub App installation. 
            The app needs to be linked to your Makapix account to enable certain features.
          </p>
          <p>
            If you're not already logged in, you'll be redirected to GitHub to authenticate first.
          </p>
        </div>
      </main>
      
      <style jsx>{`
        .container {
          max-width: 600px;
          margin: 2rem auto;
          padding: 0 1rem;
          font-family: system-ui, sans-serif;
        }
        
        .status-box {
          padding: 2rem;
          border-radius: 8px;
          margin: 2rem 0;
          text-align: center;
        }
        
        .status-box.loading {
          background: #e0f2fe;
          border: 2px solid #0ea5e9;
        }
        
        .status-box.redirecting {
          background: #fef3c7;
          border: 2px solid #f59e0b;
        }
        
        .status-box.success {
          background: #d1fae5;
          border: 2px solid #10b981;
        }
        
        .status-box.error {
          background: #fee2e2;
          border: 2px solid #ef4444;
        }
        
        .spinner {
          border: 4px solid #f3f3f3;
          border-top: 4px solid #0070f3;
          border-radius: 50%;
          width: 40px;
          height: 40px;
          animation: spin 1s linear infinite;
          margin: 0 auto 1rem;
        }
        
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
        
        .success-icon, .error-icon {
          font-size: 3rem;
          margin-bottom: 1rem;
        }
        
        .button {
          padding: 0.75rem 1.5rem;
          font-size: 1rem;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          margin: 0.5rem;
          text-decoration: none;
          display: inline-block;
        }
        
        .button.primary {
          background: #0070f3;
          color: white;
        }
        
        .button.primary:hover {
          background: #0051a2;
        }
        
        .button.secondary {
          background: #f5f5f5;
          color: #333;
        }
        
        .button.secondary:hover {
          background: #e5e5e5;
        }
        
        .actions {
          margin-top: 1rem;
        }
        
        .debug {
          margin-top: 1rem;
          padding: 1rem;
          background: #f8f9fa;
          border: 1px solid #dee2e6;
          border-radius: 4px;
          font-family: monospace;
          font-size: 0.875rem;
          text-align: left;
        }
        
        .help {
          margin-top: 2rem;
          padding: 1rem;
          background: #f8f9fa;
          border: 1px solid #dee2e6;
          border-radius: 6px;
          text-align: left;
        }
        
        .help h3 {
          margin-top: 0;
          color: #495057;
        }
        
        .help p {
          margin: 0.5rem 0;
          color: #6c757d;
        }
      `}</style>
    </>
  );
}


import { useState, useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

export default function UpdateInstallationPage() {
  const router = useRouter();
  const [status, setStatus] = useState<string>('idle');
  const [message, setMessage] = useState<string>('');
  const [installationId, setInstallationId] = useState<string>('');
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : 'http://localhost';

  useEffect(() => {
    // Check for installation_id in URL params
    const { installation_id, setup_action } = router.query;
    
    if (installation_id && typeof installation_id === 'string') {
      setInstallationId(installation_id);
      
      if (setup_action === 'install') {
        // Auto-bind if we have the parameters
        handleBind(installation_id);
      }
    }
  }, [router.query]);

  const handleBind = async (instId?: string) => {
    const idToUse = instId || installationId;
    
    if (!idToUse) {
      setStatus('error');
      setMessage('Please enter an installation ID');
      return;
    }

    const accessToken = localStorage.getItem('access_token');
    
    if (!accessToken) {
      setStatus('error');
      setMessage('Please log in first');
      return;
    }

    setStatus('loading');
    setMessage('Binding GitHub App installation...');

    try {
      const response = await fetch(`${API_BASE_URL}/api/profiles/bind-github-app`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify({
          installation_id: parseInt(idToUse)
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to bind installation');
      }

      const result = await response.json();
      setStatus('success');
      setMessage(`GitHub App bound successfully! Installation ID: ${result.installation_id}`);
      
      // Redirect to publish page after 2 seconds
      setTimeout(() => {
        router.push('/publish');
      }, 2000);
      
    } catch (error: any) {
      setStatus('error');
      setMessage(`Error: ${error.message}`);
    }
  };

  return (
    <>
      <Head>
        <title>Update GitHub App Installation - Makapix</title>
      </Head>
      <main className="container">
        <h1>GitHub App Installation</h1>
        
        <div className={`status-box ${status}`}>
          {status === 'idle' && (
            <>
              <h2>Bind GitHub App to Your Account</h2>
              <p>Enter your GitHub App installation ID to link it to your Makapix account.</p>
              
              <div className="input-group">
                <label htmlFor="installationId">Installation ID:</label>
                <input
                  type="text"
                  id="installationId"
                  value={installationId}
                  onChange={(e) => setInstallationId(e.target.value)}
                  placeholder="92080078"
                  className="input"
                />
              </div>
              
              <button onClick={() => handleBind()} className="button primary">
                Bind Installation
              </button>
              
              <div className="help">
                <h3>How to get your Installation ID:</h3>
                <ol>
                  <li>Go to <a href="https://github.com/settings/installations" target="_blank" rel="noopener noreferrer">GitHub Settings → Applications → Installed GitHub Apps</a></li>
                  <li>Click "Configure" next to your Makapix app</li>
                  <li>Look at the URL - the number at the end is your Installation ID</li>
                </ol>
                <p>Or install the app and you'll be redirected here with the ID automatically.</p>
              </div>
            </>
          )}
          
          {status === 'loading' && (
            <>
              <div className="spinner"></div>
              <p>{message}</p>
            </>
          )}
          
          {status === 'success' && (
            <>
              <div className="success-icon">✅</div>
              <h2>Success!</h2>
              <p>{message}</p>
              <p>Redirecting to publish page...</p>
            </>
          )}
          
          {status === 'error' && (
            <>
              <div className="error-icon">❌</div>
              <h2>Error</h2>
              <p>{message}</p>
              <button onClick={() => setStatus('idle')} className="button">
                Try Again
              </button>
            </>
          )}
        </div>
        
        <div className="actions">
          <a href="/publish" className="link">← Back to Publish</a>
          <a href={`${API_BASE_URL}/auth/github/login`} className="link">Log In</a>
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
        
        .status-box.idle {
          background: #f5f5f5;
          border: 2px solid #ddd;
        }
        
        .status-box.loading {
          background: #e0f2fe;
          border: 2px solid #0ea5e9;
        }
        
        .status-box.success {
          background: #d1fae5;
          border: 2px solid #10b981;
        }
        
        .status-box.error {
          background: #fee2e2;
          border: 2px solid #ef4444;
        }
        
        .input-group {
          margin: 1.5rem 0;
          text-align: left;
        }
        
        .input-group label {
          display: block;
          margin-bottom: 0.5rem;
          font-weight: 600;
        }
        
        .input {
          width: 100%;
          padding: 0.75rem;
          font-size: 1rem;
          border: 2px solid #ddd;
          border-radius: 6px;
          box-sizing: border-box;
        }
        
        .input:focus {
          outline: none;
          border-color: #0070f3;
        }
        
        .button {
          padding: 0.75rem 1.5rem;
          font-size: 1rem;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          margin: 0.5rem;
        }
        
        .button.primary {
          background: #0070f3;
          color: white;
        }
        
        .button.primary:hover {
          background: #0051a2;
        }
        
        .button:not(.primary) {
          background: #f5f5f5;
          color: #333;
        }
        
        .help {
          margin-top: 2rem;
          padding: 1rem;
          background: #fffbeb;
          border: 1px solid #fbbf24;
          border-radius: 6px;
          text-align: left;
        }
        
        .help h3 {
          margin-top: 0;
        }
        
        .help ol {
          margin-left: 1.5rem;
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
        
        .actions {
          display: flex;
          justify-content: space-between;
          margin-top: 2rem;
        }
        
        .link {
          color: #0070f3;
          text-decoration: none;
        }
        
        .link:hover {
          text-decoration: underline;
        }
      `}</style>
    </>
  );
}

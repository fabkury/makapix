import { useEffect, useState } from 'react';
import Head from 'next/head';
import { authenticatedFetch } from '../lib/api';

export default function DebugEnv() {
  const [apiBaseUrl, setApiBaseUrl] = useState<string>('');
  const [windowOrigin, setWindowOrigin] = useState<string>('');
  const [processEnv, setProcessEnv] = useState<string>('');
  const [devicePixelRatio, setDevicePixelRatio] = useState<number>(1);
  const [apiTest, setApiTest] = useState<any>(null);
  const [apiError, setApiError] = useState<string>('');
  const [accessTokenStatus, setAccessTokenStatus] = useState<string>('loading...');
  const [userHandle, setUserHandle] = useState<string>('loading...');

  useEffect(() => {
    // Get API base URL
    const API_BASE_URL = typeof window !== 'undefined'
      ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
      : 'http://localhost';

    setApiBaseUrl(API_BASE_URL);
    setWindowOrigin(window.location.origin);
    setProcessEnv(process.env.NEXT_PUBLIC_API_BASE_URL || 'undefined');
    setDevicePixelRatio(window.devicePixelRatio || 1);
    
    // Access localStorage only on client side
    setAccessTokenStatus(localStorage.getItem('access_token') ? 'present' : 'missing');
    setUserHandle(localStorage.getItem('user_handle') || 'missing');

    // Test API endpoint
    const testApi = async () => {
      try {
        const response = await authenticatedFetch(`${API_BASE_URL}/api/auth/github-app/status`);

        if (response.ok) {
          const data = await response.json();
          setApiTest(data);
        } else {
          setApiError(`API returned ${response.status}: ${response.statusText}`);
        }
      } catch (error: any) {
        setApiError(`API error: ${error.message}`);
      }
    };

    testApi();
  }, []);

  return (
    <>
      <Head>
        <title>Debug Environment - Makapix</title>
      </Head>
      <main style={{ padding: '20px', fontFamily: 'monospace' }}>
        <h1>Debug Environment Variables</h1>

        <h2>Environment Info:</h2>
        <ul>
          <li><strong>API_BASE_URL (computed):</strong> {apiBaseUrl}</li>
          <li><strong>window.location.origin:</strong> {windowOrigin}</li>
          <li><strong>process.env.NEXT_PUBLIC_API_BASE_URL:</strong> {processEnv}</li>
          <li><strong>window.devicePixelRatio (DPR):</strong> {devicePixelRatio}</li>
        </ul>

        <h2>API Test:</h2>
        {apiError && (
          <div style={{ color: 'red', padding: '10px', background: '#fee', border: '1px solid red', borderRadius: '4px', marginBottom: '10px' }}>
            <strong>Error:</strong> {apiError}
          </div>
        )}
        {apiTest && (
          <div style={{ padding: '10px', background: '#efe', border: '1px solid green', borderRadius: '4px' }}>
            <strong>Success!</strong>
            <pre>{JSON.stringify(apiTest, null, 2)}</pre>
          </div>
        )}
        {!apiTest && !apiError && <div>Loading...</div>}

        <h2>LocalStorage:</h2>
        <ul>
          <li><strong>access_token:</strong> {accessTokenStatus}</li>
          <li><strong>user_handle:</strong> {userHandle}</li>
        </ul>
      </main>
    </>
  );
}

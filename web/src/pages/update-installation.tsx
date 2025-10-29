import { useState } from 'react';
import Head from 'next/head';

export default function UpdateInstallationPage() {
  const [status, setStatus] = useState<string>('');
  const [loading, setLoading] = useState(false);

  const handleUpdate = async () => {
    setLoading(true);
    setStatus('Updating installation...');

    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        setStatus('❌ Error: Not authenticated. Please log in first.');
        setLoading(false);
        return;
      }

      // Use relative URL or environment variable
      const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL 
        ? `${process.env.NEXT_PUBLIC_API_BASE_URL}/profiles/bind-github-app`
        : '/api/profiles/bind-github-app';

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          installation_id: 92061343
        })
      });

      if (!response.ok) {
        const error = await response.json();
        setStatus(`❌ Error: ${error.detail || response.statusText}`);
        setLoading(false);
        return;
      }

      const result = await response.json();
      setStatus(`✅ Success! Status: ${result.status}, Installation ID: ${result.installation_id}`);
    } catch (error: any) {
      setStatus(`❌ Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>Update GitHub App Installation - Makapix</title>
      </Head>
      <main style={{ 
        maxWidth: '600px', 
        margin: '40px auto', 
        padding: '20px',
        fontFamily: 'Arial, sans-serif'
      }}>
        <h1>Update GitHub App Installation</h1>
        
        <div style={{ 
          background: '#f0f9ff', 
          border: '1px solid #0ea5e9',
          borderRadius: '8px',
          padding: '20px',
          marginBottom: '20px'
        }}>
          <p style={{ margin: '0 0 10px 0' }}>
            <strong>New Installation ID:</strong> 92061343
          </p>
          <p style={{ margin: 0, fontSize: '14px', color: '#666' }}>
            Click the button below to update your GitHub App installation ID.
          </p>
        </div>

        <button
          onClick={handleUpdate}
          disabled={loading}
          style={{
            background: '#0070f3',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            padding: '12px 24px',
            fontSize: '16px',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1,
            width: '100%',
            marginBottom: '20px'
          }}
        >
          {loading ? 'Updating...' : 'Update Installation ID'}
        </button>

        {status && (
          <div style={{
            background: status.startsWith('✅') ? '#d1fae5' : '#fee2e2',
            border: `1px solid ${status.startsWith('✅') ? '#10b981' : '#ef4444'}`,
            borderRadius: '6px',
            padding: '15px',
            marginTop: '20px',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word'
          }}>
            {status}
          </div>
        )}

        <div style={{ 
          marginTop: '30px', 
          padding: '15px', 
          background: '#fff7ed',
          border: '1px solid #f97316',
          borderRadius: '6px'
        }}>
          <h3 style={{ marginTop: 0 }}>After updating:</h3>
          <ol style={{ marginBottom: 0, paddingLeft: '20px' }}>
            <li>Restart the worker: <code style={{ background: '#f3f4f6', padding: '2px 6px', borderRadius: '3px' }}>docker compose restart worker</code></li>
            <li>Go back to <a href="/publish">Publish page</a> and try uploading again</li>
          </ol>
        </div>
      </main>
    </>
  );
}


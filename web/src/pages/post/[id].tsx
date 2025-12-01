import { useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';

/**
 * Legacy post route - redirects to canonical /p/[sqid] URL.
 * 
 * This page handles old URLs like /post/{storage_key} (UUID format)
 * and redirects to the new canonical URL /p/{public_sqid}.
 */
export default function LegacyPostRedirect() {
  const router = useRouter();
  const { id } = router.query;
  
  // Use absolute URL to ensure we hit the API backend, not Next.js routing
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';
  
  // Ensure we're using the full API URL, not a relative path
  const getApiUrl = (path: string) => {
    if (path.startsWith('http')) return path;
    if (path.startsWith('/api/')) {
      // Use full URL to bypass Next.js routing
      return `${API_BASE_URL}${path}`;
    }
    return `${API_BASE_URL}/api${path.startsWith('/') ? path : '/' + path}`;
  };

  useEffect(() => {
    if (!id || typeof id !== 'string') return;

    const redirectToCanonical = async () => {
      try {
        const accessToken = localStorage.getItem('access_token');
        const headers: HeadersInit = {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        };
        if (accessToken) {
          headers['Authorization'] = `Bearer ${accessToken}`;
        }
        
        const apiUrl = getApiUrl(`/post/${id}`);
        console.log('Fetching from:', apiUrl);
        
        // Fetch from the legacy API endpoint - it returns JSON with public_sqid
        // Use cache: 'no-store' to bypass Next.js fetch interception
        const response = await fetch(apiUrl, { 
          headers,
          redirect: 'follow',
          method: 'GET'
        });
        
        console.log('Response status:', response.status);
        console.log('Response Content-Type:', response.headers.get('Content-Type'));
        
        if (response.ok) {
          const contentType = response.headers.get('Content-Type');
          if (contentType && contentType.includes('application/json')) {
            const data = await response.json();
            console.log('Received data:', data);
            if (data.public_sqid) {
              console.log('Redirecting to:', `/p/${data.public_sqid}`);
              router.replace(`/p/${data.public_sqid}`);
              return;
            }
          } else {
            console.error('Unexpected content type:', contentType);
            const text = await response.text();
            console.error('Response text:', text.substring(0, 200));
          }
        } else {
          console.error('Response not OK:', response.status, response.statusText);
        }
        
        // Post not found - redirect to home
        console.log('Redirecting to home (fallback)');
        router.replace('/');
      } catch (err) {
        console.error('Error redirecting to canonical URL:', err);
        router.replace('/');
      }
    };
    
    redirectToCanonical();
  }, [id, API_BASE_URL, router]);

    return (
    <Layout title="Redirecting...">
      <div className="redirect-container">
          <div className="loading-spinner"></div>
        <p>Redirecting to post...</p>
        </div>
        <style jsx>{`
        .redirect-container {
            display: flex;
          flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - var(--header-height));
          gap: 16px;
          }
          .loading-spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--bg-tertiary);
            border-top-color: var(--accent-cyan);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
          }
        p {
          color: var(--text-muted);
          font-size: 0.9rem;
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </Layout>
  );
}

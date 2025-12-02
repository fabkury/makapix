import { useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../../components/Layout';

/**
 * Legacy player route - redirects to canonical /u/[sqid]/player URL.
 * 
 * This page handles old URLs like /user/{user_key}/player (UUID format)
 * and redirects to the new canonical URL /u/{public_sqid}/player.
 */
export default function LegacyPlayerRedirect() {
  const router = useRouter();
  const { id } = router.query;
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';
  
  useEffect(() => {
    if (!id || typeof id !== 'string') return;

    const redirectToCanonical = async () => {
      try {
        const accessToken = localStorage.getItem('access_token');
        const headers: HeadersInit = {
          'Accept': 'application/json',
        };
        if (accessToken) {
          headers['Authorization'] = `Bearer ${accessToken}`;
        }
        
        // Fetch user by user_key (UUID) to get public_sqid
        const response = await fetch(`${API_BASE_URL}/api/user/${id}`, { headers });
        
        if (response.ok) {
          const data = await response.json();
          if (data.public_sqid) {
            router.replace(`/u/${data.public_sqid}/player`);
            return;
          }
        }
        
        // User not found - redirect to home
        router.replace('/');
      } catch (err) {
        console.error('Error redirecting to canonical URL:', err);
        router.replace('/');
      }
    };

    redirectToCanonical();
  }, [id, router, API_BASE_URL]);

  return (
    <Layout title="Loading...">
      <div className="loading-container">
        <div className="loading-spinner"></div>
      </div>
      <style jsx>{`
        .loading-container {
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: calc(100vh - var(--header-height));
        }
        .loading-spinner {
          width: 40px;
          height: 40px;
          border: 3px solid var(--bg-tertiary);
          border-top-color: var(--accent-cyan);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </Layout>
  );
}

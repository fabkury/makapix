import { useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import { authenticatedFetch } from '../../lib/api';

/**
 * Legacy blog post route - redirects to canonical /b/[sqid] URL.
 * 
 * This page handles old URLs like /blog/{blog_post_key} (UUID format)
 * and redirects to the new canonical URL /b/{public_sqid}.
 */
export default function LegacyBlogPostRedirect() {
  const router = useRouter();
  const { id } = router.query;
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';
  
  const getApiUrl = (path: string): string => {
    if (path.startsWith('http')) return path;
    if (path.startsWith('/api/')) {
      return `${API_BASE_URL}${path}`;
    }
    return `${API_BASE_URL}/api${path}`;
  };

  useEffect(() => {
    if (!id || typeof id !== 'string') return;

    const redirectToCanonical = async () => {
      try {
        const apiUrl = getApiUrl(`/blog-post/${id}`);
        
        // Fetch from the legacy API endpoint - it returns JSON with public_sqid
        const response = await authenticatedFetch(apiUrl, {
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
          },
          redirect: 'follow',
          method: 'GET'
        });
        
        if (response.ok) {
          const contentType = response.headers.get('Content-Type');
          if (contentType && contentType.includes('application/json')) {
            const data = await response.json();
            if (data.public_sqid) {
              router.replace(`/b/${data.public_sqid}`);
              return;
            }
          }
        }
        
        // Blog post not found - redirect to blog feed
        router.replace('/blog');
      } catch (err) {
        console.error('Error redirecting to canonical URL:', err);
        router.replace('/blog');
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

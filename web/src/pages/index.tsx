import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';
import CardGrid from '../components/CardGrid';

interface PostOwner {
  id: string;
  handle: string;
}

interface Post {
  id: string;
  title: string;
  description?: string;
  hashtags?: string[];
  art_url: string;
  canvas: string;
  owner_id: string;
  created_at: string;
  promoted?: boolean;
  visible?: boolean;
  owner?: PostOwner;
}

interface PageResponse<T> {
  items: T[];
  next_cursor: string | null;
}

export default function HomePage() {
  const router = useRouter();
  const [posts, setPosts] = useState<Post[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  
  const observerTarget = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);
  const nextCursorRef = useRef<string | null>(null);
  const initialLoadRef = useRef(false);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Redirect non-logged-in users to Recommended page (landing page)
  // Note: Click handler in Layout.tsx intercepts Recent artworks clicks for unauthenticated users
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.replace('/recommended');
    } else {
      setIsAuthenticated(true);
    }
  }, [router]);

  const loadPosts = useCallback(async (cursor: string | null = null) => {
    if (loadingRef.current || (cursor !== null && !hasMoreRef.current)) {
      return;
    }
    
    const token = localStorage.getItem('access_token');
    if (!token) {
      return;
    }
    
    loadingRef.current = true;
    setLoading(true);
    setError(null);
    
    try {
      const url = `${API_BASE_URL}/api/posts?limit=20&sort=created_at&order=desc${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });
      
      if (response.status === 401) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_id');
        router.push('/auth');
        return;
      }
      
      if (!response.ok) {
        const errorText = await response.text().catch(() => response.statusText);
        throw new Error(`Failed to load posts: ${response.status} ${errorText}`);
      }
      
      const data: PageResponse<Post> = await response.json();
      
      if (!data || typeof data !== 'object' || !Array.isArray(data.items)) {
        throw new Error('Invalid response format from server');
      }
      
      if (cursor) {
        setPosts(prev => [...prev, ...data.items]);
      } else {
        setPosts(data.items);
      }
      
      setNextCursor(data.next_cursor);
      nextCursorRef.current = data.next_cursor;
      const hasMoreValue = data.next_cursor !== null;
      hasMoreRef.current = hasMoreValue;
      setHasMore(hasMoreValue);
      
      if (cursor === null) {
        initialLoadRef.current = true;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load posts');
      console.error('Error loading posts:', err);
      
      if (cursor === null) {
        initialLoadRef.current = true;
      }
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, [API_BASE_URL, router]);

  // Initial load
  useEffect(() => {
    if (API_BASE_URL && isAuthenticated) {
      loadPosts();
    }
  }, [API_BASE_URL, isAuthenticated, loadPosts]);

  // Intersection Observer for infinite scroll
  useEffect(() => {
    if (!initialLoadRef.current) return;
    if (posts.length === 0 || !hasMoreRef.current) return;
    
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && 
            initialLoadRef.current && 
            hasMoreRef.current && 
            !loadingRef.current) {
          loadPosts(nextCursorRef.current);
        }
      },
      { threshold: 0.1 }
    );

    const currentTarget = observerTarget.current;
    if (currentTarget) {
      observer.observe(currentTarget);
    }

    return () => {
      if (currentTarget) {
        observer.unobserve(currentTarget);
      }
    };
  }, [posts.length, loadPosts]);

  // Don't render content if not authenticated (will redirect)
  if (!isAuthenticated) {
    return (
      <Layout title="Recent Pixel Art">
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
          <div className="loading-spinner" style={{ width: 40, height: 40, border: '3px solid var(--bg-tertiary)', borderTopColor: 'var(--accent-cyan)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }}></div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title="Recent Pixel Art" description="Discover the latest pixel art creations">
      <div className="feed-container">
        {error && (
          <div className="error-message">
            <p>{error}</p>
            <button onClick={() => loadPosts()} className="retry-button">
              Retry
            </button>
          </div>
        )}

        {posts.length === 0 && !loading && !error && (
          <div className="empty-state">
            <span className="empty-icon">🐣</span>
            <p>No recent posts yet. Check back later!</p>
          </div>
        )}

        {posts.length > 0 && (
          <CardGrid posts={posts} API_BASE_URL={API_BASE_URL} />
        )}

        {posts.length > 0 && (
          <div ref={observerTarget} className="load-more-trigger">
            {loading && (
              <div className="loading-indicator">
                <div className="loading-spinner"></div>
              </div>
            )}
            {!hasMore && (
              <div className="end-message">
                <span>✨</span>
              </div>
            )}
          </div>
        )}
      </div>

      <style jsx>{`
        .feed-container {
          width: 100%;
          min-height: calc(100vh - var(--header-height));
        }

        .error-message {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 3rem;
          text-align: center;
          color: var(--text-secondary);
        }

        .retry-button {
          margin-top: 1rem;
          padding: 0.75rem 1.5rem;
          background: var(--accent-pink);
          color: var(--bg-primary);
          border-radius: 8px;
          font-weight: 600;
          transition: all var(--transition-fast);
        }

        .retry-button:hover {
          box-shadow: var(--glow-pink);
        }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 4rem 2rem;
          text-align: center;
          color: var(--text-muted);
        }

        .empty-icon {
          font-size: 4rem;
          margin-bottom: 1rem;
        }

        .load-more-trigger {
          height: 100px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .loading-indicator {
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .loading-spinner {
          width: 32px;
          height: 32px;
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

        .end-message {
          color: var(--text-muted);
          font-size: 1.5rem;
        }
      `}</style>
    </Layout>
  );
}

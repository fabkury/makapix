import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';
import CardGrid from '../components/CardGrid';
import PlayerBar from '../components/PlayerBarDynamic';
import { authenticatedFetch, clearTokens } from '../lib/api';
import { usePlayerBarOptional } from '../contexts/PlayerBarContext';
import { calculatePageSize } from '../utils/gridUtils';

interface PostOwner {
  id: string;
  handle: string;
  avatar_url?: string | null;
  public_sqid?: string;
}

interface Post {
  id: number;
  public_sqid: string;
  title: string;
  description?: string;
  hashtags?: string[];
  art_url: string;
  canvas: string;
  width: number;
  height: number;
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

export default function RecommendedPage() {
  const router = useRouter();
  const playerBarContext = usePlayerBarOptional();
  const [posts, setPosts] = useState<Post[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  
  const observerTarget = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);
  const nextCursorRef = useRef<string | null>(null);
  const initialLoadRef = useRef(false);
  const pageSizeRef = useRef(20); // Will be set on mount

  const API_BASE_URL = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Calculate page size on mount (client-side only)
  useEffect(() => {
    pageSizeRef.current = calculatePageSize();
  }, []);

  // Set current channel for PlayerBar
  useEffect(() => {
    if (playerBarContext) {
      playerBarContext.setCurrentChannel({
        displayName: 'Recommended',
        channelName: 'promoted',
      });
    }
    // Clear channel on unmount
    return () => {
      if (playerBarContext) {
        playerBarContext.setCurrentChannel(null);
      }
    };
    // Note: We intentionally use an empty dependency array here.
    // The context's setCurrentChannel is stable (from useState), and we only
    // want to set/clear the channel on mount/unmount, not on every context update.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadPosts = useCallback(async (cursor: string | null = null) => {
    if (loadingRef.current || (cursor !== null && !hasMoreRef.current)) {
      return;
    }
    
    loadingRef.current = true;
    setLoading(true);
    setError(null);
    
    try {
      const url = `${API_BASE_URL}/api/feed/promoted?limit=${pageSizeRef.current}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
      const response = await authenticatedFetch(url);
      
      if (response.status === 401) {
        clearTokens();
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
    if (API_BASE_URL) {
      loadPosts();
    }
  }, [API_BASE_URL, loadPosts]);

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
      // Document scrolling: observe relative to viewport
      { threshold: 0.1, root: null }
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

  return (
    <Layout title="Recommended Pixel Art" description="Curated pixel art selections promoted by moderators">
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
            <span className="empty-icon">⭐</span>
            <p>No recommended posts yet. Check back later!</p>
          </div>
        )}

        {posts.length > 0 && (
          <CardGrid 
            posts={posts} 
            API_BASE_URL={API_BASE_URL}
            source={{ type: 'recommended' }}
            cursor={nextCursor}
          />
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
                <div className="end-spacer" aria-hidden="true" />
              </div>
            )}
          </div>
        )}
      </div>

      <PlayerBar />

      <style jsx>{`
        .feed-container {
          width: 100%;
          min-height: calc(100vh - var(--header-offset));
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
          min-height: 100px;
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
          display: flex;
          flex-direction: column;
          align-items: center;
          padding-top: 24px;
        }

        .end-spacer {
          height: max(25vh, 200px);
          width: 1px;
        }
      `}</style>
    </Layout>
  );
}


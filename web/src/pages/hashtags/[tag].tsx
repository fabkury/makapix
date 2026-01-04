import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import CardGrid from '../../components/CardGrid';
import PlayerBar from '../../components/PlayerBarDynamic';
import { FilterButton } from '../../components/FilterButton';
import { authenticatedFetch, clearTokens } from '../../lib/api';
import { usePlayerBarOptional } from '../../contexts/PlayerBarContext';
import { useFilters, FilterConfig } from '../../hooks/useFilters';
import { calculatePageSize } from '../../utils/gridUtils';

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
  owner?: PostOwner;
}

interface PageResponse<T> {
  items: T[];
  next_cursor: string | null;
}

export default function HashtagPage() {
  const router = useRouter();
  const { tag } = router.query;
  const playerBarContext = usePlayerBarOptional();
  const { filters, setFilters, buildApiQuery } = useFilters();

  const [posts, setPosts] = useState<Post[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);

  const observerTarget = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);
  const nextCursorRef = useRef<string | null>(null);
  const pageSizeRef = useRef(20); // Will be set on mount
  const filtersRef = useRef(filters);

  const API_BASE_URL = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Calculate page size on mount (client-side only)
  useEffect(() => {
    pageSizeRef.current = calculatePageSize();
  }, []);

  // Check authentication on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/auth');
    }
  }, [router]);

  // Set current channel for PlayerBar
  useEffect(() => {
    if (playerBarContext && tag && typeof tag === 'string') {
      playerBarContext.setCurrentChannel({
        displayName: `#${tag}`,
        hashtag: tag,
      });
    }
    // Clear channel on unmount
    return () => {
      if (playerBarContext) {
        playerBarContext.setCurrentChannel(null);
      }
    };
    // Note: We intentionally exclude playerBarContext from dependencies.
    // The context's setCurrentChannel is stable (from useState), and including
    // the entire context object would cause infinite re-renders that block navigation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tag]);

  const loadPosts = useCallback(async (hashtag: string, cursor: string | null = null) => {
    if (loadingRef.current || (!hasMoreRef.current && cursor !== null) || !hashtag) return;

    loadingRef.current = true;
    setLoading(true);
    setError(null);

    try {
      // Build query string with filters
      const baseParams: Record<string, string> = {
        hashtag: hashtag,
        limit: String(pageSizeRef.current),
      };
      if (!filters.sortBy) {
        baseParams.sort = 'created_at';
        baseParams.order = 'desc';
      }
      const queryString = buildApiQuery(baseParams);
      const url = `${API_BASE_URL}/api/post?${queryString}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
      const response = await authenticatedFetch(url);
      
      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      
      if (!response.ok) {
        throw new Error(`Failed to load posts: ${response.statusText}`);
      }
      
      const data: PageResponse<Post> = await response.json();
      
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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load posts');
      console.error('Error loading posts:', err);
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, [API_BASE_URL, router, buildApiQuery, filters.sortBy]);

  // Handle filter changes
  const handleFilterChange = useCallback((newFilters: FilterConfig) => {
    setFilters(newFilters);
  }, [setFilters]);

  // Load posts when tag changes
  useEffect(() => {
    if (tag && typeof tag === 'string') {
      setPosts([]);
      setNextCursor(null);
      nextCursorRef.current = null;
      hasMoreRef.current = true;
      setHasMore(true);
      loadPosts(tag);
    }
  }, [tag, loadPosts]);

  // Reset posts when filters change
  useEffect(() => {
    const prevFilters = filtersRef.current;
    const filtersChanged = JSON.stringify(prevFilters) !== JSON.stringify(filters);

    if (filtersChanged && tag && typeof tag === 'string') {
      filtersRef.current = filters;
      setPosts([]);
      setNextCursor(null);
      nextCursorRef.current = null;
      hasMoreRef.current = true;
      setHasMore(true);
      loadPosts(tag);
    }
  }, [filters, tag, loadPosts]);

  // Intersection Observer for infinite scroll
  useEffect(() => {
    if (!tag || typeof tag !== 'string') return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMoreRef.current && !loadingRef.current) {
          loadPosts(tag, nextCursorRef.current);
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
  }, [tag, loadPosts]);

  const hashtagName = typeof tag === 'string' ? tag : '';

  return (
    <Layout title={`#${hashtagName}`} description={`Pixel art tagged with #${hashtagName}`}>
      <FilterButton
        onFilterChange={handleFilterChange}
        initialFilters={filters}
        isLoading={loading}
      />

      <div className="feed-container">
        <div className="hashtag-header">
          <span className="hashtag-symbol">#</span>
          <span className="hashtag-name">{hashtagName}</span>
          {posts.length > 0 && (
            <span className="post-count">{posts.length}+</span>
          )}
        </div>

        {error && (
          <div className="error-message">
            <p>{error}</p>
            <button onClick={() => hashtagName && loadPosts(hashtagName)} className="retry-button">
              Retry
            </button>
          </div>
        )}

        {posts.length === 0 && loading && hashtagName && (
          <div className="loading-state">
            <div className="loading-spinner"></div>
            <p>Loading posts...</p>
          </div>
        )}

        {posts.length === 0 && !loading && !error && hashtagName && (
          <div className="empty-state">
            <span className="empty-icon">#</span>
            <p>No posts found with #{hashtagName}</p>
          </div>
        )}

        {!hashtagName && (
          <div className="empty-state">
            <p>Invalid hashtag</p>
          </div>
        )}

        {posts.length > 0 && (
          <CardGrid 
            posts={posts} 
            API_BASE_URL={API_BASE_URL}
            source={{ type: 'hashtag', id: hashtagName }}
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

        .hashtag-header {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 24px;
          background: var(--bg-secondary);
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .hashtag-symbol {
          font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
          font-weight: 700;
          font-size: 2rem;
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .hashtag-name {
          font-size: 1.5rem;
          font-weight: 600;
          color: var(--text-primary);
        }

        .post-count {
          font-size: 0.9rem;
          color: var(--text-muted);
          background: var(--bg-tertiary);
          padding: 4px 12px;
          border-radius: 12px;
          margin-left: auto;
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
          font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
          font-weight: 700;
          opacity: 0.3;
        }

        .loading-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 4rem 2rem;
          text-align: center;
          color: var(--text-muted);
          gap: 16px;
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
          border-top-color: var(--accent-purple);
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

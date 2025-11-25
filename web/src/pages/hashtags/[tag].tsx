import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import { useArtworkScaling } from '../../hooks/useArtworkScaling';

interface Post {
  id: string;
  title: string;
  description?: string;
  hashtags?: string[];
  art_url: string;
  canvas: string;
  owner_id: string;
  created_at: string;
}

interface PageResponse<T> {
  items: T[];
  next_cursor: string | null;
}

export default function HashtagPage() {
  const router = useRouter();
  const { tag } = router.query;
  
  const [posts, setPosts] = useState<Post[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  
  const observerTarget = useRef<HTMLDivElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);
  const nextCursorRef = useRef<string | null>(null);
  
  // Apply integer multiple scaling to artworks
  useArtworkScaling(gridRef);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
    : '';

  // Check authentication on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/auth');
    }
  }, [router]);

  const loadPosts = useCallback(async (hashtag: string, cursor: string | null = null) => {
    if (loadingRef.current || (!hasMoreRef.current && cursor !== null) || !hashtag) return;
    
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/auth');
      return;
    }
    
    loadingRef.current = true;
    setLoading(true);
    setError(null);
    
    try {
      const url = `${API_BASE_URL}/api/posts?hashtag=${encodeURIComponent(hashtag)}&limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
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
  }, [API_BASE_URL, router]);

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

  // Intersection Observer for infinite scroll
  useEffect(() => {
    if (!tag || typeof tag !== 'string') return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMoreRef.current && !loadingRef.current) {
          loadPosts(tag, nextCursorRef.current);
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
  }, [tag, loadPosts]);

  const hashtagName = typeof tag === 'string' ? tag : '';

  return (
    <Layout title={`#${hashtagName}`} description={`Pixel art tagged with #${hashtagName}`}>
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

        <div className="artwork-grid" ref={gridRef}>
          {posts.map((post) => (
            <Link key={post.id} href={`/posts/${post.id}`} className="artwork-card">
              <div className="artwork-image-container">
                <img
                  src={post.art_url}
                  alt={post.title}
                  className="artwork-image pixel-art"
                  data-canvas={post.canvas}
                  loading="lazy"
                />
              </div>
            </Link>
          ))}
        </div>

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

        .artwork-grid {
          --artwork-card-size: 256px;
          display: grid;
          grid-template-columns: repeat(2, var(--artwork-card-size));
          gap: var(--grid-gap);
          padding: var(--grid-gap);
          max-width: 1200px;
          margin: 0 auto;
          justify-content: center;
        }

        @media (min-width: 768px) {
          .artwork-grid {
            grid-template-columns: repeat(3, var(--artwork-card-size));
          }
        }

        @media (min-width: 1024px) {
          .artwork-grid {
            grid-template-columns: repeat(4, var(--artwork-card-size));
          }
        }

        .artwork-card {
          display: block;
          aspect-ratio: 1;
          background: var(--bg-secondary);
          overflow: hidden;
          transition: transform var(--transition-fast), box-shadow var(--transition-fast), width var(--transition-fast), height var(--transition-fast);
        }

        .artwork-card:hover {
          transform: scale(1.02);
          box-shadow: var(--glow-purple);
          z-index: 1;
        }

        .artwork-image-container {
          width: 100%;
          height: 100%;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--bg-tertiary);
        }

        .artwork-image {
          width: 100%;
          height: 100%;
          object-fit: contain;
          image-rendering: -webkit-optimize-contrast !important;
          image-rendering: -moz-crisp-edges !important;
          image-rendering: crisp-edges !important;
          image-rendering: pixelated !important;
          -ms-interpolation-mode: nearest-neighbor !important;
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
        }
      `}</style>
    </Layout>
  );
}

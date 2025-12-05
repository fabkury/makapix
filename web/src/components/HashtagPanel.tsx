import { useState, useEffect, useRef } from 'react';
import CardRoller from './CardRoller';
import { authenticatedFetch, clearTokens } from '../lib/api';
import { useRouter } from 'next/router';

interface HashtagStats {
  tag: string;
  reaction_count: number;
  comment_count: number;
  artwork_count: number;
}

interface HashtagPanelProps {
  API_BASE_URL: string;
  searchQuery?: string;
  sortBy?: 'popularity' | 'alphabetical';
}

export default function HashtagPanel({ API_BASE_URL, searchQuery = '', sortBy = 'popularity' }: HashtagPanelProps) {
  const router = useRouter();
  const [hashtags, setHashtags] = useState<HashtagStats[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const observerTarget = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);
  const nextCursorRef = useRef<string | null>(null);

  // Fetch hashtags with statistics
  const fetchHashtags = async (cursor: string | null = null, append = false) => {
    if (loadingRef.current || (!hasMoreRef.current && cursor !== null)) return;
    
    loadingRef.current = true;
    if (!append) {
      setLoading(true);
    } else {
      setLoadingMore(true);
    }
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set('limit', '15'); // Paginate 15 hashtags at a time
      params.set('sort', sortBy);
      
      if (searchQuery.trim()) {
        params.set('q', searchQuery.trim());
      }
      if (cursor) {
        params.set('cursor', cursor);
      }

      const response = await authenticatedFetch(`${API_BASE_URL}/api/hashtags/stats?${params.toString()}`);

      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }

      if (!response.ok) {
        if (response.status === 404) {
          setHashtags([]);
          setNextCursor(null);
          hasMoreRef.current = false;
          return;
        }
        throw new Error(`Failed to fetch hashtags: ${response.statusText}`);
      }

      const data: { items: HashtagStats[]; next_cursor: string | null } = await response.json();

      if (append) {
        setHashtags(prev => [...prev, ...data.items]);
      } else {
        setHashtags(data.items);
      }
      
      setNextCursor(data.next_cursor);
      nextCursorRef.current = data.next_cursor;
      hasMoreRef.current = data.next_cursor !== null;
    } catch (err) {
      console.error('Error fetching hashtags:', err);
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to load hashtags');
      }
    } finally {
      loadingRef.current = false;
      setLoading(false);
      setLoadingMore(false);
    }
  };

  // Fetch hashtags when searchQuery or sortBy changes
  useEffect(() => {
    setHashtags([]);
    setNextCursor(null);
    nextCursorRef.current = null;
    hasMoreRef.current = true;
    fetchHashtags();
  }, [searchQuery, sortBy, API_BASE_URL]);

  // Intersection Observer for vertical infinite scroll
  useEffect(() => {
    const target = observerTarget.current;
    if (!target) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMoreRef.current && !loadingRef.current) {
          fetchHashtags(nextCursorRef.current, true);
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(target);

    return () => {
      observer.disconnect();
    };
  }, []);

  if (loading && hashtags.length === 0) {
    return (
      <div className="hashtag-panel-loading">
        <div className="loading-spinner"></div>
        <style jsx>{`
          .hashtag-panel-loading {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 400px;
          }

          .loading-spinner {
            width: 40px;
            height: 40px;
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
        `}</style>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-message">
        <span className="error-icon">⚠️</span>
        <p>{error}</p>
        <button onClick={() => fetchHashtags()} className="retry-button">
          Retry
        </button>
        <style jsx>{`
          .error-message {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 3rem;
            text-align: center;
            color: var(--text-secondary);
          }

          .error-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
          }

          .retry-button {
            margin-top: 1rem;
            padding: 0.75rem 1.5rem;
            background: var(--accent-pink);
            color: white;
            border-radius: 8px;
            font-weight: 600;
            transition: all var(--transition-fast);
            border: none;
            cursor: pointer;
          }

          .retry-button:hover {
            box-shadow: var(--glow-pink);
          }
        `}</style>
      </div>
    );
  }

  if (hashtags.length === 0) {
    return (
      <div className="empty-state">
        <div className="empty-icon-container">
          <span className="empty-icon">#</span>
        </div>
        <h2>No hashtags found</h2>
        {searchQuery && (
          <p className="empty-description">
            No hashtags match &quot;{searchQuery}&quot;
          </p>
        )}
        <style jsx>{`
          .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 4rem 2rem;
            text-align: center;
            max-width: 500px;
            margin: 0 auto;
          }

          .empty-icon-container {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: var(--bg-secondary);
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 24px;
          }

          .empty-icon {
            font-size: 4rem;
            font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
          }

          h2 {
            font-size: 1.5rem;
            color: var(--text-primary);
            margin: 0 0 12px 0;
          }

          .empty-description {
            font-size: 1rem;
            color: var(--text-secondary);
            line-height: 1.6;
            margin: 0;
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="hashtag-panel">
      {hashtags.map((hashtag) => (
        <CardRoller
          key={hashtag.tag}
          hashtag={hashtag.tag}
          stats={hashtag}
          API_BASE_URL={API_BASE_URL}
        />
      ))}
      
      {/* Observer target for loading more hashtags */}
      <div ref={observerTarget} className="load-more-trigger">
        {loadingMore && (
          <div className="loading-indicator">
            <div className="loading-spinner"></div>
          </div>
        )}
        {!hasMoreRef.current && hashtags.length > 0 && (
          <div className="end-message">
            <span>✨ That&apos;s all! ✨</span>
          </div>
        )}
      </div>

      <style jsx>{`
        .hashtag-panel {
          width: 100%;
          min-height: calc(100vh - var(--header-height) - 60px);
        }

        .load-more-trigger {
          height: 100px;
          display: flex;
          align-items: center;
          justify-content: center;
          margin-top: 32px;
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
          font-size: 1rem;
          text-align: center;
        }
      `}</style>
    </div>
  );
}

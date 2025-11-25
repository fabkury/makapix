import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';

interface HashtagItem {
  tag: string;
  count: number;
}

interface HashtagListResponse {
  items: HashtagItem[];
  next_cursor: string | null;
}

export default function HashtagsPage() {
  const router = useRouter();
  const [hashtags, setHashtags] = useState<HashtagItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'popularity' | 'alphabetical'>('popularity');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
    : '';

  // Check authentication
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/auth');
      return;
    }
    setIsAuthenticated(true);
  }, [router]);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const fetchHashtags = useCallback(async (cursor?: string, append = false) => {
    if (!append) {
      setLoading(true);
    } else {
      setLoadingMore(true);
    }
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set('limit', '50');
      params.set('sort', sortBy); // API supports alphabetical, popularity, recent
      
      if (debouncedQuery.trim()) {
        params.set('q', debouncedQuery.trim());
      }
      if (cursor) {
        params.set('cursor', cursor);
      }

      const headers: HeadersInit = {};
      const token = localStorage.getItem('access_token');
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${API_BASE_URL}/api/hashtags?${params.toString()}`, { headers });

      if (!response.ok) {
        if (response.status === 404) {
          setHashtags([]);
          setNextCursor(null);
          return;
        }
        throw new Error(`Failed to fetch hashtags: ${response.statusText}`);
      }

      const data: HashtagListResponse = await response.json();
      const items = data.items || [];

      if (append) {
        setHashtags(prev => [...prev, ...items]);
      } else {
        setHashtags(items);
      }
      setNextCursor(data.next_cursor);
    } catch (err) {
      console.error('Error fetching hashtags:', err);
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to load hashtags');
      }
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [API_BASE_URL, debouncedQuery, sortBy]);

  // Fetch hashtags when query or sort changes
  useEffect(() => {
    fetchHashtags();
  }, [fetchHashtags]);

  const handleLoadMore = () => {
    if (nextCursor && !loadingMore) {
      fetchHashtags(nextCursor, true);
    }
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  };

  const handleSortChange = (newSort: 'popularity' | 'alphabetical') => {
    setSortBy(newSort);
    setHashtags([]);
    setNextCursor(null);
  };

  // Don't render until authenticated
  if (!isAuthenticated) {
    return (
      <Layout title="Browse Hashtags">
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
          <div className="loading-spinner" style={{ width: 40, height: 40, border: '3px solid var(--bg-tertiary)', borderTopColor: 'var(--accent-cyan)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }}></div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title="Browse Hashtags" description="Explore hashtags used in pixel art">
      <div className="hashtags-container">
        <div className="hashtags-header">
          <h1>Hashtags</h1>
        </div>

        <div className="controls">
          <div className="search-box">
            <span className="search-icon">🔍</span>
            <input
              type="text"
              placeholder="Search hashtags..."
              value={searchQuery}
              onChange={handleSearchChange}
              className="search-input"
            />
            {searchQuery && (
              <button 
                className="clear-search"
                onClick={() => setSearchQuery('')}
              >
                ✕
              </button>
            )}
          </div>

          <div className="sort-buttons">
            <button
              className={`sort-btn ${sortBy === 'popularity' ? 'active' : ''}`}
              onClick={() => handleSortChange('popularity')}
            >
              Popular
            </button>
            <button
              className={`sort-btn ${sortBy === 'alphabetical' ? 'active' : ''}`}
              onClick={() => handleSortChange('alphabetical')}
            >
              A-Z
            </button>
          </div>
        </div>

        {error && (
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            <p>{error}</p>
            <button onClick={() => fetchHashtags()} className="retry-button">
              Retry
            </button>
          </div>
        )}

        {loading && (
          <div className="loading-state">
            <div className="loading-spinner"></div>
          </div>
        )}

        {!loading && !error && hashtags.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon-container">
              <span className="empty-icon">#</span>
            </div>
            {debouncedQuery ? (
              <>
                <h2>No hashtags found</h2>
                <p className="empty-description">
                  No hashtags match &quot;{debouncedQuery}&quot;
                </p>
                <button onClick={() => setSearchQuery('')} className="browse-link">
                  Clear Search
                </button>
              </>
            ) : (
              <>
                <h2>No hashtags yet</h2>
                <Link href="/" className="browse-link">
                  Browse Recent Art →
                </Link>
              </>
            )}
          </div>
        )}

        {!loading && !error && hashtags.length > 0 && (
          <>
            <div className="hashtags-count">
              {hashtags.length} hashtag{hashtags.length !== 1 ? 's' : ''}
              {debouncedQuery && ` matching "${debouncedQuery}"`}
            </div>

            <div className="hashtags-grid">
              {hashtags.map((hashtag) => (
                <Link 
                  key={hashtag.tag} 
                  href={`/hashtags/${encodeURIComponent(hashtag.tag)}`}
                  className="hashtag-card"
                >
                  <span className="hashtag-symbol">#</span>
                  <span className="hashtag-name">{hashtag.tag}</span>
                  {hashtag.count > 0 && (
                    <span className="hashtag-count">{hashtag.count}</span>
                  )}
                </Link>
              ))}
            </div>

            {nextCursor && (
              <div className="load-more-container">
                <button 
                  onClick={handleLoadMore} 
                  disabled={loadingMore}
                  className="load-more-btn"
                >
                  {loadingMore ? 'Loading...' : 'Load More'}
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <style jsx>{`
        .hashtags-container {
          width: 100%;
          min-height: calc(100vh - var(--header-height));
          padding: 24px;
          max-width: 1200px;
          margin: 0 auto;
        }

        .hashtags-header {
          text-align: center;
          margin-bottom: 32px;
        }

        .hashtags-header h1 {
          font-size: 2rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0;
        }

        .controls {
          display: flex;
          flex-wrap: wrap;
          gap: 16px;
          margin-bottom: 24px;
          align-items: center;
          justify-content: space-between;
        }

        .search-box {
          flex: 1;
          min-width: 250px;
          max-width: 400px;
          position: relative;
          display: flex;
          align-items: center;
        }

        .search-icon {
          position: absolute;
          left: 16px;
          font-size: 1rem;
          opacity: 0.6;
        }

        .search-input {
          width: 100%;
          padding: 12px 40px 12px 44px;
          background: var(--bg-secondary);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          color: var(--text-primary);
          font-size: 1rem;
          transition: all var(--transition-fast);
        }

        .search-input:focus {
          outline: none;
          border-color: var(--accent-cyan);
          box-shadow: 0 0 0 3px rgba(78, 205, 196, 0.15);
        }

        .search-input::placeholder {
          color: var(--text-muted);
        }

        .clear-search {
          position: absolute;
          right: 12px;
          width: 24px;
          height: 24px;
          border-radius: 50%;
          background: var(--bg-tertiary);
          color: var(--text-muted);
          font-size: 0.8rem;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all var(--transition-fast);
        }

        .clear-search:hover {
          background: var(--accent-pink);
          color: white;
        }

        .sort-buttons {
          display: flex;
          gap: 8px;
        }

        .sort-btn {
          padding: 10px 20px;
          background: var(--bg-secondary);
          color: var(--text-secondary);
          border-radius: 8px;
          font-size: 0.9rem;
          font-weight: 500;
          transition: all var(--transition-fast);
        }

        .sort-btn:hover {
          background: var(--bg-tertiary);
        }

        .sort-btn.active {
          background: var(--accent-cyan);
          color: var(--bg-primary);
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
        }

        .retry-button:hover {
          box-shadow: var(--glow-pink);
        }

        .loading-state {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 4rem;
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

        .empty-state h2 {
          font-size: 1.5rem;
          color: var(--text-primary);
          margin: 0 0 12px 0;
        }

        .empty-description {
          font-size: 1rem;
          color: var(--text-secondary);
          line-height: 1.6;
          margin: 0 0 24px 0;
        }

        .browse-link {
          display: inline-block;
          padding: 12px 24px;
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          color: white;
          font-weight: 600;
          border-radius: 10px;
          transition: all var(--transition-fast);
        }

        .browse-link:hover {
          box-shadow: var(--glow-purple);
          transform: translateY(-2px);
        }

        .hashtags-count {
          font-size: 0.9rem;
          color: var(--text-muted);
          margin-bottom: 16px;
        }

        .hashtags-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
          gap: 12px;
        }

        @media (min-width: 768px) {
          .hashtags-grid {
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
          }
        }

        .hashtag-card {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 16px 20px;
          background: var(--bg-secondary);
          border-radius: 12px;
          text-decoration: none;
          transition: all var(--transition-fast);
          border: 1px solid transparent;
        }

        .hashtag-card:hover {
          background: var(--bg-tertiary);
          border-color: var(--accent-purple);
          box-shadow: var(--glow-purple);
          transform: translateY(-2px);
        }

        .hashtag-symbol {
          font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
          font-weight: 700;
          font-size: 1.25rem;
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .hashtag-name {
          flex: 1;
          font-size: 0.95rem;
          font-weight: 500;
          color: var(--text-primary);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .hashtag-count {
          font-size: 0.8rem;
          color: var(--text-muted);
          background: var(--bg-primary);
          padding: 2px 8px;
          border-radius: 10px;
        }

        .load-more-container {
          display: flex;
          justify-content: center;
          margin-top: 32px;
        }

        .load-more-btn {
          padding: 14px 32px;
          background: var(--bg-secondary);
          color: var(--accent-cyan);
          border-radius: 10px;
          font-size: 1rem;
          font-weight: 600;
          transition: all var(--transition-fast);
        }

        .load-more-btn:hover:not(:disabled) {
          background: var(--bg-tertiary);
          box-shadow: var(--glow-cyan);
        }

        .load-more-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        @media (max-width: 600px) {
          .controls {
            flex-direction: column;
            align-items: stretch;
          }

          .search-box {
            max-width: 100%;
          }

          .sort-buttons {
            justify-content: center;
          }
        }
      `}</style>
    </Layout>
  );
}

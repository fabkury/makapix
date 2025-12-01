import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';
import CardGrid from '../components/CardGrid';
import { authenticatedFetch, clearTokens } from '../lib/api';

// Search Tab Interfaces
interface PostOwner {
  id: string;
  handle: string;
}

interface Post {
  id: number;
  public_sqid: string;
  title: string;
  description?: string;
  hashtags?: string[];
  art_url: string;
  canvas: string;
  owner_id: string;
  created_at: string;
  owner?: PostOwner;
}

interface User {
  id: string;
  handle: string;
  display_name: string;
  avatar_url?: string;
  reputation: number;
}

interface SearchResultUser {
  type: 'users';
  user: User;
}

interface SearchResultPost {
  type: 'posts';
  post: Post;
}

type SearchResult = SearchResultUser | SearchResultPost;

interface SearchResults {
  items: SearchResult[];
  next_cursor: string | null;
}

// Hashtags Tab Interfaces
interface HashtagItem {
  tag: string;
  count: number;
}

interface HashtagListResponse {
  items: HashtagItem[];
  next_cursor: string | null;
}

// Users Tab Interfaces
interface UserDirectory {
  id: string;
  handle: string;
  bio: string | null;
  avatar_url: string | null;
  reputation: number;
  created_at: string;
}

interface UserListResponse {
  items: UserDirectory[];
  next_cursor: string | null;
}

type TabType = 'search' | 'hashtags' | 'users';

export default function SearchPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>('search');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Check authentication on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/auth');
      return;
    }
    setIsAuthenticated(true);
  }, [router]);

  // Read tab from URL query parameter
  useEffect(() => {
    const tab = router.query.tab as string;
    if (tab === 'hashtags' || tab === 'users' || tab === 'search') {
      setActiveTab(tab);
    } else {
      setActiveTab('search');
    }
  }, [router.query.tab]);

  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab);
    router.replace({ query: { ...router.query, tab } }, undefined, { shallow: true });
  };

  // Don't render until authenticated
  if (!isAuthenticated) {
    return (
      <Layout title="Search">
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
          <div className="loading-spinner" style={{ width: 40, height: 40, border: '3px solid var(--bg-tertiary)', borderTopColor: 'var(--accent-cyan)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }}></div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title="Search" description="Search for pixel art, hashtags, and users">
      <div className="search-container">
        <div className="tabs-header">
          <div className="tabs-nav">
            <button
              className={`tab-button ${activeTab === 'search' ? 'active' : ''}`}
              onClick={() => handleTabChange('search')}
            >
              🔍 Search
            </button>
            <button
              className={`tab-button ${activeTab === 'hashtags' ? 'active' : ''}`}
              onClick={() => handleTabChange('hashtags')}
            >
              # Hashtags
            </button>
            <button
              className={`tab-button ${activeTab === 'users' ? 'active' : ''}`}
              onClick={() => handleTabChange('users')}
            >
              👥 Users
            </button>
          </div>
        </div>

        <div className="tabs-content">
          <div className={`tab-panel ${activeTab === 'search' ? 'active' : ''}`}>
            <SearchTab API_BASE_URL={API_BASE_URL} router={router} />
          </div>
          <div className={`tab-panel ${activeTab === 'hashtags' ? 'active' : ''}`}>
            <HashtagsTab API_BASE_URL={API_BASE_URL} router={router} />
          </div>
          <div className={`tab-panel ${activeTab === 'users' ? 'active' : ''}`}>
            <UsersTab API_BASE_URL={API_BASE_URL} router={router} />
          </div>
        </div>
      </div>

      <style jsx>{`
        .search-container {
          width: 100%;
          min-height: calc(100vh - var(--header-height));
        }

        .tabs-header {
          position: sticky;
          top: var(--header-height);
          z-index: 50;
          background: var(--bg-primary);
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .tabs-nav {
          display: flex;
          gap: 0;
          max-width: 1200px;
          margin: 0 auto;
          padding: 0 16px;
        }

        .tab-button {
          flex: 1;
          padding: 16px 24px;
          background: transparent;
          border: none;
          border-bottom: 3px solid transparent;
          color: var(--text-secondary);
          font-size: 1rem;
          font-weight: 500;
          cursor: pointer;
          transition: all var(--transition-fast);
          text-align: center;
        }

        .tab-button:hover {
          color: var(--text-primary);
          background: var(--bg-secondary);
        }

        .tab-button.active {
          color: var(--accent-cyan);
          border-bottom-color: var(--accent-cyan);
          background: var(--bg-secondary);
        }

        .tabs-content {
          position: relative;
        }

        .tab-panel {
          display: none;
        }

        .tab-panel.active {
          display: block;
        }

        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }

        @media (max-width: 480px) {
          .tab-button {
            padding: 12px 8px;
            font-size: 0.9rem;
          }
        }
      `}</style>
    </Layout>
  );
}

// Artwork Grid Component
function SearchArtworkGrid({ posts, API_BASE_URL }: { posts: Post[]; API_BASE_URL: string }) {
  return <CardGrid posts={posts} API_BASE_URL={API_BASE_URL} />;
}

// Search Tab Component
function SearchTab({ API_BASE_URL, router }: { API_BASE_URL: string; router: any }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const debounceTimer = useRef<NodeJS.Timeout | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Get initial query from URL
  useEffect(() => {
    const q = router.query.q as string;
    if (q) {
      setQuery(q);
      performSearch(q);
    }
  }, [router.query.q]);

  const performSearch = async (searchQuery: string, cursor: string | null = null) => {
    if (!searchQuery.trim()) {
      setResults([]);
      setNextCursor(null);
      return;
    }

    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/auth');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const url = `${API_BASE_URL}/api/search?q=${encodeURIComponent(searchQuery)}&types=users&types=posts&limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
      const response = await authenticatedFetch(url);

      if (response.status === 401) {
        // Token refresh failed - clear tokens and redirect to login
        clearTokens();
        router.push('/auth');
        return;
      }

      if (!response.ok) {
        throw new Error(`Failed to search: ${response.statusText}`);
      }

      const data: SearchResults = await response.json();

      if (cursor) {
        setResults(prev => [...prev, ...data.items]);
      } else {
        setResults(data.items);
      }

      setNextCursor(data.next_cursor);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to search');
      console.error('Error searching:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchChange = (value: string) => {
    setQuery(value);

    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    const newQuery: any = { ...router.query };
    if (value.trim()) {
      newQuery.q = value;
    } else {
      delete newQuery.q;
    }
    router.replace({ query: newQuery }, undefined, { shallow: true });

    debounceTimer.current = setTimeout(() => {
      performSearch(value);
    }, 300);
  };

  const handleLoadMore = () => {
    if (nextCursor && !loading) {
      performSearch(query, nextCursor);
    }
  };

  const postResults = results.filter((r): r is SearchResultPost => r.type === 'posts');
  const userResults = results.filter((r): r is SearchResultUser => r.type === 'users');

  return (
    <>
      <div className="search-header">
        <div className="search-input-wrapper">
          <span className="search-icon">🔍</span>
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search artworks, users, hashtags..."
            className="search-input"
          />
          {loading && <div className="search-spinner"></div>}
        </div>
      </div>

      {error && (
        <div className="error-message">
          <p>{error}</p>
        </div>
      )}

      {results.length === 0 && !loading && query.trim() && (
        <div className="empty-state">
          <span className="empty-icon">🔍</span>
          <p>No results found for &quot;{query}&quot;</p>
        </div>
      )}

      {results.length === 0 && !query.trim() && (
        <div className="empty-state">
          <span className="empty-icon">🔍</span>
          <p>Start typing to search</p>
        </div>
      )}

      {userResults.length > 0 && (
        <section className="results-section">
          <div className="user-results">
            {userResults.map((result) => (
              <Link
                key={result.user.id}
                href={`/user/${result.user.user_key}`}
                className="user-card"
              >
                <div className="user-avatar">
                  {result.user.avatar_url ? (
                    <img src={result.user.avatar_url} alt="" className="avatar-image" />
                  ) : (
                    <span className="avatar-placeholder">👤</span>
                  )}
                </div>
                <div className="user-info">
                  <span className="user-handle">@{result.user.handle}</span>
                  <span className="user-name">{result.user.display_name}</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {postResults.length > 0 && (
        <section className="results-section">
          <SearchArtworkGrid posts={postResults.map(r => r.post)} API_BASE_URL={API_BASE_URL} />
        </section>
      )}

      {nextCursor && (
        <div className="load-more-container">
          <button onClick={handleLoadMore} disabled={loading} className="load-more-button">
            {loading ? 'Loading...' : 'Load More'}
          </button>
        </div>
      )}

      <style jsx>{`
        .search-header {
          padding: 16px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .search-input-wrapper {
          max-width: 600px;
          margin: 0 auto;
          position: relative;
          display: flex;
          align-items: center;
        }

        .search-icon {
          position: absolute;
          left: 16px;
          font-size: 18px;
          pointer-events: none;
        }

        .search-input {
          width: 100%;
          padding: 14px 48px;
          font-size: 1rem;
          background: var(--bg-secondary);
          border: 2px solid var(--bg-tertiary);
          border-radius: 24px;
          color: var(--text-primary);
          transition: all var(--transition-fast);
        }

        .search-input:focus {
          border-color: var(--accent-cyan);
          box-shadow: var(--glow-cyan);
          outline: none;
        }

        .search-input::placeholder {
          color: var(--text-muted);
        }

        .search-spinner {
          position: absolute;
          right: 16px;
          width: 20px;
          height: 20px;
          border: 2px solid var(--bg-tertiary);
          border-top-color: var(--accent-cyan);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        .error-message {
          padding: 2rem;
          text-align: center;
          color: var(--accent-pink);
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
          font-size: 3rem;
          margin-bottom: 1rem;
          opacity: 0.5;
        }

        .results-section {
          padding: 16px;
        }

        .user-results {
          display: flex;
          flex-wrap: wrap;
          gap: 12px;
          max-width: 1200px;
          margin: 0 auto 24px;
        }

        .user-card {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 12px 16px;
          background: var(--bg-secondary);
          border-radius: 12px;
          text-decoration: none;
          transition: all var(--transition-fast);
        }

        .user-card:hover {
          background: var(--bg-tertiary);
          transform: translateY(-2px);
        }

        .user-avatar {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          background: var(--bg-tertiary);
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
        }

        .avatar-image {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }

        .avatar-placeholder {
          font-size: 20px;
        }

        .user-info {
          display: flex;
          flex-direction: column;
        }

        .user-handle {
          font-size: 0.9rem;
          font-weight: 600;
          color: var(--accent-cyan);
        }

        .user-name {
          font-size: 0.8rem;
          color: var(--text-muted);
        }

        .load-more-container {
          padding: 24px;
          text-align: center;
        }

        .load-more-button {
          padding: 12px 32px;
          background: var(--bg-secondary);
          color: var(--text-primary);
          border: 2px solid var(--accent-cyan);
          border-radius: 24px;
          font-size: 1rem;
          font-weight: 500;
          transition: all var(--transition-fast);
          cursor: pointer;
        }

        .load-more-button:hover:not(:disabled) {
          background: var(--accent-cyan);
          color: var(--bg-primary);
          box-shadow: var(--glow-cyan);
        }

        .load-more-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      `}</style>
    </>
  );
}

// Hashtags Tab Component
function HashtagsTab({ API_BASE_URL, router }: { API_BASE_URL: string; router: any }) {
  const [hashtags, setHashtags] = useState<HashtagItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'popularity' | 'alphabetical'>('popularity');

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
      params.set('sort', sortBy);
      
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

  return (
    <>
      <div className="hashtags-content">
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
        .hashtags-content {
          width: 100%;
          min-height: calc(100vh - var(--header-height) - 60px);
          padding: 24px;
          max-width: 1200px;
          margin: 0 auto;
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
          border: none;
          cursor: pointer;
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
          border: none;
          cursor: pointer;
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
          border: none;
          cursor: pointer;
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
          text-decoration: none;
          border: none;
          cursor: pointer;
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
          border: none;
          cursor: pointer;
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
    </>
  );
}

// Users Tab Component
function UsersTab({ API_BASE_URL, router }: { API_BASE_URL: string; router: any }) {
  const [users, setUsers] = useState<UserDirectory[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'alphabetical' | 'recent' | 'reputation'>('alphabetical');

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const fetchUsers = useCallback(async (cursor?: string, append = false) => {
    if (!append) {
      setLoading(true);
    } else {
      setLoadingMore(true);
    }
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set('limit', '50');
      params.set('sort', sortBy);
      
      if (debouncedQuery.trim()) {
        params.set('q', debouncedQuery.trim());
      }
      if (cursor) {
        params.set('cursor', cursor);
      }

      const token = localStorage.getItem('access_token');
      if (!token) {
        throw new Error('Not authenticated');
      }

      const response = await fetch(`${API_BASE_URL}/api/user/browse?${params.toString()}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('user_id');
          router.push('/auth');
          return;
        }
        if (response.status === 404) {
          setUsers([]);
          setNextCursor(null);
          return;
        }
        throw new Error(`Failed to fetch users: ${response.statusText}`);
      }

      const data: UserListResponse = await response.json();
      const items = data.items || [];

      if (append) {
        setUsers(prev => [...prev, ...items]);
      } else {
        setUsers(items);
      }
      setNextCursor(data.next_cursor);
    } catch (err) {
      console.error('Error fetching users:', err);
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to load users');
      }
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [API_BASE_URL, debouncedQuery, sortBy, router]);

  // Fetch users when query or sort changes
  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleLoadMore = () => {
    if (nextCursor && !loadingMore) {
      fetchUsers(nextCursor, true);
    }
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  };

  const handleSortChange = (newSort: 'alphabetical' | 'recent' | 'reputation') => {
    setSortBy(newSort);
    setUsers([]);
    setNextCursor(null);
  };

  const getAvatarUrl = (avatarUrl: string | null): string | null => {
    if (!avatarUrl) return null;
    if (avatarUrl.startsWith('http')) return avatarUrl;
    return `${API_BASE_URL}${avatarUrl}`;
  };

  return (
    <>
      <div className="users-content">
        <div className="controls">
          <div className="search-box">
            <span className="search-icon">🔍</span>
            <input
              type="text"
              placeholder="Search users..."
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
              className={`sort-btn ${sortBy === 'alphabetical' ? 'active' : ''}`}
              onClick={() => handleSortChange('alphabetical')}
            >
              A-Z
            </button>
            <button
              className={`sort-btn ${sortBy === 'recent' ? 'active' : ''}`}
              onClick={() => handleSortChange('recent')}
            >
              Recent
            </button>
            <button
              className={`sort-btn ${sortBy === 'reputation' ? 'active' : ''}`}
              onClick={() => handleSortChange('reputation')}
            >
              Reputation
            </button>
          </div>
        </div>

        {error && (
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            <p>{error}</p>
            <button onClick={() => fetchUsers()} className="retry-button">
              Retry
            </button>
          </div>
        )}

        {loading && (
          <div className="loading-state">
            <div className="loading-spinner"></div>
          </div>
        )}

        {!loading && !error && users.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon-container">
              <span className="empty-icon">👥</span>
            </div>
            {debouncedQuery ? (
              <>
                <h2>No users found</h2>
                <p className="empty-description">
                  No users match &quot;{debouncedQuery}&quot;
                </p>
                <button onClick={() => setSearchQuery('')} className="browse-link">
                  Clear Search
                </button>
              </>
            ) : (
              <>
                <h2>No users yet</h2>
                <Link href="/" className="browse-link">
                  Browse Recent Art →
                </Link>
              </>
            )}
          </div>
        )}

        {!loading && !error && users.length > 0 && (
          <>
            <div className="users-count">
              {users.length} user{users.length !== 1 ? 's' : ''}
              {debouncedQuery && ` matching "${debouncedQuery}"`}
            </div>

            <div className="users-grid">
              {users.map((user) => {
                const avatarUrl = getAvatarUrl(user.avatar_url);
                return (
                  <Link 
                    key={user.id} 
                    href={`/user/${user.user_key}`}
                    className="user-card"
                  >
                    <div className="user-avatar-container">
                      {avatarUrl ? (
                        <img 
                          src={avatarUrl} 
                          alt={user.handle}
                          className="user-avatar"
                        />
                      ) : (
                        <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor" className="user-avatar-icon">
                          <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                        </svg>
                      )}
                    </div>
                    <div className="user-info">
                      <span className="user-handle">{user.handle}</span>
                      {user.reputation > 0 && (
                        <span className="user-reputation">⭐ {user.reputation}</span>
                      )}
                    </div>
                  </Link>
                );
              })}
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
        .users-content {
          width: 100%;
          min-height: calc(100vh - var(--header-height) - 60px);
          padding: 24px;
          max-width: 1200px;
          margin: 0 auto;
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
          border: none;
          cursor: pointer;
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
          border: none;
          cursor: pointer;
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
          border: none;
          cursor: pointer;
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
          text-decoration: none;
          border: none;
          cursor: pointer;
        }

        .browse-link:hover {
          box-shadow: var(--glow-purple);
          transform: translateY(-2px);
        }

        .users-count {
          font-size: 0.9rem;
          color: var(--text-muted);
          margin-bottom: 16px;
        }

        .users-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
          gap: 12px;
        }

        @media (min-width: 768px) {
          .users-grid {
            grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
          }
        }

        .user-card {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 16px 20px;
          background: var(--bg-secondary);
          border-radius: 12px;
          text-decoration: none;
          transition: all var(--transition-fast);
          border: 1px solid transparent;
        }

        .user-card:hover {
          background: var(--bg-tertiary);
          border-color: var(--accent-purple);
          box-shadow: var(--glow-purple);
          transform: translateY(-2px);
        }

        .user-avatar-container {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          background: var(--bg-tertiary);
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          overflow: hidden;
        }

        .user-avatar {
          width: 100%;
          height: 100%;
          object-fit: cover;
          border-radius: 50%;
        }

        .user-avatar-icon {
          width: 24px;
          height: 24px;
          color: var(--text-muted);
        }

        .user-info {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 4px;
          min-width: 0;
        }

        .user-handle {
          font-size: 0.95rem;
          font-weight: 500;
          color: var(--text-primary);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .user-reputation {
          font-size: 0.8rem;
          color: var(--text-muted);
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
          border: none;
          cursor: pointer;
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
    </>
  );
}

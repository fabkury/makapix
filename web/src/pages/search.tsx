import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';

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

export default function SearchPage() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const debounceTimer = useRef<NodeJS.Timeout | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  
  // Check authentication on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/auth');
    }
  }, [router]);

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
    : '';

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

    if (value.trim()) {
      router.replace({ query: { ...router.query, q: value } }, undefined, { shallow: true });
    } else {
      router.replace({ query: {} }, undefined, { shallow: true });
    }

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
    <Layout title="Search" description="Search for pixel art and users">
      <div className="search-container">
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
                  href={`/users/${result.user.id}`}
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
            <div className="artwork-grid">
              {postResults.map((result) => (
                <Link key={result.post.id} href={`/posts/${result.post.id}`} className="artwork-card">
                  <div className="artwork-image-container">
                    <img
                      src={result.post.art_url}
                      alt={result.post.title}
                      className="artwork-image pixel-art"
                      loading="lazy"
                    />
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}

        {nextCursor && (
          <div className="load-more-container">
            <button onClick={handleLoadMore} disabled={loading} className="load-more-button">
              {loading ? 'Loading...' : 'Load More'}
            </button>
          </div>
        )}
      </div>

      <style jsx>{`
        .search-container {
          width: 100%;
          min-height: calc(100vh - var(--header-height));
        }

        .search-header {
          position: sticky;
          top: var(--header-height);
          z-index: 50;
          background: var(--bg-primary);
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

        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
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

        .artwork-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
          gap: var(--grid-gap);
        }

        @media (min-width: 768px) {
          .artwork-grid {
            grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
          }
        }

        .artwork-card {
          display: block;
          aspect-ratio: 1;
          background: var(--bg-secondary);
          overflow: hidden;
          transition: transform var(--transition-fast), box-shadow var(--transition-fast);
        }

        .artwork-card:hover {
          transform: scale(1.02);
          box-shadow: 0 0 20px rgba(0, 212, 255, 0.2);
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
          image-rendering: pixelated;
          image-rendering: -moz-crisp-edges;
          image-rendering: crisp-edges;
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
    </Layout>
  );
}

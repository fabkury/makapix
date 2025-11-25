import { useState, useEffect, useRef } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';

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
  
  // Check authentication on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/auth');
    }
  }, [router]);
  
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

    // Clear existing timer
    if (debounceTimer.current) {
      clearTimeout(debounceTimer.current);
    }

    // Update URL without triggering navigation
    if (value.trim()) {
      router.replace({ query: { ...router.query, q: value } }, undefined, { shallow: true });
    } else {
      router.replace({ query: {} }, undefined, { shallow: true });
    }

    // Debounce search
    debounceTimer.current = setTimeout(() => {
      performSearch(value);
    }, 300);
  };

  const handleLoadMore = () => {
    if (nextCursor && !loading) {
      performSearch(query, nextCursor);
    }
  };

  // Group results by type
  const userResults = results.filter((r): r is SearchResultUser => r.type === 'users');
  const postResults = results.filter((r): r is SearchResultPost => r.type === 'posts');

  return (
    <>
      <Head>
        <title>Search - Makapix</title>
      </Head>
      <div style={styles.container}>
        <header style={styles.header}>
          <h1 style={styles.title}>Makapix</h1>
          <nav style={styles.nav}>
            <Link href="/" style={styles.navLink}>Home</Link>
            <Link href="/recent" style={styles.navLink}>Recent</Link>
            <Link href="/search" style={styles.navLink}>Search</Link>
            <Link href="/publish" style={styles.navLink}>Publish</Link>
          </nav>
        </header>

        <main style={styles.main}>
          <h2 style={styles.sectionTitle}>Search</h2>

          <div style={styles.searchContainer}>
            <input
              type="text"
              value={query}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Search users, posts, or hashtags..."
              style={styles.searchInput}
            />
            {loading && <div style={styles.loadingIndicator}>Searching...</div>}
          </div>

          {error && (
            <div style={styles.error}>
              <p>{error}</p>
            </div>
          )}

          {results.length === 0 && !loading && query.trim() && (
            <div style={styles.empty}>
              <p>No results found for &quot;{query}&quot;</p>
            </div>
          )}

          {results.length === 0 && !query.trim() && (
            <div style={styles.empty}>
              <p>Enter a search query to find users, posts, or hashtags</p>
            </div>
          )}

          {userResults.length > 0 && (
            <section style={styles.section}>
              <h3 style={styles.resultGroupTitle}>Users ({userResults.length})</h3>
              <div style={styles.userGrid}>
                {userResults.map((result) => (
                  <Link
                    key={result.user.id}
                    href={`/users/${result.user.id}`}
                    style={styles.userCard}
                  >
                    {result.user.avatar_url && (
                      <img
                        src={result.user.avatar_url}
                        alt={result.user.display_name}
                        style={styles.userAvatar}
                      />
                    )}
                    <div style={styles.userInfo}>
                      <div style={styles.userHandle}>@{result.user.handle}</div>
                      <div style={styles.userDisplayName}>{result.user.display_name}</div>
                      <div style={styles.userReputation}>Rep: {result.user.reputation}</div>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {postResults.length > 0 && (
            <section style={styles.section}>
              <h3 style={styles.resultGroupTitle}>Posts ({postResults.length})</h3>
              <div style={styles.grid}>
                {postResults.map((result) => (
                  <div key={result.post.id} style={styles.card}>
                    <Link href={`/posts/${result.post.id}`} style={styles.cardLink}>
                      <div style={styles.imageContainer}>
                        <img
                          src={result.post.art_url}
                          alt={result.post.title}
                          style={styles.image}
                          loading="lazy"
                        />
                      </div>
                      <div style={styles.cardContent}>
                        <h4 style={styles.cardTitle}>{result.post.title}</h4>
                        {result.post.description && (
                          <p style={styles.cardDescription}>{result.post.description}</p>
                        )}
                        {result.post.hashtags && result.post.hashtags.length > 0 && (
                          <div style={styles.hashtags}>
                            {result.post.hashtags.map((tag, idx) => (
                              <Link
                                key={idx}
                                href={`/hashtags/${tag}`}
                                style={styles.hashtag}
                                onClick={(e) => e.stopPropagation()}
                              >
                                #{tag}
                              </Link>
                            ))}
                          </div>
                        )}
                      </div>
                    </Link>
                  </div>
                ))}
              </div>
            </section>
          )}

          {nextCursor && (
            <div style={styles.loadMoreContainer}>
              <button onClick={handleLoadMore} disabled={loading} style={styles.loadMoreButton}>
                {loading ? 'Loading...' : 'Load More'}
              </button>
            </div>
          )}
        </main>
      </div>
    </>
  );
}

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    minHeight: '100vh',
    backgroundColor: '#f5f5f5',
  },
  header: {
    backgroundColor: '#fff',
    borderBottom: '1px solid #e0e0e0',
    padding: '1rem 2rem',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  title: {
    fontSize: '1.5rem',
    fontWeight: 'bold',
    margin: 0,
    color: '#333',
  },
  nav: {
    display: 'flex',
    gap: '1.5rem',
  },
  navLink: {
    color: '#666',
    textDecoration: 'none',
    fontSize: '0.9rem',
  },
  main: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '2rem',
  },
  sectionTitle: {
    fontSize: '1.8rem',
    marginBottom: '2rem',
    color: '#333',
  },
  searchContainer: {
    marginBottom: '2rem',
    position: 'relative',
  },
  searchInput: {
    width: '100%',
    padding: '0.75rem 1rem',
    fontSize: '1rem',
    border: '1px solid #ddd',
    borderRadius: '4px',
    outline: 'none',
  },
  loadingIndicator: {
    position: 'absolute',
    right: '1rem',
    top: '50%',
    transform: 'translateY(-50%)',
    color: '#999',
    fontSize: '0.9rem',
  },
  error: {
    backgroundColor: '#fee',
    border: '1px solid #fcc',
    borderRadius: '4px',
    padding: '1rem',
    marginBottom: '2rem',
    textAlign: 'center',
  },
  empty: {
    textAlign: 'center',
    padding: '3rem',
    color: '#666',
  },
  section: {
    marginBottom: '3rem',
  },
  resultGroupTitle: {
    fontSize: '1.3rem',
    marginBottom: '1.5rem',
    color: '#333',
  },
  userGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
    gap: '1rem',
    marginBottom: '2rem',
  },
  userCard: {
    backgroundColor: '#fff',
    borderRadius: '8px',
    padding: '1rem',
    display: 'flex',
    alignItems: 'center',
    gap: '1rem',
    textDecoration: 'none',
    color: 'inherit',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
    transition: 'transform 0.2s',
  },
  userAvatar: {
    width: '50px',
    height: '50px',
    borderRadius: '50%',
    objectFit: 'cover',
  },
  userInfo: {
    flex: 1,
  },
  userHandle: {
    fontWeight: '600',
    fontSize: '0.95rem',
    color: '#333',
  },
  userDisplayName: {
    fontSize: '0.85rem',
    color: '#666',
    marginTop: '0.25rem',
  },
  userReputation: {
    fontSize: '0.75rem',
    color: '#999',
    marginTop: '0.25rem',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: '1.5rem',
  },
  card: {
    backgroundColor: '#fff',
    borderRadius: '8px',
    overflow: 'hidden',
    boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
  },
  cardLink: {
    textDecoration: 'none',
    color: 'inherit',
    display: 'block',
  },
  imageContainer: {
    width: '100%',
    backgroundColor: '#f0f0f0',
    aspectRatio: '1',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  image: {
    width: '100%',
    height: '100%',
    objectFit: 'contain',
    imageRendering: 'pixelated',
  },
  cardContent: {
    padding: '1rem',
  },
  cardTitle: {
    fontSize: '1rem',
    fontWeight: '600',
    margin: '0 0 0.5rem 0',
    color: '#333',
  },
  cardDescription: {
    fontSize: '0.85rem',
    color: '#666',
    margin: '0 0 0.5rem 0',
    lineHeight: '1.4',
  },
  hashtags: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '0.5rem',
  },
  hashtag: {
    fontSize: '0.8rem',
    color: '#2563eb',
    textDecoration: 'none',
  },
  loadMoreContainer: {
    textAlign: 'center',
    marginTop: '2rem',
  },
  loadMoreButton: {
    padding: '0.75rem 2rem',
    backgroundColor: '#2563eb',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontSize: '1rem',
  },
};


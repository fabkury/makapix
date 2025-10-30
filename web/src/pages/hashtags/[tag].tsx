import { useState, useEffect, useRef, useCallback } from 'react';
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
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
    : '';

  const loadPosts = useCallback(async (hashtag: string, cursor: string | null = null) => {
    if (loading || (!hasMore && cursor !== null) || !hashtag) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const url = `${API_BASE_URL}/api/hashtags/${encodeURIComponent(hashtag)}/posts?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
      const response = await fetch(url);
      
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
      setHasMore(data.next_cursor !== null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load posts');
      console.error('Error loading posts:', err);
    } finally {
      setLoading(false);
    }
  }, [API_BASE_URL, loading, hasMore]);

  // Load posts when tag changes
  useEffect(() => {
    if (tag && typeof tag === 'string') {
      setPosts([]);
      setNextCursor(null);
      setHasMore(true);
      loadPosts(tag);
    }
  }, [tag, loadPosts]);

  // Intersection Observer for infinite scroll
  useEffect(() => {
    if (!tag || typeof tag !== 'string') return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading) {
          loadPosts(tag, nextCursor);
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
  }, [hasMore, loading, nextCursor, tag, loadPosts]);

  const hashtagName = typeof tag === 'string' ? tag : '';

  return (
    <>
      <Head>
        <title>#{hashtagName} - Makapix</title>
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
          <h2 style={styles.sectionTitle}>#{hashtagName}</h2>
          {posts.length > 0 && (
            <p style={styles.count}>{posts.length} {posts.length === 1 ? 'post' : 'posts'}</p>
          )}
          
          {error && (
            <div style={styles.error}>
              <p>{error}</p>
              <button onClick={() => hashtagName && loadPosts(hashtagName)} style={styles.retryButton}>
                Retry
              </button>
            </div>
          )}

          {posts.length === 0 && !loading && !error && hashtagName && (
            <div style={styles.empty}>
              <p>No posts found with hashtag #{hashtagName}</p>
            </div>
          )}

          {!hashtagName && (
            <div style={styles.empty}>
              <p>Invalid hashtag</p>
            </div>
          )}

          <div style={styles.grid}>
            {posts.map((post) => (
              <div key={post.id} style={styles.card}>
                <Link href={`/posts/${post.id}`} style={styles.cardLink}>
                  <div style={styles.imageContainer}>
                    <img
                      src={post.art_url}
                      alt={post.title}
                      style={styles.image}
                      loading="lazy"
                    />
                  </div>
                  <div style={styles.cardContent}>
                    <h3 style={styles.cardTitle}>{post.title}</h3>
                    {post.description && (
                      <p style={styles.cardDescription}>{post.description}</p>
                    )}
                    {post.hashtags && post.hashtags.length > 0 && (
                      <div style={styles.hashtags}>
                        {post.hashtags.map((tagItem, idx) => (
                          <Link
                            key={idx}
                            href={`/hashtags/${tagItem}`}
                            style={styles.hashtag}
                            onClick={(e) => e.stopPropagation()}
                          >
                            #{tagItem}
                          </Link>
                        ))}
                      </div>
                    )}
                    <div style={styles.cardMeta}>
                      <span style={styles.canvas}>{post.canvas}</span>
                      <span style={styles.date}>
                        {new Date(post.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </Link>
              </div>
            ))}
          </div>

          {/* Loading indicator / Observer target */}
          <div ref={observerTarget} style={styles.observerTarget}>
            {loading && (
              <div style={styles.loading}>
                <p>Loading more posts...</p>
              </div>
            )}
            {!hasMore && posts.length > 0 && (
              <div style={styles.endMessage}>
                <p>You&apos;ve reached the end!</p>
              </div>
            )}
          </div>
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
    marginBottom: '0.5rem',
    color: '#333',
  },
  count: {
    fontSize: '1rem',
    color: '#666',
    marginBottom: '2rem',
  },
  error: {
    backgroundColor: '#fee',
    border: '1px solid #fcc',
    borderRadius: '4px',
    padding: '1rem',
    marginBottom: '2rem',
    textAlign: 'center',
  },
  retryButton: {
    marginTop: '0.5rem',
    padding: '0.5rem 1rem',
    backgroundColor: '#dc2626',
    color: 'white',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
  },
  empty: {
    textAlign: 'center',
    padding: '3rem',
    color: '#666',
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
    transition: 'transform 0.2s, box-shadow 0.2s',
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
    fontSize: '1.1rem',
    fontWeight: '600',
    margin: '0 0 0.5rem 0',
    color: '#333',
  },
  cardDescription: {
    fontSize: '0.9rem',
    color: '#666',
    margin: '0 0 0.5rem 0',
    lineHeight: '1.4',
  },
  hashtags: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '0.5rem',
    marginBottom: '0.5rem',
  },
  hashtag: {
    fontSize: '0.85rem',
    color: '#2563eb',
    textDecoration: 'none',
  },
  cardMeta: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '0.8rem',
    color: '#999',
    marginTop: '0.5rem',
  },
  canvas: {
    fontWeight: '500',
  },
  date: {},
  observerTarget: {
    height: '100px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  loading: {
    textAlign: 'center',
    color: '#666',
    padding: '2rem',
  },
  endMessage: {
    textAlign: 'center',
    color: '#999',
    padding: '2rem',
  },
};


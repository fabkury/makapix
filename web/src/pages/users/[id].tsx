import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';

interface User {
  id: string;
  handle: string;
  display_name: string;
  bio?: string;
  avatar_url?: string;
  reputation: number;
  created_at: string;
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
}

interface PageResponse<T> {
  items: T[];
  next_cursor: string | null;
}

export default function UserProfilePage() {
  const router = useRouter();
  const { id } = router.query;
  
  const [user, setUser] = useState<User | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [postsLoading, setPostsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  
  const observerTarget = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);
  const nextCursorRef = useRef<string | null>(null);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
    : '';

  // Fetch user profile
  useEffect(() => {
    if (!id || typeof id !== 'string') return;

    const fetchUser = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const token = localStorage.getItem('access_token');
        const headers: HeadersInit = token ? { 'Authorization': `Bearer ${token}` } : {};
        
        const response = await fetch(`${API_BASE_URL}/api/profiles/${id}`, { headers });
        
        if (!response.ok) {
          if (response.status === 404) {
            setError('User not found');
          } else {
            setError(`Failed to load profile: ${response.statusText}`);
          }
          setLoading(false);
          return;
        }
        
        const data = await response.json();
        setUser(data);
      } catch (err) {
        setError('Failed to load profile');
        console.error('Error fetching user:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchUser();
  }, [id, API_BASE_URL]);

  // Load user's posts
  const loadPosts = useCallback(async (cursor: string | null = null) => {
    if (!id || typeof id !== 'string') return;
    if (loadingRef.current || (cursor !== null && !hasMoreRef.current)) return;
    
    loadingRef.current = true;
    setPostsLoading(true);
    
    try {
      const token = localStorage.getItem('access_token');
      const headers: HeadersInit = token ? { 'Authorization': `Bearer ${token}` } : {};
      
      const url = `${API_BASE_URL}/api/posts?owner_id=${id}&limit=20&sort=created_at&order=desc${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
      const response = await fetch(url, { headers });
      
      if (!response.ok) {
        throw new Error('Failed to load posts');
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
      console.error('Error loading posts:', err);
    } finally {
      loadingRef.current = false;
      setPostsLoading(false);
    }
  }, [id, API_BASE_URL]);

  // Load posts when user is loaded
  useEffect(() => {
    if (user) {
      loadPosts();
    }
  }, [user, loadPosts]);

  // Intersection Observer for infinite scroll
  useEffect(() => {
    if (!user || posts.length === 0 || !hasMoreRef.current) return;
    
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMoreRef.current && !loadingRef.current) {
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
  }, [user, posts.length, loadPosts]);

  if (loading) {
    return (
      <Layout title="Loading...">
        <div className="loading-container">
          <div className="loading-spinner"></div>
        </div>
        <style jsx>{`
          .loading-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - var(--header-height));
          }
          .loading-spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--bg-tertiary);
            border-top-color: var(--accent-cyan);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
          }
          @keyframes spin { to { transform: rotate(360deg); } }
        `}</style>
      </Layout>
    );
  }

  if (error || !user) {
    return (
      <Layout title="Not Found">
        <div className="error-container">
          <span className="error-icon">😢</span>
          <h1>{error || 'User not found'}</h1>
          <Link href="/" className="back-link">← Back to Home</Link>
        </div>
        <style jsx>{`
          .error-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - var(--header-height));
            padding: 2rem;
            text-align: center;
          }
          .error-icon {
            font-size: 4rem;
            margin-bottom: 1rem;
          }
          h1 {
            font-size: 1.5rem;
            color: var(--text-primary);
            margin-bottom: 1rem;
          }
          .back-link {
            color: var(--accent-cyan);
            font-size: 1rem;
          }
        `}</style>
      </Layout>
    );
  }

  return (
    <Layout title={user.display_name || user.handle} description={user.bio || `${user.display_name}'s profile on Makapix Club`}>
      <div className="profile-container">
        <div className="profile-header">
          <div className="avatar-container">
            {user.avatar_url ? (
              <img src={user.avatar_url} alt={user.display_name} className="avatar" />
            ) : (
              <div className="avatar-placeholder">
                {user.display_name?.charAt(0) || user.handle.charAt(0)}
              </div>
            )}
          </div>
          
          <div className="profile-info">
            <h1 className="display-name">{user.display_name}</h1>
            <p className="handle">@{user.handle}</p>
            
            {user.bio && (
              <p className="bio">{user.bio}</p>
            )}
            
            <div className="stats">
              <div className="stat">
                <span className="stat-value">{posts.length}+</span>
                <span className="stat-label">artworks</span>
              </div>
              <div className="stat">
                <span className="stat-value">{user.reputation}</span>
                <span className="stat-label">reputation</span>
              </div>
              <div className="stat">
                <span className="stat-value">{new Date(user.created_at).getFullYear()}</span>
                <span className="stat-label">joined</span>
              </div>
            </div>
          </div>
        </div>

        <div className="artworks-section">
          {posts.length === 0 && !postsLoading && (
            <div className="empty-state">
              <span className="empty-icon">🎨</span>
              <p>No artworks yet</p>
            </div>
          )}

          <div className="artwork-grid">
            {posts.map((post) => (
              <Link key={post.id} href={`/posts/${post.id}`} className="artwork-card">
                <div className="artwork-image-container">
                  <img
                    src={post.art_url}
                    alt={post.title}
                    className="artwork-image pixel-art"
                    loading="lazy"
                  />
                </div>
              </Link>
            ))}
          </div>

          {posts.length > 0 && (
            <div ref={observerTarget} className="load-more-trigger">
              {postsLoading && (
                <div className="loading-indicator">
                  <div className="loading-spinner-small"></div>
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
      </div>

      <style jsx>{`
        .profile-container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 24px;
        }

        .profile-header {
          display: flex;
          gap: 24px;
          align-items: flex-start;
          background: var(--bg-secondary);
          border-radius: 16px;
          padding: 32px;
          margin-bottom: 24px;
        }

        @media (max-width: 600px) {
          .profile-header {
            flex-direction: column;
            align-items: center;
            text-align: center;
          }
        }

        .avatar-container {
          flex-shrink: 0;
        }

        .avatar {
          width: 120px;
          height: 120px;
          border-radius: 50%;
          object-fit: cover;
          border: 3px solid var(--bg-tertiary);
        }

        .avatar-placeholder {
          width: 120px;
          height: 120px;
          border-radius: 50%;
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 3rem;
          font-weight: 700;
          color: white;
          text-transform: uppercase;
        }

        .profile-info {
          flex: 1;
        }

        .display-name {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0 0 4px 0;
        }

        .handle {
          font-size: 1rem;
          color: var(--accent-cyan);
          margin: 0 0 16px 0;
        }

        .bio {
          font-size: 1rem;
          color: var(--text-secondary);
          line-height: 1.6;
          margin: 0 0 20px 0;
          max-width: 600px;
        }

        .stats {
          display: flex;
          gap: 32px;
        }

        @media (max-width: 600px) {
          .stats {
            justify-content: center;
          }
        }

        .stat {
          display: flex;
          flex-direction: column;
          align-items: center;
        }

        .stat-value {
          font-size: 1.5rem;
          font-weight: 700;
          color: var(--text-primary);
        }

        .stat-label {
          font-size: 0.8rem;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .artworks-section {
          min-height: 400px;
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
          opacity: 0.5;
        }

        .artwork-grid {
          display: grid;
          grid-template-columns: repeat(1, 1fr);
          gap: var(--grid-gap);
          padding: var(--grid-gap);
          max-width: 1200px;
          margin: 0 auto;
        }

        @media (min-width: 500px) {
          .artwork-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (min-width: 768px) {
          .artwork-grid {
            grid-template-columns: repeat(3, 1fr);
          }
        }

        @media (min-width: 1024px) {
          .artwork-grid {
            grid-template-columns: repeat(4, 1fr);
          }
        }

        .artwork-card {
          display: block;
          aspect-ratio: 1;
          background: var(--bg-secondary);
          overflow: hidden;
          border-radius: 8px;
          transition: transform var(--transition-fast), box-shadow var(--transition-fast);
        }

        .artwork-card:hover {
          transform: scale(1.02);
          box-shadow: 0 0 20px rgba(0, 212, 255, 0.2);
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

        .loading-spinner-small {
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


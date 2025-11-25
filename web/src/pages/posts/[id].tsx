import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Script from 'next/script';
import Layout from '../../components/Layout';

interface Post {
  id: string;
  title: string;
  description?: string;
  hashtags?: string[];
  art_url: string;
  canvas: string;
  owner_id: string;
  created_at: string;
  kind?: string;
  hidden_by_user?: boolean;
  owner?: {
    id: string;
    handle: string;
    display_name: string;
  };
}

export default function PostPage() {
  const router = useRouter();
  const { id } = router.query;
  const [post, setPost] = useState<Post | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<{ id: string } | null>(null);
  const [isOwner, setIsOwner] = useState(false);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
    : '';

  useEffect(() => {
    if (!id || typeof id !== 'string') return;

    const fetchPost = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const response = await fetch(`${API_BASE_URL}/api/posts/${id}`);
        
        if (!response.ok) {
          if (response.status === 404) {
            setError('Post not found');
          } else {
            setError(`Failed to load post: ${response.statusText}`);
          }
          setLoading(false);
          return;
        }
        
        const data = await response.json();
        setPost(data);
        
        const accessToken = localStorage.getItem('access_token');
        if (accessToken) {
          try {
            const userResponse = await fetch(`${API_BASE_URL}/api/auth/me`, {
              headers: {
                'Authorization': `Bearer ${accessToken}`
              }
            });
            if (userResponse.ok) {
              const userData = await userResponse.json();
              setCurrentUser({ id: userData.user.id });
              setIsOwner(userData.user.id === data.owner_id);
            }
          } catch (err) {
            setCurrentUser(null);
            setIsOwner(false);
          }
        }
      } catch (err) {
        setError('Failed to load post');
        console.error('Error fetching post:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPost();
  }, [id, API_BASE_URL]);

  // Set API URL for widget
  useEffect(() => {
    if (typeof window === 'undefined') return;
    
    if ((window as any).MAKAPIX_API_URL === undefined) {
      (window as any).MAKAPIX_API_URL = `${API_BASE_URL}/api`;
    }
  }, [API_BASE_URL]);

  // Initialize widget
  useEffect(() => {
    if (!post || !id || typeof id !== 'string') return;

    const initializeWidget = () => {
      if (typeof (window as any).MakapixWidget === 'undefined') {
        setTimeout(initializeWidget, 100);
        return;
      }

      const container = document.getElementById(`makapix-widget-${post.id}`);
      if (!container) {
        setTimeout(initializeWidget, 100);
        return;
      }

      if ((container as any).__makapix_initialized) {
        return;
      }

      try {
        new (window as any).MakapixWidget(container);
        (container as any).__makapix_initialized = true;
      } catch (error) {
        console.error('Failed to initialize Makapix widget:', error);
      }
    };

    const timer = setTimeout(initializeWidget, 100);

    return () => {
      clearTimeout(timer);
    };
  }, [post, id]);

  const handleDelete = async () => {
    if (!post || !id || typeof id !== 'string') return;
    
    const confirmed = confirm(
      'Are you sure you want to delete this post?\n\n' +
      'This action cannot be undone.'
    );
    
    if (!confirmed) return;
    
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      alert('You must be logged in to delete posts.');
      return;
    }
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/posts/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      });
      
      if (response.ok || response.status === 204) {
        router.push('/');
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to delete post' }));
        alert(errorData.detail || 'Failed to delete post.');
      }
    } catch (err) {
      console.error('Error deleting post:', err);
      alert('Failed to delete post.');
    }
  };

  const handleHide = async () => {
    if (!post || !id || typeof id !== 'string') return;
    
    const isHidden = post.hidden_by_user;
    const action = isHidden ? 'unhide' : 'hide';
    const confirmed = confirm(
      isHidden
        ? 'Unhide this post? It will become visible again in feeds.'
        : 'Hide this post? It will be removed from feeds temporarily.'
    );
    
    if (!confirmed) return;
    
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      alert('You must be logged in.');
      return;
    }
    
    try {
      const url = `${API_BASE_URL}/api/posts/${id}/hide`;
      const method = isHidden ? 'DELETE' : 'POST';
      
      const response = await fetch(url, {
        method: method,
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok || response.status === 201 || response.status === 204) {
        const refreshResponse = await fetch(`${API_BASE_URL}/api/posts/${id}`);
        if (refreshResponse.ok) {
          const updatedPost = await refreshResponse.json();
          setPost(updatedPost);
        }
      } else {
        const errorData = await response.json().catch(() => ({ detail: `Failed to ${action} post` }));
        alert(errorData.detail || `Failed to ${action} post.`);
      }
    } catch (err) {
      console.error(`Error ${action}ing post:`, err);
      alert(`Failed to ${action} post.`);
    }
  };

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
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </Layout>
    );
  }

  if (error || !post) {
    return (
      <Layout title="Not Found">
        <div className="error-container">
          <span className="error-icon">😢</span>
          <h1>{error || 'Post not found'}</h1>
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
    <Layout title={post.title} description={post.description || post.title}>
      <div className="post-container">
        <img
          src={post.art_url}
          alt={post.title}
          className="artwork-image pixel-art"
        />

        <div className="post-info">
          <h1 className="post-title">{post.title}</h1>
          
          <div className="post-meta">
            {post.owner && (
              <Link href={`/users/${post.owner.id}`} className="author-link">
                {post.owner.display_name || post.owner.handle}
              </Link>
            )}
            <span className="meta-separator">•</span>
            <span className="post-date">{new Date(post.created_at).toLocaleDateString()}</span>
            <span className="meta-separator">•</span>
            <span className="post-canvas">{post.canvas}</span>
          </div>

          {post.description && (
            <div className="post-description">
              {post.description.split('\n').map((line, i) => (
                <p key={i}>{line}</p>
              ))}
            </div>
          )}

          {post.hashtags && post.hashtags.length > 0 && (
            <div className="hashtags">
              {post.hashtags.map((tag) => (
                <Link
                  key={tag}
                  href={`/hashtags/${encodeURIComponent(tag)}`}
                  className="hashtag"
                >
                  #{tag}
                </Link>
              ))}
            </div>
          )}

          {isOwner && (
            <div className="owner-actions">
              <button
                onClick={handleHide}
                className={`action-button ${post.hidden_by_user ? 'unhide' : 'hide'}`}
              >
                {post.hidden_by_user ? '👁 Unhide' : '👁‍🗨 Hide'}
              </button>
              <button
                onClick={handleDelete}
                className="action-button delete"
              >
                🗑 Delete
              </button>
            </div>
          )}
        </div>

        <div className="widget-section">
          <div id={`makapix-widget-${post.id}`} data-post-id={post.id}></div>
        </div>
      </div>

      <Script
        src={`${API_BASE_URL}/makapix-widget.js`}
        strategy="afterInteractive"
        onLoad={() => {
          if (post && id && typeof id === 'string') {
            setTimeout(() => {
              const container = document.getElementById(`makapix-widget-${post.id}`);
              if (container && typeof (window as any).MakapixWidget !== 'undefined') {
                if (!(container as any).__makapix_initialized) {
                  try {
                    new (window as any).MakapixWidget(container);
                    (container as any).__makapix_initialized = true;
                  } catch (error) {
                    console.error('Failed to initialize Makapix widget:', error);
                  }
                }
              }
            }, 100);
          }
        }}
      />

      <style jsx>{`
        .post-container {
          max-width: 1000px;
          margin: 0 auto;
          padding: 24px;
        }

        .artwork-image {
          display: block;
          width: 100%;
          height: auto;
          margin-bottom: 24px;
          image-rendering: -webkit-optimize-contrast !important;
          image-rendering: -moz-crisp-edges !important;
          image-rendering: crisp-edges !important;
          image-rendering: pixelated !important;
          -ms-interpolation-mode: nearest-neighbor !important;
        }

        .post-info {
          background: var(--bg-secondary);
          border-radius: 12px;
          padding: 24px;
          margin-bottom: 24px;
        }

        .post-title {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          margin-bottom: 12px;
        }

        .post-meta {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;
          font-size: 0.9rem;
          color: var(--text-muted);
          margin-bottom: 16px;
        }

        .author-link {
          color: var(--accent-cyan);
          font-weight: 500;
        }

        .author-link:hover {
          color: var(--accent-pink);
        }

        .meta-separator {
          opacity: 0.5;
        }

        .post-description {
          color: var(--text-secondary);
          line-height: 1.6;
          margin-bottom: 16px;
        }

        .post-description p {
          margin-bottom: 0.5rem;
        }

        .post-description p:last-child {
          margin-bottom: 0;
        }

        .hashtags {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }

        .hashtag {
          background: linear-gradient(135deg, rgba(180, 78, 255, 0.2), rgba(78, 159, 255, 0.2));
          color: var(--accent-purple);
          padding: 6px 14px;
          border-radius: 20px;
          font-size: 0.85rem;
          font-weight: 500;
          transition: all var(--transition-fast);
        }

        .hashtag:hover {
          background: linear-gradient(135deg, rgba(180, 78, 255, 0.4), rgba(78, 159, 255, 0.4));
          box-shadow: var(--glow-purple);
        }

        .owner-actions {
          display: flex;
          gap: 12px;
          margin-top: 24px;
          padding-top: 24px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .action-button {
          padding: 10px 20px;
          border-radius: 8px;
          font-size: 0.9rem;
          font-weight: 600;
          transition: all var(--transition-fast);
        }

        .action-button.hide {
          background: var(--bg-tertiary);
          color: var(--text-secondary);
        }

        .action-button.hide:hover {
          background: rgba(245, 158, 11, 0.2);
          color: #f59e0b;
        }

        .action-button.unhide {
          background: rgba(16, 185, 129, 0.2);
          color: #10b981;
        }

        .action-button.unhide:hover {
          background: rgba(16, 185, 129, 0.3);
        }

        .action-button.delete {
          background: rgba(239, 68, 68, 0.2);
          color: #ef4444;
        }

        .action-button.delete:hover {
          background: rgba(239, 68, 68, 0.3);
        }

        .widget-section {
          background: var(--bg-secondary);
          border-radius: 12px;
          padding: 24px;
        }

        /* Ensure widget inherits dark theme properly */
        .widget-section :global(.makapix-widget) {
          background: transparent;
        }
      `}</style>
    </Layout>
  );
}

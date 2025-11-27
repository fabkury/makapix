import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';

interface BlogPost {
  id: string;
  title: string;
  body: string;
  image_urls: string[];
  created_at: string;
  updated_at: string | null;
  owner_id: string;
  owner: {
    id: string;
    handle: string;
  };
  hidden_by_user: boolean;
  hidden_by_mod: boolean;
}

export default function BlogPostPage() {
  const router = useRouter();
  const { id } = router.query;
  const [post, setPost] = useState<BlogPost | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<{ id: string } | null>(null);
  const [isOwner, setIsOwner] = useState(false);
  const [isModerator, setIsModerator] = useState(false);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  useEffect(() => {
    if (!id || typeof id !== 'string') return;

    const fetchPost = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const token = localStorage.getItem('access_token');
        const headers: HeadersInit = token ? { 'Authorization': `Bearer ${token}` } : {};
        
        const response = await fetch(`${API_BASE_URL}/api/blog-posts/${id}`, { headers });
        
        if (!response.ok) {
          if (response.status === 404) {
            setError('Blog post not found');
          } else {
            setError(`Failed to load post: ${response.statusText}`);
          }
          setLoading(false);
          return;
        }
        
        const data = await response.json();
        setPost(data);
        
        if (token) {
          try {
            const userResponse = await fetch(`${API_BASE_URL}/api/auth/me`, {
              headers: { 'Authorization': `Bearer ${token}` }
            });
            if (userResponse.ok) {
              const userData = await userResponse.json();
              setCurrentUser({ id: userData.user.id });
              setIsOwner(userData.user.id === data.owner_id);
              const roles = userData.user.roles || userData.roles || [];
              setIsModerator(roles.includes('moderator') || roles.includes('owner'));
            }
          } catch (err) {
            setCurrentUser(null);
            setIsOwner(false);
            setIsModerator(false);
          }
        }
      } catch (err) {
        setError('Failed to load post');
        console.error('Error fetching blog post:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPost();
  }, [id, API_BASE_URL]);

  const handleDelete = async () => {
    if (!post || !id || typeof id !== 'string') return;
    
    const confirmed = confirm(
      'Are you sure you want to delete this blog post?\n\n' +
      'This action cannot be undone.'
    );
    
    if (!confirmed) return;
    
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      alert('You must be logged in to delete posts.');
      return;
    }
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/blog-posts/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });
      
      if (response.ok || response.status === 204) {
        router.push('/blog');
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to delete post' }));
        alert(errorData.detail || 'Failed to delete post.');
      }
    } catch (err) {
      console.error('Error deleting blog post:', err);
      alert('Failed to delete post.');
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
          @keyframes spin { to { transform: rotate(360deg); } }
        `}</style>
      </Layout>
    );
  }

  if (error || !post) {
    return (
      <Layout title="Not Found">
        <div className="error-container">
          <span className="error-icon">😢</span>
          <h1>{error || 'Blog post not found'}</h1>
          <Link href="/blog" className="back-link">← Back to Blog</Link>
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
          .error-container :global(.back-link) {
            color: var(--accent-cyan);
            font-size: 1rem;
          }
        `}</style>
      </Layout>
    );
  }

  return (
    <Layout title={post.title} description={post.body.substring(0, 160)}>
      <div className="blog-post-container">
        <div className="blog-post-header">
          <h1 className="blog-post-title">{post.title}</h1>
          <div className="blog-post-meta">
            <Link href={`/users/${post.owner.id}`} className="author-link">
              {post.owner.handle}
            </Link>
            <span className="meta-separator">•</span>
            <span className="post-date">
              {new Date(post.updated_at || post.created_at).toLocaleDateString()}
            </span>
            {post.updated_at && post.updated_at !== post.created_at && (
              <>
                <span className="meta-separator">•</span>
                <span className="updated-badge">Updated</span>
              </>
            )}
          </div>
        </div>

        <div className="blog-post-content">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeSanitize]}
            components={{
              img: ({ src, alt }) => (
                <img
                  src={src?.startsWith('http') ? src : `${API_BASE_URL}${src}`}
                  alt={alt}
                  className="blog-post-image"
                />
              ),
            }}
          >
            {post.body}
          </ReactMarkdown>
        </div>

        {isOwner && (
          <div className="owner-actions">
            <Link href={`/blog/write?edit=${post.id}`} className="action-button edit">
              ✏️ Edit
            </Link>
            <button onClick={handleDelete} className="action-button delete">
              🗑 Delete
            </button>
          </div>
        )}

        {/* TODO: Add reactions and comments widgets here */}
        <div className="blog-post-interactions">
          <p className="interactions-placeholder">Reactions and comments coming soon...</p>
        </div>
      </div>

      <style jsx>{`
        .blog-post-container {
          max-width: 800px;
          margin: 0 auto;
          padding: 24px;
        }

        .blog-post-header {
          margin-bottom: 32px;
        }

        .blog-post-title {
          font-size: 2rem;
          font-weight: 700;
          color: var(--text-primary);
          margin-bottom: 16px;
        }

        .blog-post-meta {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;
          font-size: 0.9rem;
          color: var(--text-muted);
        }

        .blog-post-meta :global(.author-link) {
          color: var(--accent-cyan);
          font-weight: 500;
        }

        .blog-post-meta :global(.author-link:hover) {
          color: var(--accent-pink);
        }

        .meta-separator {
          opacity: 0.5;
        }

        .updated-badge {
          background: rgba(78, 159, 255, 0.2);
          color: var(--accent-blue);
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 0.75rem;
          font-weight: 600;
        }

        .blog-post-content {
          background: var(--bg-secondary);
          border-radius: 12px;
          padding: 32px;
          margin-bottom: 24px;
          line-height: 1.8;
          color: var(--text-secondary);
        }

        .blog-post-content :global(h1),
        .blog-post-content :global(h2),
        .blog-post-content :global(h3) {
          color: var(--text-primary);
          margin-top: 24px;
          margin-bottom: 12px;
        }

        .blog-post-content :global(h1) {
          font-size: 1.75rem;
        }

        .blog-post-content :global(h2) {
          font-size: 1.5rem;
        }

        .blog-post-content :global(h3) {
          font-size: 1.25rem;
        }

        .blog-post-content :global(p) {
          margin-bottom: 16px;
        }

        .blog-post-content :global(ul),
        .blog-post-content :global(ol) {
          margin-bottom: 16px;
          padding-left: 24px;
        }

        .blog-post-content :global(li) {
          margin-bottom: 8px;
        }

        .blog-post-content :global(code) {
          background: var(--bg-tertiary);
          padding: 2px 6px;
          border-radius: 4px;
          font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
          font-size: 0.9em;
        }

        .blog-post-content :global(pre) {
          background: var(--bg-tertiary);
          padding: 16px;
          border-radius: 8px;
          overflow-x: auto;
          margin-bottom: 16px;
        }

        .blog-post-content :global(pre code) {
          background: none;
          padding: 0;
        }

        .blog-post-content :global(blockquote) {
          border-left: 4px solid var(--accent-cyan);
          padding-left: 16px;
          margin-left: 0;
          margin-bottom: 16px;
          color: var(--text-secondary);
        }

        .blog-post-content :global(a) {
          color: var(--accent-cyan);
          text-decoration: underline;
        }

        .blog-post-content :global(a:hover) {
          color: var(--accent-pink);
        }

        .blog-post-image {
          max-width: 100%;
          height: auto;
          border-radius: 8px;
          margin: 16px 0;
        }

        .owner-actions {
          display: flex;
          gap: 12px;
          margin-bottom: 24px;
        }

        .owner-actions :global(.action-button) {
          padding: 10px 20px;
          border-radius: 8px;
          font-size: 0.9rem;
          font-weight: 600;
          transition: all var(--transition-fast);
          cursor: pointer;
          border: none;
          text-decoration: none;
          display: inline-block;
        }

        .owner-actions :global(.action-button.edit) {
          background: rgba(78, 159, 255, 0.2);
          color: #4e9fff;
        }

        .owner-actions :global(.action-button.edit:hover) {
          background: rgba(78, 159, 255, 0.3);
        }

        .owner-actions .action-button.delete {
          background: rgba(239, 68, 68, 0.2);
          color: #ef4444;
        }

        .owner-actions .action-button.delete:hover {
          background: rgba(239, 68, 68, 0.3);
        }

        .blog-post-interactions {
          background: var(--bg-secondary);
          border-radius: 12px;
          padding: 24px;
        }

        .interactions-placeholder {
          color: var(--text-muted);
          text-align: center;
          font-style: italic;
        }
      `}</style>
    </Layout>
  );
}


import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import CommentsAndReactions from '../../components/CommentsAndReactions';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { authenticatedFetch, clearTokens } from '../../lib/api';

interface BlogPost {
  id: number;
  blog_post_key: string;
  public_sqid: string | null;
  title: string;
  body: string;
  image_urls: string[];
  created_at: string;
  updated_at: string | null;
  owner_id: number;
  owner: {
    id: number;
    user_key: string;
    public_sqid: string;
    handle: string;
  };
  hidden_by_user: boolean;
  hidden_by_mod: boolean;
}

export default function BlogPostPage() {
  const router = useRouter();
  const { sqid } = router.query;
  const sqidStr = typeof sqid === 'string' ? sqid : null;
  const [post, setPost] = useState<BlogPost | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<{ id: number } | null>(null);
  const [isOwner, setIsOwner] = useState(false);
  const [isModerator, setIsModerator] = useState(false);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  useEffect(() => {
    if (!sqidStr) return;

    const fetchPost = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // Fetch blog post by public_sqid using the canonical endpoint
        const response = await authenticatedFetch(`${API_BASE_URL}/api/blog-post/b/${sqidStr}`);
        
        if (response.status === 401) {
          // Token refresh failed - treat as unauthenticated
          setCurrentUser(null);
          setIsOwner(false);
          setIsModerator(false);
        }
        
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
        
        // Try to get current user info if authenticated
        try {
          const userResponse = await authenticatedFetch(`${API_BASE_URL}/api/auth/me`);
          if (userResponse.status === 401) {
            // Not authenticated or token refresh failed
            setCurrentUser(null);
            setIsOwner(false);
            setIsModerator(false);
          } else if (userResponse.ok) {
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
      } catch (err) {
        setError('Failed to load post');
        console.error('Error fetching blog post:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPost();
  }, [sqidStr, API_BASE_URL]);

  const handleDelete = async () => {
    if (!post || !post.id) return;
    
    const confirmed = confirm(
      'Are you sure you want to delete this blog post?\n\n' +
      'This action cannot be undone.'
    );
    
    if (!confirmed) return;
    
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/blog-post/${post.id}`, {
        method: 'DELETE',
      });
      
      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      
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
        <div className="blog-post-wrapper">
          <div className="blog-post-header">
            <h1 className="blog-post-title">{post.title}</h1>
            <div className="blog-post-meta">
              <Link href={`/u/${post.owner.public_sqid}`} className="author-link">
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
        </div>

        <div className="blog-post-content">
          <div className="blog-post-content-inner">
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
        </div>

        <div className="blog-post-wrapper">
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

        <CommentsAndReactions
          contentType="blog"
          contentId={post.id}
          API_BASE_URL={API_BASE_URL}
          currentUserId={currentUser?.id != null ? String(currentUser.id) : null}
          isModerator={isModerator}
        />
        </div>
      </div>

      <style jsx>{`
        .blog-post-container {
          width: 100%;
          padding: 24px 0;
        }

        .blog-post-wrapper {
          max-width: 800px;
          margin: 0 auto;
          padding: 0 24px;
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
          width: 100%;
          background: var(--bg-secondary);
          margin-bottom: 24px;
        }

        .blog-post-content-inner {
          max-width: 800px;
          margin: 0 auto;
          padding: 32px 24px;
          line-height: 1.8;
          color: var(--text-secondary);
        }

        .blog-post-content-inner :global(h1),
        .blog-post-content-inner :global(h2),
        .blog-post-content-inner :global(h3) {
          color: var(--text-primary);
          margin-top: 24px;
          margin-bottom: 12px;
        }

        .blog-post-content-inner :global(h1) {
          font-size: 1.75rem;
        }

        .blog-post-content-inner :global(h2) {
          font-size: 1.5rem;
        }

        .blog-post-content-inner :global(h3) {
          font-size: 1.25rem;
        }

        .blog-post-content-inner :global(p) {
          margin-bottom: 16px;
        }

        .blog-post-content-inner :global(ul),
        .blog-post-content-inner :global(ol) {
          margin-bottom: 16px;
          padding-left: 24px;
        }

        .blog-post-content-inner :global(li) {
          margin-bottom: 8px;
        }

        .blog-post-content-inner :global(code) {
          background: var(--bg-tertiary);
          padding: 2px 6px;
          border-radius: 4px;
          font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
          font-size: 0.9em;
        }

        .blog-post-content-inner :global(pre) {
          background: var(--bg-tertiary);
          padding: 16px;
          border-radius: 8px;
          overflow-x: auto;
          margin-bottom: 16px;
        }

        .blog-post-content-inner :global(pre code) {
          background: none;
          padding: 0;
        }

        .blog-post-content-inner :global(blockquote) {
          border-left: 4px solid var(--accent-cyan);
          padding-left: 16px;
          margin-left: 0;
          margin-bottom: 16px;
          color: var(--text-secondary);
        }

        .blog-post-content-inner :global(a) {
          color: var(--accent-cyan);
          text-decoration: underline;
        }

        .blog-post-content-inner :global(a:hover) {
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
      `}</style>
    </Layout>
  );
}


import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface BlogPost {
  id: string;
  title: string;
  body: string;
  image_urls: string[];
  updated_at: string | null;
  created_at: string;
  owner: {
    id: string;
    handle: string;
  };
  // Stats returned by the API (from annotate_blog_posts_with_counts)
  reaction_count?: number;
  comment_count?: number;
}

interface PageResponse<T> {
  items: T[];
  next_cursor: string | null;
}

export default function BlogFeedPage() {
  const router = useRouter();
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [sort, setSort] = useState<string>('created_at');
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  
  const observerTarget = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);
  const nextCursorRef = useRef<string | null>(null);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Check if user is logged in
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    setIsLoggedIn(!!token);
  }, []);

  const loadPosts = useCallback(async (cursor: string | null = null, sortBy: string = sort) => {
    if (loadingRef.current || (cursor !== null && !hasMoreRef.current)) {
      return;
    }
    
    const token = localStorage.getItem('access_token');
    
    loadingRef.current = true;
    setLoading(true);
    setError(null);
    
    try {
      const url = `${API_BASE_URL}/api/blog-posts?limit=20&sort=${sortBy}&order=desc${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
      const headers: HeadersInit = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      
      const response = await fetch(url, { headers });
      
      if (response.status === 401 && token) {
        // Only clear tokens if we were authenticated
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_id');
        // Retry without token
        const retryResponse = await fetch(url);
        if (!retryResponse.ok) {
          throw new Error(`Failed to load posts: ${retryResponse.status}`);
        }
        const retryData: PageResponse<BlogPost> = await retryResponse.json();
        if (cursor) {
          setPosts(prev => [...prev, ...retryData.items]);
        } else {
          setPosts(retryData.items);
        }
        setNextCursor(retryData.next_cursor);
        nextCursorRef.current = retryData.next_cursor;
        const hasMoreValue = retryData.next_cursor !== null;
        hasMoreRef.current = hasMoreValue;
        setHasMore(hasMoreValue);
        return;
      }
      
      if (!response.ok) {
        throw new Error(`Failed to load posts: ${response.status}`);
      }
      
      const data: PageResponse<BlogPost> = await response.json();
      
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
      setError(err instanceof Error ? err.message : 'Failed to load posts');
      console.error('Error loading blog posts:', err);
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, [API_BASE_URL, sort]);

  // Load posts when sort changes
  useEffect(() => {
    setPosts([]);
    setNextCursor(null);
    nextCursorRef.current = null;
    hasMoreRef.current = true;
    loadPosts(null, sort);
  }, [sort, loadPosts]);

  // Intersection Observer for infinite scroll
  useEffect(() => {
    if (posts.length === 0 || !hasMoreRef.current) return;
    
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMoreRef.current && !loadingRef.current) {
          loadPosts(nextCursorRef.current, sort);
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
  }, [posts.length, loadPosts, sort]);

  const truncateBody = (body: string, maxLength: number = 200): string => {
    if (body.length <= maxLength) return body;
    // Remove markdown images and links for preview
    const cleaned = body.replace(/!\[.*?\]\(.*?\)/g, '').replace(/\[.*?\]\(.*?\)/g, '');
    if (cleaned.length <= maxLength) return cleaned + '...';
    return cleaned.substring(0, maxLength).trim() + '...';
  };

  return (
    <Layout title="Blog Feed" description="Read blog posts from the community">
      <div className="blog-feed-container">
        <div className="blog-feed-header">
          {isLoggedIn && (
            <Link href="/blog/write" className="write-button">
              <span className="write-icon">✍️</span>
              <span className="write-text">Write Post</span>
            </Link>
          )}
          
          <div className="sort-controls">
            <label htmlFor="sort-select">Sort by:</label>
            <select
              id="sort-select"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              className="sort-select"
            >
              <option value="created_at">Recent</option>
              <option value="updated_at">Last Modified</option>
              <option value="reactions">Most Reactions</option>
              <option value="comments">Most Comments</option>
            </select>
          </div>
        </div>

        {error && (
          <div className="error-message">
            <p>{error}</p>
            <button onClick={() => loadPosts(null, sort)} className="retry-button">
              Retry
            </button>
          </div>
        )}

        {posts.length === 0 && !loading && !error && (
          <div className="empty-state">
            <span className="empty-icon">📰</span>
            <p>No blog posts yet. Be the first to write one!</p>
          </div>
        )}

        <div className="blog-posts-list">
          {posts.map((post) => {
            // Use counts from API response (batch-fetched on backend)
            const reactionCount = post.reaction_count ?? 0;
            const commentCount = post.comment_count ?? 0;
            const displayDate = post.updated_at || post.created_at;
            
            const firstImage = post.image_urls && post.image_urls.length > 0 ? post.image_urls[0] : null;
            
            return (
              <Link key={post.id} href={`/blog/${post.id}`} className={`blog-post-card ${firstImage ? 'has-image' : ''}`}>
                {firstImage && (
                  <div className="blog-post-thumbnail">
                    <img src={firstImage} alt="" className="thumbnail-image pixel-art" />
                  </div>
                )}
                <div className="blog-post-content">
                  <h2 className="blog-post-title">{post.title}</h2>
                  <div className="blog-post-meta">
                    <span className="blog-post-author">by {post.owner.handle}</span>
                    <span className="meta-separator">•</span>
                    <span className="blog-post-date">
                      {new Date(displayDate).toLocaleDateString()}
                    </span>
                    <span className="meta-separator">•</span>
                    <span className="blog-post-reactions">⚡ {reactionCount}</span>
                    <span className="meta-separator">•</span>
                    <span className="blog-post-comments">💬 {commentCount}</span>
                  </div>
                  <div className="blog-post-preview">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {truncateBody(post.body)}
                    </ReactMarkdown>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>

        {posts.length > 0 && (
          <div ref={observerTarget} className="load-more-trigger">
            {loading && (
              <div className="loading-indicator">
                <div className="loading-spinner"></div>
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

      <style jsx>{`
        .blog-feed-container {
          max-width: 900px;
          margin: 0 auto;
          padding: 24px;
        }

        .blog-feed-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 32px;
          flex-wrap: wrap;
          gap: 16px;
        }

        .blog-feed-header :global(.write-button) {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px 24px;
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          border-radius: 8px;
          font-weight: 600;
          transition: all var(--transition-fast);
          text-decoration: none;
        }

        .blog-feed-header :global(.write-button:hover) {
          transform: translateY(-2px);
          box-shadow: var(--glow-pink);
        }

        .blog-feed-header :global(.write-button) .write-icon {
          font-size: 1.2rem;
        }

        .sort-controls {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .sort-controls label {
          color: var(--text-secondary);
          font-size: 0.9rem;
        }

        .sort-select {
          padding: 8px 12px;
          background: var(--bg-tertiary);
          border: 1px solid var(--bg-tertiary);
          color: var(--text-primary);
          border-radius: 6px;
          font-size: 0.9rem;
          cursor: pointer;
        }

        .sort-select:focus {
          outline: none;
          border-color: var(--accent-cyan);
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

        .retry-button {
          margin-top: 1rem;
          padding: 0.75rem 1.5rem;
          background: var(--accent-pink);
          color: var(--bg-primary);
          border-radius: 8px;
          font-weight: 600;
          transition: all var(--transition-fast);
        }

        .retry-button:hover {
          box-shadow: var(--glow-pink);
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
        }

        .blog-posts-list {
          display: flex;
          flex-direction: column;
          gap: 24px;
        }

        .blog-posts-list :global(.blog-post-card) {
          display: flex;
          background: var(--bg-secondary);
          border-radius: 12px;
          overflow: hidden;
          transition: all var(--transition-fast);
          text-decoration: none;
          border: 1px solid transparent;
        }

        .blog-posts-list :global(.blog-post-card:not(.has-image)) {
          padding: 24px;
        }

        .blog-posts-list :global(.blog-post-card:hover) {
          border-color: var(--accent-cyan);
          transform: translateY(-2px);
          box-shadow: 0 4px 20px rgba(0, 212, 255, 0.2);
        }

        .blog-posts-list :global(.blog-post-card) .blog-post-thumbnail {
          flex-shrink: 0;
          width: 120px;
          align-self: stretch;
          position: relative;
          background: var(--bg-tertiary);
          overflow: hidden;
        }

        .blog-posts-list :global(.blog-post-card) .blog-post-thumbnail .thumbnail-image {
          position: absolute;
          top: 0;
          left: 50%;
          transform: translateX(-50%);
          height: 100%;
          width: auto;
          object-fit: contain;
        }

        .blog-posts-list :global(.blog-post-card) .blog-post-content {
          flex: 1;
          padding: 24px;
          min-width: 0;
        }

        .blog-posts-list :global(.blog-post-card) .blog-post-title {
          font-size: 1.5rem;
          font-weight: 700;
          color: var(--text-primary);
          margin-bottom: 12px;
        }

        .blog-posts-list :global(.blog-post-card) .blog-post-meta {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;
          font-size: 0.85rem;
          color: var(--text-muted);
          margin-bottom: 16px;
        }

        .blog-posts-list :global(.blog-post-card) .blog-post-author {
          color: var(--accent-cyan);
          font-weight: 500;
        }

        .blog-posts-list :global(.blog-post-card) .meta-separator {
          opacity: 0.5;
        }

        .blog-posts-list :global(.blog-post-card) .blog-post-preview {
          color: var(--text-secondary);
          line-height: 1.5;
          margin: 0;
          overflow: hidden;
          max-height: 3em;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
        }

        .blog-posts-list :global(.blog-post-card) .blog-post-preview :global(p) {
          margin: 0;
        }

        .blog-posts-list :global(.blog-post-card) .blog-post-preview :global(h1),
        .blog-posts-list :global(.blog-post-card) .blog-post-preview :global(h2),
        .blog-posts-list :global(.blog-post-card) .blog-post-preview :global(h3),
        .blog-posts-list :global(.blog-post-card) .blog-post-preview :global(h4) {
          font-size: 1em;
          font-weight: 600;
          margin: 0;
          color: var(--text-primary);
        }

        .blog-posts-list :global(.blog-post-card) .blog-post-preview :global(ul),
        .blog-posts-list :global(.blog-post-card) .blog-post-preview :global(ol) {
          margin: 0;
          padding-left: 1.5em;
        }

        .blog-posts-list :global(.blog-post-card) .blog-post-preview :global(code) {
          background: var(--bg-tertiary);
          padding: 0.1em 0.3em;
          border-radius: 3px;
          font-size: 0.9em;
        }

        .blog-posts-list :global(.blog-post-card) .blog-post-preview :global(a) {
          color: var(--accent-cyan);
        }

        .blog-posts-list :global(.blog-post-card) .blog-post-preview :global(strong) {
          color: var(--text-primary);
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

        .loading-spinner {
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

        @media (max-width: 600px) {
          .blog-posts-list :global(.blog-post-card) {
            flex-direction: column;
          }

          .blog-posts-list :global(.blog-post-card) .blog-post-thumbnail {
            width: 100%;
            height: 80px;
            align-self: auto;
          }

          .blog-posts-list :global(.blog-post-card) .blog-post-thumbnail .thumbnail-image {
            left: 50%;
            transform: translateX(-50%);
            height: 100%;
            width: auto;
          }
        }
      `}</style>
    </Layout>
  );
}


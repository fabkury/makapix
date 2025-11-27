import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';

interface PostOwner {
  id: string;
  handle: string;
  avatar_url?: string | null;
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
  owner?: PostOwner;
}

interface PostStats {
  reactions: number;
  comments: number;
  liked: boolean;
}

interface CardGridProps {
  posts: Post[];
  API_BASE_URL: string;
}

export default function CardGrid({ posts, API_BASE_URL }: CardGridProps) {
  const gridRef = useRef<HTMLDivElement>(null);
  const [postStats, setPostStats] = useState<Record<string, PostStats>>({});
  const [loadingStats, setLoadingStats] = useState<Record<string, boolean>>({});

  // Fetch reactions and comments counts for posts
  useEffect(() => {
    const fetchStats = async () => {
      const token = localStorage.getItem('access_token');
      
      const statsPromises = posts.map(async (post) => {
        try {
          const headers: HeadersInit = token ? { 'Authorization': `Bearer ${token}` } : {};
          
          const [reactionsRes, commentsRes] = await Promise.all([
            fetch(`${API_BASE_URL}/api/posts/${post.id}/reactions`, { headers }),
            fetch(`${API_BASE_URL}/api/posts/${post.id}/comments`, { headers })
          ]);
          
          if (reactionsRes.ok && commentsRes.ok) {
            const reactionsData = await reactionsRes.json();
            const commentsData = await commentsRes.json();
            
            // Sum all reaction counts
            const reactionCount = Object.values(reactionsData.totals || {}).reduce(
              (sum: number, count) => sum + (count as number), 
              0
            );
            const commentCount = commentsData.items?.length || 0;
            
            // Check if user has liked (thumbs up emoji)
            const liked = reactionsData.mine?.includes('👍') || false;
            
            return { 
              postId: post.id, 
              stats: { 
                reactions: reactionCount, 
                comments: commentCount,
                liked 
              } 
            };
          }
        } catch (err) {
          console.error(`Error fetching stats for post ${post.id}:`, err);
        }
        return null;
      });
      
      const results = await Promise.all(statsPromises);
      const statsMap: Record<string, PostStats> = {};
      results.forEach(result => {
        if (result) {
          statsMap[result.postId] = result.stats;
        }
      });
      
      // Set default stats for posts that didn't return results
      posts.forEach(post => {
        if (!statsMap[post.id]) {
          statsMap[post.id] = { reactions: 0, comments: 0, liked: false };
        }
      });
      
      setPostStats(statsMap);
    };
    
    if (posts.length > 0) {
      fetchStats();
    }
  }, [posts, API_BASE_URL]);

  // Handle like/unlike
  const handleLike = async (postId: string, currentlyLiked: boolean) => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      // Could redirect to login or show a message
      return;
    }

    setLoadingStats(prev => ({ ...prev, [postId]: true }));

    try {
      const url = `${API_BASE_URL}/api/posts/${postId}/reactions/👍`;
      const method = currentlyLiked ? 'DELETE' : 'PUT';
      
      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok || response.status === 204) {
        // Update local state optimistically
        setPostStats(prev => ({
          ...prev,
          [postId]: {
            ...prev[postId],
            liked: !currentlyLiked,
            reactions: prev[postId]?.reactions + (currentlyLiked ? -1 : 1) || (currentlyLiked ? 0 : 1)
          }
        }));

        // Refetch to get accurate counts
        const reactionsRes = await fetch(`${API_BASE_URL}/api/posts/${postId}/reactions`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (reactionsRes.ok) {
          const reactionsData = await reactionsRes.json();
          const reactionCount = Object.values(reactionsData.totals || {}).reduce(
            (sum: number, count) => sum + (count as number), 
            0
          );
          const liked = reactionsData.mine?.includes('👍') || false;
          
          setPostStats(prev => ({
            ...prev,
            [postId]: {
              ...prev[postId],
              reactions: reactionCount,
              liked
            }
          }));
        }
      }
    } catch (err) {
      console.error(`Error ${currentlyLiked ? 'unliking' : 'liking'} post:`, err);
    } finally {
      setLoadingStats(prev => ({ ...prev, [postId]: false }));
    }
  };

  // Apply crisp scaling to artworks
  useEffect(() => {
    const grid = gridRef.current;
    if (!grid) return;

    const calculateScales = () => {
      const artworkAreas = grid.querySelectorAll('.artwork-area');
      
      artworkAreas.forEach((area) => {
        const image = area.querySelector('.artwork-image') as HTMLImageElement;
        if (!image) return;

        const canvasStr = image.getAttribute('data-canvas') || '';
        if (!canvasStr) return;

        const [widthStr, heightStr] = canvasStr.split('x');
        const nativeWidth = parseInt(widthStr, 10);
        const nativeHeight = parseInt(heightStr, 10);

        if (!nativeWidth || !nativeHeight || isNaN(nativeWidth) || isNaN(nativeHeight)) return;

        // Use the larger dimension to calculate scale
        const nativeSize = Math.max(nativeWidth, nativeHeight);
        
        // Calculate maximum integer scale that fits in 256px
        const scale = Math.floor(256 / nativeSize);
        const finalScale = Math.max(1, scale);

        // Calculate display size at integer multiple
        const displayWidth = nativeWidth * finalScale;
        const displayHeight = nativeHeight * finalScale;

        // Apply size to image
        image.style.width = `${displayWidth}px`;
        image.style.height = `${displayHeight}px`;
        image.style.maxWidth = 'none';
        image.style.maxHeight = 'none';
        image.style.objectFit = 'contain';
      });
    };

    const timeoutId = setTimeout(() => {
      calculateScales();
    }, 100);

    const resizeObserver = new ResizeObserver(() => {
      setTimeout(() => {
        calculateScales();
      }, 0);
    });

    resizeObserver.observe(grid);

    window.addEventListener('resize', () => {
      setTimeout(() => {
        calculateScales();
      }, 0);
    });

    return () => {
      clearTimeout(timeoutId);
      resizeObserver.disconnect();
      window.removeEventListener('resize', calculateScales);
    };
  }, [posts]);

  const formatDateTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="card-grid" ref={gridRef}>
      {posts.map((post, index) => {
        const isTypeA = index % 2 === 0; // Even-indexed (0-based) = Type A, Odd-indexed = Type B
        const stats = postStats[post.id] || { reactions: 0, comments: 0, liked: false };
        const isLoading = loadingStats[post.id] || false;

        return (
          <div key={post.id} className={`artwork-card artwork-card-${isTypeA ? 'a' : 'b'}`}>
            {isTypeA ? (
              <>
                {/* Type A: info-left, art-right */}
                <div className="info-area">
                  <div className="info-content">
                    <Link href={`/users/${post.owner_id}`} className="author-handle">
                      {post.owner?.avatar_url && (
                        <img src={post.owner.avatar_url} alt="" className="author-avatar" />
                      )}
                      <span>{post.owner?.handle || 'Unknown'}</span>
                    </Link>
                    <Link href={`/posts/${post.id}`} className="post-title">
                      {post.title}
                    </Link>
                    <div className="post-date">{formatDateTime(post.created_at)}</div>
                    {post.description && (
                      <div className="post-description">{post.description}</div>
                    )}
                    <div className="post-actions">
                      <div className="post-stats">
                        <span className="stat-item">
                          <span className="stat-emoji">⚡</span>
                          <span className="stat-count">{stats.reactions}</span>
                        </span>
                        <span className="stat-item">
                          <span className="stat-emoji">💬</span>
                          <span className="stat-count">{stats.comments}</span>
                        </span>
                      </div>
                      <button
                        className={`like-button ${stats.liked ? 'liked' : ''}`}
                        onClick={(e) => {
                          e.preventDefault();
                          handleLike(post.id, stats.liked);
                        }}
                        disabled={isLoading}
                        aria-label={stats.liked ? 'Unlike' : 'Like'}
                      >
                        👍
                      </button>
                    </div>
                  </div>
                </div>
                <div className="artwork-area">
                  <Link href={`/posts/${post.id}`}>
                    <img
                      src={post.art_url}
                      alt={post.title}
                      className="artwork-image pixel-art"
                      data-canvas={post.canvas}
                      loading="lazy"
                    />
                  </Link>
                </div>
              </>
            ) : (
              <>
                {/* Type B: art-left, info-right */}
                <div className="artwork-area">
                  <Link href={`/posts/${post.id}`}>
                    <img
                      src={post.art_url}
                      alt={post.title}
                      className="artwork-image pixel-art"
                      data-canvas={post.canvas}
                      loading="lazy"
                    />
                  </Link>
                </div>
                <div className="info-area">
                  <div className="info-content">
                    <Link href={`/users/${post.owner_id}`} className="author-handle">
                      {post.owner?.avatar_url && (
                        <img src={post.owner.avatar_url} alt="" className="author-avatar" />
                      )}
                      <span>{post.owner?.handle || 'Unknown'}</span>
                    </Link>
                    <Link href={`/posts/${post.id}`} className="post-title">
                      {post.title}
                    </Link>
                    <div className="post-date">{formatDateTime(post.created_at)}</div>
                    {post.description && (
                      <div className="post-description">{post.description}</div>
                    )}
                    <div className="post-actions">
                      <div className="post-stats">
                        <span className="stat-item">
                          <span className="stat-emoji">⚡</span>
                          <span className="stat-count">{stats.reactions}</span>
                        </span>
                        <span className="stat-item">
                          <span className="stat-emoji">💬</span>
                          <span className="stat-count">{stats.comments}</span>
                        </span>
                      </div>
                      <button
                        className={`like-button ${stats.liked ? 'liked' : ''}`}
                        onClick={(e) => {
                          e.preventDefault();
                          handleLike(post.id, stats.liked);
                        }}
                        disabled={isLoading}
                        aria-label={stats.liked ? 'Unlike' : 'Like'}
                      >
                        👍
                      </button>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        );
      })}

      <style jsx>{`
        .card-grid {
          display: grid;
          grid-template-columns: repeat(1, 514px);
          gap: var(--grid-gap, 4px);
          padding: var(--grid-gap, 4px);
          max-width: 100%;
          margin: 0 auto;
          justify-content: center;
        }

        @media (min-width: 1032px) {
          .card-grid {
            grid-template-columns: repeat(2, 514px);
          }
        }

        @media (min-width: 1550px) {
          .card-grid {
            grid-template-columns: repeat(3, 514px);
          }
        }

        @media (min-width: 2068px) {
          .card-grid {
            grid-template-columns: repeat(4, 514px);
          }
        }

        .artwork-card {
          display: flex;
          width: 514px;
          height: 256px;
          background: var(--bg-secondary);
          overflow: hidden;
          transition: transform var(--transition-fast), box-shadow var(--transition-fast);
        }

        .artwork-card:hover {
          transform: scale(1.01);
          box-shadow: 0 0 20px rgba(0, 212, 255, 0.2);
          z-index: 1;
        }

        .artwork-card-a {
          flex-direction: row;
          gap: 2px;
        }

        .artwork-card-b {
          flex-direction: row;
          gap: 2px;
        }

        .artwork-area {
          width: 256px;
          height: 256px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--bg-tertiary);
          flex-shrink: 0;
        }

        .artwork-area a {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 100%;
          height: 100%;
          line-height: 0;
        }

        .artwork-image {
          display: block;
          image-rendering: -webkit-optimize-contrast !important;
          image-rendering: -moz-crisp-edges !important;
          image-rendering: crisp-edges !important;
          image-rendering: pixelated !important;
          -ms-interpolation-mode: nearest-neighbor !important;
        }

        .info-area {
          width: 256px;
          height: 256px;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
          flex-shrink: 0;
        }

        .info-content {
          width: 100%;
          height: 100%;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .author-handle {
          display: flex;
          flex-direction: row;
          align-items: center;
          gap: 8px;
          font-size: 1rem;
          font-weight: 600;
          color: var(--accent-cyan);
          text-decoration: none;
          transition: color var(--transition-fast);
          white-space: nowrap;
        }

        .author-handle span {
          line-height: 20px;
          display: inline-block;
          vertical-align: middle;
        }

        .author-handle:hover {
          color: var(--accent-blue);
        }

        .author-avatar {
          width: 20px;
          height: 20px;
          border-radius: 50%;
          object-fit: cover;
          flex-shrink: 0;
          display: inline-block;
          vertical-align: middle;
        }

        .post-title {
          font-size: 1.25rem;
          font-weight: 700;
          color: var(--text-primary);
          text-decoration: none;
          transition: color var(--transition-fast);
        }

        .post-title:hover {
          color: var(--accent-pink);
        }

        .post-date {
          font-size: 0.875rem;
          color: var(--text-muted);
        }

        .post-description {
          font-size: 0.8rem;
          color: var(--text-secondary);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 100%;
        }

        .post-actions {
          display: flex;
          align-items: center;
          gap: 16px;
          margin-top: auto;
        }

        .post-stats {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .stat-item {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 0.85rem;
          color: var(--text-secondary);
        }

        .stat-emoji {
          font-size: 1rem;
        }

        .stat-count {
          font-weight: 600;
        }

        .like-button {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          border: 2px solid var(--bg-tertiary);
          background: var(--bg-secondary);
          font-size: 1rem;
          cursor: pointer;
          transition: all var(--transition-fast);
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }

        .like-button:hover:not(:disabled) {
          background: var(--bg-tertiary);
          border-color: var(--accent-pink);
          transform: scale(1.1);
        }

        .like-button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .like-button.liked {
          background: var(--accent-pink);
          border-color: var(--accent-pink);
        }

        .like-button.liked:hover:not(:disabled) {
          background: var(--accent-cyan);
          border-color: var(--accent-cyan);
        }
      `}</style>
    </div>
  );
}


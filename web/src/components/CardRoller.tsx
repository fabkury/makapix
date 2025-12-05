import { useState, useEffect, useRef, useLayoutEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { setNavigationContext, NavigationSource } from '../lib/navigation-context';
import { authenticatedFetch, clearTokens } from '../lib/api';

interface PostOwner {
  id: string;
  handle: string;
  avatar_url?: string | null;
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
  reaction_count?: number;
  comment_count?: number;
  user_has_liked?: boolean;
}

interface HashtagStats {
  tag: string;
  reaction_count: number;
  comment_count: number;
  artwork_count: number;
}

interface CardRollerProps {
  hashtag: string;
  stats: HashtagStats;
  API_BASE_URL: string;
  initialPosts?: Post[];
}

// Local state for optimistic like updates
interface LikeState {
  liked: boolean;
  reactionCount: number;
}

export default function CardRoller({ hashtag, stats, API_BASE_URL, initialPosts = [] }: CardRollerProps) {
  const router = useRouter();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  
  const [posts, setPosts] = useState<Post[]>(initialPosts);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [likeOverrides, setLikeOverrides] = useState<Record<number, LikeState>>({});
  const [loadingLikes, setLoadingLikes] = useState<Record<number, boolean>>({});

  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);
  const nextCursorRef = useRef<string | null>(null);

  // Load more posts for this hashtag
  const loadMorePosts = useCallback(async () => {
    if (loadingRef.current || !hasMoreRef.current) return;
    
    loadingRef.current = true;
    setLoading(true);
    
    try {
      const url = `${API_BASE_URL}/api/hashtags/${encodeURIComponent(hashtag)}/posts?limit=20${nextCursorRef.current ? `&cursor=${encodeURIComponent(nextCursorRef.current)}` : ''}`;
      const response = await authenticatedFetch(url);
      
      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      
      if (!response.ok) {
        throw new Error(`Failed to load posts: ${response.statusText}`);
      }
      
      const data: { items: Post[]; next_cursor: string | null } = await response.json();
      
      setPosts(prev => [...prev, ...data.items]);
      setNextCursor(data.next_cursor);
      nextCursorRef.current = data.next_cursor;
      const hasMoreValue = data.next_cursor !== null;
      hasMoreRef.current = hasMoreValue;
      setHasMore(hasMoreValue);
    } catch (err) {
      console.error('Error loading posts:', err);
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, [hashtag, API_BASE_URL, router]);

  // Initial load if no initial posts provided
  useEffect(() => {
    if (initialPosts.length === 0) {
      loadMorePosts();
    }
  }, [initialPosts.length, loadMorePosts]);

  // Intersection Observer for horizontal infinite scroll
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMoreRef.current && !loadingRef.current) {
          loadMorePosts();
        }
      },
      { threshold: 0.1, root: scrollContainerRef.current }
    );

    observer.observe(sentinel);

    return () => {
      observer.disconnect();
    };
  }, [loadMorePosts]);

  // Handle post click - store navigation context before navigating
  const handlePostClick = (postIndex: number) => {
    const contextPosts = posts.map((post) => ({
      public_sqid: post.public_sqid,
      id: post.id,
      owner_id: post.owner_id,
    }));

    setNavigationContext(contextPosts, postIndex, { type: 'hashtag', id: hashtag }, nextCursor, null);
  };

  // Handle like/unlike with optimistic update
  const handleLike = async (postId: number, currentlyLiked: boolean, currentReactionCount: number) => {
    setLoadingLikes(prev => ({ ...prev, [postId]: true }));

    // Optimistic update
    setLikeOverrides(prev => ({
      ...prev,
      [postId]: {
        liked: !currentlyLiked,
        reactionCount: currentReactionCount + (currentlyLiked ? -1 : 1)
      }
    }));

    try {
      const url = `${API_BASE_URL}/api/post/${postId}/reactions/👍`;
      const method = currentlyLiked ? 'DELETE' : 'PUT';
      
      const response = await authenticatedFetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (response.status === 401) {
        // Token refresh failed - revert optimistic update, clear tokens and redirect
        setLikeOverrides(prev => ({
          ...prev,
          [postId]: {
            liked: currentlyLiked,
            reactionCount: currentReactionCount
          }
        }));
        clearTokens();
        router.push('/auth');
        return;
      }

      if (!response.ok && response.status !== 204) {
        // Revert optimistic update on failure
        setLikeOverrides(prev => ({
          ...prev,
          [postId]: {
            liked: currentlyLiked,
            reactionCount: currentReactionCount
          }
        }));
      }
    } catch (err) {
      console.error(`Error ${currentlyLiked ? 'unliking' : 'liking'} post:`, err);
      // Revert optimistic update on error
      setLikeOverrides(prev => ({
        ...prev,
        [postId]: {
          liked: currentlyLiked,
          reactionCount: currentReactionCount
        }
      }));
    } finally {
      setLoadingLikes(prev => ({ ...prev, [postId]: false }));
    }
  };

  // Apply crisp scaling to artworks
  useLayoutEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const calculateScales = () => {
      const artworkAreas = container.querySelectorAll('.artwork-area');
      
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
        
        // Calculate maximum integer scale that fits in 128px
        const scale = Math.floor(128 / nativeSize);
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

    calculateScales();

    const resizeObserver = new ResizeObserver(() => {
      calculateScales();
    });

    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
    };
  }, [posts]);

  // Reset overrides when posts change
  useEffect(() => {
    setLikeOverrides({});
  }, [posts]);

  return (
    <div className="card-roller">
      <div className="card-roller-header">
        <div className="hashtag-info">
          <Link href={`/hashtags/${encodeURIComponent(hashtag)}`} className="hashtag-link">
            <span className="hashtag-symbol">#</span>
            <span className="hashtag-name">{hashtag}</span>
          </Link>
        </div>
        <div className="hashtag-stats">
          <div className="stat-item">
            <span className="stat-emoji">⚡</span>
            <span className="stat-count">{stats.reaction_count}</span>
          </div>
          <div className="stat-item">
            <span className="stat-emoji">💬</span>
            <span className="stat-count">{stats.comment_count}</span>
          </div>
          <div className="stat-item">
            <span className="stat-emoji">🎨</span>
            <span className="stat-count">{stats.artwork_count}</span>
          </div>
        </div>
      </div>
      
      <div className="card-roller-body" ref={scrollContainerRef}>
        <div className="artwork-cards-horizontal">
          {posts.map((post, index) => {
            const override = likeOverrides[post.id];
            const reactionCount = override?.reactionCount ?? post.reaction_count ?? 0;
            const commentCount = post.comment_count ?? 0;
            const isLiked = override?.liked ?? post.user_has_liked ?? false;
            const isLoading = loadingLikes[post.id] || false;

            return (
              <div key={post.id} className="artwork-card">
                <div className="card-top">
                  <div className="artwork-area">
                    <Link href={`/p/${post.public_sqid}`} onClick={() => handlePostClick(index)}>
                      <img
                        src={post.art_url}
                        alt={post.title}
                        className="artwork-image pixel-art"
                        data-canvas={post.canvas}
                        loading="lazy"
                      />
                    </Link>
                  </div>
                  <div className="stats-panel">
                    <div className="stat-item">
                      <span className="stat-emoji">⚡</span>
                      <span className="stat-count">{reactionCount}</span>
                    </div>
                    <div className="stat-item">
                      <span className="stat-emoji">💬</span>
                      <span className="stat-count">{commentCount}</span>
                    </div>
                    <button
                      className={`like-button ${isLiked ? 'liked' : ''}`}
                      onClick={(e) => {
                        e.preventDefault();
                        handleLike(post.id, isLiked, reactionCount);
                      }}
                      disabled={isLoading}
                      aria-label={isLiked ? 'Unlike' : 'Like'}
                    >
                      👍
                    </button>
                  </div>
                </div>
                <div className="author-bar">
                  <div className="author-line">
                    <Link href={`/u/${post.owner?.handle}`} className="author-handle">
                      {post.owner?.avatar_url && (
                        <img src={post.owner.avatar_url} alt="" className="author-avatar" />
                      )}
                      <span>{post.owner?.handle || 'Unknown'}</span>
                    </Link>
                  </div>
                  <div className="title-line">
                    <Link href={`/p/${post.public_sqid}`} className="post-title" onClick={() => handlePostClick(index)}>
                      {post.title}
                    </Link>
                  </div>
                </div>
              </div>
            );
          })}
          
          {/* Sentinel for infinite scroll */}
          {hasMore && (
            <div ref={sentinelRef} className="scroll-sentinel">
              {loading && (
                <div className="loading-indicator">
                  <div className="loading-spinner"></div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .card-roller {
          width: 100%;
          margin-bottom: 32px;
        }

        .card-roller-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 16px 24px;
          background: var(--bg-secondary);
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .hashtag-info {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .hashtag-link {
          display: flex;
          align-items: center;
          gap: 8px;
          text-decoration: none;
          transition: all var(--transition-fast);
        }

        .hashtag-link:hover {
          transform: translateX(4px);
        }

        .hashtag-symbol {
          font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
          font-weight: 700;
          font-size: 1.5rem;
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .hashtag-name {
          font-size: 1.2rem;
          font-weight: 600;
          color: var(--text-primary);
        }

        .hashtag-stats {
          display: flex;
          gap: 16px;
          align-items: center;
        }

        .hashtag-stats .stat-item {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 0.9rem;
          color: var(--text-secondary);
        }

        .hashtag-stats .stat-emoji {
          font-size: 1.1rem;
        }

        .hashtag-stats .stat-count {
          font-weight: 600;
          color: var(--text-primary);
        }

        .card-roller-body {
          overflow-x: auto;
          overflow-y: hidden;
          -webkit-overflow-scrolling: touch;
          scrollbar-width: thin;
        }

        .artwork-cards-horizontal {
          display: flex;
          gap: 16px;
          padding: 16px 24px;
          min-height: 210px;
        }

        .artwork-card {
          display: flex;
          flex-direction: column;
          width: 178px;
          height: 178px;
          background: var(--bg-secondary);
          flex-shrink: 0;
          transition: box-shadow var(--transition-fast);
          border: 1px solid transparent;
        }

        .artwork-card:hover {
          box-shadow: 0 0 20px rgba(0, 212, 255, 0.2);
          z-index: 1;
        }

        .card-top {
          display: flex;
          flex-direction: row;
          width: 100%;
          height: 128px;
          gap: 1px;
        }

        .artwork-area {
          width: 128px;
          height: 128px;
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

        .stats-panel {
          width: 49px;
          height: 128px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 8px;
          background: var(--bg-secondary);
          flex-shrink: 0;
          padding: 8px 4px;
        }

        .stat-item {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
          font-size: 0.75rem;
          color: var(--text-secondary);
        }

        .stat-emoji {
          font-size: 1rem;
        }

        .stat-count {
          font-weight: 600;
          font-size: 0.7rem;
        }

        .like-button {
          width: 28px;
          height: 28px;
          border-radius: 50%;
          border: 2px solid var(--bg-tertiary);
          background: var(--bg-secondary);
          font-size: 0.9rem;
          cursor: pointer;
          transition: all var(--transition-fast);
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          margin-top: 4px;
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

        .author-bar {
          width: 168px;
          height: 49px;
          display: flex;
          flex-direction: column;
          justify-content: center;
          gap: 4px;
          background: var(--bg-secondary);
          padding: 4px 6px;
          margin-top: 1px;
        }

        .author-line {
          display: block;
          width: 100%;
          height: 18px;
          line-height: 18px;
          overflow: hidden;
          white-space: nowrap;
          text-overflow: ellipsis;
        }

        .title-line {
          display: block;
          width: 100%;
          height: 18px;
          line-height: 18px;
          overflow: hidden;
          white-space: nowrap;
          text-overflow: ellipsis;
        }

        .author-handle {
          display: inline-flex;
          flex-direction: row;
          align-items: center;
          gap: 3px;
          font-size: 0.7rem;
          font-weight: 600;
          color: white;
          text-decoration: none;
          transition: color var(--transition-fast);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 100%;
        }

        .author-handle span {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .author-handle:hover {
          color: var(--accent-cyan);
        }

        .author-avatar {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          object-fit: cover;
          flex-shrink: 0;
        }

        .post-title {
          display: inline-block;
          font-size: 0.7rem;
          font-weight: 600;
          color: var(--accent-cyan);
          text-decoration: none;
          transition: color var(--transition-fast);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 100%;
        }

        .post-title:hover {
          color: var(--accent-pink);
        }

        .scroll-sentinel {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 100px;
          flex-shrink: 0;
        }

        .loading-indicator {
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .loading-spinner {
          width: 24px;
          height: 24px;
          border: 2px solid var(--bg-tertiary);
          border-top-color: var(--accent-purple);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }

        @media (max-width: 768px) {
          .card-roller-header {
            flex-direction: column;
            align-items: flex-start;
            gap: 12px;
          }

          .hashtag-stats {
            width: 100%;
            justify-content: space-around;
          }
        }
      `}</style>
    </div>
  );
}

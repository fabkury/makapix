import { useState, useEffect } from 'react';

interface ReactionTotals {
  totals: Record<string, number>;
  authenticated_totals: Record<string, number>;
  anonymous_totals: Record<string, number>;
  mine: string[];
}

interface Comment {
  id: string;
  author_id: string | null;
  author_ip: string | null;
  parent_id: string | null;
  depth: number;
  body: string;
  hidden_by_mod: boolean;
  deleted_by_owner: boolean;
  created_at: string;
  updated_at: string | null;
  author_handle?: string;
  author_display_name?: string;
}

interface CommentsAndReactionsProps {
  contentType: 'artwork' | 'blog';
  contentId: string | number;
  API_BASE_URL: string;
  currentUserId?: string | null;
  isModerator?: boolean;
}

const EMOJI_OPTIONS = ['👍', '❤️', '🔥', '😊', '⭐'];

// API endpoint helpers
const getReactionsEndpoint = (contentType: 'artwork' | 'blog', contentId: string | number): string => {
  return contentType === 'artwork'
    ? `/api/post/${contentId}/reactions`
    : `/api/blog-post/${contentId}/reactions`;
};

const getCommentsEndpoint = (contentType: 'artwork' | 'blog', contentId: string | number): string => {
  return contentType === 'artwork'
    ? `/api/post/${contentId}/comments`
    : `/api/blog-post/${contentId}/comments`;
};

const getCommentDeleteEndpoint = (contentType: 'artwork' | 'blog', commentId: string): string => {
  return contentType === 'artwork'
    ? `/api/post/comments/${commentId}`
    : `/api/blog-post/comments/${commentId}`;
};

const getWidgetDataEndpoint = (contentType: 'artwork' | 'blog', contentId: string | number): string | null => {
  // Widget data endpoint only exists for artwork posts
  return contentType === 'artwork'
    ? `/api/post/${contentId}/widget-data`
    : null;
};

export default function CommentsAndReactions({
  contentType,
  contentId,
  API_BASE_URL,
  currentUserId,
  isModerator = false,
}: CommentsAndReactionsProps) {
  const [reactions, setReactions] = useState<ReactionTotals | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loadingReactions, setLoadingReactions] = useState(true);
  const [loadingComments, setLoadingComments] = useState(true);
  const [commentBody, setCommentBody] = useState('');
  const [replyingTo, setReplyingTo] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState('');
  const [submittingComment, setSubmittingComment] = useState(false);
  const [foldedComments, setFoldedComments] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadWidgetData();
  }, [contentType, contentId]);

  const getAuthHeaders = (): HeadersInit => {
    const token = localStorage.getItem('access_token');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  };

  const loadWidgetData = async () => {
    // Try combined endpoint for artwork posts
    const widgetEndpoint = getWidgetDataEndpoint(contentType, contentId);
    if (widgetEndpoint) {
      try {
        const response = await fetch(`${API_BASE_URL}${widgetEndpoint}`, {
          headers: getAuthHeaders(),
        });
        if (response.ok) {
          const data = await response.json();
          setReactions({
            totals: data?.reactions?.totals || {},
            authenticated_totals: data?.reactions?.authenticated_totals || {},
            anonymous_totals: data?.reactions?.anonymous_totals || {},
            mine: data?.reactions?.mine || [],
          });
          setComments((data?.comments || []).filter((comment: Comment) => {
            if (!comment || typeof comment.id === 'undefined') return false;
            if (typeof comment.depth !== 'number' || comment.depth > 3) return false;
            if (!comment.body && !comment.deleted_by_owner) return false;
            return true;
          }));
          setLoadingReactions(false);
          setLoadingComments(false);
          return;
        }
      } catch (error) {
        console.warn('Combined endpoint failed, falling back to separate requests');
      }
    }
    
    // Fallback to separate endpoints
    await Promise.all([loadReactions(), loadComments()]);
  };

  const loadReactions = async () => {
    try {
      setLoadingReactions(true);
      const response = await fetch(`${API_BASE_URL}${getReactionsEndpoint(contentType, contentId)}`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setReactions({
          totals: data?.totals || {},
          authenticated_totals: data?.authenticated_totals || {},
          anonymous_totals: data?.anonymous_totals || {},
          mine: data?.mine || [],
        });
      }
    } catch (error) {
      console.error('Failed to load reactions:', error);
    } finally {
      setLoadingReactions(false);
    }
  };

  const loadComments = async () => {
    try {
      setLoadingComments(true);
      const response = await fetch(`${API_BASE_URL}${getCommentsEndpoint(contentType, contentId)}`, {
        headers: getAuthHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setComments((data.items || []).filter((comment: Comment) => {
          if (!comment || typeof comment.id === 'undefined') return false;
          if (typeof comment.depth !== 'number' || comment.depth > 3) return false;
          if (!comment.body && !comment.deleted_by_owner) return false;
          return true;
        }));
      }
    } catch (error) {
      console.error('Failed to load comments:', error);
    } finally {
      setLoadingComments(false);
    }
  };

  const toggleReaction = async (emoji: string) => {
    if (!reactions) return;

    const isMine = reactions.mine.includes(emoji);
    const method = isMine ? 'DELETE' : 'PUT';

    if (!isMine && reactions.mine.length >= 5) {
      alert('You can only add up to 5 reactions per post.');
      return;
    }

    try {
      const response = await fetch(
        `${API_BASE_URL}${getReactionsEndpoint(contentType, contentId)}/${encodeURIComponent(emoji)}`,
        {
          method,
          headers: getAuthHeaders(),
        }
      );

      if (response.ok || response.status === 204) {
        await loadReactions();
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to update reaction' }));
        alert(errorData.detail || 'Failed to update reaction');
      }
    } catch (error) {
      console.error('Failed to toggle reaction:', error);
      alert('Failed to update reaction. Please try again.');
    }
  };

  const handleSubmitComment = async (e: React.FormEvent, parentId: string | null = null) => {
    e.preventDefault();
    const body = parentId ? replyBody : commentBody;
    if (!body.trim()) return;

    setSubmittingComment(true);
    try {
      const payload: { body: string; parent_id?: string } = { body: body.trim() };
      if (parentId) payload.parent_id = parentId;

      const response = await fetch(
        `${API_BASE_URL}${getCommentsEndpoint(contentType, contentId)}`,
        {
          method: 'POST',
          headers: {
            ...getAuthHeaders(),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        }
      );

      if (response.ok) {
        if (parentId) {
          setReplyBody('');
          setReplyingTo(null);
        } else {
          setCommentBody('');
        }
        await loadComments();
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to post comment' }));
        alert(errorData.detail || 'Failed to post comment');
      }
    } catch (error) {
      console.error('Failed to submit comment:', error);
      alert('Failed to post comment. Please try again.');
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleDeleteComment = async (commentId: string) => {
    if (!confirm('Are you sure you want to delete this comment? This action cannot be undone.')) return;

    try {
      const response = await fetch(
        `${API_BASE_URL}${getCommentDeleteEndpoint(contentType, commentId)}`,
        {
          method: 'DELETE',
          headers: getAuthHeaders(),
        }
      );

      if (response.ok || response.status === 204) {
        await loadComments();
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to delete comment' }));
        alert(errorData.detail || 'Failed to delete comment');
      }
    } catch (error) {
      console.error('Failed to delete comment:', error);
      alert('Failed to delete comment. Please try again.');
    }
  };

  const toggleFold = (commentId: string) => {
    const newFolded = new Set(foldedComments);
    if (newFolded.has(commentId)) {
      newFolded.delete(commentId);
    } else {
      newFolded.add(commentId);
    }
    setFoldedComments(newFolded);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  const canDeleteComment = (comment: Comment): boolean => {
    if (comment.deleted_by_owner) return false;
    // Moderators can delete any comment
    if (isModerator) return true;
    // Anonymous user can delete their own guest comments
    if (!currentUserId && !comment.author_id && comment.author_ip) return true;
    // Authenticated user can delete their own comments
    if (currentUserId && comment.author_id === currentUserId) return true;
    return false;
  };

  const renderComment = (comment: Comment): JSX.Element | null => {
    // Find replies first to check if we should render this comment
    const replies = comments.filter(c => c.parent_id === comment.id);
    const hasReplies = replies.length > 0;
    
    // Filter out deleted comments only if they have no replies
    // This ensures deleted middle comments still render (showing "[deleted]") so their children remain visible
    if (comment.deleted_by_owner && !hasReplies) {
      return null;
    }

    const isFolded = foldedComments.has(comment.id);
    const authorName = comment.deleted_by_owner
      ? '[deleted]'
      : (comment.author_display_name || comment.author_handle || 'Unknown');
    const isGuest = !comment.deleted_by_owner && !comment.author_id && comment.author_ip !== null;

    return (
      <div key={comment.id} className={`makapix-comment ${isFolded ? 'makapix-folded' : ''}`} data-comment-id={comment.id}>
        <div className="makapix-comment-header">
          <button
            className="makapix-comment-fold-btn"
            onClick={() => toggleFold(comment.id)}
            aria-label={isFolded ? 'Unfold comment' : 'Fold comment'}
          >
            {isFolded ? '▶' : '▼'}
          </button>
          <span className={`makapix-comment-author ${isGuest ? 'makapix-guest' : ''} ${comment.deleted_by_owner ? 'deleted' : ''}`}>
            {authorName}
          </span>
          <span className="makapix-comment-date">{formatDate(comment.created_at)}</span>
        </div>
        {!isFolded && (
          <div className="makapix-comment-content">
            <div className="makapix-comment-body">
              {comment.deleted_by_owner ? '[deleted]' : comment.body}
            </div>
            {!comment.deleted_by_owner && (
              <div className="makapix-comment-actions">
                {comment.depth < 3 && (
                  <button
                    className="makapix-comment-reply-btn"
                    onClick={() => setReplyingTo(replyingTo === comment.id ? null : comment.id)}
                  >
                    Reply
                  </button>
                )}
                {canDeleteComment(comment) && (
                  <button
                    className="makapix-comment-delete-btn"
                    onClick={() => handleDeleteComment(comment.id)}
                  >
                    Delete
                  </button>
                )}
              </div>
            )}
            {replyingTo === comment.id && (
              <form
                className="makapix-reply-form"
                onSubmit={(e) => handleSubmitComment(e, comment.id)}
              >
                <textarea
                  className="makapix-comment-input"
                  placeholder="Write a reply..."
                  value={replyBody}
                  onChange={(e) => setReplyBody(e.target.value)}
                  maxLength={2000}
                />
                <div className="makapix-reply-actions">
                  <button type="submit" className="makapix-comment-submit" disabled={!replyBody.trim() || submittingComment}>
                    {submittingComment ? 'Posting...' : 'Post Reply'}
                  </button>
                  <button type="button" className="makapix-reply-cancel" onClick={() => { setReplyingTo(null); setReplyBody(''); }}>
                    Cancel
                  </button>
                </div>
              </form>
            )}
            {hasReplies && (
              <div className="makapix-comment-replies">
                {replies.map(reply => renderComment(reply)).filter(Boolean)}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  const topLevelComments = comments.filter(c => !c.parent_id);
  const isAuthenticated = !!currentUserId;

  return (
    <div className="makapix-widget">
      {/* Reactions Section */}
      <div className="makapix-reactions-section">
        <h3>Reactions</h3>
        {loadingReactions && !reactions ? (
          <div className="makapix-loading">Loading reactions...</div>
        ) : (
          <div className="makapix-reaction-picker">
            {EMOJI_OPTIONS.map(emoji => {
              const count = reactions?.totals[emoji] || 0;
              const isActive = reactions?.mine.includes(emoji) || false;
              return (
                <button
                  key={emoji}
                  className={`makapix-reaction-btn ${isActive ? 'makapix-reaction-btn-active' : ''}`}
                  onClick={() => toggleReaction(emoji)}
                  aria-label={`${isActive ? 'Remove' : 'Add'} ${emoji} reaction`}
                  disabled={loadingReactions}
                >
                  {emoji}
                  {count > 0 && <span className="makapix-reaction-btn-count">{count}</span>}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Comments Section */}
      <div className="makapix-comments-section">
        <h3>Comments</h3>
        
        {/* Comment Form */}
        <form className="makapix-comment-form" onSubmit={(e) => handleSubmitComment(e, null)}>
          <textarea
            className="makapix-comment-input"
            placeholder={`Add a comment... ${isAuthenticated ? '' : '(posting as guest)'}`}
            value={commentBody}
            onChange={(e) => setCommentBody(e.target.value)}
            maxLength={2000}
          />
          <button
            type="submit"
            className="makapix-comment-submit"
            disabled={!commentBody.trim() || submittingComment}
          >
            {submittingComment ? 'Posting...' : 'Post Comment'}
          </button>
        </form>

        {/* Comments List */}
        {loadingComments ? (
          <div className="makapix-loading">Loading comments...</div>
        ) : topLevelComments.length === 0 ? (
          <div className="makapix-no-comments">No comments yet. Be the first to comment!</div>
        ) : (
          <div className="makapix-comments-list">
            {topLevelComments.map(comment => renderComment(comment))}
          </div>
        )}
      </div>

      <style jsx global>{`
        .makapix-widget {
          font-family: 'Noto Sans', 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          display: flex;
          flex-direction: column;
          gap: 24px;
        }
        
        .makapix-reactions-section,
        .makapix-comments-section {
          background: transparent;
        }
        
        .makapix-widget h3 {
          font-size: 1rem;
          font-weight: 600;
          margin: 0 0 16px 0;
          color: #e8e8f0;
          letter-spacing: 0.02em;
        }
        
        .makapix-reaction-picker {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }
        
        .makapix-reaction-btn {
          position: relative;
          padding: 10px 14px;
          font-size: 1.25rem;
          background: #1a1a24;
          border: 2px solid #252530;
          border-radius: 10px;
          cursor: pointer;
          transition: all 0.15s ease;
        }
        
        .makapix-reaction-btn:hover {
          border-color: #ff6eb4;
          transform: scale(1.1);
          box-shadow: 0 0 12px rgba(255, 110, 180, 0.4);
        }
        
        .makapix-reaction-btn-active {
          background: rgba(0, 212, 255, 0.15);
          border-color: #00d4ff;
          box-shadow: 0 0 12px rgba(0, 212, 255, 0.3);
        }
        
        .makapix-reaction-btn-active:hover {
          border-color: #00d4ff;
          box-shadow: 0 0 16px rgba(0, 212, 255, 0.5);
        }

        .makapix-reaction-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .makapix-reaction-btn:disabled:hover {
          transform: none;
          border-color: #252530;
          box-shadow: none;
        }
        
        .makapix-reaction-btn-count {
          position: absolute;
          bottom: -4px;
          right: -4px;
          background: #00d4ff;
          color: #1a1a24;
          font-size: 0.7rem;
          font-weight: 700;
          padding: 2px 6px;
          border-radius: 10px;
          min-width: 18px;
          text-align: center;
          line-height: 1.2;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        }
        
        .makapix-comment-form,
        .makapix-reply-form {
          margin-bottom: 20px;
        }
        
        .makapix-comment-input {
          width: 100%;
          padding: 14px 16px;
          background: #1a1a24;
          border: 1px solid #252530;
          border-radius: 10px;
          font-family: inherit;
          font-size: 0.95rem;
          color: #e8e8f0;
          resize: vertical;
          min-height: 80px;
          box-sizing: border-box;
          transition: border-color 0.15s ease, box-shadow 0.15s ease;
        }
        
        .makapix-comment-input::placeholder {
          color: #6a6a80;
        }
        
        .makapix-comment-input:focus {
          outline: none;
          border-color: #00d4ff;
          box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.15);
        }
        
        .makapix-comment-submit {
          margin-top: 10px;
          padding: 12px 24px;
          background: linear-gradient(135deg, #ff6eb4, #b44eff);
          color: #fff;
          border: none;
          border-radius: 10px;
          font-size: 0.95rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.15s ease;
        }
        
        .makapix-comment-submit:hover:not(:disabled) {
          box-shadow: 0 0 20px rgba(255, 110, 180, 0.4);
          transform: translateY(-1px);
        }

        .makapix-comment-submit:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        
        .makapix-reply-cancel {
          margin-top: 10px;
          padding: 12px 24px;
          background: #1a1a24;
          color: #a0a0b8;
          border: 1px solid #252530;
          border-radius: 10px;
          font-size: 0.95rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.15s ease;
          margin-left: 8px;
        }
        
        .makapix-reply-cancel:hover {
          background: #252530;
          color: #e8e8f0;
        }
        
        .makapix-reply-actions {
          display: flex;
          gap: 8px;
        }
        
        .makapix-comment {
          padding: 16px;
          border: 1px solid rgba(255, 255, 255, 0.05);
          border-radius: 12px;
          margin-bottom: 12px;
          background: #16161f;
        }
        
        .makapix-comment-header {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 10px;
        }
        
        .makapix-comment-fold-btn {
          padding: 4px 8px;
          background: transparent;
          border: none;
          color: #6a6a80;
          font-size: 0.75rem;
          cursor: pointer;
          line-height: 1;
          min-width: 24px;
          text-align: center;
          transition: color 0.15s ease;
          border-radius: 4px;
        }
        
        .makapix-comment-fold-btn:hover {
          color: #00d4ff;
          background: rgba(0, 212, 255, 0.1);
        }
        
        .makapix-comment-content {
          /* Content wrapper - hidden when comment is folded */
        }
        
        .makapix-comment.makapix-folded .makapix-comment-content {
          display: none;
        }
        
        .makapix-comment-author {
          font-weight: 600;
          color: #00d4ff;
        }
        
        .makapix-comment-author.makapix-guest {
          color: #6a6a80;
          font-style: italic;
        }

        .makapix-comment-author.deleted {
          color: #6a6a80;
          font-style: italic;
        }
        
        .makapix-comment-date {
          font-size: 0.8rem;
          color: #6a6a80;
          margin-left: auto;
        }
        
        .makapix-comment-body {
          color: #a0a0b8;
          line-height: 1.6;
          margin-bottom: 10px;
          white-space: pre-wrap;
          word-wrap: break-word;
        }
        
        .makapix-comment-reply-btn {
          padding: 6px 14px;
          background: transparent;
          color: #b44eff;
          border: none;
          font-size: 0.85rem;
          font-weight: 600;
          cursor: pointer;
          border-radius: 6px;
          transition: all 0.15s ease;
        }
        
        .makapix-comment-reply-btn:hover {
          background: rgba(180, 78, 255, 0.1);
          color: #c77aff;
        }
        
        .makapix-comment-actions {
          display: flex;
          gap: 8px;
          margin-top: 10px;
        }
        
        .makapix-comment-delete-btn {
          padding: 6px 14px;
          background: transparent;
          color: #ef4444;
          border: none;
          font-size: 0.85rem;
          font-weight: 600;
          cursor: pointer;
          border-radius: 6px;
          transition: all 0.15s ease;
        }
        
        .makapix-comment-delete-btn:hover {
          background: rgba(239, 68, 68, 0.1);
          color: #f87171;
        }
        
        .makapix-comment-replies {
          margin-left: 24px;
          margin-top: 12px;
          padding-left: 16px;
          border-left: 2px solid rgba(180, 78, 255, 0.2);
        }
        
        .makapix-no-comments,
        .makapix-loading {
          color: #6a6a80;
          font-style: italic;
          text-align: center;
          padding: 24px;
          background: #16161f;
          border-radius: 12px;
        }
      `}</style>
    </div>
  );
}


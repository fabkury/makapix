/**
 * RecentCommentsPanel - View and moderate user's comments.
 * Supports hide/unhide and delete actions with confirmation.
 */

import { useState, useEffect, useCallback } from 'react';
import CollapsiblePanel from './CollapsiblePanel';
import { authenticatedFetch } from '../../lib/api';

interface Comment {
  id: string;
  post_id: number;
  post_public_sqid: string;
  post_title: string;
  post_art_url: string | null;
  body: string;
  hidden_by_mod: boolean;
  created_at: string;
}

interface RecentCommentsPanelProps {
  sqid: string;
}

const COMMENTS_PER_PAGE = 10;

export default function RecentCommentsPanel({ sqid }: RecentCommentsPanelProps) {
  const [comments, setComments] = useState<Comment[]>([]);
  const [total, setTotal] = useState(0);
  const [cursor, setCursor] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const fetchComments = useCallback(async (cursorValue: string | null = null) => {
    setIsLoading(true);
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const params = new URLSearchParams({ limit: String(COMMENTS_PER_PAGE) });
      if (cursorValue) params.set('cursor', cursorValue);

      const response = await authenticatedFetch(
        `${apiBaseUrl}/api/admin/user/${sqid}/comments?${params}`
      );

      if (response.ok) {
        const data = await response.json();
        setComments(data.items);
        setTotal(data.total);
        setNextCursor(data.next_cursor);
      }
    } catch (err) {
      console.error('Failed to fetch comments:', err);
    } finally {
      setIsLoading(false);
    }
  }, [sqid]);

  useEffect(() => {
    fetchComments();
  }, [fetchComments]);

  const handleToggleHide = async (commentId: string, isCurrentlyHidden: boolean) => {
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const method = isCurrentlyHidden ? 'DELETE' : 'POST';
      const response = await authenticatedFetch(
        `${apiBaseUrl}/api/admin/comment/${commentId}/hide`,
        { method }
      );

      if (response.ok || response.status === 204) {
        setComments(comments.map(c =>
          c.id === commentId ? { ...c, hidden_by_mod: !isCurrentlyHidden } : c
        ));
      }
    } catch (err) {
      console.error('Failed to toggle comment visibility:', err);
    }
  };

  const handleDelete = async (commentId: string) => {
    if (confirmDelete !== commentId) {
      setConfirmDelete(commentId);
      setTimeout(() => setConfirmDelete(null), 3000);
      return;
    }

    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const response = await authenticatedFetch(
        `${apiBaseUrl}/api/admin/comment/${commentId}`,
        { method: 'DELETE' }
      );

      if (response.ok || response.status === 204) {
        setComments(comments.filter(c => c.id !== commentId));
        setTotal(total - 1);
        setConfirmDelete(null);
      }
    } catch (err) {
      console.error('Failed to delete comment:', err);
    }
  };

  const formatDateTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const handlePrevPage = () => {
    // For simplicity, we don't track previous cursors
    // In a full implementation, you'd maintain a cursor stack
    setCursor(null);
    fetchComments(null);
  };

  const handleNextPage = () => {
    if (nextCursor) {
      setCursor(nextCursor);
      fetchComments(nextCursor);
    }
  };

  return (
    <CollapsiblePanel title="Recent comments">
      <div className="comments-panel">
        <div className="total-count">Total comments: {total}</div>

        {isLoading ? (
          <div className="loading">Loading...</div>
        ) : comments.length === 0 ? (
          <div className="empty">No comments found</div>
        ) : (
          <>
            <div className="comments-list">
              {comments.map((comment) => (
                <div
                  key={comment.id}
                  className={`comment-item ${comment.hidden_by_mod ? 'hidden' : ''}`}
                >
                  <div className="comment-content">
                    {comment.post_art_url && (
                      <img
                        src={comment.post_art_url}
                        alt="Artwork"
                        className="comment-artwork"
                      />
                    )}
                    <div className="comment-details">
                      <div className="comment-meta">{formatDateTime(comment.created_at)}</div>
                      <div className="comment-body">{comment.body}</div>
                    </div>
                  </div>
                  <div className="comment-actions">
                    <button
                      onClick={() => handleToggleHide(comment.id, comment.hidden_by_mod)}
                      className="action-btn"
                      title={comment.hidden_by_mod ? 'Unhide' : 'Hide'}
                    >
                      {comment.hidden_by_mod ? (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                          <line x1="1" y1="1" x2="23" y2="23" />
                        </svg>
                      ) : (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                          <circle cx="12" cy="12" r="3" />
                        </svg>
                      )}
                    </button>
                    <button
                      onClick={() => handleDelete(comment.id)}
                      className={`action-btn delete ${confirmDelete === comment.id ? 'confirm' : ''}`}
                      title={confirmDelete === comment.id ? 'Click again to confirm' : 'Delete'}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>

            {(cursor || nextCursor) && (
              <div className="pagination">
                <button onClick={handlePrevPage} disabled={!cursor}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="m15 18-6-6 6-6" />
                  </svg>
                  Previous
                </button>
                <button onClick={handleNextPage} disabled={!nextCursor}>
                  Next
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="m9 18 6-6-6-6" />
                  </svg>
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <style jsx>{`
        .comments-panel {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .total-count {
          font-size: 0.9rem;
          color: var(--text-secondary);
        }
        .loading, .empty {
          font-size: 0.9rem;
          color: var(--text-muted);
          padding: 16px 0;
          text-align: center;
        }
        .comments-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .comment-item {
          display: flex;
          gap: 12px;
          padding: 12px;
          background: var(--bg-tertiary);
          border: 1px solid var(--border-color);
          border-radius: 8px;
          transition: opacity 0.15s ease;
        }
        .comment-item.hidden {
          opacity: 0.4;
        }
        .comment-content {
          display: flex;
          gap: 12px;
          flex: 1;
          min-width: 0;
        }
        .comment-artwork {
          width: 48px;
          height: 48px;
          border-radius: 4px;
          object-fit: cover;
          flex-shrink: 0;
          border: 1px solid var(--border-color);
        }
        .comment-details {
          flex: 1;
          min-width: 0;
        }
        .comment-meta {
          font-size: 0.75rem;
          color: var(--text-muted);
          margin-bottom: 4px;
        }
        .comment-body {
          font-size: 0.85rem;
          color: var(--text-primary);
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }
        .comment-actions {
          display: flex;
          flex-direction: column;
          gap: 4px;
          flex-shrink: 0;
        }
        .action-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          background: transparent;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          color: var(--accent-cyan);
          transition: background 0.15s ease;
        }
        .action-btn:hover {
          background: rgba(255, 255, 255, 0.1);
        }
        .action-btn.delete {
          color: var(--accent-pink);
        }
        .action-btn.delete.confirm {
          background: rgba(255, 82, 130, 0.2);
        }
        .pagination {
          display: flex;
          justify-content: space-between;
          padding-top: 8px;
          border-top: 1px solid var(--border-color);
        }
        .pagination button {
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 8px 12px;
          background: transparent;
          border: none;
          border-radius: 6px;
          color: var(--text-primary);
          font-size: 0.85rem;
          cursor: pointer;
          transition: background 0.15s ease;
        }
        .pagination button:hover:not(:disabled) {
          background: rgba(255, 255, 255, 0.1);
        }
        .pagination button:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }
      `}</style>
    </CollapsiblePanel>
  );
}

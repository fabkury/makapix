import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { authenticatedFetch, authenticatedPostJson } from '../lib/api';

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

interface SPOCommentsOverlayProps {
  postId: number;
  isOpen: boolean;
  onClose: () => void;
  currentUserId?: string | null;
  isModerator?: boolean;
  initialComments?: Comment[];
}

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

export default function SPOCommentsOverlay({
  postId,
  isOpen,
  onClose,
  currentUserId,
  isModerator = false,
  initialComments = [],
}: SPOCommentsOverlayProps) {
  const [comments, setComments] = useState<Comment[]>(initialComments);
  const [loading, setLoading] = useState(false);
  const [commentBody, setCommentBody] = useState('');
  const [replyingTo, setReplyingTo] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const API_BASE_URL = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Load comments when overlay opens
  useEffect(() => {
    if (!isOpen || !postId) return;
    loadComments();
  }, [isOpen, postId]);

  const loadComments = async () => {
    setLoading(true);
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/post/${postId}/comments`);
      if (response.ok) {
        const data = await response.json();
        const items = (data.items || []).filter((comment: Comment) => {
          if (!comment || typeof comment.id === 'undefined') return false;
          if (typeof comment.depth !== 'number' || comment.depth > 2) return false;
          if (!comment.body && !comment.deleted_by_owner) return false;
          return true;
        });
        setComments(items);
      }
    } catch (error) {
      console.error('Failed to load comments:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentBody.trim() || submitting) return;

    setSubmitting(true);
    try {
      await authenticatedPostJson<{ id: string }>(
        `${API_BASE_URL}/api/post/${postId}/comments`,
        { body: commentBody.trim() }
      );
      setCommentBody('');
      await loadComments();
    } catch (error) {
      console.error('Failed to submit comment:', error);
      alert('Failed to post comment. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitReply = async (parentId: string) => {
    if (!replyBody.trim() || submitting) return;

    setSubmitting(true);
    try {
      await authenticatedPostJson<{ id: string }>(
        `${API_BASE_URL}/api/post/${postId}/comments`,
        { body: replyBody.trim(), parent_id: parentId }
      );
      setReplyBody('');
      setReplyingTo(null);
      await loadComments();
    } catch (error) {
      console.error('Failed to submit reply:', error);
      alert('Failed to post reply. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteComment = async (commentId: string) => {
    if (!confirm('Are you sure you want to delete this comment? This action cannot be undone.')) return;

    try {
      const response = await authenticatedFetch(
        `${API_BASE_URL}/api/post/comments/${commentId}`,
        { method: 'DELETE' }
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

  const canDeleteComment = useCallback((comment: Comment): boolean => {
    if (comment.deleted_by_owner) return false;
    // Moderators can delete any comment
    if (isModerator) return true;
    // Anonymous user can delete their own guest comments
    if (!currentUserId && !comment.author_id && comment.author_ip) return true;
    // Authenticated user can delete their own comments
    if (currentUserId && comment.author_id === currentUserId) return true;
    return false;
  }, [currentUserId, isModerator]);

  const renderComment = (comment: Comment, depth: number = 0): JSX.Element | null => {
    // Find replies
    const replies = comments.filter(c => c.parent_id === comment.id);
    const hasReplies = replies.length > 0;
    
    // Filter out deleted comments only if they have no replies
    if (comment.deleted_by_owner && !hasReplies) {
      return null;
    }

    const authorName = comment.deleted_by_owner
      ? '[deleted]'
      : (comment.author_display_name || comment.author_handle || 'Anonymous');
    const isGuest = !comment.deleted_by_owner && !comment.author_id && comment.author_ip !== null;
    const canReply = depth < 2; // Only allow replies up to 2 levels deep (0, 1)

    return (
      <div
        key={comment.id}
        style={{
          marginLeft: depth > 0 ? 24 : 0,
          marginBottom: 12,
          paddingLeft: depth > 0 ? 16 : 0,
          borderLeft: depth > 0 ? '2px solid rgba(180, 78, 255, 0.2)' : 'none',
        }}
      >
        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{
            width: 32,
            height: 32,
            borderRadius: '50%',
            background: '#1a1a24',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            fontSize: 16,
          }}>
            {comment.deleted_by_owner ? '🗑️' : (isGuest ? '👤' : '👨‍💻')}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}>
              <span style={{
                fontSize: 13,
                fontWeight: 600,
                color: depth === 0 ? '#00d4ff' : (depth === 1 ? '#ff6eb4' : '#b44eff'),
              }}>
                {authorName}
              </span>
              {isGuest && !comment.deleted_by_owner && (
                <span style={{ fontSize: 11, color: '#6a6a80', fontStyle: 'italic' }}>guest</span>
              )}
              <span style={{ fontSize: 11, color: '#6a6a80', marginLeft: 'auto' }}>
                {formatDate(comment.created_at)}
              </span>
            </div>
            <div style={{
              fontSize: 13,
              lineHeight: 1.5,
              color: comment.deleted_by_owner ? '#6a6a80' : '#a0a0b8',
              marginBottom: 6,
              wordWrap: 'break-word',
            }}>
              {comment.deleted_by_owner ? '[deleted]' : comment.body}
            </div>
            {!comment.deleted_by_owner && (
              <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                {canReply && (
                  <button
                    onClick={() => setReplyingTo(replyingTo === comment.id ? null : comment.id)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: '#b44eff',
                      fontSize: 12,
                      cursor: 'pointer',
                      padding: '4px 0',
                      fontWeight: 500,
                    }}
                  >
                    {replyingTo === comment.id ? 'Cancel' : 'Reply'}
                  </button>
                )}
                {canDeleteComment(comment) && (
                  <button
                    onClick={() => handleDeleteComment(comment.id)}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: '#ef4444',
                      fontSize: 12,
                      cursor: 'pointer',
                      padding: '4px 0',
                      fontWeight: 500,
                    }}
                  >
                    Delete
                  </button>
                )}
              </div>
            )}
            {replyingTo === comment.id && (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void handleSubmitReply(comment.id);
                }}
                style={{ marginTop: 8 }}
              >
                <textarea
                  value={replyBody}
                  onChange={(e) => setReplyBody(e.target.value)}
                  placeholder={`Reply to ${authorName}...`}
                  maxLength={2000}
                  style={{
                    width: '100%',
                    minHeight: 60,
                    padding: 8,
                    background: '#1a1a24',
                    border: '1px solid #252530',
                    borderRadius: 8,
                    color: '#e8e8f0',
                    fontSize: 13,
                    fontFamily: 'inherit',
                    resize: 'vertical',
                  }}
                  autoFocus
                />
                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <button
                    type="submit"
                    disabled={!replyBody.trim() || submitting}
                    style={{
                      padding: '6px 16px',
                      background: 'linear-gradient(135deg, #ff6eb4, #b44eff)',
                      color: '#fff',
                      border: 'none',
                      borderRadius: 8,
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: !replyBody.trim() || submitting ? 'not-allowed' : 'pointer',
                      opacity: !replyBody.trim() || submitting ? 0.5 : 1,
                    }}
                  >
                    {submitting ? 'Posting...' : 'Post Reply'}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setReplyingTo(null);
                      setReplyBody('');
                    }}
                    style={{
                      padding: '6px 16px',
                      background: '#1a1a24',
                      color: '#a0a0b8',
                      border: '1px solid #252530',
                      borderRadius: 8,
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}
            {/* Render replies */}
            {hasReplies && (
              <div style={{ marginTop: 12 }}>
                {replies.map(reply => renderComment(reply, depth + 1))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  const topLevelComments = comments.filter(c => !c.parent_id);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.95)',
          backdropFilter: 'blur(8px)',
          zIndex: 20002,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 16,
        }}
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          transition={{ duration: 0.2 }}
          style={{
            width: '100%',
            maxWidth: 500,
            maxHeight: '90vh',
            background: '#000',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            borderRadius: 12,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            fontFamily: "'Noto Sans', 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div style={{
            padding: 16,
            borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}>
            <h2 style={{ fontSize: 16, fontWeight: 600, color: '#e8e8f0', margin: 0 }}>
              Comments ({comments.length})
            </h2>
            <button
              onClick={onClose}
              style={{
                background: 'transparent',
                border: 'none',
                fontSize: 24,
                cursor: 'pointer',
                color: '#e8e8f0',
                padding: 0,
                lineHeight: 1,
              }}
            >
              ✕
            </button>
          </div>

          {/* Comment Input */}
          <div style={{ padding: 16, borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>
            <form onSubmit={handleSubmitComment}>
              <textarea
                value={commentBody}
                onChange={(e) => setCommentBody(e.target.value)}
                placeholder="Add a comment..."
                maxLength={2000}
                style={{
                  width: '100%',
                  minHeight: 80,
                  padding: 12,
                  background: '#1a1a24',
                  border: '1px solid #252530',
                  borderRadius: 10,
                  color: '#e8e8f0',
                  fontSize: 14,
                  fontFamily: 'inherit',
                  resize: 'vertical',
                }}
              />
              <button
                type="submit"
                disabled={!commentBody.trim() || submitting}
                style={{
                  marginTop: 8,
                  padding: '10px 20px',
                  background: 'linear-gradient(135deg, #ff6eb4, #b44eff)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 10,
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: !commentBody.trim() || submitting ? 'not-allowed' : 'pointer',
                  opacity: !commentBody.trim() || submitting ? 0.5 : 1,
                }}
              >
                {submitting ? 'Posting...' : 'Post Comment'}
              </button>
            </form>
          </div>

          {/* Comments List */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: 16,
          }}>
            {loading ? (
              <div style={{ textAlign: 'center', color: '#6a6a80', padding: 24 }}>
                Loading comments...
              </div>
            ) : topLevelComments.length === 0 ? (
              <div style={{ textAlign: 'center', color: '#6a6a80', padding: 24 }}>
                No comments yet. Be the first to comment!
              </div>
            ) : (
              topLevelComments.map(comment => renderComment(comment, 0))
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

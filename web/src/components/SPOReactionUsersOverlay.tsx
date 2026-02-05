import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/router';

interface ReactionUserItem {
  emoji: string;
  created_at: string;
  user_handle: string;
  user_avatar_url: string | null;
  user_public_sqid: string | null;
}

interface SPOReactionUsersOverlayProps {
  postId: number;
  isOpen: boolean;
  onClose: () => void;
}

export default function SPOReactionUsersOverlay({
  postId,
  isOpen,
  onClose,
}: SPOReactionUsersOverlayProps) {
  const [items, setItems] = useState<ReactionUserItem[]>([]);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const API_BASE_URL = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  useEffect(() => {
    if (!isOpen || !postId) return;
    setLoading(true);
    fetch(`${API_BASE_URL}/api/post/${postId}/reaction-users`)
      .then((res) => {
        if (res.ok) return res.json();
        throw new Error('Failed to load');
      })
      .then((data) => {
        setItems(data.items || []);
      })
      .catch((err) => {
        console.error('Failed to load reaction users:', err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [isOpen, postId]);

  const navigateToUser = (sqid: string) => {
    onClose();
    void router.push(`/u/${sqid}`);
  };

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
              Reactions ({items.length})
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

          {/* Reaction Users List */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: 16,
          }}>
            {loading ? (
              <div style={{ textAlign: 'center', color: '#6a6a80', padding: 24 }}>
                Loading reactions...
              </div>
            ) : items.length === 0 ? (
              <div style={{ textAlign: 'center', color: '#6a6a80', padding: 24 }}>
                No reactions yet.
              </div>
            ) : (
              items.map((item, idx) => (
                <div
                  key={`${item.user_handle}-${item.emoji}-${idx}`}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    marginBottom: 12,
                  }}
                >
                  {/* Avatar */}
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      background: '#1a1a24',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                      overflow: 'hidden',
                      cursor: item.user_public_sqid ? 'pointer' : 'default',
                    }}
                    onClick={() => item.user_public_sqid && navigateToUser(item.user_public_sqid)}
                  >
                    {item.user_avatar_url ? (
                      <img
                        src={item.user_avatar_url}
                        alt=""
                        style={{
                          width: '100%',
                          height: '100%',
                          objectFit: 'cover',
                          imageRendering: 'pixelated',
                        }}
                      />
                    ) : (
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6a6a80" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                        <circle cx="12" cy="7" r="4" />
                      </svg>
                    )}
                  </div>

                  {/* Handle */}
                  <span
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      color: '#00d4ff',
                      flex: 1,
                      minWidth: 0,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      cursor: item.user_public_sqid ? 'pointer' : 'default',
                    }}
                    onClick={() => item.user_public_sqid && navigateToUser(item.user_public_sqid)}
                  >
                    {item.user_handle}
                  </span>

                  {/* Emoji */}
                  <span style={{ fontSize: 18, flexShrink: 0 }}>
                    {item.emoji}
                  </span>
                </div>
              ))
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

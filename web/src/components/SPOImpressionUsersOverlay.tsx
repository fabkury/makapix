import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/router';
import { authenticatedFetch, getAccessToken } from '../lib/api';

/**
 * "Displayed on" list, opened from the 📺 number (docs/impression-list/).
 *
 * Members whose screens showed this artwork in the last 90 days. The API
 * gives a date, never a time (L3), and device models, never player names (L2).
 */
interface ImpressionUserItem {
  user_handle: string;
  user_avatar_url: string | null;
  user_public_sqid: string | null;
  device_models: string[];
  web_player: boolean;
  app: boolean;
  count: number;
  /** UTC calendar day, YYYY-MM-DD. */
  last_shown_on: string;
}

interface SPOImpressionUsersOverlayProps {
  postId: number;
  isOpen: boolean;
  onClose: () => void;
}

const PAGE_SIZE = 50;

function sourceLabel(item: ImpressionUserItem): string {
  const parts = [...item.device_models];
  if (item.web_player) parts.push('Web Player');
  if (item.app) parts.push('App');
  return parts.length > 0 ? parts.join(', ') : 'Player';
}

/** Day-granular wording; both sides are UTC calendar days. */
function lastShownLabel(isoDay: string): string {
  const [y, m, d] = isoDay.split('-').map(Number);
  const now = new Date();
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  const days = Math.max(0, Math.round((today - Date.UTC(y, m - 1, d)) / 86400000));
  if (days === 0) return 'today';
  if (days === 1) return 'yesterday';
  if (days < 14) return `${days} days ago`;
  return `${Math.floor(days / 7)} weeks ago`;
}

export default function SPOImpressionUsersOverlay({
  postId,
  isOpen,
  onClose,
}: SPOImpressionUsersOverlayProps) {
  const [items, setItems] = useState<ImpressionUserItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [signedOut, setSignedOut] = useState(false);
  const router = useRouter();

  const API_BASE_URL = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  const loadPage = async (cursor: string | null) => {
    setLoading(true);
    setFailed(false);
    try {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
      if (cursor) params.set('cursor', cursor);
      const res = await authenticatedFetch(
        `${API_BASE_URL}/api/post/${postId}/impression-users?${params}`,
      );
      if (res.status === 401) {
        setSignedOut(true);
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setItems((prev) => (cursor ? [...prev, ...(data.items || [])] : data.items || []));
      setNextCursor(data.next_cursor || null);
    } catch (err) {
      console.error('Failed to load impression users:', err);
      setFailed(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isOpen || !postId) return;
    setItems([]);
    setNextCursor(null);
    if (!getAccessToken()) {
      setSignedOut(true);
      return;
    }
    setSignedOut(false);
    void loadPage(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, postId]);

  const navigateToUser = (sqid: string) => {
    onClose();
    void router.push(`/u/${sqid}`);
  };

  if (!isOpen) return null;
  if (typeof document === 'undefined') return null;

  const muted = { textAlign: 'center' as const, color: '#6a6a80', padding: 24 };

  // Portal to body so zIndex applies at document root, not inside SPO's
  // stacking context. See SPOCommentsOverlay for the full reasoning.
  return createPortal(
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
              Displayed on
            </h2>
            <button
              onClick={onClose}
              aria-label="Close"
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

          <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
            {signedOut ? (
              <div style={muted}>
                <p style={{ margin: '0 0 12px' }}>
                  Sign in to see whose screens displayed this artwork.
                </p>
                <button
                  onClick={() => {
                    onClose();
                    void router.push('/auth');
                  }}
                  style={{
                    background: 'transparent',
                    border: '1px solid #00d4ff',
                    color: '#00d4ff',
                    padding: '6px 14px',
                    borderRadius: 6,
                    cursor: 'pointer',
                    fontSize: 13,
                  }}
                >
                  Sign in
                </button>
              </div>
            ) : (
              <>
                {items.map((item) => (
                  <div
                    key={item.user_public_sqid || item.user_handle}
                    style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}
                  >
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
                        marginRight: 10,
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

                    <div style={{ flex: 1, minWidth: 0, marginRight: 10 }}>
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: 600,
                          color: '#00d4ff',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          cursor: item.user_public_sqid ? 'pointer' : 'default',
                        }}
                        onClick={() => item.user_public_sqid && navigateToUser(item.user_public_sqid)}
                      >
                        {item.user_handle}
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: '#a0a0b8',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {sourceLabel(item)}
                      </div>
                    </div>

                    <div style={{ flexShrink: 0, textAlign: 'right' }}>
                      <div style={{ fontSize: 12, color: '#e8e8f0' }}>
                        {item.count === 1 ? 'shown once' : `shown ${item.count} times`}
                      </div>
                      <div style={{ fontSize: 11, color: '#6a6a80' }}>
                        {lastShownLabel(item.last_shown_on)}
                      </div>
                    </div>
                  </div>
                ))}

                {loading && <div style={muted}>Loading…</div>}
                {failed && <div style={muted}>Could not load the list.</div>}
                {!loading && !failed && items.length === 0 && (
                  <div style={muted}>No members to show yet.</div>
                )}

                {!loading && nextCursor && (
                  <div style={{ textAlign: 'center', marginBottom: 12 }}>
                    <button
                      onClick={() => void loadPage(nextCursor)}
                      style={{
                        background: 'transparent',
                        border: '1px solid rgba(255, 255, 255, 0.2)',
                        color: '#e8e8f0',
                        padding: '6px 14px',
                        borderRadius: 6,
                        cursor: 'pointer',
                        fontSize: 13,
                      }}
                    >
                      Show more
                    </button>
                  </div>
                )}
              </>
            )}
          </div>

          {!signedOut && (
            <div style={{
              padding: '10px 16px',
              borderTop: '1px solid rgba(255, 255, 255, 0.1)',
              fontSize: 11,
              color: '#6a6a80',
              lineHeight: 1.4,
            }}>
              Members whose player or Web Player showed this artwork in the last
              90 days. Anonymous and private showings are not listed.
            </div>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body
  );
}

/**
 * FollowersOverlay component - modal showing a user's followers.
 */

import { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { authenticatedFetch } from '../../lib/api';

interface Follower {
  public_sqid: string | null;
  handle: string;
  avatar_url: string | null;
}

interface FollowersOverlayProps {
  isOpen: boolean;
  onClose: () => void;
  userSqid: string;
}

export default function FollowersOverlay({ isOpen, onClose, userSqid }: FollowersOverlayProps) {
  const router = useRouter();
  const [followers, setFollowers] = useState<Follower[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (!isOpen || !userSqid) return;

    setLoading(true);
    setFollowers([]);

    const API_BASE_URL = typeof window !== 'undefined'
      ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
      : '';

    authenticatedFetch(`${API_BASE_URL}/api/user/u/${userSqid}/followers?limit=200`)
      .then((res) => res.json())
      .then((data) => {
        setFollowers(data.items || []);
        setTotal(data.total || 0);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [isOpen, userSqid]);

  if (!isOpen) return null;

  return (
    <div className="followers-overlay" onClick={onClose}>
      <div className="followers-modal" onClick={(e) => e.stopPropagation()}>
        <div className="followers-header">
          <h2>👤 Followers{!loading && ` (${total})`}</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <div className="followers-content">
          {loading && <p className="loading">Loading followers...</p>}

          {!loading && followers.length === 0 && (
            <p className="empty">No followers yet</p>
          )}

          {!loading && followers.map((follower) => (
            <div
              key={follower.public_sqid || follower.handle}
              className="follower-item"
              onClick={() => {
                if (follower.public_sqid) {
                  router.push(`/u/${follower.public_sqid}`);
                  onClose();
                }
              }}
            >
              {follower.avatar_url ? (
                <img
                  src={follower.avatar_url}
                  alt={follower.handle}
                  className="follower-avatar"
                  width={32}
                  height={32}
                />
              ) : (
                <span className="follower-avatar-placeholder">👤</span>
              )}
              <span className="follower-handle">@{follower.handle}</span>
            </div>
          ))}
        </div>
      </div>

      <style jsx>{`
        .followers-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.8);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: 20px;
        }
        .followers-modal {
          background: var(--bg-secondary);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          max-width: 400px;
          width: 100%;
          max-height: 80vh;
          overflow: hidden;
          display: flex;
          flex-direction: column;
        }
        .followers-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px 20px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        .followers-header h2 {
          margin: 0;
          font-size: 1.2rem;
        }
        .close-btn {
          background: none;
          border: none;
          color: var(--text-secondary);
          font-size: 1.5rem;
          cursor: pointer;
          padding: 0 8px;
        }
        .close-btn:hover {
          color: white;
        }
        .followers-content {
          padding: 12px 20px;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .loading, .empty {
          text-align: center;
          color: var(--text-secondary);
          padding: 20px;
        }
        .follower-item {
          display: flex;
          gap: 12px;
          align-items: center;
          padding: 8px;
          border-radius: 8px;
          cursor: pointer;
        }
        .follower-item:hover {
          background: rgba(255, 255, 255, 0.05);
        }
        .follower-avatar {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          image-rendering: pixelated;
          flex-shrink: 0;
        }
        .follower-avatar-placeholder {
          width: 32px;
          height: 32px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.2rem;
          flex-shrink: 0;
        }
        .follower-handle {
          color: var(--text-primary);
          font-weight: 500;
          font-size: 0.95rem;
        }
      `}</style>
    </div>
  );
}

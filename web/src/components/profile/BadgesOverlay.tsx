/**
 * BadgesOverlay component - modal showing all user badges.
 */

import { useEffect, useState } from 'react';
import { BadgeDefinition, BadgeGrant } from '../../types/profile';
import { authenticatedFetch } from '../../lib/api';

interface BadgesOverlayProps {
  isOpen: boolean;
  onClose: () => void;
  userBadges: BadgeGrant[];
}

export default function BadgesOverlay({ isOpen, onClose, userBadges }: BadgesOverlayProps) {
  const [badgeDefinitions, setBadgeDefinitions] = useState<BadgeDefinition[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && badgeDefinitions.length === 0) {
      setLoading(true);
      const API_BASE_URL = typeof window !== 'undefined'
        ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
        : '';

      authenticatedFetch(`${API_BASE_URL}/api/badge`)
        .then((res) => res.json())
        .then((data) => {
          setBadgeDefinitions(data.items || []);
        })
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [isOpen, badgeDefinitions.length]);

  if (!isOpen) return null;

  // Create lookup for user badges
  const userBadgeSet = new Set(userBadges.map((b) => b.badge));

  // Match user badges with definitions
  const matchedBadges = badgeDefinitions.filter((def) => userBadgeSet.has(def.badge));

  return (
    <div className="badges-overlay" onClick={onClose}>
      <div className="badges-modal" onClick={(e) => e.stopPropagation()}>
        <div className="badges-header">
          <h2>🛡️ Badges</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        <div className="badges-content">
          {loading && <p className="loading">Loading badges...</p>}

          {!loading && matchedBadges.length === 0 && (
            <p className="empty">No badges yet</p>
          )}

          {!loading && matchedBadges.map((badge) => (
            <div key={badge.badge} className="badge-item">
              <img
                src={badge.icon_url_64}
                alt={badge.label}
                className="badge-icon"
                width={64}
                height={64}
              />
              <div className="badge-info">
                <span className="badge-label">{badge.label}</span>
                {badge.description && (
                  <span className="badge-desc">{badge.description}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <style jsx>{`
        .badges-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.8);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: 20px;
        }
        .badges-modal {
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
        .badges-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px 20px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        .badges-header h2 {
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
        .badges-content {
          padding: 20px;
          overflow-y: auto;
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .loading, .empty {
          text-align: center;
          color: var(--text-secondary);
          padding: 20px;
        }
        .badge-item {
          display: flex;
          gap: 16px;
          align-items: center;
        }
        .badge-icon {
          width: 64px;
          height: 64px;
          image-rendering: pixelated;
          flex-shrink: 0;
        }
        .badge-info {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .badge-label {
          font-weight: 600;
          color: var(--text-primary);
        }
        .badge-desc {
          font-size: 0.85rem;
          color: var(--text-secondary);
        }
      `}</style>
    </div>
  );
}

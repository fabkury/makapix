/**
 * BadgePanel - Grant/revoke badges for a user.
 * Shows current badges and allows moderators to manage them.
 */

import { useState, useEffect } from 'react';
import CollapsiblePanel from './CollapsiblePanel';
import { authenticatedFetch } from '../../lib/api';

interface Badge {
  badge: string;
  label: string;
}

interface BadgeGrant {
  badge: string;
  granted_at: string;
}

interface BadgePanelProps {
  sqid: string;
  currentBadges: BadgeGrant[];
  onBadgesChange: (badges: BadgeGrant[]) => void;
}

export default function BadgePanel({ sqid, currentBadges, onBadgesChange }: BadgePanelProps) {
  const [availableBadges, setAvailableBadges] = useState<Badge[]>([]);
  const [selectedBadge, setSelectedBadge] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch available badges
  useEffect(() => {
    const fetchBadges = async () => {
      try {
        const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
        const response = await authenticatedFetch(`${apiBaseUrl}/api/admin/badges`);
        if (response.ok) {
          const data = await response.json();
          setAvailableBadges(data.badges);
        }
      } catch (err) {
        console.error('Failed to fetch badges:', err);
      }
    };
    fetchBadges();
  }, []);

  const userBadgeSet = new Set(currentBadges.map(b => b.badge));
  const hasBadge = selectedBadge && userBadgeSet.has(selectedBadge);

  const handleGrantRevoke = async () => {
    if (!selectedBadge) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const method = hasBadge ? 'DELETE' : 'POST';
      const response = await authenticatedFetch(
        `${apiBaseUrl}/api/admin/user/${sqid}/badge/${selectedBadge}`,
        { method }
      );

      if (!response.ok && response.status !== 204) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to update badge');
      }

      // Update local state
      if (hasBadge) {
        onBadgesChange(currentBadges.filter(b => b.badge !== selectedBadge));
      } else {
        onBadgesChange([...currentBadges, { badge: selectedBadge, granted_at: new Date().toISOString() }]);
      }

      setSelectedBadge('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update badge');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <CollapsiblePanel title="Badges">
      <div className="badge-panel">
        <div className="current-badges">
          <label>Current badges ({currentBadges.length})</label>
          <div className="badge-list">
            {currentBadges.length > 0 ? (
              currentBadges.map((badge) => {
                const badgeDef = availableBadges.find(b => b.badge === badge.badge);
                return (
                  <span key={badge.badge} className="badge-tag">
                    {badgeDef?.label || badge.badge}
                  </span>
                );
              })
            ) : (
              <span className="no-badges">No badges yet</span>
            )}
          </div>
        </div>

        <div className="select-section">
          <label>Select badge</label>
          <select
            value={selectedBadge}
            onChange={(e) => setSelectedBadge(e.target.value)}
            disabled={isSubmitting}
          >
            <option value="">-- Choose a badge --</option>
            {availableBadges.map((badge) => (
              <option key={badge.badge} value={badge.badge}>
                {badge.label} {userBadgeSet.has(badge.badge) ? '\u2713' : ''}
              </option>
            ))}
          </select>
        </div>

        {error && <div className="error">{error}</div>}

        <button
          onClick={handleGrantRevoke}
          disabled={!selectedBadge || isSubmitting}
          className={`submit-btn ${hasBadge ? 'revoke' : 'grant'}`}
        >
          {isSubmitting ? 'Updating...' : hasBadge ? 'Revoke' : 'Grant'}
        </button>
      </div>

      <style jsx>{`
        .badge-panel {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .current-badges {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .current-badges label {
          font-size: 0.9rem;
          color: var(--text-secondary);
        }
        .badge-list {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
        .badge-tag {
          display: inline-flex;
          align-items: center;
          padding: 4px 12px;
          background: rgba(0, 212, 255, 0.15);
          border: 1px solid rgba(0, 212, 255, 0.3);
          border-radius: 16px;
          font-size: 0.85rem;
          color: var(--accent-cyan);
        }
        .no-badges {
          font-size: 0.85rem;
          color: var(--text-muted);
          font-style: italic;
        }
        .select-section {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .select-section label {
          font-size: 0.9rem;
          color: var(--text-secondary);
        }
        select {
          width: 100%;
          padding: 10px 12px;
          background: var(--bg-tertiary);
          border: 1px solid var(--border-color);
          border-radius: 6px;
          color: var(--text-primary);
          font-size: 0.9rem;
          cursor: pointer;
        }
        select:focus {
          outline: none;
          border-color: var(--accent-cyan);
        }
        select option {
          background: var(--bg-secondary);
        }
        .error {
          color: var(--accent-pink);
          font-size: 0.85rem;
        }
        .submit-btn {
          width: 100%;
          padding: 12px;
          border: none;
          border-radius: 6px;
          font-size: 0.95rem;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.15s ease, opacity 0.15s ease;
        }
        .submit-btn:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }
        .submit-btn.grant {
          background: var(--accent-cyan);
          color: #000;
        }
        .submit-btn.grant:hover:not(:disabled) {
          background: #00e5ff;
        }
        .submit-btn.revoke {
          background: var(--accent-pink);
          color: #000;
        }
        .submit-btn.revoke:hover:not(:disabled) {
          background: #ff6090;
        }
      `}</style>
    </CollapsiblePanel>
  );
}

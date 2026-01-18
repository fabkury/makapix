/**
 * TagBadges component - displays tag badges under the username.
 * Shows 16x16 badge icons, or 🛡️ emoji if no badges.
 * Clicking anywhere in the area opens the badges overlay.
 */

import { TagBadgeInfo } from '../../types/profile';

interface TagBadgesProps {
  badges: TagBadgeInfo[];
  onAreaClick: () => void;
}

export default function TagBadges({ badges, onAreaClick }: TagBadgesProps) {
  return (
    <button
      className="tag-badges-area"
      onClick={onAreaClick}
      aria-label="View all badges"
      type="button"
    >
      {badges.length > 0 ? (
        badges.map((badge) => {
          const icon32 = badge.icon_url_16.replace('_16.png', '_32.png');
          return (
            <img
              key={badge.badge}
              src={badge.icon_url_16}
              srcSet={`${badge.icon_url_16} 1x, ${icon32} 2x`}
              alt={badge.label}
              title={badge.label}
              className="tag-badge-icon"
              width={16}
              height={16}
            />
          );
        })
      ) : (
        <span className="tag-badge-placeholder">🛡️</span>
      )}

      <style jsx>{`
        .tag-badges-area {
          display: flex;
          align-items: center;
          gap: 4px;
          min-height: 16px;
          cursor: pointer;
          padding: 4px;
          background: none;
          border: none;
          border-radius: 4px;
          transition: background 0.15s ease;
        }
        .tag-badges-area:hover {
          background: rgba(255, 255, 255, 0.1);
        }
        .tag-badges-area:focus {
          outline: none;
        }
        .tag-badges-area:active {
          background: none;
        }
        .tag-badge-icon {
          width: 16px;
          height: 16px;
          image-rendering: pixelated;
        }
        .tag-badge-placeholder {
          font-size: 16px;
          line-height: 16px;
        }
      `}</style>
    </button>
  );
}

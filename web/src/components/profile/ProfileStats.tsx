/**
 * ProfileStats component - displays user statistics in a horizontal row.
 * Uses emojis as labels:
 * - 👤 Followers
 * - 🖼️ Posts
 * - 👁️ Views
 * - 🧮 Reputation
 */

import { formatCount } from '../../utils/formatCount';
import { UserProfileStats as Stats } from '../../types/profile';

interface ProfileStatsProps {
  stats: Stats;
  reputation: number;
  onFollowerClick?: () => void;
}

export default function ProfileStats({ stats, reputation, onFollowerClick }: ProfileStatsProps) {
  return (
    <div className="profile-stats">
      <div
        className={`stat${onFollowerClick ? ' stat-clickable' : ''}`}
        onClick={onFollowerClick}
      >
        <span className="stat-icon">👤</span>
        <span className="stat-value">{formatCount(stats.follower_count)}</span>
      </div>
      <div className="stat-separator" />
      <div className="stat">
        <span className="stat-icon">🖼️</span>
        <span className="stat-value">{formatCount(stats.total_posts)}</span>
      </div>
      <div className="stat-separator" />
      <div className="stat">
        <span className="stat-icon">👁️</span>
        <span className="stat-value">{formatCount(stats.total_views)}</span>
      </div>
      <div className="stat-separator" />
      <div className="stat">
        <span className="stat-icon">🧮</span>
        <span className="stat-value">{formatCount(reputation)}</span>
      </div>

      <style jsx>{`
        .profile-stats {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          margin: -8px;
          margin-top: 8px;
          font-size: 0.9rem;
        }
        .profile-stats > :global(*) {
          margin: 8px;
        }
        .stat {
          display: flex;
          align-items: center;
        }
        .stat > :global(* + *) {
          margin-left: 6px;
        }
        .stat-icon {
          font-size: 1rem;
          opacity: 0.7;
        }
        .stat-value {
          color: var(--text-primary);
          font-weight: 500;
        }
        .stat-clickable {
          cursor: pointer;
        }
        .stat-clickable:hover {
          opacity: 0.7;
        }
        .stat-separator {
          width: 1px;
          height: 16px;
          background: rgba(255, 255, 255, 0.2);
        }
        @media (max-width: 600px) {
          .profile-stats {
            margin: -6px;
            margin-top: 10px;
          }
          .profile-stats > :global(*) {
            margin: 6px;
          }
        }
      `}</style>
    </div>
  );
}

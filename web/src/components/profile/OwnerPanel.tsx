/**
 * OwnerPanel component - displays management buttons for the profile owner.
 * Only visible when viewing own profile or for moderators viewing others.
 */

import Link from 'next/link';
import { logout } from '../../lib/api';
import { useRouter } from 'next/router';

interface OwnerPanelProps {
  userSqid: string;
  onEditClick?: () => void;
  isOwner: boolean;           // true = viewing own profile
  isModerator?: boolean;      // viewer is moderator
  isTargetOwner?: boolean;    // target user has owner badge
}

export default function OwnerPanel({
  userSqid,
  onEditClick,
  isOwner,
  isModerator = false,
  isTargetOwner = false,
}: OwnerPanelProps) {
  const router = useRouter();

  // Show PMD button if: own profile OR (moderator AND NOT target is owner)
  const showPMD = isOwner || (isModerator && !isTargetOwner);

  const handleLogout = async () => {
    if (window.confirm('Are you sure you want to log out?')) {
      await logout();
      router.push('/');
    }
  };

  return (
    <div className="owner-panel">
      <Link
        href={`/u/${userSqid}/dashboard`}
        className="panel-btn"
        title="Artist Dashboard"
      >
        📊
      </Link>
      {/* PMD button - shown for own profile or moderators (except for site owner's profile) */}
      {showPMD && (
        <Link
          href={`/u/${userSqid}/posts`}
          className="panel-btn"
          title="Post Management Dashboard"
        >
          🗂️
        </Link>
      )}
      {/* Rest of owner-only buttons */}
      {isOwner && (
        <>
          <Link
            href={`/u/${userSqid}/player`}
            className="panel-btn"
            title="Manage Players"
          >
            📺
          </Link>
          <div className="spacer" />
          <button
            className="panel-btn"
            onClick={onEditClick}
            title="Edit Profile"
          >
            ✏️
          </button>
          <button
            className="panel-btn logout"
            onClick={handleLogout}
            title="Log Out"
          >
            🚪
          </button>
        </>
      )}

      <style jsx>{`
        .owner-panel {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 16px;
        }
        .spacer {
          width: 16px;
        }
        :global(.panel-btn) {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 8px 12px;
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 8px;
          background: transparent;
          cursor: pointer;
          transition: all 0.2s ease;
          font-size: 1.1rem;
          text-decoration: none;
        }
        :global(.panel-btn:hover) {
          background: rgba(255, 255, 255, 0.1);
          border-color: var(--accent-cyan);
        }
        .logout:hover {
          border-color: var(--accent-pink) !important;
        }
      `}</style>
    </div>
  );
}

/**
 * OwnerPanel - Owner-only actions for managing moderator status.
 * Uses triple-click confirmation for both granting and revoking.
 * Only visible to the site owner.
 */

import { useState } from 'react';
import CollapsiblePanel from './CollapsiblePanel';
import { authenticatedFetch } from '../../lib/api';

interface OwnerPanelProps {
  userKey: string;
  isModerator: boolean;
  onModeratorChange: (isModerator: boolean) => void;
}

export default function OwnerPanel({
  userKey,
  isModerator,
  onModeratorChange,
}: OwnerPanelProps) {
  const [confirmClicks, setConfirmClicks] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const handleToggleModerator = async () => {
    if (confirmClicks < 2) {
      setConfirmClicks(confirmClicks + 1);
      setTimeout(() => setConfirmClicks(0), 3000);
      return;
    }

    setIsLoading(true);
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const method = isModerator ? 'DELETE' : 'POST';
      const response = await authenticatedFetch(
        `${apiBaseUrl}/api/admin/user/${userKey}/moderator`,
        { method }
      );

      if (response.ok || response.status === 204) {
        onModeratorChange(!isModerator);
      } else {
        // Log the error response for debugging
        const errorText = await response.text();
        console.error(`Failed to toggle moderator: ${response.status} - ${errorText}`);
      }
    } catch (err) {
      console.error('Failed to toggle moderator:', err);
    } finally {
      setIsLoading(false);
      setConfirmClicks(0);
    }
  };

  const getButtonText = () => {
    if (confirmClicks === 0) {
      return isModerator ? 'Revoke Moderator' : 'Make Moderator';
    }
    if (confirmClicks === 1) {
      return 'Click again to confirm';
    }
    return `Click once more to ${isModerator ? 'revoke' : 'grant'}`;
  };

  return (
    <CollapsiblePanel title="Owner actions" defaultOpen={false}>
      <div className="owner-panel">
        <p className="description">
          {isModerator
            ? 'This user is currently a moderator. Revoking will remove their moderation privileges.'
            : 'Grant moderator privileges to this user. Moderators can manage other users and content.'}
        </p>

        <button
          onClick={handleToggleModerator}
          disabled={isLoading}
          className={`action-btn ${
            confirmClicks > 0
              ? isModerator ? 'danger-confirm' : 'primary-confirm'
              : isModerator ? 'danger' : 'primary'
          }`}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            {isModerator ? (
              <>
                <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <line x1="17" y1="8" x2="23" y2="8" />
              </>
            ) : (
              <>
                <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                <circle cx="9" cy="7" r="4" />
                <line x1="20" y1="8" x2="20" y2="14" />
                <line x1="17" y1="11" x2="23" y2="11" />
              </>
            )}
          </svg>
          {isLoading ? 'Updating...' : getButtonText()}
        </button>

        {isModerator && (
          <div className="current-status">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            <span>Currently a moderator</span>
          </div>
        )}
      </div>

      <style jsx>{`
        .owner-panel {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .description {
          font-size: 0.9rem;
          color: var(--text-secondary);
          margin: 0;
          line-height: 1.5;
        }
        .action-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          width: 100%;
          padding: 12px 16px;
          border: none;
          border-radius: 8px;
          font-size: 0.95rem;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.15s ease, opacity 0.15s ease;
        }
        .action-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
        .action-btn.primary {
          background: var(--accent-cyan);
          color: #000;
        }
        .action-btn.primary:hover:not(:disabled) {
          background: #00e5ff;
        }
        .action-btn.primary-confirm {
          background: #0097a7;
          color: #000;
        }
        .action-btn.danger {
          background: var(--accent-pink);
          color: #000;
        }
        .action-btn.danger:hover:not(:disabled) {
          background: #ff6090;
        }
        .action-btn.danger-confirm {
          background: #d4004a;
          color: #000;
        }
        .current-status {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 12px;
          background: rgba(0, 212, 255, 0.1);
          border: 1px solid rgba(0, 212, 255, 0.3);
          border-radius: 8px;
          color: var(--accent-cyan);
          font-size: 0.9rem;
        }
      `}</style>
    </CollapsiblePanel>
  );
}

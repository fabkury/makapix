/**
 * ModeratorActionsPanel - Major moderation actions for a user.
 * Trust/Distrust, Hide/Unhide, Ban, and Reveal Email.
 * Uses multi-click confirmations for destructive actions.
 */

import { useState } from 'react';
import CollapsiblePanel from './CollapsiblePanel';
import { authenticatedFetch } from '../../lib/api';

interface ModeratorActionsPanelProps {
  sqid: string;
  isTrusted: boolean;
  isHidden: boolean;
  isBanned: boolean;
  bannedUntil: string | null;
  onTrustChange: (trusted: boolean) => void;
  onHiddenChange: (hidden: boolean) => void;
  onBanChange: (bannedUntil: string | null) => void;
}

export default function ModeratorActionsPanel({
  sqid,
  isTrusted,
  isHidden,
  isBanned,
  bannedUntil,
  onTrustChange,
  onHiddenChange,
  onBanChange,
}: ModeratorActionsPanelProps) {
  const [confirmHide, setConfirmHide] = useState(0);
  const [confirmBan, setConfirmBan] = useState(0);
  const [confirmEmail, setConfirmEmail] = useState(false);
  const [emailRevealed, setEmailRevealed] = useState(false);
  const [revealedEmail, setRevealedEmail] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<string | null>(null);

  const handleToggleTrust = async () => {
    setIsLoading('trust');
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const method = isTrusted ? 'DELETE' : 'POST';
      const response = await authenticatedFetch(
        `${apiBaseUrl}/api/admin/user/${sqid}/trust`,
        { method }
      );

      if (response.ok || response.status === 204) {
        onTrustChange(!isTrusted);
      }
    } catch (err) {
      console.error('Failed to toggle trust:', err);
    } finally {
      setIsLoading(null);
    }
  };

  const handleToggleHide = async () => {
    if (confirmHide < 2) {
      setConfirmHide(confirmHide + 1);
      setTimeout(() => setConfirmHide(0), 3000);
      return;
    }

    setIsLoading('hide');
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const method = isHidden ? 'DELETE' : 'POST';
      const response = await authenticatedFetch(
        `${apiBaseUrl}/api/admin/user/${sqid}/hide`,
        { method }
      );

      if (response.ok || response.status === 204) {
        onHiddenChange(!isHidden);
      }
    } catch (err) {
      console.error('Failed to toggle hide:', err);
    } finally {
      setIsLoading(null);
      setConfirmHide(0);
    }
  };

  const handleBan = async () => {
    if (confirmBan < 2) {
      setConfirmBan(confirmBan + 1);
      setTimeout(() => setConfirmBan(0), 3000);
      return;
    }

    setIsLoading('ban');
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const response = await authenticatedFetch(
        `${apiBaseUrl}/api/admin/user/${sqid}/ban`,
        { method: 'POST' }
      );

      if (response.ok) {
        const data = await response.json();
        onBanChange(data.until);
      }
    } catch (err) {
      console.error('Failed to ban user:', err);
    } finally {
      setIsLoading(null);
      setConfirmBan(0);
    }
  };

  const handleUnban = async () => {
    setIsLoading('unban');
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const response = await authenticatedFetch(
        `${apiBaseUrl}/api/admin/user/${sqid}/ban`,
        { method: 'DELETE' }
      );

      if (response.ok || response.status === 204) {
        onBanChange(null);
      }
    } catch (err) {
      console.error('Failed to unban user:', err);
    } finally {
      setIsLoading(null);
    }
  };

  const handleRevealEmail = async () => {
    if (!confirmEmail) {
      setConfirmEmail(true);
      setTimeout(() => setConfirmEmail(false), 3000);
      return;
    }

    setIsLoading('email');
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const response = await authenticatedFetch(
        `${apiBaseUrl}/api/admin/user/${sqid}/email`
      );

      if (response.ok) {
        const data = await response.json();
        setRevealedEmail(data.email);
        setEmailRevealed(true);
      }
    } catch (err) {
      console.error('Failed to reveal email:', err);
    } finally {
      setIsLoading(null);
      setConfirmEmail(false);
    }
  };

  const getHideButtonText = () => {
    if (confirmHide === 0) return isHidden ? 'Unhide User' : 'Hide User';
    if (confirmHide === 1) return 'Click again to confirm';
    return `Click once more to ${isHidden ? 'unhide' : 'hide'}`;
  };

  const getBanButtonText = () => {
    if (confirmBan === 0) return 'Ban User';
    if (confirmBan === 1) return 'Click again to confirm';
    return 'Click once more to ban';
  };

  return (
    <CollapsiblePanel title="Moderation actions">
      <div className="actions-panel">
        {/* Trust/Distrust */}
        <button
          onClick={handleToggleTrust}
          disabled={isLoading === 'trust'}
          className={`action-btn ${isTrusted ? 'secondary' : 'primary'}`}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            {isTrusted ? (
              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8m7.5-4.5 3 3L23 6" />
            ) : (
              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8m13 0h-6" />
            )}
          </svg>
          {isLoading === 'trust' ? 'Updating...' : isTrusted ? 'Distrust User' : 'Trust User'}
        </button>

        <div className="spacer" />

        {/* Hide/Unhide */}
        <button
          onClick={handleToggleHide}
          disabled={isLoading === 'hide'}
          className={`action-btn ${
            confirmHide > 0
              ? isHidden ? 'secondary-confirm' : 'danger-confirm'
              : isHidden ? 'secondary' : 'danger'
          }`}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            {isHidden ? (
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z" />
            ) : (
              <>
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                <line x1="1" y1="1" x2="23" y2="23" />
              </>
            )}
          </svg>
          {isLoading === 'hide' ? 'Updating...' : getHideButtonText()}
        </button>

        <div className="spacer" />

        {/* Ban/Unban */}
        {isBanned ? (
          <button
            onClick={handleUnban}
            disabled={isLoading === 'unban'}
            className="action-btn secondary"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="m4.93 4.93 14.14 14.14" />
            </svg>
            {isLoading === 'unban' ? 'Updating...' : 'Unban User'}
          </button>
        ) : (
          <button
            onClick={handleBan}
            disabled={isLoading === 'ban'}
            className={`action-btn ${confirmBan > 0 ? 'danger-confirm' : 'danger'}`}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="m4.93 4.93 14.14 14.14" />
            </svg>
            {isLoading === 'ban' ? 'Updating...' : getBanButtonText()}
          </button>
        )}

        <div className="spacer" />

        {/* Reveal Email */}
        <button
          onClick={handleRevealEmail}
          disabled={isLoading === 'email' || emailRevealed}
          className={`action-btn ${confirmEmail ? 'primary-confirm' : 'primary'}`}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
            <polyline points="22,6 12,13 2,6" />
          </svg>
          {isLoading === 'email'
            ? 'Loading...'
            : confirmEmail
            ? 'Click to confirm (action will be logged)'
            : "Reveal User's Email"
          }
        </button>

        {emailRevealed && revealedEmail && (
          <div className="email-revealed">
            <div className="email-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                <polyline points="22,6 12,13 2,6" />
              </svg>
            </div>
            <div className="email-content">
              <div className="email-label">Email Address</div>
              <div className="email-value">{revealedEmail}</div>
              <div className="email-warning">This action has been logged for auditing purposes.</div>
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        .actions-panel {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .spacer {
          height: 4px;
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
        .action-btn.secondary {
          background: rgba(255, 255, 255, 0.1);
          color: var(--text-primary);
          border: 1px solid var(--border-color);
        }
        .action-btn.secondary:hover:not(:disabled) {
          background: rgba(255, 255, 255, 0.15);
        }
        .action-btn.secondary-confirm {
          background: rgba(255, 255, 255, 0.2);
          color: var(--text-primary);
          border: 1px solid var(--border-color);
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
        .email-revealed {
          display: flex;
          gap: 12px;
          padding: 16px;
          background: rgba(0, 212, 255, 0.1);
          border: 1px solid rgba(0, 212, 255, 0.3);
          border-radius: 8px;
          margin-top: 8px;
        }
        .email-icon {
          color: var(--accent-cyan);
          flex-shrink: 0;
        }
        .email-content {
          flex: 1;
        }
        .email-label {
          font-size: 0.9rem;
          font-weight: 600;
          color: var(--text-primary);
          margin-bottom: 4px;
        }
        .email-value {
          font-size: 0.95rem;
          color: var(--accent-cyan);
          margin-bottom: 8px;
          word-break: break-all;
        }
        .email-warning {
          font-size: 0.75rem;
          color: var(--text-muted);
        }
      `}</style>
    </CollapsiblePanel>
  );
}

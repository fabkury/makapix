/**
 * ViolationsPanel - Issue and manage user violations.
 * Supports 3-click confirmation for deletion and 2-click for issuing.
 */

import { useState, useEffect, useCallback } from 'react';
import CollapsiblePanel from './CollapsiblePanel';
import { authenticatedFetch } from '../../lib/api';

interface Violation {
  id: number;
  reason: string;
  moderator_id: number;
  moderator_handle: string;
  created_at: string;
}

interface ViolationsPanelProps {
  sqid: string;
}

const VIOLATIONS_PER_PAGE = 5;

export default function ViolationsPanel({ sqid }: ViolationsPanelProps) {
  const [violations, setViolations] = useState<Violation[]>([]);
  const [total, setTotal] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const [reason, setReason] = useState('');
  const [confirmIssue, setConfirmIssue] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<{ id: number; clicks: number } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchViolations = useCallback(async (cursorValue: string | null = null) => {
    setIsLoading(true);
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const params = new URLSearchParams({ limit: String(VIOLATIONS_PER_PAGE) });
      if (cursorValue) params.set('cursor', cursorValue);

      const response = await authenticatedFetch(
        `${apiBaseUrl}/api/admin/user/${sqid}/violations?${params}`
      );

      if (response.ok) {
        const data = await response.json();
        setViolations(data.items);
        setTotal(data.total);
        setNextCursor(data.next_cursor);
      }
    } catch (err) {
      console.error('Failed to fetch violations:', err);
    } finally {
      setIsLoading(false);
    }
  }, [sqid]);

  useEffect(() => {
    fetchViolations();
  }, [fetchViolations]);

  const handleIssueViolation = async () => {
    if (reason.length < 8) return;

    if (!confirmIssue) {
      setConfirmIssue(true);
      setTimeout(() => setConfirmIssue(false), 3000);
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const response = await authenticatedFetch(
        `${apiBaseUrl}/api/admin/user/${sqid}/violation`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason }),
        }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to issue violation');
      }

      // Refresh violations list
      await fetchViolations();
      setReason('');
      setConfirmIssue(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to issue violation');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteViolation = async (id: number) => {
    if (confirmDelete?.id === id) {
      const newClicks = confirmDelete.clicks + 1;
      if (newClicks >= 3) {
        // Execute delete
        try {
          const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
          const response = await authenticatedFetch(
            `${apiBaseUrl}/api/admin/violation/${id}`,
            { method: 'DELETE' }
          );

          if (response.ok || response.status === 204) {
            setViolations(violations.filter(v => v.id !== id));
            setTotal(total - 1);
          }
        } catch (err) {
          console.error('Failed to delete violation:', err);
        }
        setConfirmDelete(null);
      } else {
        setConfirmDelete({ id, clicks: newClicks });
        setTimeout(() => setConfirmDelete(null), 3000);
      }
    } else {
      setConfirmDelete({ id, clicks: 1 });
      setTimeout(() => setConfirmDelete(null), 3000);
    }
  };

  const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const getDeleteButtonTitle = (id: number) => {
    if (confirmDelete?.id === id) {
      const remaining = 3 - confirmDelete.clicks;
      return `Click ${remaining} more time${remaining === 1 ? '' : 's'} to confirm`;
    }
    return 'Revoke violation';
  };

  const isDisabled = reason.length < 8 || isSubmitting;

  return (
    <CollapsiblePanel title="Violations">
      <div className="violations-panel">
        <div className="total-count">Total violations: {total}</div>

        {isLoading ? (
          <div className="loading">Loading...</div>
        ) : violations.length > 0 ? (
          <div className="violations-list">
            {violations.map((violation) => (
              <div key={violation.id} className="violation-item">
                <div className="violation-content">
                  <div className="violation-meta">
                    {formatDate(violation.created_at)} \u2022 by {violation.moderator_handle}
                  </div>
                  <div className="violation-reason">{violation.reason}</div>
                </div>
                <button
                  onClick={() => handleDeleteViolation(violation.id)}
                  className={`delete-btn ${
                    confirmDelete?.id === violation.id
                      ? confirmDelete.clicks === 1
                        ? 'confirm-1'
                        : 'confirm-2'
                      : ''
                  }`}
                  title={getDeleteButtonTitle(violation.id)}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty">No violations</div>
        )}

        <div className="issue-section">
          <label>Issue new violation</label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Enter reason for violation (min 8 characters)..."
            rows={3}
          />
          <div className="char-count">{reason.length} / 8 characters</div>
        </div>

        {error && <div className="error">{error}</div>}

        <button
          onClick={handleIssueViolation}
          disabled={isDisabled}
          className={`submit-btn ${confirmIssue ? 'confirm' : ''}`}
        >
          {confirmIssue ? 'Click again to confirm' : 'Issue Violation'}
        </button>
      </div>

      <style jsx>{`
        .violations-panel {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .total-count {
          font-size: 0.9rem;
          color: var(--text-secondary);
        }
        .loading, .empty {
          font-size: 0.9rem;
          color: var(--text-muted);
          padding: 16px 0;
          text-align: center;
          border-bottom: 1px solid var(--border-color);
        }
        .violations-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          padding-bottom: 16px;
          border-bottom: 1px solid var(--border-color);
        }
        .violation-item {
          display: flex;
          gap: 12px;
          padding: 12px;
          background: var(--bg-tertiary);
          border: 1px solid var(--border-color);
          border-radius: 8px;
        }
        .violation-content {
          flex: 1;
          min-width: 0;
        }
        .violation-meta {
          font-size: 0.75rem;
          color: var(--text-muted);
          margin-bottom: 4px;
        }
        .violation-reason {
          font-size: 0.85rem;
          color: var(--text-primary);
        }
        .delete-btn {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          background: transparent;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          color: var(--accent-pink);
          transition: background 0.15s ease;
          flex-shrink: 0;
        }
        .delete-btn:hover {
          background: rgba(255, 82, 130, 0.2);
        }
        .delete-btn.confirm-1 {
          background: rgba(255, 82, 130, 0.2);
        }
        .delete-btn.confirm-2 {
          background: rgba(255, 82, 130, 0.4);
        }
        .issue-section {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
        .issue-section label {
          font-size: 0.9rem;
          color: var(--text-secondary);
        }
        textarea {
          width: 100%;
          padding: 12px;
          background: var(--bg-tertiary);
          border: 1px solid var(--border-color);
          border-radius: 6px;
          color: var(--text-primary);
          font-size: 0.9rem;
          resize: none;
        }
        textarea::placeholder {
          color: var(--text-muted);
        }
        textarea:focus {
          outline: none;
          border-color: var(--accent-pink);
          box-shadow: 0 0 0 2px rgba(255, 82, 130, 0.2);
        }
        .char-count {
          font-size: 0.75rem;
          color: var(--text-muted);
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
          background: var(--accent-pink);
          color: #000;
          transition: background 0.15s ease, opacity 0.15s ease;
        }
        .submit-btn:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }
        .submit-btn:hover:not(:disabled) {
          background: #ff6090;
        }
        .submit-btn.confirm {
          background: #d4004a;
        }
      `}</style>
    </CollapsiblePanel>
  );
}

import { useEffect, useState } from 'react';
import {
  ReportReason,
  getModerationConfig,
  getAccessToken,
  authenticatedFetch,
} from '../lib/api';

const API_BASE_URL =
  typeof window !== 'undefined'
    ? process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin
    : '';

const CONTACT_EMAIL = 'acme@makapix.club';

interface ReportDialogProps {
  targetType: 'post' | 'comment' | 'user';
  targetId: string;
  open: boolean;
  onClose: () => void;
}

/**
 * Report affordance for posts, comments, and user profiles (docs/ugc-safety/).
 * Reason list is fetched from /api/config -> moderation.report_reasons so new
 * codes appear without a client change. Works logged-out: sends the Bearer token
 * when signed in, plain fetch otherwise (the endpoint accepts anonymous reports
 * subject to stricter IP rate limits). Errors come back on the legacy root path
 * as { detail } + status codes (429/404/422).
 */
export default function ReportDialog({
  targetType,
  targetId,
  open,
  onClose,
}: ReportDialogProps) {
  const [reasons, setReasons] = useState<ReportReason[] | null>(null);
  const [selectedReason, setSelectedReason] = useState<string>('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  // Load reason labels from config once the dialog first opens.
  useEffect(() => {
    if (!open || reasons) return;
    let cancelled = false;
    getModerationConfig().then((cfg) => {
      if (cancelled) return;
      setReasons(cfg?.report_reasons ?? []);
    });
    return () => {
      cancelled = true;
    };
  }, [open, reasons]);

  // Reset the transient state each time the dialog is reopened.
  useEffect(() => {
    if (open) {
      setSelectedReason('');
      setNotes('');
      setError(null);
      setDone(false);
      setSubmitting(false);
    }
  }, [open]);

  if (!open) return null;

  const targetLabel =
    targetType === 'post'
      ? 'post'
      : targetType === 'comment'
        ? 'comment'
        : 'user';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedReason || submitting) return;

    setSubmitting(true);
    setError(null);

    const payload = {
      target_type: targetType,
      target_id: targetId,
      reason_code: selectedReason,
      notes: notes.trim() ? notes.trim() : undefined,
    };

    try {
      const url = `${API_BASE_URL}/api/report`;
      const init: RequestInit = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      };
      // authenticatedFetch attaches the Bearer token; use a plain fetch when
      // logged out so we don't trigger a spurious refresh attempt.
      const response = getAccessToken()
        ? await authenticatedFetch(url, init)
        : await fetch(url, init);

      if (response.status === 201 || response.ok) {
        setDone(true);
        return;
      }

      if (response.status === 429) {
        setError(
          `You're reporting too fast — try again later, or email ${CONTACT_EMAIL}.`,
        );
      } else if (response.status === 404) {
        setError('That content could not be found — it may have been removed.');
      } else {
        const data = await response.json().catch(() => ({}));
        setError(data.detail || 'Could not submit your report. Please try again.');
      }
    } catch (err) {
      console.error('Report submission failed:', err);
      setError('Could not submit your report. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{done ? 'Report received' : `Report this ${targetLabel}`}</h2>
          <button
            className="close-btn"
            onClick={onClose}
            disabled={submitting}
            aria-label="Close"
          >
            ×
          </button>
        </div>

        {done ? (
          <div className="success-body">
            <p className="success-msg">
              Thanks — our moderators will review this.
            </p>
            <div className="modal-actions">
              <button type="button" className="submit-btn" onClick={onClose}>
                Done
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <p className="intro">
              Tell us what&apos;s wrong with this {targetLabel}. Reports are
              confidential.
            </p>

            {reasons === null ? (
              <div className="reasons-loading">Loading…</div>
            ) : (
              <div className="reasons-list">
                {reasons.map((reason) => (
                  <label key={reason.code} className="reason-row">
                    <input
                      type="radio"
                      name="report-reason"
                      value={reason.code}
                      checked={selectedReason === reason.code}
                      onChange={() => setSelectedReason(reason.code)}
                      disabled={submitting}
                    />
                    <span>{reason.label}</span>
                  </label>
                ))}
              </div>
            )}

            <label className="notes-label" htmlFor="report-notes">
              Additional details (optional)
            </label>
            <textarea
              id="report-notes"
              className="notes-input"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={2000}
              rows={3}
              placeholder="Anything else our moderators should know?"
              disabled={submitting}
            />
            <div className="notes-count">{notes.length}/2000</div>

            {error && <div className="error-message">{error}</div>}

            <div className="modal-actions">
              <button
                type="button"
                className="cancel-btn"
                onClick={onClose}
                disabled={submitting}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="submit-btn"
                disabled={submitting || !selectedReason}
              >
                {submitting ? 'Submitting…' : 'Submit report'}
              </button>
            </div>
          </form>
        )}
      </div>

      <style jsx>{`
        .modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.6);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 21000;
          padding: 20px;
        }

        .modal-content {
          background: var(--bg-primary);
          border-radius: 12px;
          width: 100%;
          max-width: 460px;
          max-height: 90vh;
          overflow-y: auto;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }

        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px 24px;
          border-bottom: 1px solid var(--bg-tertiary);
        }

        .modal-header h2 {
          font-size: 1.35rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0;
        }

        .close-btn {
          background: none;
          border: none;
          font-size: 2rem;
          color: var(--text-secondary);
          cursor: pointer;
          padding: 0;
          width: 32px;
          height: 32px;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: color var(--transition-fast);
        }

        .close-btn:hover:not(:disabled) {
          color: var(--text-primary);
        }

        .close-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        form,
        .success-body {
          padding: 24px;
        }

        .intro {
          color: var(--text-secondary);
          font-size: 0.9rem;
          margin: 0 0 16px 0;
          line-height: 1.5;
        }

        .reasons-loading {
          color: var(--text-muted);
          font-size: 0.9rem;
          padding: 8px 0 16px;
        }

        .reasons-list {
          display: flex;
          flex-direction: column;
          margin-bottom: 20px;
        }

        .reason-row {
          display: flex;
          align-items: center;
          padding: 10px;
          border-radius: 6px;
          cursor: pointer;
          transition: background var(--transition-fast);
        }

        .reason-row:hover {
          background: var(--bg-secondary);
        }

        .reason-row > :global(* + *) {
          margin-left: 10px;
        }

        .reason-row input[type='radio'] {
          width: 16px;
          height: 16px;
          cursor: pointer;
          accent-color: var(--accent-cyan);
          flex-shrink: 0;
        }

        .reason-row span {
          color: var(--text-primary);
          font-size: 0.95rem;
        }

        .notes-label {
          display: block;
          font-size: 0.85rem;
          color: var(--text-secondary);
          margin-bottom: 6px;
        }

        .notes-input {
          display: block;
          width: 100%;
          font-size: 0.95rem;
          color: var(--text-primary);
          background: var(--bg-tertiary);
          border: 2px solid var(--bg-tertiary);
          border-radius: 8px;
          padding: 10px 12px;
          resize: vertical;
          min-height: 64px;
          font-family: inherit;
          line-height: 1.5;
          transition: border-color var(--transition-fast);
        }

        .notes-input:focus {
          outline: none;
          border-color: var(--accent-cyan);
        }

        .notes-count {
          text-align: right;
          font-size: 0.75rem;
          color: var(--text-muted);
          margin-top: 4px;
        }

        .error-message {
          background: rgba(239, 68, 68, 0.1);
          color: var(--accent-pink);
          padding: 12px;
          border-radius: 6px;
          font-size: 0.9rem;
          margin-top: 16px;
        }

        .success-msg {
          color: var(--text-primary);
          font-size: 1rem;
          line-height: 1.6;
          margin: 0 0 24px 0;
        }

        .modal-actions {
          display: flex;
          justify-content: flex-end;
          margin-top: 24px;
        }

        .modal-actions > :global(* + *) {
          margin-left: 12px;
        }

        .cancel-btn,
        .submit-btn {
          padding: 10px 20px;
          font-size: 1rem;
          border-radius: 6px;
          cursor: pointer;
          transition: all var(--transition-fast);
          border: none;
        }

        .cancel-btn {
          background: var(--bg-tertiary);
          color: var(--text-secondary);
        }

        .cancel-btn:hover:not(:disabled) {
          background: var(--bg-secondary);
          color: var(--text-primary);
        }

        .submit-btn {
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          font-weight: 600;
        }

        .submit-btn:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 4px 20px rgba(255, 110, 180, 0.4);
        }

        .cancel-btn:disabled,
        .submit-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }
      `}</style>
    </div>
  );
}

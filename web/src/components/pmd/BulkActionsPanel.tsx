import { useState } from 'react';

interface BulkActionsPanelProps {
  selectedCount: number;
  selectedIds: Set<number>;
  onHide: () => void;
  onUnhide: () => void;
  onDelete: () => void;
  onRequestDownload: (
    postIds: number[],
    includeComments: boolean,
    includeReactions: boolean,
    sendEmail: boolean
  ) => void;
  loading: boolean;
}

export function BulkActionsPanel({
  selectedCount,
  selectedIds,
  onHide,
  onUnhide,
  onDelete,
  onRequestDownload,
  loading,
}: BulkActionsPanelProps) {
  const [includeComments, setIncludeComments] = useState(false);
  const [includeReactions, setIncludeReactions] = useState(false);
  const [sendEmail, setSendEmail] = useState(false);

  const handleDeleteClick = () => {
    if (selectedCount > 32) {
      alert('You can only delete up to 32 posts at a time.');
      return;
    }
    if (window.confirm(`Delete ${selectedCount} post(s)? This action cannot be undone.`)) {
      onDelete();
    }
  };

  const handleDownloadClick = () => {
    if (selectedCount > 128) {
      alert('You can only download up to 128 posts at a time.');
      return;
    }
    onRequestDownload(
      Array.from(selectedIds),
      includeComments,
      includeReactions,
      sendEmail
    );
  };

  return (
    <div className="bulk-actions-panel">
      <div className="selection-info">
        <span className="count">{selectedCount}</span> post{selectedCount !== 1 ? 's' : ''} selected
      </div>

      <div className="actions-section">
        <h3>Batch Actions</h3>
        <div className="action-buttons">
          <button
            className="action-btn"
            onClick={onHide}
            disabled={selectedCount === 0 || loading}
            title="Hide selected posts from public view"
          >
            Hide
          </button>
          <button
            className="action-btn"
            onClick={onUnhide}
            disabled={selectedCount === 0 || loading}
            title="Make selected posts visible again"
          >
            Unhide
          </button>
          <button
            className="action-btn danger"
            onClick={handleDeleteClick}
            disabled={selectedCount === 0 || selectedCount > 32 || loading}
            title={selectedCount > 32 ? 'Max 32 posts per delete' : 'Delete selected posts'}
          >
            Delete {selectedCount > 32 && '(max 32)'}
          </button>
        </div>
      </div>

      <div className="download-section">
        <h3>Batch Download</h3>
        <div className="download-options">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={includeComments}
              onChange={(e) => setIncludeComments(e.target.checked)}
            />
            Include comments
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={includeReactions}
              onChange={(e) => setIncludeReactions(e.target.checked)}
            />
            Include reactions
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={sendEmail}
              onChange={(e) => setSendEmail(e.target.checked)}
            />
            Email me when ready
          </label>
        </div>
        <button
          className="action-btn primary"
          onClick={handleDownloadClick}
          disabled={selectedCount === 0 || selectedCount > 128 || loading}
          title={selectedCount > 128 ? 'Max 128 posts per download' : 'Request download ZIP'}
        >
          {loading ? (
            <>
              <span className="spinner"></span>
              Processing...
            </>
          ) : (
            <>Request Download {selectedCount > 128 && '(max 128)'}</>
          )}
        </button>
        <p className="limit-info">Daily limit: 8 requests per day</p>
      </div>

      <style jsx>{`
        .bulk-actions-panel {
          padding: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.1);
          background: var(--bg-secondary);
        }

        .selection-info {
          font-size: 0.9rem;
          color: var(--text-secondary);
          margin-bottom: 16px;
        }

        .selection-info .count {
          font-weight: 600;
          color: var(--accent-cyan);
          font-size: 1.1rem;
        }

        h3 {
          font-size: 0.85rem;
          color: var(--text-secondary);
          text-transform: uppercase;
          margin: 0 0 12px 0;
          font-weight: 600;
        }

        .actions-section {
          margin-bottom: 20px;
        }

        .action-buttons {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }

        .action-btn {
          background: var(--bg-tertiary);
          border: 1px solid rgba(255, 255, 255, 0.1);
          color: var(--text-primary);
          padding: 10px 16px;
          border-radius: 6px;
          cursor: pointer;
          font-size: 0.85rem;
          transition: all 0.15s ease;
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }

        .action-btn:hover:not(:disabled) {
          border-color: var(--accent-cyan);
          color: var(--accent-cyan);
        }

        .action-btn:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }

        .action-btn.danger {
          border-color: rgba(239, 68, 68, 0.3);
        }

        .action-btn.danger:hover:not(:disabled) {
          border-color: #ef4444;
          color: #ef4444;
          background: rgba(239, 68, 68, 0.1);
        }

        .action-btn.primary {
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          border: none;
          color: white;
          font-weight: 500;
        }

        .action-btn.primary:hover:not(:disabled) {
          opacity: 0.9;
          transform: translateY(-1px);
        }

        .download-section {
          padding-top: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .download-options {
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-bottom: 16px;
        }

        .checkbox-label {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 0.85rem;
          color: var(--text-secondary);
          cursor: pointer;
        }

        .checkbox-label:hover {
          color: var(--text-primary);
        }

        .checkbox-label input[type="checkbox"] {
          width: 16px;
          height: 16px;
          cursor: pointer;
          accent-color: var(--accent-cyan);
        }

        .limit-info {
          font-size: 0.75rem;
          color: var(--text-muted);
          margin: 8px 0 0;
        }

        .spinner {
          width: 14px;
          height: 14px;
          border: 2px solid rgba(255, 255, 255, 0.3);
          border-top-color: white;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        @media (max-width: 640px) {
          .action-buttons {
            flex-direction: column;
          }

          .action-btn {
            width: 100%;
            justify-content: center;
          }
        }
      `}</style>
    </div>
  );
}

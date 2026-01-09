import { useState } from 'react';

interface BulkActionsPanelProps {
  selectedCount: number;
  selectedIds: Set<number>;
  onHide: () => void;
  onUnhide: () => void;
  onDelete: () => void;
  onRequestDownload: (
    postIds: number[],
    includeCommentsAndReactions: boolean,
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
  const [includeCommentsAndReactions, setIncludeCommentsAndReactions] = useState(true);
  const [sendEmail, setSendEmail] = useState(false);

  const isDisabled = selectedCount === 0;
  const isDeleteDisabled = selectedCount === 0 || selectedCount > 32;
  const isDownloadDisabled = selectedCount === 0 || selectedCount > 128;

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
      includeCommentsAndReactions,
      sendEmail
    );
  };

  return (
    <div className="bulk-actions-panel">
      {/* Selection state */}
      <div className="selection-section">
        <h3>Selection</h3>
        <div className="selection-info">
          {selectedCount > 0 ? (
            <>
              <span className="count">{selectedCount}</span> artwork
              {selectedCount !== 1 ? 's' : ''} selected
            </>
          ) : (
            <>No artworks selected</>
          )}
        </div>
      </div>

      {/* Batch actions */}
      <div className="actions-section">
        <h3>Batch Actions</h3>
        <div className="action-buttons">
          <button
            className="action-btn"
            onClick={onHide}
            disabled={isDisabled || loading}
            title="Hide selected posts from public view"
          >
            🙈 Hide
          </button>
          <button
            className="action-btn"
            onClick={onUnhide}
            disabled={isDisabled || loading}
            title="Make selected posts visible again"
          >
            👁️ Unhide
          </button>
          <button
            className="action-btn danger"
            onClick={handleDeleteClick}
            disabled={isDeleteDisabled || loading}
            title={selectedCount > 32 ? 'Max 32 posts per delete' : 'Delete selected posts'}
          >
            🗑️ Delete {selectedCount > 32 && '(max 32)'}
          </button>
        </div>
      </div>

      {/* Batch download */}
      <div className="download-section">
        <h3>Batch Download</h3>
        <ul className="download-info">
          <li>Selected artworks will be put into one zip file for download.</li>
          <li>Maximum 128 artworks per batch and 8 batches per day.</li>
          <li>Most requests are ready within minutes.</li>
          <li>Once the link is available, it lasts for 7 days.</li>
        </ul>
        <div className="download-options">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={includeCommentsAndReactions}
              onChange={(e) => setIncludeCommentsAndReactions(e.target.checked)}
              disabled={isDisabled}
            />
            Include received comments and reactions
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={sendEmail}
              onChange={(e) => setSendEmail(e.target.checked)}
              disabled={isDisabled}
            />
            Send me an e-mail when the link is ready
          </label>
        </div>
        <button
          className="action-btn primary"
          onClick={handleDownloadClick}
          disabled={isDownloadDisabled || loading}
          title={selectedCount > 128 ? 'Max 128 posts per download' : 'Request download ZIP'}
        >
          {loading ? (
            <>
              <span className="spinner"></span>
              Processing...
            </>
          ) : (
            <>📥 Request Download {selectedCount > 128 && '(max 128)'}</>
          )}
        </button>
      </div>

      <style jsx>{`
        .bulk-actions-panel {
          padding: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.1);
          background: var(--bg-secondary);
        }

        .selection-section,
        .actions-section,
        .download-section {
          margin-bottom: 20px;
        }

        .download-section {
          margin-bottom: 0;
          padding-top: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        h3 {
          font-size: 0.75rem;
          color: var(--text-muted);
          text-transform: uppercase;
          margin: 0 0 12px 0;
          font-weight: 600;
          letter-spacing: 0.5px;
        }

        .selection-info {
          font-size: 0.9rem;
          color: var(--text-secondary);
        }

        .selection-info .count {
          font-weight: 700;
          font-size: 1.25rem;
          color: var(--accent-cyan);
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

        .download-info {
          margin: 0 0 16px 0;
          padding-left: 20px;
          font-size: 0.85rem;
          color: var(--text-secondary);
          line-height: 1.6;
        }

        .download-info li {
          margin-bottom: 4px;
        }

        .download-options {
          display: flex;
          flex-direction: column;
          gap: 10px;
          margin-bottom: 16px;
        }

        .checkbox-label {
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 0.85rem;
          color: var(--text-secondary);
          cursor: pointer;
        }

        .checkbox-label:hover {
          color: var(--text-primary);
        }

        .checkbox-label input[type='checkbox'] {
          width: 18px;
          height: 18px;
          cursor: pointer;
          accent-color: var(--accent-cyan);
        }

        .checkbox-label input[type='checkbox']:disabled {
          opacity: 0.4;
          cursor: not-allowed;
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
          to {
            transform: rotate(360deg);
          }
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

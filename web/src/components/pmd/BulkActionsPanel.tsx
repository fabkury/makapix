import { useState, useEffect, useRef, useMemo } from 'react';

interface License {
  id: number;
  identifier: string;
  title: string;
}

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
  onChangeLicense: (postIds: number[], licenseId: number | null) => Promise<void>;
  loading: boolean;
}

export function BulkActionsPanel({
  selectedCount,
  selectedIds,
  onHide,
  onUnhide,
  onDelete,
  onRequestDownload,
  onChangeLicense,
  loading,
}: BulkActionsPanelProps) {
  const [includeCommentsAndReactions, setIncludeCommentsAndReactions] = useState(true);
  const [sendEmail, setSendEmail] = useState(false);

  // License change state
  const [showLicensePanel, setShowLicensePanel] = useState(false);
  const [selectedLicenseId, setSelectedLicenseId] = useState<number | null>(null);
  const [licenseConfirmState, setLicenseConfirmState] = useState<'idle' | 'confirming'>('idle');
  const [licenses, setLicenses] = useState<License[]>([]);
  const [licensesLoading, setLicensesLoading] = useState(false);
  const confirmTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const isDisabled = selectedCount === 0;
  const isDeleteDisabled = selectedCount === 0 || selectedCount > 32;
  const isDownloadDisabled = selectedCount === 0 || selectedCount > 128;

  const API_BASE_URL = useMemo(
    () =>
      typeof window !== 'undefined'
        ? process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin
        : '',
    []
  );

  // Fetch licenses on mount
  useEffect(() => {
    const fetchLicenses = async () => {
      setLicensesLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/license`);
        if (response.ok) {
          const data = await response.json();
          // API returns {items: [...]}
          setLicenses(data.items || []);
        }
      } catch (err) {
        console.error('Failed to fetch licenses:', err);
      } finally {
        setLicensesLoading(false);
      }
    };
    fetchLicenses();
  }, [API_BASE_URL]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (confirmTimeoutRef.current) {
        clearTimeout(confirmTimeoutRef.current);
      }
    };
  }, []);

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

  const handleLicenseClick = async () => {
    if (licenseConfirmState === 'idle') {
      // First click - enter confirm state
      setLicenseConfirmState('confirming');
      // Reset after 3 seconds
      confirmTimeoutRef.current = setTimeout(() => {
        setLicenseConfirmState('idle');
      }, 3000);
    } else {
      // Second click - execute action
      if (confirmTimeoutRef.current) {
        clearTimeout(confirmTimeoutRef.current);
        confirmTimeoutRef.current = null;
      }
      setLicenseConfirmState('idle');
      await onChangeLicense(Array.from(selectedIds), selectedLicenseId);
    }
  };

  const selectedLicenseName = useMemo(() => {
    if (selectedLicenseId === null) return 'None';
    const license = licenses.find(l => l.id === selectedLicenseId);
    return license?.identifier || 'Unknown';
  }, [selectedLicenseId, licenses]);

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
            Hide
          </button>
          <button
            className="action-btn"
            onClick={onUnhide}
            disabled={isDisabled || loading}
            title="Make selected posts visible again"
          >
            Unhide
          </button>
          <button
            className="action-btn danger"
            onClick={handleDeleteClick}
            disabled={isDeleteDisabled || loading}
            title={selectedCount > 32 ? 'Max 32 posts per delete' : 'Delete selected posts'}
          >
            Delete {selectedCount > 32 && '(max 32)'}
          </button>
        </div>
      </div>

      {/* Change license section */}
      <div className="license-section">
        <button
          className="section-toggle"
          onClick={() => setShowLicensePanel(!showLicensePanel)}
          disabled={isDisabled}
        >
          <span className="toggle-icon">{showLicensePanel ? '▼' : '▶'}</span>
          <h3>Change License</h3>
          {!showLicensePanel && selectedLicenseId !== null && (
            <span className="selected-license-badge">{selectedLicenseName}</span>
          )}
        </button>

        {showLicensePanel && (
          <div className="license-panel">
            <div className="license-selector">
              <label htmlFor="license-select">Select license:</label>
              <select
                id="license-select"
                value={selectedLicenseId ?? ''}
                onChange={(e) => {
                  const value = e.target.value;
                  setSelectedLicenseId(value === '' ? null : parseInt(value, 10));
                  setLicenseConfirmState('idle');
                  if (confirmTimeoutRef.current) {
                    clearTimeout(confirmTimeoutRef.current);
                    confirmTimeoutRef.current = null;
                  }
                }}
                disabled={isDisabled || licensesLoading}
              >
                <option value="">None (remove license)</option>
                {licenses.map((license) => (
                  <option key={license.id} value={license.id}>
                    {license.identifier}
                  </option>
                ))}
              </select>
            </div>
            <button
              className={`action-btn warning ${licenseConfirmState === 'confirming' ? 'confirming' : ''}`}
              onClick={handleLicenseClick}
              disabled={isDisabled || loading}
              title="Set license for selected posts"
            >
              {loading ? (
                <>
                  <span className="spinner"></span>
                  Processing...
                </>
              ) : licenseConfirmState === 'confirming' ? (
                'Click again to confirm'
              ) : (
                'Set license'
              )}
            </button>
          </div>
        )}
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
            <>Request Download {selectedCount > 128 && '(max 128)'}</>
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
        .license-section,
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

        .action-btn.warning {
          border-color: rgba(245, 158, 11, 0.3);
        }

        .action-btn.warning:hover:not(:disabled) {
          border-color: #f59e0b;
          color: #f59e0b;
          background: rgba(245, 158, 11, 0.1);
        }

        .action-btn.warning.confirming {
          border-color: #f59e0b;
          color: #f59e0b;
          background: rgba(245, 158, 11, 0.15);
          animation: pulse-warning 1s ease-in-out infinite;
        }

        @keyframes pulse-warning {
          0%, 100% {
            box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4);
          }
          50% {
            box-shadow: 0 0 0 4px rgba(245, 158, 11, 0);
          }
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

        /* License section */
        .license-section {
          padding-top: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .section-toggle {
          display: flex;
          align-items: center;
          gap: 8px;
          background: none;
          border: none;
          cursor: pointer;
          padding: 0;
          width: 100%;
          text-align: left;
        }

        .section-toggle:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }

        .section-toggle h3 {
          margin: 0;
        }

        .toggle-icon {
          font-size: 0.65rem;
          color: var(--text-muted);
          transition: transform 0.15s ease;
        }

        .selected-license-badge {
          margin-left: auto;
          padding: 2px 8px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 4px;
          font-size: 0.75rem;
          color: var(--text-secondary);
        }

        .license-panel {
          margin-top: 12px;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .license-selector {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .license-selector label {
          font-size: 0.85rem;
          color: var(--text-secondary);
        }

        .license-selector select {
          padding: 8px 12px;
          border-radius: 6px;
          border: 1px solid rgba(255, 255, 255, 0.1);
          background: var(--bg-tertiary);
          color: var(--text-primary);
          font-size: 0.85rem;
          cursor: pointer;
        }

        .license-selector select:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }

        .license-selector select:focus {
          outline: none;
          border-color: var(--accent-cyan);
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

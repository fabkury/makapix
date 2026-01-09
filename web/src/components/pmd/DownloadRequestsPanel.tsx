import { BDRItem } from '../../hooks/usePMDSSE';

interface DownloadRequestsPanelProps {
  bdrs: BDRItem[];
}

const formatDate = (dateStr: string | null): string => {
  if (!dateStr) return '-';
  return new Date(dateStr).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
};

const getStatusConfig = (status: BDRItem['status']) => {
  switch (status) {
    case 'pending':
      return { icon: '⏳', label: 'Pending', className: 'status-pending' };
    case 'processing':
      return { icon: '🔄', label: 'Processing', className: 'status-processing' };
    case 'ready':
      return { icon: '✅', label: 'Ready', className: 'status-ready' };
    case 'failed':
      return { icon: '❌', label: 'Failed', className: 'status-failed' };
    case 'expired':
      return { icon: '🕐', label: 'Expired', className: 'status-expired' };
    default:
      return { icon: '?', label: status, className: '' };
  }
};

export function DownloadRequestsPanel({ bdrs }: DownloadRequestsPanelProps) {
  if (bdrs.length === 0) {
    return null;
  }

  return (
    <div className="download-requests-panel" id="bdr-section">
      <h2>Download Requests</h2>
      <div className="requests-list">
        {bdrs.map((bdr) => {
          const statusConfig = getStatusConfig(bdr.status);

          return (
            <div key={bdr.id} className={`request-card ${statusConfig.className}`}>
              <div className="request-header">
                <span className="status-badge">
                  {statusConfig.icon} {statusConfig.label}
                </span>
                <span className="artwork-count">{bdr.artwork_count} artworks</span>
              </div>

              <div className="request-details">
                <div className="detail-row">
                  <span className="detail-label">Requested:</span>
                  <span className="detail-value">{formatDate(bdr.created_at)}</span>
                </div>

                {bdr.completed_at && (
                  <div className="detail-row">
                    <span className="detail-label">Completed:</span>
                    <span className="detail-value">{formatDate(bdr.completed_at)}</span>
                  </div>
                )}

                {bdr.expires_at && bdr.status === 'ready' && (
                  <div className="detail-row expires">
                    <span className="detail-label">Expires:</span>
                    <span className="detail-value">{formatDate(bdr.expires_at)}</span>
                  </div>
                )}

                {bdr.error_message && (
                  <div className="error-message">
                    {bdr.error_message}
                  </div>
                )}
              </div>

              <div className="request-actions">
                {bdr.status === 'ready' && bdr.download_url && (
                  <a
                    href={bdr.download_url}
                    className="download-btn"
                    download
                  >
                    Download ZIP
                  </a>
                )}
                {bdr.status === 'pending' && (
                  <span className="action-note">Queued for processing...</span>
                )}
                {bdr.status === 'processing' && (
                  <span className="action-note">
                    <span className="processing-spinner"></span>
                    Building ZIP file...
                  </span>
                )}
                {bdr.status === 'expired' && (
                  <span className="action-note expired">Download link expired</span>
                )}
                {bdr.status === 'failed' && (
                  <span className="action-note failed">Request a new download</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <style jsx>{`
        .download-requests-panel {
          margin-top: 24px;
          padding: 24px;
          background: var(--bg-secondary);
          border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.1);
        }

        h2 {
          font-size: 1.25rem;
          color: var(--text-primary);
          margin: 0 0 16px 0;
        }

        .requests-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .request-card {
          background: var(--bg-tertiary);
          border-radius: 8px;
          padding: 16px;
          border: 1px solid rgba(255, 255, 255, 0.05);
        }

        .request-card.status-pending {
          border-left: 3px solid #fbbf24;
        }

        .request-card.status-processing {
          border-left: 3px solid #3b82f6;
        }

        .request-card.status-ready {
          border-left: 3px solid #22c55e;
        }

        .request-card.status-failed {
          border-left: 3px solid #ef4444;
        }

        .request-card.status-expired {
          border-left: 3px solid #6b7280;
          opacity: 0.7;
        }

        .request-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 12px;
        }

        .status-badge {
          font-size: 0.85rem;
          font-weight: 500;
        }

        .status-pending .status-badge { color: #fbbf24; }
        .status-processing .status-badge { color: #3b82f6; }
        .status-ready .status-badge { color: #22c55e; }
        .status-failed .status-badge { color: #ef4444; }
        .status-expired .status-badge { color: #6b7280; }

        .artwork-count {
          font-size: 0.85rem;
          color: var(--text-secondary);
        }

        .request-details {
          margin-bottom: 12px;
        }

        .detail-row {
          display: flex;
          gap: 8px;
          font-size: 0.8rem;
          margin-bottom: 4px;
        }

        .detail-label {
          color: var(--text-muted);
        }

        .detail-value {
          color: var(--text-secondary);
        }

        .detail-row.expires .detail-value {
          color: #fbbf24;
        }

        .error-message {
          background: rgba(239, 68, 68, 0.1);
          border: 1px solid rgba(239, 68, 68, 0.3);
          border-radius: 4px;
          padding: 8px 12px;
          font-size: 0.8rem;
          color: #ef4444;
          margin-top: 8px;
        }

        .request-actions {
          padding-top: 12px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .download-btn {
          display: inline-block;
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          padding: 10px 20px;
          border-radius: 6px;
          text-decoration: none;
          font-size: 0.85rem;
          font-weight: 500;
          transition: all 0.15s ease;
        }

        .download-btn:hover {
          opacity: 0.9;
          transform: translateY(-1px);
        }

        .action-note {
          font-size: 0.8rem;
          color: var(--text-muted);
          display: inline-flex;
          align-items: center;
          gap: 8px;
        }

        .action-note.expired {
          color: #6b7280;
        }

        .action-note.failed {
          color: #ef4444;
        }

        .processing-spinner {
          width: 12px;
          height: 12px;
          border: 2px solid var(--bg-secondary);
          border-top-color: #3b82f6;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        @media (max-width: 640px) {
          .request-header {
            flex-direction: column;
            align-items: flex-start;
            gap: 4px;
          }
        }
      `}</style>
    </div>
  );
}

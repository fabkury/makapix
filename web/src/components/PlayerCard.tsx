import { useState } from 'react';
import { Player, sendPlayerCommand, deletePlayer, renewPlayerCert, downloadPlayerCerts } from '../lib/api';

interface PlayerCardProps {
  player: Player;
  sqid: string;
  onDelete: () => void;
  onRefresh: () => void;
}

export default function PlayerCard({ player, sqid, onDelete, onRefresh }: PlayerCardProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCommand = async (commandType: 'swap_next' | 'swap_back') => {
    setIsLoading(true);
    setError(null);
    try {
      await sendPlayerCommand(sqid, player.id, { command_type: commandType });
      onRefresh();
    } catch (err: any) {
      setError(err.message || 'Failed to send command');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Are you sure you want to delete "${player.name || 'Unnamed Player'}"?`)) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      await deletePlayer(sqid, player.id);
      onDelete();
    } catch (err: any) {
      setError(err.message || 'Failed to delete player');
      setIsLoading(false);
    }
  };

  const handleRenewCert = async () => {
    setIsLoading(true);
    setError(null);
    try {
      await renewPlayerCert(sqid, player.id);
      onRefresh();
    } catch (err: any) {
      setError(err.message || 'Failed to renew certificate');
      setIsLoading(false);
    }
  };

  const handleDownloadCerts = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const certBundle = await downloadPlayerCerts(sqid, player.id);
      
      // Create downloadable files
      const files = [
        { name: 'ca.crt', content: certBundle.ca_pem },
        { name: 'client.crt', content: certBundle.cert_pem },
        { name: 'client.key', content: certBundle.key_pem },
        { name: 'certs.json', content: JSON.stringify(certBundle, null, 2) },
      ];
      
      // Download each file
      files.forEach((file) => {
        const blob = new Blob([file.content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${player.name || 'player'}-${file.name}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      });
    } catch (err: any) {
      setError(err.message || 'Failed to download certificates');
    } finally {
      setIsLoading(false);
    }
  };

  const isOnline = player.connection_status === 'online';
  const certExpiresAt = player.cert_expires_at ? new Date(player.cert_expires_at) : null;
  const certNeedsRenewal = certExpiresAt && certExpiresAt.getTime() - Date.now() < 30 * 24 * 60 * 60 * 1000;

  return (
    <div className="player-card">
      <div className="player-header">
        <div className="player-info">
          <h3 className="player-name">{player.name || 'Unnamed Player'}</h3>
          <div className="player-meta">
            <span className={`status-indicator ${isOnline ? 'online' : 'offline'}`}>
              {isOnline ? '●' : '○'} {player.connection_status}
            </span>
            {player.device_model && (
              <span className="device-model">{player.device_model}</span>
            )}
            {player.firmware_version && (
              <span className="firmware-version">v{player.firmware_version}</span>
            )}
          </div>
        </div>
        <div className="player-actions">
          <button
            className="control-btn prev-btn"
            onClick={() => handleCommand('swap_back')}
            disabled={isLoading || !isOnline}
            title="Previous artwork"
          >
            ◀ Prev
          </button>
          <button
            className="control-btn next-btn"
            onClick={() => handleCommand('swap_next')}
            disabled={isLoading || !isOnline}
            title="Next artwork"
          >
            Next ▶
          </button>
          <button
            className="download-btn"
            onClick={handleDownloadCerts}
            disabled={isLoading || !player.cert_expires_at}
            title="Download certificates"
          >
            📜 Certs
          </button>
          <button
            className="delete-btn"
            onClick={handleDelete}
            disabled={isLoading}
            title="Delete player"
          >
            🗑️
          </button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      {certNeedsRenewal && (
        <div className="cert-warning">
          <span>Certificate expires soon</span>
          <button className="renew-btn" onClick={handleRenewCert} disabled={isLoading}>
            Renew Certificate
          </button>
        </div>
      )}

      {player.last_seen_at && (
        <div className="last-seen">
          Last seen: {new Date(player.last_seen_at).toLocaleString()}
        </div>
      )}

      <style jsx>{`
        .player-card {
          background: var(--bg-secondary);
          border-radius: 12px;
          padding: 20px;
          margin-bottom: 16px;
          border: 1px solid var(--bg-tertiary);
        }

        .player-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 12px;
        }

        .player-info {
          flex: 1;
        }

        .player-name {
          font-size: 1.2rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0 0 8px 0;
        }

        .player-meta {
          display: flex;
          gap: 12px;
          align-items: center;
          font-size: 0.85rem;
          color: var(--text-secondary);
        }

        .status-indicator {
          display: inline-flex;
          align-items: center;
          gap: 4px;
        }

        .status-indicator.online {
          color: #10b981;
        }

        .status-indicator.offline {
          color: var(--text-muted);
        }

        .device-model,
        .firmware-version {
          color: var(--text-muted);
        }

        .player-actions {
          display: flex;
          gap: 8px;
        }

        .control-btn {
          background: var(--bg-tertiary);
          border: none;
          border-radius: 6px;
          padding: 8px 12px;
          font-size: 0.9rem;
          cursor: pointer;
          transition: all var(--transition-fast);
          color: var(--text-primary);
        }

        .control-btn:hover:not(:disabled) {
          background: var(--accent-cyan);
          transform: translateY(-1px);
        }

        .control-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .delete-btn {
          background: var(--bg-tertiary);
          border: none;
          border-radius: 6px;
          padding: 8px 12px;
          font-size: 1rem;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .delete-btn:hover:not(:disabled) {
          background: var(--accent-pink);
          transform: scale(1.05);
        }

        .download-btn {
          background: var(--bg-tertiary);
          border: none;
          border-radius: 6px;
          padding: 8px 12px;
          font-size: 0.85rem;
          cursor: pointer;
          transition: all var(--transition-fast);
          color: var(--text-primary);
        }

        .download-btn:hover:not(:disabled) {
          background: var(--accent-cyan);
          transform: translateY(-1px);
        }

        .download-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .error-message {
          color: var(--accent-pink);
          font-size: 0.85rem;
          margin-top: 8px;
        }

        .cert-warning {
          display: flex;
          justify-content: space-between;
          align-items: center;
          background: #fef3c7;
          color: #92400e;
          padding: 10px 12px;
          border-radius: 6px;
          margin-top: 12px;
          font-size: 0.85rem;
        }

        .renew-btn {
          background: #f59e0b;
          color: white;
          border: none;
          border-radius: 4px;
          padding: 6px 12px;
          font-size: 0.85rem;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .renew-btn:hover:not(:disabled) {
          background: #d97706;
        }

        .renew-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .last-seen {
          font-size: 0.8rem;
          color: var(--text-muted);
          margin-top: 8px;
        }

        @media (max-width: 600px) {
          .player-header {
            flex-direction: column;
            gap: 12px;
          }

          .player-actions {
            width: 100%;
            justify-content: flex-start;
          }
        }
      `}</style>
    </div>
  );
}


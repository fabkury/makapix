import { OnlinePlayer } from './types';

interface OnlinePlayersGridProps {
  players: OnlinePlayer[];
}

export default function OnlinePlayersGrid({ players }: OnlinePlayersGridProps) {
  if (players.length === 0) {
    return (
      <p className="no-players">
        No players currently online or recently active.
        <style jsx>{`
          .no-players {
            color: var(--text-muted, #6a6a80);
            font-style: italic;
            margin: 0;
          }
        `}</style>
      </p>
    );
  }

  return (
    <div className="online-players-list">
      {players.map((player) => (
        <div key={player.id} className="online-player-card">
          <div className="player-header">
            <span
              className={`player-status-dot ${player.transport === 'https' ? 'https' : ''}`}
            >
              ●
            </span>
            <span className="player-name">{player.name || 'Unnamed Player'}</span>
            <span
              className="player-transport"
              title={
                player.transport === 'https'
                  ? 'No live connection: made an HTTPS request in the last 5 minutes'
                  : 'Connected to the MQTT broker'
              }
            >
              {player.transport === 'https' ? 'HTTPS' : 'MQTT'}
            </span>
          </div>
          <div className="player-details">
            {player.device_model && (
              <div className="player-detail">
                <span className="detail-label">Model:</span>
                <span className="detail-value">{player.device_model}</span>
              </div>
            )}
            {player.firmware_version && (
              <div className="player-detail">
                <span className="detail-label">Firmware:</span>
                <span className="detail-value">{player.firmware_version}</span>
              </div>
            )}
            {player.owner_handle && (
              <div className="player-detail">
                <span className="detail-label">Owner:</span>
                <span className="detail-value">{player.owner_handle}</span>
              </div>
            )}
            {player.last_seen_at && (
              <div className="player-detail">
                <span className="detail-label">
                  {player.transport === 'https' ? 'Last request:' : 'Last seen:'}
                </span>
                <span className="detail-value">
                  {new Date(player.last_seen_at).toLocaleTimeString()}
                </span>
              </div>
            )}
          </div>
        </div>
      ))}
      <style jsx>{`
        .online-players-list {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 12px;
        }

        .online-player-card {
          background: var(--bg-tertiary, #1a1a24);
          border: 1px solid rgba(255, 255, 255, 0.06);
          border-radius: 8px;
          padding: 16px;
          transition: border-color 0.2s ease;
        }

        .online-player-card:hover {
          border-color: rgba(0, 212, 255, 0.3);
        }

        .player-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 12px;
          padding-bottom: 12px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .player-status-dot {
          color: #00ff00;
          font-size: 1.2rem;
          animation: pulse 2s ease-in-out infinite;
        }

        /* HTTPS players have no live connection: steady dot, different hue. */
        .player-status-dot.https {
          color: #00d4ff;
          animation: none;
        }

        .player-transport {
          margin-left: auto;
          font-size: 0.7rem;
          font-family: monospace;
          letter-spacing: 0.04em;
          color: var(--text-muted, #6a6a80);
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 4px;
          padding: 1px 6px;
        }

        @keyframes pulse {
          0%,
          100% {
            opacity: 1;
          }
          50% {
            opacity: 0.5;
          }
        }

        .player-name {
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-weight: 600;
          color: var(--text-primary, #e8e8f0);
          font-size: 1rem;
        }

        .player-details {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .player-detail {
          display: flex;
          justify-content: space-between;
          font-size: 0.85rem;
        }

        .detail-label {
          color: var(--text-muted, #6a6a80);
        }

        .detail-value {
          color: var(--text-secondary, #a0a0b8);
          font-family: monospace;
        }
      `}</style>
    </div>
  );
}

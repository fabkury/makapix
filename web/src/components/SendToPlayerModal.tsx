import { useState } from 'react';
import { Player, sendPlayerCommand, sendCommandToAllPlayers } from '../lib/api';

interface SendToPlayerModalProps {
  isOpen: boolean;
  onClose: () => void;
  players: Player[];
  userId: string;
  postId: number;
}

export default function SendToPlayerModal({
  isOpen,
  onClose,
  players,
  userId,
  postId,
}: SendToPlayerModalProps) {
  const [selectedPlayerIds, setSelectedPlayerIds] = useState<Set<string>>(new Set());
  const [sendToAll, setSendToAll] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const onlinePlayers = players.filter((p) => p.connection_status === 'online');
  const hasOnlinePlayers = onlinePlayers.length > 0;

  const handleTogglePlayer = (playerId: string) => {
    const newSet = new Set(selectedPlayerIds);
    if (newSet.has(playerId)) {
      newSet.delete(playerId);
    } else {
      newSet.add(playerId);
    }
    setSelectedPlayerIds(newSet);
    setSendToAll(false);
  };

  const handleToggleAll = () => {
    setSendToAll(!sendToAll);
    setSelectedPlayerIds(new Set());
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      if (sendToAll) {
        await sendCommandToAllPlayers(userId, {
          command_type: 'show_artwork',
          post_id: postId,
        });
      } else if (selectedPlayerIds.size > 0) {
        // Send to selected players
        const promises = Array.from(selectedPlayerIds).map((playerId) =>
          sendPlayerCommand(userId, playerId, {
            command_type: 'show_artwork',
            post_id: postId,
          })
        );
        await Promise.all(promises);
      } else {
        setError('Please select at least one player');
        setIsLoading(false);
        return;
      }

      onClose();
      setSelectedPlayerIds(new Set());
      setSendToAll(false);
    } catch (err: any) {
      setError(err.message || 'Failed to send artwork');
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    if (!isLoading) {
      setSelectedPlayerIds(new Set());
      setSendToAll(false);
      setError(null);
      onClose();
    }
  };

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Send to Player</h2>
          <button className="close-btn" onClick={handleClose} disabled={isLoading}>
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          {!hasOnlinePlayers ? (
            <div className="no-players">
              <p>No online players available.</p>
              <p className="hint">Make sure your players are connected and online.</p>
            </div>
          ) : (
            <>
              <div className="option-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={sendToAll}
                    onChange={handleToggleAll}
                    disabled={isLoading}
                  />
                  <span>Send to all players ({onlinePlayers.length})</span>
                </label>
              </div>

              {!sendToAll && (
                <div className="players-list">
                  <h3>Select players:</h3>
                  {onlinePlayers.map((player) => (
                    <label key={player.id} className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={selectedPlayerIds.has(player.id)}
                        onChange={() => handleTogglePlayer(player.id)}
                        disabled={isLoading}
                      />
                      <span>
                        {player.name || 'Unnamed Player'}
                        {player.device_model && ` (${player.device_model})`}
                      </span>
                    </label>
                  ))}
                </div>
              )}
            </>
          )}

          {error && <div className="error-message">{error}</div>}

          <div className="modal-actions">
            <button type="button" className="cancel-btn" onClick={handleClose} disabled={isLoading}>
              Cancel
            </button>
            <button
              type="submit"
              className="submit-btn"
              disabled={isLoading || !hasOnlinePlayers}
            >
              {isLoading ? 'Sending...' : 'Send'}
            </button>
          </div>
        </form>
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
          z-index: 1000;
          padding: 20px;
        }

        .modal-content {
          background: var(--bg-primary);
          border-radius: 12px;
          width: 100%;
          max-width: 500px;
          max-height: 90vh;
          overflow-y: auto;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }

        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 24px;
          border-bottom: 1px solid var(--bg-tertiary);
        }

        .modal-header h2 {
          font-size: 1.5rem;
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

        form {
          padding: 24px;
        }

        .no-players {
          text-align: center;
          padding: 40px 20px;
          color: var(--text-secondary);
        }

        .no-players .hint {
          font-size: 0.9rem;
          color: var(--text-muted);
          margin-top: 8px;
        }

        .option-group {
          margin-bottom: 24px;
        }

        .players-list {
          margin-bottom: 24px;
        }

        .players-list h3 {
          font-size: 1rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0 0 12px 0;
        }

        .checkbox-label {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px;
          border-radius: 6px;
          cursor: pointer;
          transition: background var(--transition-fast);
          margin-bottom: 8px;
        }

        .checkbox-label:hover {
          background: var(--bg-secondary);
        }

        .checkbox-label input[type='checkbox'] {
          width: 18px;
          height: 18px;
          cursor: pointer;
        }

        .checkbox-label span {
          color: var(--text-primary);
          font-size: 0.95rem;
        }

        .error-message {
          background: rgba(239, 68, 68, 0.1);
          color: var(--accent-pink);
          padding: 12px;
          border-radius: 6px;
          font-size: 0.9rem;
          margin-bottom: 20px;
        }

        .modal-actions {
          display: flex;
          gap: 12px;
          justify-content: flex-end;
          margin-top: 24px;
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


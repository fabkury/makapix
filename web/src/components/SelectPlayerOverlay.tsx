import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { Player } from '../lib/api';

interface SelectPlayerOverlayProps {
  isOpen: boolean;
  onClose: () => void;
  onlinePlayers: Player[];
  onSelectPlayer: (playerId: string) => void;
}

/**
 * SelectPlayerOverlay - A simple overlay for selecting which player to send commands to.
 * Shows when user has multiple online players.
 * Rendered via portal to appear above SelectedPostOverlay and other portal-based overlays.
 */
export default function SelectPlayerOverlay({
  isOpen,
  onClose,
  onlinePlayers,
  onSelectPlayer,
}: SelectPlayerOverlayProps) {
  const [portalEl, setPortalEl] = useState<HTMLElement | null>(null);

  // Create portal root
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const el = document.createElement('div');
    el.setAttribute('data-select-player-overlay', 'true');
    document.body.appendChild(el);
    setPortalEl(el);

    return () => {
      el.remove();
    };
  }, []);

  if (!isOpen || !portalEl) return null;

  return createPortal(
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 50000,
        padding: '20px',
      }}
      onClick={onClose}
    >
      <div className="overlay-content" onClick={(e) => e.stopPropagation()}>
        <div className="overlay-header">
          <h3>Select Player</h3>
          <button className="close-btn" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="player-buttons">
          {onlinePlayers.map((player) => (
            <button
              key={player.id}
              className="player-btn"
              onClick={() => {
                onSelectPlayer(player.id);
                onClose();
              }}
            >
              <span className="player-name">
                {player.name || 'Unnamed Player'}
              </span>
              {player.device_model && (
                <span className="player-model">{player.device_model}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      <style jsx>{`
        .overlay-content {
          background: var(--bg-primary, #1a1a1a);
          border: 2px solid var(--text-primary, #ffffff);
          border-radius: 8px;
          min-width: 280px;
          max-width: 400px;
          box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
        }

        .overlay-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px 20px;
          border-bottom: 1px solid var(--text-secondary, #666666);
        }

        .overlay-header h3 {
          font-size: 1.1rem;
          font-weight: 600;
          color: var(--text-primary, #ffffff);
          margin: 0;
        }

        .close-btn {
          background: none;
          border: none;
          font-size: 1.8rem;
          color: var(--text-secondary, #666666);
          cursor: pointer;
          padding: 0;
          width: 28px;
          height: 28px;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: color 0.2s ease;
          line-height: 1;
        }

        .close-btn:hover {
          color: var(--text-primary, #ffffff);
        }

        .player-buttons {
          padding: 12px;
          display: flex;
          flex-direction: column;
        }

        .player-buttons > :global(* + *) {
          margin-top: 8px;
        }

        .player-btn {
          background: var(--bg-secondary, #2a2a2a);
          border: 2px solid var(--text-secondary, #666666);
          border-radius: 6px;
          padding: 14px 16px;
          cursor: pointer;
          transition: all 0.2s ease;
          display: flex;
          flex-direction: column;
          align-items: flex-start;
          text-align: left;
        }

        .player-btn > :global(* + *) {
          margin-top: 4px;
        }

        .player-btn:hover {
          background: var(--bg-tertiary, #3a3a3a);
          border-color: var(--text-primary, #ffffff);
          transform: translateY(-1px);
        }

        .player-btn:active {
          transform: translateY(0);
        }

        .player-name {
          color: var(--text-primary, #ffffff);
          font-size: 1rem;
          font-weight: 600;
        }

        .player-model {
          color: var(--text-secondary, #666666);
          font-size: 0.85rem;
        }
      `}</style>
    </div>,
    portalEl
  );
}

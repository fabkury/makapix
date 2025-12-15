'use client';

import { useState } from 'react';
import { usePlayerBarOptional } from '../contexts/PlayerBarContext';
import { sendPlayerCommand } from '../lib/api';
import SendToPlayerModal from './SendToPlayerModal';

export const PLAYER_BAR_HEIGHT = 64;

// z-index must be above SelectedArtworkOverlay which uses 9999
const PLAYER_BAR_Z_INDEX = 10001;

/**
 * PlayerBar - A fixed bar at the bottom of the viewport for sending artwork to players.
 * 
 * Visibility rules:
 * - Shows when user has at least one online player
 * - Hides when no players or no online players
 * - Always appears ABOVE the artwork selection overlay
 */
export default function PlayerBar() {
  const context = usePlayerBarOptional();
  const [showModal, setShowModal] = useState(false);
  const [isSending, setIsSending] = useState(false);

  // Visibility: show only when there's at least one online player
  if (!context || context.isLoading || !context.hasOnlinePlayer) {
    return null;
  }

  const { onlinePlayers, selectedArtwork, players } = context;
  const userSqid = localStorage.getItem('public_sqid');

  const handleSendClick = async () => {
    if (!selectedArtwork || !userSqid) {
      // No artwork selected - stub for future functionality
      return;
    }

    // If exactly one online player, send directly without modal
    if (onlinePlayers.length === 1) {
      setIsSending(true);
      try {
        await sendPlayerCommand(userSqid, onlinePlayers[0].id, {
          command_type: 'show_artwork',
          post_id: selectedArtwork.id,
        });
      } catch (err) {
        console.error('Failed to send artwork to player:', err);
      } finally {
        setIsSending(false);
      }
    } else {
      // Multiple online players - show modal to select
      setShowModal(true);
    }
  };

  return (
    <>
      <div className="player-bar">
        <div className="player-bar-content">
          <button
            className="send-to-player-btn"
            onClick={handleSendClick}
            disabled={isSending}
            title={selectedArtwork ? `Send "${selectedArtwork.title}" to player` : 'Select an artwork first'}
          >
            <img
              src="/button/send-to-player-128p.webp"
              alt="Send to Player"
              className="send-icon"
            />
          </button>
        </div>
      </div>

      {showModal && selectedArtwork && userSqid && (
        <SendToPlayerModal
          isOpen={showModal}
          onClose={() => setShowModal(false)}
          players={players}
          sqid={userSqid}
          postId={selectedArtwork.id}
        />
      )}

      <style jsx>{`
        .player-bar {
          position: fixed;
          bottom: 0;
          left: 0;
          right: 0;
          height: ${PLAYER_BAR_HEIGHT}px;
          background: #000000;
          border-top: 2px solid #ffffff;
          z-index: ${PLAYER_BAR_Z_INDEX};
          display: flex;
          align-items: center;
          justify-content: flex-end;
        }

        .player-bar-content {
          display: flex;
          align-items: center;
          padding: 0 16px;
        }

        .send-to-player-btn {
          background: transparent;
          border: none;
          cursor: pointer;
          padding: 8px;
          border-radius: 8px;
          transition: transform 0.15s ease;
          display: flex;
          align-items: center;
          justify-content: center;
          outline: none;
          -webkit-tap-highlight-color: transparent;
          user-select: none;
        }

        .send-to-player-btn:hover:not(:disabled) {
          transform: scale(1.08);
        }

        .send-to-player-btn:active:not(:disabled) {
          transform: scale(0.95);
        }

        .send-to-player-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .send-icon {
          width: 48px;
          height: 48px;
          image-rendering: auto;
          pointer-events: none;
        }
      `}</style>
    </>
  );
}

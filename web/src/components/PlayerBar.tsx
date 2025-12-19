'use client';

import { useState } from 'react';
import { usePlayerBarOptional } from '../contexts/PlayerBarContext';
import { sendPlayerCommand, PlayerCommandRequest } from '../lib/api';
import SelectPlayerOverlay from './SelectPlayerOverlay';

export const PLAYER_BAR_HEIGHT = 64;

// z-index must be above SelectedArtworkOverlay (overlay is intentionally very high).
// PlayerBar must remain visible and NOT be darkened by the selection overlay backdrop.
const PLAYER_BAR_Z_INDEX = 40000;

/**
 * PlayerBar - A fixed bar at the bottom of the viewport for sending artwork/channels to players.
 * 
 * Visibility rules:
 * - Shows when user has at least one online player
 * - Hides when no players or no online players
 * - Always appears ABOVE the artwork selection overlay
 * 
 * Behaviors:
 * - When on a channel with no artwork selected: shows channel name, sends play_channel command
 * - When artwork is selected: shows artwork title, sends show_artwork command
 * - Single online player: sends immediately
 * - Multiple online players: shows player selection overlay
 */
export default function PlayerBar() {
  const context = usePlayerBarOptional();
  const [showPlayerSelector, setShowPlayerSelector] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [showPulse, setShowPulse] = useState(false);

  // Visibility: show only when there's at least one online player
  if (!context || context.isLoading || !context.hasOnlinePlayer) {
    return null;
  }

  const { onlinePlayers, selectedArtwork, currentChannel } = context;
  const userSqid = localStorage.getItem('public_sqid');

  // Determine what to display and what command to send
  const displayText = selectedArtwork 
    ? selectedArtwork.title 
    : currentChannel?.displayName || '';
  
  const hasContent = selectedArtwork || currentChannel;

  const triggerPulse = () => {
    setShowPulse(true);
    setTimeout(() => setShowPulse(false), 600);
  };

  const sendCommand = async (playerId: string) => {
    if (!userSqid || !hasContent) return;

    setIsSending(true);
    try {
      if (selectedArtwork) {
        // Send show_artwork command
        await sendPlayerCommand(userSqid, playerId, {
          command_type: 'show_artwork',
          post_id: selectedArtwork.id,
        });
      } else if (currentChannel) {
        // Send play_channel command
        const channelCommand: PlayerCommandRequest = {
          command_type: 'play_channel',
          channel_name: currentChannel.channelName,
          hashtag: currentChannel.hashtag,
          user_sqid: currentChannel.userSqid,
        };
        
        await sendPlayerCommand(userSqid, playerId, channelCommand);
      }
      
      triggerPulse();
    } catch (err) {
      console.error('Failed to send command to player:', err);
    } finally {
      setIsSending(false);
    }
  };

  const handleSendClick = async () => {
    if (!hasContent || !userSqid) {
      return;
    }

    // If exactly one online player, send directly
    if (onlinePlayers.length === 1) {
      await sendCommand(onlinePlayers[0].id);
    } else {
      // Multiple online players - show selector
      setShowPlayerSelector(true);
    }
  };

  const handlePlayerSelected = async (playerId: string) => {
    await sendCommand(playerId);
  };

  const buttonTitle = selectedArtwork
    ? `Send "${selectedArtwork.title}" to player`
    : currentChannel
    ? `Play "${currentChannel.displayName}" on player`
    : 'Nothing to send';

  return (
    <>
      <div className="player-bar">
        <div className="player-bar-content">
          {displayText && (
            <div className="display-text">
              {displayText}
            </div>
          )}
          <button
            className={`send-to-player-btn ${showPulse ? 'pulse' : ''}`}
            onClick={handleSendClick}
            disabled={isSending || !hasContent}
            title={buttonTitle}
          >
            <img
              src="/button/send-to-player-128p.webp"
              alt="Send to Player"
              className="send-icon"
            />
          </button>
        </div>
      </div>

      <SelectPlayerOverlay
        isOpen={showPlayerSelector}
        onClose={() => setShowPlayerSelector(false)}
        onlinePlayers={onlinePlayers}
        onSelectPlayer={handlePlayerSelected}
      />

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
          gap: 16px;
          padding: 0 16px;
        }

        .display-text {
          color: #ffffff;
          font-size: 0.95rem;
          font-weight: 500;
          max-width: 300px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
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

        .send-to-player-btn.pulse {
          animation: pulse 0.6s cubic-bezier(0.34, 1.56, 0.64, 1);
        }

        @keyframes pulse {
          0% {
            transform: scale(1);
          }
          50% {
            transform: scale(1.3);
          }
          100% {
            transform: scale(1);
          }
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

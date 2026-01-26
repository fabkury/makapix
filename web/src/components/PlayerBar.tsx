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
  const [showSwapNextPulse, setShowSwapNextPulse] = useState(false);
  const [showSwapBackPulse, setShowSwapBackPulse] = useState(false);
  const [pendingCommand, setPendingCommand] = useState<'send' | 'swap_next' | 'swap_back' | null>(null);

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

  const triggerSwapNextPulse = () => {
    setShowSwapNextPulse(true);
    setTimeout(() => setShowSwapNextPulse(false), 600);
  };

  const triggerSwapBackPulse = () => {
    setShowSwapBackPulse(true);
    setTimeout(() => setShowSwapBackPulse(false), 600);
  };

  const sendCommand = async (playerId: string, commandType?: 'send' | 'swap_next' | 'swap_back') => {
    const cmdType = commandType || pendingCommand || 'send';
    
    if (!userSqid) return;

    // For send command, we need content
    if (cmdType === 'send' && !hasContent) return;

    setIsSending(true);
    try {
      if (cmdType === 'swap_next') {
        await sendPlayerCommand(userSqid, playerId, {
          command_type: 'swap_next',
        });
        triggerSwapNextPulse();
      } else if (cmdType === 'swap_back') {
        await sendPlayerCommand(userSqid, playerId, {
          command_type: 'swap_back',
        });
        triggerSwapBackPulse();
      } else if (selectedArtwork) {
        // Send show_artwork command
        await sendPlayerCommand(userSqid, playerId, {
          command_type: 'show_artwork',
          post_id: selectedArtwork.id,
        });
        triggerPulse();
      } else if (currentChannel) {
        // Send play_channel command
        const channelCommand: PlayerCommandRequest = {
          command_type: 'play_channel',
          channel_name: currentChannel.userSqid ? 'by_user' : currentChannel.channelName,
          hashtag: currentChannel.hashtag,
          user_sqid: currentChannel.userSqid,
          user_handle: currentChannel.userHandle,
        };

        await sendPlayerCommand(userSqid, playerId, channelCommand);
        triggerPulse();
      }
    } catch (err) {
      console.error('Failed to send command to player:', err);
    } finally {
      setIsSending(false);
      setPendingCommand(null);
    }
  };

  const handleSendClick = async () => {
    if (!hasContent || !userSqid) {
      return;
    }

    // If exactly one online player, send directly
    if (onlinePlayers.length === 1) {
      await sendCommand(onlinePlayers[0].id, 'send');
    } else {
      // Multiple online players - show selector
      setPendingCommand('send');
      setShowPlayerSelector(true);
    }
  };

  const handleSwapNextClick = async () => {
    if (!userSqid) return;

    // If exactly one online player, send directly
    if (onlinePlayers.length === 1) {
      await sendCommand(onlinePlayers[0].id, 'swap_next');
    } else {
      // Multiple online players - show selector
      setPendingCommand('swap_next');
      setShowPlayerSelector(true);
    }
  };

  const handleSwapBackClick = async () => {
    if (!userSqid) return;

    // If exactly one online player, send directly
    if (onlinePlayers.length === 1) {
      await sendCommand(onlinePlayers[0].id, 'swap_back');
    } else {
      // Multiple online players - show selector
      setPendingCommand('swap_back');
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
            className={`swap-btn ${showSwapBackPulse ? 'pulse' : ''}`}
            onClick={handleSwapBackClick}
            disabled={isSending}
            title="Previous artwork"
          >
            ◀
          </button>
          <button
            className={`swap-btn ${showSwapNextPulse ? 'pulse' : ''}`}
            onClick={handleSwapNextClick}
            disabled={isSending}
            title="Next artwork"
          >
            ▶
          </button>
          <button
            className={`send-to-player-btn ${showPulse ? 'pulse' : ''}`}
            onClick={handleSendClick}
            disabled={isSending || !hasContent}
            title={buttonTitle}
          >
            <img
              src="/button/send-to-player/btn005-send-to-player-32px-1x.png"
              srcSet="/button/send-to-player/btn005-send-to-player-32px-1x.png 1x, /button/send-to-player/btn005-send-to-player-40px-1_25x.png 1.25x, /button/send-to-player/btn005-send-to-player-48px-1_5x.png 1.5x, /button/send-to-player/btn005-send-to-player-56px-1_75x.png 1.75x, /button/send-to-player/btn005-send-to-player-64px-2x.png 2x, /button/send-to-player/btn005-send-to-player-72px-2_25x.png 2.25x, /button/send-to-player/btn005-send-to-player-80px-2_5x.png 2.5x, /button/send-to-player/btn005-send-to-player-88px-2_75x.png 2.75x, /button/send-to-player/btn005-send-to-player-96px-3x.png 3x, /button/send-to-player/btn005-send-to-player-104px-3_25x.png 3.25x, /button/send-to-player/btn005-send-to-player-112px-3_5x.png 3.5x, /button/send-to-player/btn005-send-to-player-128px-4x.png 4x"
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
          transform: scale(1.04);
        }

        .send-to-player-btn:active,
        .send-to-player-btn:focus,
        .send-to-player-btn:focus-visible {
          background: transparent;
          outline: none;
          opacity: 1;
        }

        .send-to-player-btn:disabled {
          opacity: 0.5;
          cursor: pointer;
        }

        .send-to-player-btn.pulse {
          animation: pulse 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
        }

        @keyframes pulse {
          0% {
            transform: scale(1);
          }
          50% {
            transform: scale(1.12);
          }
          100% {
            transform: scale(1);
          }
        }

        .send-icon {
          width: 32px;
          height: 32px;
          image-rendering: auto;
          pointer-events: none;
        }

        .swap-btn {
          background: transparent;
          border: none;
          color: #ffffff;
          cursor: pointer;
          padding: 8px 12px;
          border-radius: 8px;
          font-size: 1.2rem;
          transition: all 0.15s ease;
          display: flex;
          align-items: center;
          justify-content: center;
          outline: none;
          -webkit-tap-highlight-color: transparent;
          user-select: none;
          min-width: 44px;
          height: 44px;
        }

        .swap-btn:hover:not(:disabled) {
          background: rgba(255, 255, 255, 0.1);
          transform: scale(1.04);
        }

        .swap-btn:active,
        .swap-btn:focus,
        .swap-btn:focus-visible {
          background: transparent;
          outline: none;
          opacity: 1;
        }

        .swap-btn:hover:active,
        .swap-btn:hover:focus {
          background: rgba(255, 255, 255, 0.1);
        }

        .swap-btn:disabled {
          opacity: 0.5;
          cursor: pointer;
        }

        .swap-btn.pulse {
          animation: pulse 0.5s cubic-bezier(0.34, 1.56, 0.64, 1);
        }
      `}</style>
    </>
  );
}

'use client';

import { useEffect, useRef, useState } from 'react';
import { PendingField, PendingPatch, usePlayerBarOptional } from '../contexts/PlayerBarContext';
import {
  sendPlayerCommand,
  setPlayerBrightness,
  setPlayerMirror,
  setPlayerPause,
  setPlayerRotation,
  PlayerCommandRequest,
  Player,
} from '../lib/api';
import SelectPlayerOverlay from './SelectPlayerOverlay';

export const PLAYER_BAR_HEIGHT = 64;

const PLAYER_BAR_Z_INDEX = 40000;
// How long an unconfirmed pending overlay sticks around before falling back
// to the player's actual state. Reached only if the device never publishes a
// matching state update (e.g. it dropped offline mid-command).
const PENDING_TIMEOUT_MS = 5000;
const BRIGHTNESS_DEBOUNCE_MS = 150;

/**
 * PlayerBar — controls for an online player. The bar shows base send/swap
 * actions plus a three-dot menu of optional features (pause/resume gets its
 * own button outside the menu).
 *
 * Optional commands use an optimistic overlay (`pendingPatches` in the
 * context) that auto-clears when the device's `state` event confirms the
 * new value. If the API call fails, or no confirmation arrives within
 * PENDING_TIMEOUT_MS, the overlay is cleared and the UI falls back to the
 * player's actual state.
 */
export default function PlayerBar() {
  const context = usePlayerBarOptional();
  const [showPlayerSelector, setShowPlayerSelector] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [showPulse, setShowPulse] = useState(false);
  const [showSwapNextPulse, setShowSwapNextPulse] = useState(false);
  const [showSwapBackPulse, setShowSwapBackPulse] = useState(false);
  const [pendingCommand, setPendingCommand] =
    useState<'send' | 'swap_next' | 'swap_back' | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const brightnessTimerRef = useRef<number | null>(null);
  const [brightnessLocal, setBrightnessLocal] = useState<number | null>(null);
  // Per-(player,field) request token. Lets a stale timeout keep its hands off
  // a pending value that a newer click has overwritten.
  const pendingTokenRef = useRef<Record<string, number>>({});

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [menuOpen]);

  if (!context || context.isLoading || !context.hasOnlinePlayer) {
    return null;
  }

  const { onlinePlayers, selectedArtwork, currentChannel, activePlayerId,
    setActivePlayerId, pendingPatches, setPendingPatch, clearPendingPatch } = context;
  const userSqid = typeof window !== 'undefined'
    ? localStorage.getItem('public_sqid') : null;

  const activePlayer: Player | undefined =
    onlinePlayers.find((p) => p.id === activePlayerId) || onlinePlayers[0];
  const caps = activePlayer?.capabilities || {};
  const supportsPause = !!caps.pause;
  const supportsBrightness = !!caps.brightness;
  const supportsRotation = !!caps.rotation;
  const supportsMirror = !!caps.mirror;
  // Menu shows if there's at least one menu-eligible item: a player switcher
  // (>1 online) or any non-pause optional control. Pause has its own button
  // outside the menu, so a player whose only capability is "pause" (with one
  // online player) gets no menu button at all.
  const showMenuButton =
    onlinePlayers.length > 1 || supportsBrightness || supportsRotation || supportsMirror;

  const displayText = selectedArtwork
    ? selectedArtwork.title
    : currentChannel?.displayName || '';

  const hasContent = !!(selectedArtwork || currentChannel);

  const triggerPulse = () => { setShowPulse(true); setTimeout(() => setShowPulse(false), 600); };
  const triggerSwapNextPulse = () => { setShowSwapNextPulse(true); setTimeout(() => setShowSwapNextPulse(false), 600); };
  const triggerSwapBackPulse = () => { setShowSwapBackPulse(true); setTimeout(() => setShowSwapBackPulse(false), 600); };

  const sendCommand = async (
    playerId: string,
    commandType?: 'send' | 'swap_next' | 'swap_back'
  ) => {
    const cmdType = commandType || pendingCommand || 'send';
    if (!userSqid) return;
    if (cmdType === 'send' && !hasContent) return;

    setIsSending(true);
    try {
      if (cmdType === 'swap_next') {
        await sendPlayerCommand(userSqid, playerId, { command_type: 'swap_next' });
        triggerSwapNextPulse();
      } else if (cmdType === 'swap_back') {
        await sendPlayerCommand(userSqid, playerId, { command_type: 'swap_back' });
        triggerSwapBackPulse();
      } else if (selectedArtwork) {
        await sendPlayerCommand(userSqid, playerId, {
          command_type: 'show_artwork',
          post_id: selectedArtwork.id,
        });
        triggerPulse();
      } else if (currentChannel) {
        const channelCommand: PlayerCommandRequest = {
          command_type: 'play_channel',
          channel_name: currentChannel.channelName ||
            (currentChannel.userSqid ? 'by_user' : undefined),
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

  // ---- Optional commands (optimistic overlay, state-confirmed) -----------

  const activePending: PendingPatch = activePlayer
    ? (pendingPatches[activePlayer.id] ?? {})
    : {};

  const displayedPaused = activePending.is_paused ?? activePlayer?.is_paused ?? false;
  const displayedRotation = activePending.rotation ?? activePlayer?.rotation ?? null;
  const displayedMirror = activePending.mirror ?? activePlayer?.mirror ?? null;
  // brightnessLocal tracks the slider mid-drag (pre-debounce). Once the
  // debounced API call fires, brightnessLocal clears and the pending overlay
  // takes over until the device confirms.
  const displayedBrightness =
    brightnessLocal ?? activePending.brightness ?? activePlayer?.brightness ?? 0;

  /**
   * Set an optimistic overlay for `field` and fire `apiCall`. The overlay is
   * cleared when:
   *   - the API call fails,
   *   - an SSE state event confirms the value (handled in context),
   *   - PENDING_TIMEOUT_MS elapses without confirmation.
   *
   * Each call increments a per-(player, field) token; only the latest token's
   * timeout is allowed to clear the overlay, so rapid re-clicks don't fight.
   */
  const submitPending = async <T,>(
    field: PendingField,
    nextValue: T,
    apiCall: () => Promise<unknown>,
  ) => {
    if (!activePlayer || !userSqid) return;
    const playerId = activePlayer.id;
    const tokenKey = `${playerId}.${field}`;
    const token = (pendingTokenRef.current[tokenKey] ?? 0) + 1;
    pendingTokenRef.current[tokenKey] = token;

    setPendingPatch(playerId, field, nextValue);

    try {
      await apiCall();
    } catch (err) {
      if (pendingTokenRef.current[tokenKey] === token) {
        clearPendingPatch(playerId, field);
      }
      console.error(`Failed to set ${field} on player`, err);
      return;
    }

    setTimeout(() => {
      if (pendingTokenRef.current[tokenKey] === token) {
        clearPendingPatch(playerId, field);
      }
    }, PENDING_TIMEOUT_MS);
  };

  const handleTogglePause = async () => {
    if (!activePlayer || !userSqid || !supportsPause) return;
    const next = !displayedPaused;
    await submitPending('is_paused', next,
      () => setPlayerPause(userSqid, activePlayer.id, next));
  };

  const onBrightnessInput = (raw: number) => {
    setBrightnessLocal(raw);
    if (brightnessTimerRef.current) window.clearTimeout(brightnessTimerRef.current);
    brightnessTimerRef.current = window.setTimeout(() => {
      if (!activePlayer || !userSqid) return;
      submitPending('brightness', raw,
        () => setPlayerBrightness(userSqid, activePlayer.id, raw))
        .finally(() => setBrightnessLocal(null));
    }, BRIGHTNESS_DEBOUNCE_MS);
  };

  const handleSetRotation = async (value: number) => {
    if (!activePlayer || !userSqid) return;
    await submitPending('rotation', value,
      () => setPlayerRotation(userSqid, activePlayer.id, value));
  };

  const handleSetMirror = async (value: string) => {
    if (!activePlayer || !userSqid) return;
    await submitPending('mirror', value,
      () => setPlayerMirror(userSqid, activePlayer.id, value));
  };

  // ---- Base actions (send / swap) ----------------------------------------

  const handleSendClick = async () => {
    if (!hasContent || !userSqid) return;
    if (onlinePlayers.length === 1) {
      await sendCommand(onlinePlayers[0].id, 'send');
    } else if (activePlayerId) {
      await sendCommand(activePlayerId, 'send');
    } else {
      setPendingCommand('send');
      setShowPlayerSelector(true);
    }
  };

  const handleSwapNextClick = async () => {
    if (!userSqid) return;
    const target = activePlayerId || (onlinePlayers.length === 1 ? onlinePlayers[0].id : null);
    if (target) {
      await sendCommand(target, 'swap_next');
    } else {
      setPendingCommand('swap_next');
      setShowPlayerSelector(true);
    }
  };

  const handleSwapBackClick = async () => {
    if (!userSqid) return;
    const target = activePlayerId || (onlinePlayers.length === 1 ? onlinePlayers[0].id : null);
    if (target) {
      await sendCommand(target, 'swap_back');
    } else {
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
          {showMenuButton && (
            <div className="menu-wrap" ref={menuRef}>
              <button
                className="menu-btn"
                onClick={() => setMenuOpen((v) => !v)}
                title="Player options"
                aria-label="Player options"
              >
                ⋮
              </button>
              {menuOpen && (
                <div className="menu-pop" role="menu">
                  {onlinePlayers.length > 1 && (
                    <div className="menu-section">
                      <div className="menu-label">Active player</div>
                      {onlinePlayers.map((p) => (
                        <button
                          key={p.id}
                          className={`menu-item ${activePlayerId === p.id ? 'active' : ''}`}
                          onClick={() => setActivePlayerId(p.id)}
                        >
                          {activePlayerId === p.id ? '● ' : '○ '}
                          {p.name || p.id.slice(0, 8)}
                        </button>
                      ))}
                    </div>
                  )}
                  {supportsBrightness && activePlayer && (
                    <div className="menu-section">
                      <div className="menu-label">
                        Brightness {displayedBrightness}
                      </div>
                      <input
                        type="range"
                        min={caps.brightness!.min}
                        max={caps.brightness!.max}
                        step={caps.brightness!.step}
                        value={displayedBrightness}
                        onChange={(e) => onBrightnessInput(Number(e.target.value))}
                      />
                    </div>
                  )}
                  {supportsRotation && activePlayer && (
                    <div className="menu-section">
                      <div className="menu-label">Rotation</div>
                      <div className="chip-row">
                        {caps.rotation!.values.map((v) => (
                          <button
                            key={v}
                            className={`chip ${displayedRotation === v ? 'active' : ''}`}
                            onClick={() => handleSetRotation(v)}
                          >
                            {v}°
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {supportsMirror && activePlayer && (
                    <div className="menu-section">
                      <div className="menu-label">Mirror</div>
                      <div className="chip-row">
                        {caps.mirror!.values.map((v) => (
                          <button
                            key={v}
                            className={`chip ${displayedMirror === v ? 'active' : ''}`}
                            onClick={() => handleSetMirror(v)}
                          >
                            {v}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {displayText && <div className="display-text">{displayText}</div>}

          {supportsPause && activePlayer && (
            <button
              className={`pause-btn ${displayedPaused ? 'paused' : ''}`}
              onClick={handleTogglePause}
              title={displayedPaused ? 'Resume' : 'Pause'}
              aria-label={displayedPaused ? 'Resume' : 'Pause'}
            >
              {displayedPaused ? '▶' : '⏸'}
            </button>
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
          justify-content: space-between;
        }
        .player-bar-content {
          display: flex;
          align-items: center;
          padding: 0 16px;
          width: 100%;
        }
        .player-bar-content > :global(* + *) {
          margin-left: 12px;
        }
        .display-text {
          color: #ffffff;
          font-size: 0.95rem;
          font-weight: 500;
          max-width: 240px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          flex: 1;
        }
        .menu-wrap { position: relative; }
        .menu-btn {
          background: transparent;
          border: none;
          color: #ffffff;
          cursor: pointer;
          font-size: 1.6rem;
          line-height: 1;
          padding: 4px 10px;
          border-radius: 8px;
          height: 44px;
        }
        .menu-btn:hover { background: rgba(255,255,255,0.1); }
        .menu-pop {
          position: absolute;
          bottom: calc(100% + 8px);
          left: 0;
          background: #111;
          border: 1px solid #333;
          border-radius: 8px;
          min-width: 220px;
          padding: 8px 0;
          color: #fff;
          box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        }
        .menu-section {
          padding: 8px 12px;
          border-bottom: 1px solid #1d1d1d;
        }
        .menu-section:last-child { border-bottom: none; }
        .menu-label {
          font-size: 0.75rem;
          opacity: 0.7;
          margin-bottom: 6px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .menu-item {
          display: block;
          width: 100%;
          text-align: left;
          background: transparent;
          border: none;
          color: #fff;
          padding: 6px 4px;
          cursor: pointer;
          font-size: 0.9rem;
        }
        .menu-item:hover { background: rgba(255,255,255,0.06); }
        .menu-item.active { color: #4ea1ff; }
        .chip-row { display: flex; gap: 6px; flex-wrap: wrap; }
        .chip {
          background: #222;
          border: 1px solid #333;
          color: #fff;
          padding: 4px 10px;
          border-radius: 999px;
          cursor: pointer;
          font-size: 0.85rem;
        }
        .chip:hover { background: #2c2c2c; }
        .chip.active { background: #4ea1ff; border-color: #4ea1ff; color: #000; }
        input[type=range] {
          width: 100%;
          accent-color: #4ea1ff;
        }
        .pause-btn {
          background: transparent;
          border: none;
          color: #ffffff;
          cursor: pointer;
          padding: 8px 12px;
          border-radius: 8px;
          font-size: 1.1rem;
          height: 44px;
          min-width: 44px;
        }
        .pause-btn:hover { background: rgba(255,255,255,0.1); }
        .pause-btn.paused { color: #4ea1ff; }
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
        .send-to-player-btn:hover:not(:disabled) { transform: scale(1.04); }
        .send-to-player-btn:disabled { opacity: 0.5; cursor: pointer; }
        .send-to-player-btn.pulse { animation: pulse 0.5s cubic-bezier(0.34, 1.56, 0.64, 1); }
        @keyframes pulse {
          0% { transform: scale(1); }
          50% { transform: scale(1.12); }
          100% { transform: scale(1); }
        }
        .send-icon { width: 32px; height: 32px; image-rendering: auto; pointer-events: none; }
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
        .swap-btn:disabled { opacity: 0.5; cursor: pointer; }
        .swap-btn.pulse { animation: pulse 0.5s cubic-bezier(0.34, 1.56, 0.64, 1); }
      `}</style>
    </>
  );
}

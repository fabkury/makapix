import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { Player, listPlayers, authenticatedFetch } from '../lib/api';

interface PlayerStatePatch {
  is_paused?: boolean;
  brightness?: number;
  rotation?: number;
  mirror?: string;
}

export interface SelectedArtwork {
  id: number;
  public_sqid: string;
  title: string;
  art_url: string;
}

export interface ChannelInfo {
  displayName: string;
  channelName?: string;  // 'promoted', 'all', 'by_user', or 'reactions'
  hashtag?: string;      // hashtag without #
  userSqid?: string;     // user's sqid (for by_user / reactions channels)
  userHandle?: string;   // user's handle (for by_user / reactions channels)
}

interface PlayerBarContextValue {
  players: Player[];
  onlinePlayers: Player[];
  hasOnlinePlayer: boolean;
  selectedArtwork: SelectedArtwork | null;
  setSelectedArtwork: (artwork: SelectedArtwork | null) => void;
  currentChannel: ChannelInfo | null;
  setCurrentChannel: (channel: ChannelInfo | null) => void;
  isLoading: boolean;
  refreshPlayers: () => Promise<void>;
  /** Player currently targeted by the bar (chosen by user when multiple are online). */
  activePlayerId: string | null;
  setActivePlayerId: (id: string | null) => void;
  /** Optimistically update local state for a single player (used for set commands). */
  patchPlayerState: (playerId: string, patch: PlayerStatePatch) => void;
}

const PlayerBarContext = createContext<PlayerBarContextValue | null>(null);

interface PlayerBarProviderProps {
  children: ReactNode;
}

export function PlayerBarProvider({ children }: PlayerBarProviderProps) {
  const [players, setPlayers] = useState<Player[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedArtwork, setSelectedArtwork] = useState<SelectedArtwork | null>(null);
  const [currentChannel, setCurrentChannel] = useState<ChannelInfo | null>(null);
  const [userSqid, setUserSqid] = useState<string | null>(null);
  const [activePlayerId, setActivePlayerIdState] = useState<string | null>(null);
  const sseRef = useRef<EventSource | null>(null);

  // Fetch user info and then players
  const fetchPlayersForUser = useCallback(async (sqid: string) => {
    try {
      const response = await listPlayers(sqid);
      setPlayers(response.items || []);
    } catch (err) {
      setPlayers([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initialize: get user sqid and fetch players
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const token = localStorage.getItem('access_token');
    if (!token) {
      setIsLoading(false);
      return;
    }

    // Check if we already have sqid in localStorage (fast path)
    const storedSqid = localStorage.getItem('public_sqid');
    if (storedSqid) {
      setUserSqid(storedSqid);
      fetchPlayersForUser(storedSqid);
      return;
    }

    // Fallback: fetch user info from API to get sqid
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
    authenticatedFetch(`${apiBaseUrl}/api/auth/me`)
      .then(res => {
        if (!res.ok) {
          setIsLoading(false);
          return null;
        }
        return res.json();
      })
      .then(data => {
        if (data?.user?.public_sqid) {
          setUserSqid(data.user.public_sqid);
          fetchPlayersForUser(data.user.public_sqid);
        } else {
          setIsLoading(false);
        }
      })
      .catch(() => {
        setIsLoading(false);
      });
  }, [fetchPlayersForUser]);

  // Public refresh function
  const refreshPlayers = useCallback(async () => {
    const sqid = userSqid || localStorage.getItem('public_sqid');
    if (sqid) {
      await fetchPlayersForUser(sqid);
    }
  }, [userSqid, fetchPlayersForUser]);

  const onlinePlayers = players.filter((p) => p.connection_status === 'online');
  const hasOnlinePlayer = onlinePlayers.length > 0;

  // Restore preferred active player from localStorage once.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const saved = localStorage.getItem('player_bar.active_player_id');
    if (saved) setActivePlayerIdState(saved);
  }, []);

  // Auto-pick / auto-replace active player as the online set changes.
  useEffect(() => {
    if (!onlinePlayers.length) {
      // No online players — clear selection so UI collapses cleanly.
      if (activePlayerId !== null) setActivePlayerIdState(null);
      return;
    }
    const stillOnline = activePlayerId &&
      onlinePlayers.some((p) => p.id === activePlayerId);
    if (!stillOnline) {
      setActivePlayerIdState(onlinePlayers[0].id);
    }
  }, [onlinePlayers, activePlayerId]);

  const setActivePlayerId = useCallback((id: string | null) => {
    setActivePlayerIdState(id);
    if (typeof window !== 'undefined') {
      if (id) localStorage.setItem('player_bar.active_player_id', id);
      else localStorage.removeItem('player_bar.active_player_id');
    }
  }, []);

  const patchPlayerState = useCallback(
    (playerId: string, patch: PlayerStatePatch) => {
      setPlayers((prev) =>
        prev.map((p) => (p.id === playerId ? { ...p, ...patch } : p))
      );
    },
    []
  );

  // Live updates via SSE. Re-subscribes when sqid changes.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!userSqid) return;
    const token = localStorage.getItem('access_token');
    if (!token) return;

    const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || '';
    const url = `${apiBase}/api/u/${userSqid}/player/sse?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    sseRef.current = es;

    es.addEventListener('capabilities', (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        setPlayers((prev) =>
          prev.map((p) =>
            p.id === data.player_id
              ? {
                  ...p,
                  capabilities: data.capabilities ?? null,
                  firmware_version: data.firmware_version ?? p.firmware_version,
                }
              : p
          )
        );
      } catch (e) { /* ignore */ }
    });

    es.addEventListener('state', (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        setPlayers((prev) =>
          prev.map((p) =>
            p.id === data.player_id ? { ...p, ...data.state } : p
          )
        );
      } catch (e) { /* ignore */ }
    });

    es.addEventListener('command_ack', (event) => {
      try {
        const data = JSON.parse((event as MessageEvent).data);
        window.dispatchEvent(
          new CustomEvent('player-command-ack', { detail: data })
        );
      } catch (e) { /* ignore */ }
    });

    es.onerror = () => {
      // EventSource auto-reconnects; nothing to do.
    };

    return () => {
      es.close();
      sseRef.current = null;
    };
  }, [userSqid]);

  const value: PlayerBarContextValue = {
    players,
    onlinePlayers,
    hasOnlinePlayer,
    selectedArtwork,
    setSelectedArtwork,
    currentChannel,
    setCurrentChannel,
    isLoading,
    refreshPlayers,
    activePlayerId,
    setActivePlayerId,
    patchPlayerState,
  };

  return (
    <PlayerBarContext.Provider value={value}>
      {children}
    </PlayerBarContext.Provider>
  );
}

export function usePlayerBar() {
  const context = useContext(PlayerBarContext);
  if (!context) {
    throw new Error('usePlayerBar must be used within a PlayerBarProvider');
  }
  return context;
}

export function usePlayerBarOptional() {
  return useContext(PlayerBarContext);
}

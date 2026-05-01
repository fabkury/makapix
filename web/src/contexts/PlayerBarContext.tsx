import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { Player, listPlayers, authenticatedFetch } from '../lib/api';

export type PendingField = 'is_paused' | 'brightness' | 'rotation' | 'mirror';

export interface PendingPatch {
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
  /**
   * Per-player optimistic overlay for set commands. The displayed value for a
   * field is `pendingPatches[id]?.[field] ?? player[field]`. Entries are
   * cleared automatically when an SSE state event arrives reporting the same
   * value (i.e. the device confirms the change), or by the caller on API
   * error / timeout.
   */
  pendingPatches: Record<string, PendingPatch>;
  setPendingPatch: (playerId: string, field: PendingField, value: unknown) => void;
  clearPendingPatch: (playerId: string, field: PendingField) => void;
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
  const [pendingPatches, setPendingPatches] = useState<Record<string, PendingPatch>>({});
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

  const setPendingPatch = useCallback(
    (playerId: string, field: PendingField, value: unknown) => {
      setPendingPatches((prev) => ({
        ...prev,
        [playerId]: { ...prev[playerId], [field]: value as never },
      }));
    },
    []
  );

  const clearPendingPatch = useCallback(
    (playerId: string, field: PendingField) => {
      setPendingPatches((prev) => {
        const cur = prev[playerId];
        if (!cur || !(field in cur)) return prev;
        const next: PendingPatch = { ...cur };
        delete next[field];
        const out = { ...prev };
        if (Object.keys(next).length === 0) delete out[playerId];
        else out[playerId] = next;
        return out;
      });
    },
    []
  );

  // Drop pending entries that the player has now confirmed via state.
  const reconcilePendingFromState = useCallback(
    (playerId: string, state: Partial<PendingPatch>) => {
      setPendingPatches((prev) => {
        const cur = prev[playerId];
        if (!cur) return prev;
        const next: PendingPatch = { ...cur };
        let changed = false;
        for (const key of Object.keys(state) as Array<keyof PendingPatch>) {
          if (key in next && next[key] === state[key]) {
            delete next[key];
            changed = true;
          }
        }
        if (!changed) return prev;
        const out = { ...prev };
        if (Object.keys(next).length === 0) delete out[playerId];
        else out[playerId] = next;
        return out;
      });
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
        const playerId: string = data.player_id;
        const state: Partial<PendingPatch> = data.state ?? {};
        setPlayers((prev) =>
          prev.map((p) => (p.id === playerId ? { ...p, ...state } : p))
        );
        reconcilePendingFromState(playerId, state);
      } catch (e) { /* ignore */ }
    });

    es.onerror = () => {
      // EventSource auto-reconnects; nothing to do.
    };

    return () => {
      es.close();
      sseRef.current = null;
    };
  }, [userSqid, reconcilePendingFromState]);

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
    pendingPatches,
    setPendingPatch,
    clearPendingPatch,
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

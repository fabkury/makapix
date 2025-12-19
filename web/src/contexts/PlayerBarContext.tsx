import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { Player, listPlayers, authenticatedFetch } from '../lib/api';

export interface SelectedArtwork {
  id: number;
  public_sqid: string;
  title: string;
  art_url: string;
}

export interface ChannelInfo {
  displayName: string;
  channelName?: string;  // 'promoted' or 'all'
  hashtag?: string;      // hashtag without #
  userSqid?: string;     // user's sqid
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

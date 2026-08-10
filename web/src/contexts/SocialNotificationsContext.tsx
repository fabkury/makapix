/**
 * Social Notifications Context.
 *
 * Provides shared notification state across all components. Real-time
 * updates arrive over the bearer-authenticated SSE stream
 * (GET /api/v1/realtime/notifications) — browsers do not talk to the MQTT
 * broker (docs/notification-architecture/). The SSE `connected` greeting
 * carries the authoritative unread count, so the badge re-syncs on every
 * (re)connect; live items are deduped by id against everything already
 * fetched or shown.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  ReactNode,
} from "react";
import { authenticatedFetch } from "@/lib/api";
import {
  useNotificationsSSE,
  SocialNotificationItem,
} from "@/hooks/useNotificationsSSE";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export type SocialNotificationFull = SocialNotificationItem;

interface SocialNotificationsContextValue {
  /** Unread count for badge display */
  unreadCount: number;
  /** List of recent notifications */
  notifications: SocialNotificationFull[];
  /** Whether the SSE stream is open */
  connected: boolean;
  /** Loading state for initial fetch */
  loading: boolean;
  /** Fetch unread count from API */
  fetchUnreadCount: () => Promise<void>;
  /** Fetch notifications list from API */
  fetchNotifications: (cursor?: string) => Promise<{ nextCursor: string | null }>;
  /** Mark all notifications as read */
  markAllAsRead: () => Promise<void>;
}

const SocialNotificationsContext = createContext<SocialNotificationsContextValue | null>(null);

interface SocialNotificationsProviderProps {
  /** True when an authenticated session exists (the server derives the user
   *  from the bearer token; no client-side user id is needed). */
  enabled: boolean;
  children: ReactNode;
}

export function SocialNotificationsProvider({
  enabled,
  children,
}: SocialNotificationsProviderProps) {
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<SocialNotificationFull[]>([]);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  // Every notification id ever fetched or received this session — a superset
  // of the visible list (which is capped), so live duplicates never re-count.
  const knownIdsRef = useRef<Set<string>>(new Set());

  // Fetch unread count from API
  const fetchUnreadCount = useCallback(async () => {
    if (!enabled) return;

    try {
      const response = await authenticatedFetch(
        `${API_BASE}/api/v1/social-notifications/unread-count`
      );
      if (response.ok) {
        const data = await response.json();
        setUnreadCount(data.unread_count);
      }
    } catch (error) {
      console.error("Failed to fetch unread count:", error);
    }
  }, [enabled]);

  // Fetch notifications list from API
  const fetchNotifications = useCallback(
    async (cursor?: string): Promise<{ nextCursor: string | null }> => {
      if (!enabled) return { nextCursor: null };

      setLoading(true);
      try {
        const url = new URL(`${API_BASE}/api/v1/social-notifications/`);
        url.searchParams.set("limit", "50");
        if (cursor) {
          url.searchParams.set("cursor", cursor);
        }

        const response = await authenticatedFetch(url.toString());
        if (response.ok) {
          const data = await response.json();
          const newNotifications: SocialNotificationFull[] = data.items;

          if (cursor) {
            // Appending more notifications
            newNotifications.forEach((n) => knownIdsRef.current.add(n.id));
            setNotifications((prev) => [...prev, ...newNotifications]);
          } else {
            // Initial fetch
            knownIdsRef.current = new Set(newNotifications.map((n) => n.id));
            setNotifications(newNotifications);
          }

          return { nextCursor: data.next_cursor || null };
        }
      } catch (error) {
        console.error("Failed to fetch notifications:", error);
      } finally {
        setLoading(false);
      }

      return { nextCursor: null };
    },
    [enabled]
  );

  // Mark all notifications as read
  const markAllAsRead = useCallback(async () => {
    if (!enabled) return;

    try {
      const response = await authenticatedFetch(
        `${API_BASE}/api/v1/social-notifications/mark-all-read`,
        { method: "POST" }
      );
      if (response.ok || response.status === 204) {
        setUnreadCount(0);
        setNotifications((prev) =>
          prev.map((n) => ({ ...n, is_read: true }))
        );
      }
    } catch (error) {
      console.error("Failed to mark all as read:", error);
    }
  }, [enabled]);

  // Incoming live notification: dedupe by id, prepend, bump the badge.
  const handleIncoming = useCallback((item: SocialNotificationItem) => {
    if (knownIdsRef.current.has(item.id)) return;
    knownIdsRef.current.add(item.id);
    setNotifications((prev) => [item, ...prev].slice(0, 100));
    if (!item.is_read) {
      setUnreadCount((c) => c + 1);
    }
  }, []);

  // Real-time stream (no-ops while disabled).
  useNotificationsSSE({
    enabled,
    onConnected: (unread) => setUnreadCount(unread),
    onNotification: handleIncoming,
    onConnect: () => setConnected(true),
    onDisconnect: () => setConnected(false),
  });

  // Session lifecycle: seed the badge on login, clear state on logout.
  useEffect(() => {
    if (!enabled) {
      setUnreadCount(0);
      setNotifications([]);
      setConnected(false);
      knownIdsRef.current.clear();
      return;
    }
    // Fast first paint (and resilience if the SSE stream can't connect);
    // the `connected` greeting overwrites this moments later.
    fetchUnreadCount();
  }, [enabled, fetchUnreadCount]);

  // Keep the badge honest when the tab regains attention, even if the SSE
  // stream has exhausted its reconnect attempts in the background.
  useEffect(() => {
    if (!enabled) return;

    const refetch = () => fetchUnreadCount();
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") refetch();
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("focus", refetch);
    window.addEventListener("online", refetch);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("focus", refetch);
      window.removeEventListener("online", refetch);
    };
  }, [enabled, fetchUnreadCount]);

  const value: SocialNotificationsContextValue = {
    unreadCount,
    notifications,
    connected,
    loading,
    fetchUnreadCount,
    fetchNotifications,
    markAllAsRead,
  };

  return (
    <SocialNotificationsContext.Provider value={value}>
      {children}
    </SocialNotificationsContext.Provider>
  );
}

/**
 * Hook to access social notifications context.
 * Must be used within a SocialNotificationsProvider.
 */
export function useSocialNotificationsContext(): SocialNotificationsContextValue {
  const context = useContext(SocialNotificationsContext);
  if (!context) {
    throw new Error(
      "useSocialNotificationsContext must be used within a SocialNotificationsProvider"
    );
  }
  return context;
}

/**
 * Hook that returns a safe version of the context (returns defaults if not in provider).
 * Useful for components that may be rendered outside the provider.
 */
export function useSocialNotificationsSafe(): SocialNotificationsContextValue {
  const context = useContext(SocialNotificationsContext);

  // Return no-op defaults if not in provider
  if (!context) {
    return {
      unreadCount: 0,
      notifications: [],
      connected: false,
      loading: false,
      fetchUnreadCount: async () => {},
      fetchNotifications: async () => ({ nextCursor: null }),
      markAllAsRead: async () => {},
    };
  }

  return context;
}

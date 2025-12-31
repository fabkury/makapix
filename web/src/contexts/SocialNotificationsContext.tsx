/**
 * Social Notifications Context.
 *
 * Provides shared notification state across all components.
 * This ensures real-time updates from MQTT are reflected everywhere.
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
import { MQTTClient, SocialNotification } from "@/lib/mqtt-client";

const MQTT_URL = process.env.NEXT_PUBLIC_MQTT_WS_URL || "ws://localhost:9001";
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "";

export interface SocialNotificationFull extends SocialNotification {
  user_id: number;
  is_read: boolean;
}

interface SocialNotificationsContextValue {
  /** Unread count for badge display */
  unreadCount: number;
  /** List of recent notifications */
  notifications: SocialNotificationFull[];
  /** Whether the MQTT connection is active */
  connected: boolean;
  /** Loading state for initial fetch */
  loading: boolean;
  /** Fetch unread count from API */
  fetchUnreadCount: () => Promise<void>;
  /** Fetch notifications list from API */
  fetchNotifications: (cursor?: string) => Promise<{ nextCursor: string | null }>;
  /** Mark all notifications as read */
  markAllAsRead: () => Promise<void>;
  /** Mark specific notification as read */
  markAsRead: (notificationId: string) => Promise<void>;
  /** Clear local notifications state */
  clearNotifications: () => void;
}

const SocialNotificationsContext = createContext<SocialNotificationsContextValue | null>(null);

interface SocialNotificationsProviderProps {
  userId: string | null;
  children: ReactNode;
}

export function SocialNotificationsProvider({
  userId,
  children,
}: SocialNotificationsProviderProps) {
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<SocialNotificationFull[]>([]);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const clientRef = useRef<MQTTClient | null>(null);

  // Fetch unread count from API
  const fetchUnreadCount = useCallback(async () => {
    if (!userId) return;

    try {
      const response = await authenticatedFetch(
        `${API_BASE}/api/social-notifications/unread-count`
      );
      if (response.ok) {
        const data = await response.json();
        setUnreadCount(data.unread_count);
      }
    } catch (error) {
      console.error("Failed to fetch unread count:", error);
    }
  }, [userId]);

  // Fetch notifications list from API
  const fetchNotifications = useCallback(
    async (cursor?: string): Promise<{ nextCursor: string | null }> => {
      if (!userId) return { nextCursor: null };

      setLoading(true);
      try {
        const url = new URL(`${API_BASE}/api/social-notifications/`);
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
            setNotifications((prev) => [...prev, ...newNotifications]);
          } else {
            // Initial fetch
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
    [userId]
  );

  // Mark all notifications as read
  const markAllAsRead = useCallback(async () => {
    if (!userId) return;

    try {
      const response = await authenticatedFetch(
        `${API_BASE}/api/social-notifications/mark-all-read`,
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
  }, [userId]);

  // Mark specific notification as read
  const markAsRead = useCallback(
    async (notificationId: string) => {
      if (!userId) return;

      try {
        const response = await authenticatedFetch(
          `${API_BASE}/api/social-notifications/mark-read`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify([notificationId]),
          }
        );
        if (response.ok || response.status === 204) {
          setUnreadCount((prev) => Math.max(0, prev - 1));
          setNotifications((prev) =>
            prev.map((n) =>
              n.id === notificationId ? { ...n, is_read: true } : n
            )
          );
        }
      } catch (error) {
        console.error("Failed to mark as read:", error);
      }
    },
    [userId]
  );

  // Clear local notifications
  const clearNotifications = useCallback(() => {
    setNotifications([]);
    setUnreadCount(0);
  }, []);

  // Set up MQTT connection and subscribe to real-time notifications
  useEffect(() => {
    if (!userId) {
      // Clear state when user logs out
      setUnreadCount(0);
      setNotifications([]);
      setConnected(false);
      return;
    }

    // Initial fetch
    fetchUnreadCount();

    // Create MQTT client
    const client = new MQTTClient(MQTT_URL);
    clientRef.current = client;

    // Connect
    client
      .connect(userId)
      .then(() => {
        setConnected(true);
      })
      .catch((error) => {
        console.error("Failed to connect to MQTT:", error);
        setConnected(false);
      });

    // Register social notification callback
    const unsubscribe = client.onSocialNotification((notification) => {
      // Increment unread count
      setUnreadCount((prev) => prev + 1);

      // Add to notifications list (prepend, keep max 100)
      const fullNotification: SocialNotificationFull = {
        ...notification,
        user_id: parseInt(userId, 10),
        is_read: false,
      };
      setNotifications((prev) => [fullNotification, ...prev].slice(0, 100));
    });

    // Cleanup on unmount
    return () => {
      unsubscribe();
      client.disconnect();
      setConnected(false);
    };
  }, [userId, fetchUnreadCount]);

  const value: SocialNotificationsContextValue = {
    unreadCount,
    notifications,
    connected,
    loading,
    fetchUnreadCount,
    fetchNotifications,
    markAllAsRead,
    markAsRead,
    clearNotifications,
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
      markAsRead: async () => {},
      clearNotifications: () => {},
    };
  }
  
  return context;
}


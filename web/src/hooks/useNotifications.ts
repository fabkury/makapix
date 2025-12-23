/**
 * React hook for managing notifications.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import { NotificationWebSocketClient, NotificationPayload } from '../lib/websocket-client';
import { authenticatedFetch, getAccessToken } from '../lib/api';

interface Notification {
  id: string;
  notification_type: 'reaction' | 'comment';
  content_type: 'post' | 'blog_post';
  content_id: number;
  actor_handle: string;
  emoji?: string;
  comment_preview?: string;
  content_title?: string;
  content_url?: string;
  is_read: boolean;
  created_at: string;
}

export function useNotifications(userId: string | null) {
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [connected, setConnected] = useState<boolean>(false);
  
  const clientRef = useRef<NotificationWebSocketClient | null>(null);
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Fetch unread count
  const fetchUnreadCount = useCallback(async () => {
    if (!userId) return;
    
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/notifications/unread-count`);
      if (response.ok) {
        const data = await response.json();
        setUnreadCount(data.unread_count);
      }
    } catch (error) {
      console.error('Failed to fetch unread count:', error);
    }
  }, [userId, API_BASE_URL]);

  // Fetch notifications list
  const fetchNotifications = useCallback(async (unreadOnly: boolean = false) => {
    if (!userId) return;
    
    setLoading(true);
    try {
      const url = `${API_BASE_URL}/api/notifications/?limit=50${unreadOnly ? '&unread_only=true' : ''}`;
      const response = await authenticatedFetch(url);
      if (response.ok) {
        const data = await response.json();
        setNotifications(data.items);
      }
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
    } finally {
      setLoading(false);
    }
  }, [userId, API_BASE_URL]);

  // Mark notifications as read
  const markAsRead = useCallback(async (notificationIds: string[]) => {
    if (!userId || notificationIds.length === 0) return;
    
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/notifications/mark-read`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(notificationIds),
      });
      
      if (response.ok) {
        // Update local state
        setNotifications(prev => 
          prev.map(n => 
            notificationIds.includes(n.id) ? { ...n, is_read: true } : n
          )
        );
        setUnreadCount(prev => Math.max(0, prev - notificationIds.length));
      }
    } catch (error) {
      console.error('Failed to mark notifications as read:', error);
    }
  }, [userId, API_BASE_URL]);

  // Mark all as read
  const markAllAsRead = useCallback(async () => {
    if (!userId) return;
    
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/notifications/mark-all-read`, {
        method: 'POST',
      });
      
      if (response.ok) {
        setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
        setUnreadCount(0);
      }
    } catch (error) {
      console.error('Failed to mark all notifications as read:', error);
    }
  }, [userId, API_BASE_URL]);

  // Setup WebSocket connection
  useEffect(() => {
    if (!userId) return;

    const token = getAccessToken();
    if (!token) return;

    const client = new NotificationWebSocketClient(API_BASE_URL, token);
    clientRef.current = client;

    client.connect()
      .then(() => {
        setConnected(true);
        console.log('Notifications WebSocket connected');
      })
      .catch((error) => {
        console.error('Failed to connect notifications WebSocket:', error);
        setConnected(false);
      });

    // Handle incoming notifications
    const unsubscribe = client.onNotification((notification: NotificationPayload) => {
      console.log('Received notification:', notification);
      
      // Increment unread count
      setUnreadCount(prev => prev + 1);
      
      // Add to notifications list if loaded
      setNotifications(prev => {
        // Convert payload to full notification
        const newNotification: Notification = {
          id: notification.id,
          notification_type: notification.notification_type,
          content_type: notification.content_type,
          content_id: notification.content_id,
          actor_handle: notification.actor_handle,
          emoji: notification.emoji,
          comment_preview: notification.comment_preview,
          content_title: notification.content_title,
          content_url: notification.content_url,
          is_read: false,
          created_at: notification.created_at,
        };
        return [newNotification, ...prev];
      });
    });

    return () => {
      unsubscribe();
      client.disconnect();
      setConnected(false);
    };
  }, [userId, API_BASE_URL]);

  // Fetch initial unread count
  useEffect(() => {
    fetchUnreadCount();
  }, [fetchUnreadCount]);

  return {
    unreadCount,
    notifications,
    loading,
    connected,
    fetchNotifications,
    fetchUnreadCount,
    markAsRead,
    markAllAsRead,
  };
}

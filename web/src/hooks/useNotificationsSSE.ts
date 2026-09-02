import { useEffect, useRef } from 'react';
import { authenticatedFetch } from '../lib/api';

/**
 * A social notification item, exactly as served by
 * GET /api/v1/social-notifications/ and by the SSE stream's `notification`
 * events — both sources share one shape so consumers can dedupe by `id`.
 */
export interface SocialNotificationItem {
  id: string;
  user_id: number;
  notification_type:
    | 'reaction'
    | 'comment'
    | 'comment_reply'
    | 'comment_like'
    | 'follow'
    | 'post_promoted'
    | 'mod_hashtags_updated'
    | 'reputation_change'
    | 'moderator_granted'
    | 'moderator_revoked'
    | 'new_report'
    | 'report_resolved'
    | 'remix'
    | 'post_approved'
    | 'trust_granted';
  post_id: number | null;
  actor_handle: string | null;
  actor_avatar_url: string | null;
  actor_public_sqid: string | null;
  emoji: string | null;
  comment_preview: string | null;
  content_title: string | null;
  content_sqid: string | null;
  content_art_url: string | null;
  // new_report / report_resolved only (docs/report-artwork/); null otherwise
  reason_code: string | null;
  target_user_handle: string | null;
  target_user_public_sqid: string | null;
  target_user_avatar_url: string | null;
  is_read: boolean;
  created_at: string;
}

interface UseNotificationsSSEOptions {
  enabled: boolean;
  /** `connected` greeting: the authoritative unread count on every (re)connect. */
  onConnected: (unreadCount: number) => void;
  onNotification: (item: SocialNotificationItem) => void;
  onError?: (error: Error) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

/**
 * Subscribe to the user's social notifications from
 * GET /api/v1/realtime/notifications.
 *
 * Uses a fetch() streaming reader instead of the native EventSource because
 * the API authenticates via the Authorization header, which EventSource
 * cannot send. authenticatedFetch also gives us token refresh for free.
 *
 * The server closes the stream after ~5 minutes (sending a `timeout` event
 * first); that is a normal bounded-lifetime close and we reconnect
 * immediately. Unexpected errors reconnect with exponential backoff, giving
 * up after 5 consecutive failures (the badge then stays honest via the
 * provider's mount fetch and refetch-on-focus).
 */
export function useNotificationsSSE({
  enabled,
  onConnected,
  onNotification,
  onError,
  onConnect,
  onDisconnect,
}: UseNotificationsSSEOptions) {
  // Keep the latest callbacks in a ref so their identity doesn't force
  // the connection effect to tear down and reconnect on every render.
  const callbacksRef = useRef({
    onConnected,
    onNotification,
    onError,
    onConnect,
    onDisconnect,
  });
  callbacksRef.current = {
    onConnected,
    onNotification,
    onError,
    onConnect,
    onDisconnect,
  };

  useEffect(() => {
    if (!enabled || typeof window === 'undefined') {
      return;
    }

    const maxReconnectAttempts = 5;
    const baseReconnectDelay = 1000; // 1 second
    let reconnectAttempts = 0;
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
    let controller: AbortController | null = null;
    let stopped = false;

    const scheduleReconnect = (immediate: boolean) => {
      if (stopped) return;
      if (immediate) {
        reconnectTimeout = setTimeout(connect, 0);
        return;
      }
      if (reconnectAttempts >= maxReconnectAttempts) {
        console.log('[NotifSSE] Max reconnect attempts reached');
        callbacksRef.current.onError?.(
          new Error('SSE connection failed after max retries'),
        );
        return;
      }
      const delay = baseReconnectDelay * Math.pow(2, reconnectAttempts);
      reconnectAttempts += 1;
      reconnectTimeout = setTimeout(connect, delay);
    };

    const dispatchEvent = (rawEvent: string): string => {
      let eventType = 'message';
      const dataLines: string[] = [];
      for (const line of rawEvent.split('\n')) {
        if (line.startsWith(':')) continue; // keepalive comment
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trim());
        }
      }

      if (dataLines.length > 0) {
        if (eventType === 'connected') {
          try {
            const parsed = JSON.parse(dataLines.join('\n'));
            if (typeof parsed.unread_count === 'number') {
              callbacksRef.current.onConnected(parsed.unread_count);
            }
          } catch (e) {
            console.error('[NotifSSE] Failed to parse connected event:', e);
          }
        } else if (eventType === 'notification') {
          try {
            const item = JSON.parse(
              dataLines.join('\n'),
            ) as SocialNotificationItem;
            callbacksRef.current.onNotification(item);
          } catch (e) {
            console.error('[NotifSSE] Failed to parse notification:', e);
          }
        }
      }
      return eventType;
    };

    const connect = async () => {
      if (stopped) return;

      controller = new AbortController();
      let sawServerTimeout = false;

      try {
        const API_BASE_URL =
          process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin;
        const url = `${API_BASE_URL}/api/v1/realtime/notifications`;

        const response = await authenticatedFetch(url, {
          signal: controller.signal,
          headers: { Accept: 'text/event-stream' },
        });

        if (!response.ok || !response.body) {
          throw new Error(`SSE request failed with status ${response.status}`);
        }

        reconnectAttempts = 0;
        callbacksRef.current.onConnect?.();

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          let sepIndex;
          while ((sepIndex = buffer.indexOf('\n\n')) >= 0) {
            const rawEvent = buffer.slice(0, sepIndex);
            buffer = buffer.slice(sepIndex + 2);
            if (dispatchEvent(rawEvent) === 'timeout') {
              sawServerTimeout = true;
            }
          }
        }

        if (stopped) return;
        // A server-side timeout is the normal bounded-lifetime close.
        callbacksRef.current.onDisconnect?.();
        scheduleReconnect(sawServerTimeout);
      } catch (error) {
        if (stopped || (error as Error).name === 'AbortError') return;
        console.error('[NotifSSE] Connection error:', error);
        callbacksRef.current.onDisconnect?.();
        scheduleReconnect(false);
      }
    };

    connect();

    return () => {
      stopped = true;
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      controller?.abort();
    };
  }, [enabled]);
}

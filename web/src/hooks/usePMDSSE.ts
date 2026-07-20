import { useEffect, useRef } from 'react';
import { authenticatedFetch } from '../lib/api';

export interface BDRItem {
  id: string;
  status: 'pending' | 'processing' | 'ready' | 'failed' | 'expired';
  artwork_count: number;
  created_at: string;
  completed_at: string | null;
  expires_at: string | null;
  error_message: string | null;
  download_url: string | null;
}

interface UsePMDSSEOptions {
  enabled: boolean;
  targetSqid?: string | null; // For moderator cross-user access
  onBDRUpdate: (bdr: BDRItem) => void;
  onError?: (error: Error) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

/**
 * Subscribe to BDR status updates from GET /api/pmd/bdr/sse.
 *
 * Uses a fetch() streaming reader instead of the native EventSource because
 * the API authenticates via the Authorization header, which EventSource
 * cannot send. authenticatedFetch also gives us token refresh for free.
 *
 * The server closes the stream after ~5 minutes (sending a `timeout` event
 * first); that is a normal bounded-lifetime close and we reconnect
 * immediately. Unexpected errors reconnect with exponential backoff, giving
 * up after 5 consecutive failures.
 */
export function usePMDSSE({
  enabled,
  targetSqid,
  onBDRUpdate,
  onError,
  onConnect,
  onDisconnect,
}: UsePMDSSEOptions) {
  // Keep the latest callbacks in a ref so their identity doesn't force
  // the connection effect to tear down and reconnect on every render.
  const callbacksRef = useRef({ onBDRUpdate, onError, onConnect, onDisconnect });
  callbacksRef.current = { onBDRUpdate, onError, onConnect, onDisconnect };

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
        console.log('[SSE] Max reconnect attempts reached');
        callbacksRef.current.onError?.(
          new Error('SSE connection failed after max retries'),
        );
        return;
      }
      const delay = baseReconnectDelay * Math.pow(2, reconnectAttempts);
      reconnectAttempts += 1;
      console.log(
        `[SSE] Scheduling reconnect in ${delay}ms (attempt ${reconnectAttempts})`,
      );
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

      if (eventType === 'bdr_update' && dataLines.length > 0) {
        try {
          const bdr = JSON.parse(dataLines.join('\n')) as BDRItem;
          callbacksRef.current.onBDRUpdate(bdr);
        } catch (e) {
          console.error('[SSE] Failed to parse BDR update:', e);
        }
      } else if (eventType === 'connected') {
        console.log('[SSE] Connected');
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
        let url = `${API_BASE_URL}/api/pmd/bdr/sse`;
        if (targetSqid) {
          url += `?target_sqid=${encodeURIComponent(targetSqid)}`;
        }

        const response = await authenticatedFetch(url, {
          signal: controller.signal,
          headers: { Accept: 'text/event-stream' },
        });

        if (!response.ok || !response.body) {
          throw new Error(`SSE request failed with status ${response.status}`);
        }

        console.log('[SSE] Connection opened');
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
        console.log(
          sawServerTimeout
            ? '[SSE] Server timeout, reconnecting...'
            : '[SSE] Stream ended unexpectedly',
        );
        callbacksRef.current.onDisconnect?.();
        scheduleReconnect(sawServerTimeout);
      } catch (error) {
        if (stopped || (error as Error).name === 'AbortError') return;
        console.error('[SSE] Connection error:', error);
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
  }, [enabled, targetSqid]);
}

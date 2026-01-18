import { useEffect, useRef, useCallback } from 'react';

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
  targetSqid?: string | null;  // For moderator cross-user access
  onBDRUpdate: (bdr: BDRItem) => void;
  onError?: (error: Error) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

export function usePMDSSE({
  enabled,
  targetSqid,
  onBDRUpdate,
  onError,
  onConnect,
  onDisconnect,
}: UsePMDSSEOptions) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  const baseReconnectDelay = 1000; // 1 second

  const scheduleReconnect = useCallback(() => {
    if (reconnectAttempts.current >= maxReconnectAttempts) {
      console.log('[SSE] Max reconnect attempts reached');
      onError?.(new Error('SSE connection failed after max retries'));
      return;
    }

    const delay = baseReconnectDelay * Math.pow(2, reconnectAttempts.current);
    reconnectAttempts.current += 1;

    console.log(`[SSE] Scheduling reconnect in ${delay}ms (attempt ${reconnectAttempts.current})`);

    reconnectTimeoutRef.current = setTimeout(() => {
      connect();
    }, delay);
  }, [onError]);

  const connect = useCallback(() => {
    // Don't connect if disabled, already connected, or on server
    if (!enabled || eventSourceRef.current || typeof window === 'undefined') {
      return;
    }

    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin;
    let url = `${API_BASE_URL}/api/pmd/bdr/sse`;
    if (targetSqid) {
      url += `?target_sqid=${encodeURIComponent(targetSqid)}`;
    }

    try {
      const eventSource = new EventSource(url, {
        withCredentials: true, // Send cookies for auth
      });

      eventSource.onopen = () => {
        console.log('[SSE] Connection opened');
        reconnectAttempts.current = 0;
        onConnect?.();
      };

      eventSource.addEventListener('connected', (event) => {
        console.log('[SSE] Connected:', (event as MessageEvent).data);
      });

      eventSource.addEventListener('bdr_update', (event) => {
        try {
          const bdr = JSON.parse((event as MessageEvent).data) as BDRItem;
          onBDRUpdate(bdr);
        } catch (e) {
          console.error('[SSE] Failed to parse BDR update:', e);
        }
      });

      eventSource.addEventListener('timeout', () => {
        console.log('[SSE] Server timeout, reconnecting...');
        eventSource.close();
        scheduleReconnect();
      });

      eventSource.onerror = (error) => {
        console.error('[SSE] Connection error:', error);
        eventSource.close();
        eventSourceRef.current = null;
        onDisconnect?.();

        // Schedule reconnect with exponential backoff
        scheduleReconnect();
      };

      eventSourceRef.current = eventSource;
    } catch (error) {
      console.error('[SSE] Failed to create EventSource:', error);
      onError?.(error as Error);
    }
  }, [enabled, targetSqid, onBDRUpdate, onError, onConnect, onDisconnect, scheduleReconnect]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      onDisconnect?.();
    }
  }, [onDisconnect]);

  // Connect when enabled or targetSqid changes
  useEffect(() => {
    if (enabled) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, targetSqid, connect, disconnect]);

  return {
    isConnected: typeof window !== 'undefined' && eventSourceRef.current?.readyState === EventSource.OPEN,
    reconnect: connect,
    disconnect,
  };
}

# Server-Sent Events (SSE) for BDR Updates

## Overview

SSE provides real-time updates to the frontend when BDR status changes. This allows the PMD to automatically display new download links without manual page refresh.

## Architecture

```
┌─────────────────┐     SSE Connection     ┌─────────────────┐
│    Frontend     │◄──────────────────────│  FastAPI SSE    │
│  (PMD Page)     │                        │   Endpoint      │
└─────────────────┘                        └────────┬────────┘
                                                    │
                                                    │ Polls DB
                                                    │ every 5s
                                                    ▼
                                           ┌─────────────────┐
                                           │    Database     │
                                           │   (BDR table)   │
                                           └─────────────────┘
```

### Why Polling in Backend?

For simplicity, the SSE endpoint polls the database instead of using Redis pub/sub or a message queue. Reasons:

1. BDR updates are infrequent (minutes between events)
2. Simple implementation with no additional infrastructure
3. User typically has one PMD tab open at a time
4. 5-second polling interval is acceptable for this use case

For higher scale, Redis pub/sub could be added later.

---

## Backend Implementation

### SSE Endpoint

Add to `api/app/routers/pmd.py`:

```python
import asyncio
from datetime import datetime, timezone
from typing import AsyncGenerator
from fastapi import Request
from fastapi.responses import StreamingResponse


@router.get("/bdr/sse")
async def bdr_sse_stream(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Server-Sent Events stream for BDR status updates.
    
    The client connects and receives updates whenever a BDR's status changes.
    Events are sent as JSON with the BDR data.
    
    Connection stays open until client disconnects or server timeout (5 minutes).
    
    Event format:
        event: bdr_update
        data: {"id": "...", "status": "ready", ...}
    """
    
    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events."""
        
        # Track last known states to detect changes
        last_states: dict[str, tuple[str, datetime | None]] = {}
        
        # Send initial state immediately
        initial_bdrs = get_user_bdrs(db, current_user.id)
        for bdr in initial_bdrs:
            last_states[str(bdr.id)] = (bdr.status, bdr.completed_at)
            yield format_sse_event("bdr_update", bdr_to_dict(bdr))
        
        # Send heartbeat to confirm connection
        yield format_sse_event("connected", {"message": "SSE connection established"})
        
        timeout_at = datetime.now(timezone.utc).timestamp() + 300  # 5 minute timeout
        poll_interval = 5  # seconds
        
        while datetime.now(timezone.utc).timestamp() < timeout_at:
            # Check if client disconnected
            if await request.is_disconnected():
                break
            
            # Wait before next poll
            await asyncio.sleep(poll_interval)
            
            # Refresh database session
            db.expire_all()
            
            # Check for updates
            current_bdrs = get_user_bdrs(db, current_user.id)
            
            for bdr in current_bdrs:
                bdr_id = str(bdr.id)
                current_state = (bdr.status, bdr.completed_at)
                
                # Check if state changed
                if bdr_id not in last_states or last_states[bdr_id] != current_state:
                    last_states[bdr_id] = current_state
                    yield format_sse_event("bdr_update", bdr_to_dict(bdr))
            
            # Send periodic keepalive (comment line)
            yield ": keepalive\n\n"
        
        # Connection timeout - send close event
        yield format_sse_event("timeout", {"message": "Connection timeout, please reconnect"})
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


def get_user_bdrs(db: Session, user_id: int) -> list[models.BatchDownloadRequest]:
    """Get user's recent BDRs (for SSE updates)."""
    return (
        db.query(models.BatchDownloadRequest)
        .filter(models.BatchDownloadRequest.user_id == user_id)
        .order_by(models.BatchDownloadRequest.created_at.desc())
        .limit(20)
        .all()
    )


def bdr_to_dict(bdr: models.BatchDownloadRequest) -> dict:
    """Convert BDR to dictionary for SSE event."""
    download_url = None
    if bdr.status == "ready" and bdr.file_path:
        download_url = f"/api/pmd/bdr/{bdr.id}/download"
    
    return {
        "id": str(bdr.id),
        "status": bdr.status,
        "artwork_count": bdr.artwork_count,
        "created_at": bdr.created_at.isoformat() if bdr.created_at else None,
        "completed_at": bdr.completed_at.isoformat() if bdr.completed_at else None,
        "expires_at": bdr.expires_at.isoformat() if bdr.expires_at else None,
        "error_message": bdr.error_message,
        "download_url": download_url,
    }


def format_sse_event(event_type: str, data: dict) -> str:
    """Format data as SSE event string."""
    import json
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
```

---

## Frontend Implementation

### SSE Hook

Create `web/src/hooks/usePMDSSE.ts`:

```typescript
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
  onBDRUpdate: (bdr: BDRItem) => void;
  onError?: (error: Error) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
}

export function usePMDSSE({
  enabled,
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

  const connect = useCallback(() => {
    // Don't connect if disabled or already connected
    if (!enabled || eventSourceRef.current) {
      return;
    }

    const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '';
    const url = `${API_BASE_URL}/api/pmd/bdr/sse`;

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
        console.log('[SSE] Connected:', event.data);
      });

      eventSource.addEventListener('bdr_update', (event) => {
        try {
          const bdr = JSON.parse(event.data) as BDRItem;
          onBDRUpdate(bdr);
        } catch (e) {
          console.error('[SSE] Failed to parse BDR update:', e);
        }
      });

      eventSource.addEventListener('timeout', (event) => {
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
  }, [enabled, onBDRUpdate, onError, onConnect, onDisconnect]);

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
  }, [connect, onError]);

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

  // Connect when enabled changes
  useEffect(() => {
    if (enabled) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [enabled, connect, disconnect]);

  return {
    isConnected: eventSourceRef.current?.readyState === EventSource.OPEN,
    reconnect: connect,
    disconnect,
  };
}
```

### Usage in PMD Component

```typescript
// In PMD page component
import { usePMDSSE, BDRItem } from '../../hooks/usePMDSSE';

function PMDPage() {
  const [bdrs, setBdrs] = useState<BDRItem[]>([]);
  const [sseConnected, setSseConnected] = useState(false);

  // Handle BDR updates from SSE
  const handleBDRUpdate = useCallback((updatedBdr: BDRItem) => {
    setBdrs((prev) => {
      const index = prev.findIndex((b) => b.id === updatedBdr.id);
      if (index >= 0) {
        // Update existing BDR
        const newBdrs = [...prev];
        newBdrs[index] = updatedBdr;
        return newBdrs;
      } else {
        // Add new BDR at the beginning
        return [updatedBdr, ...prev];
      }
    });

    // Show toast notification for ready/failed status
    if (updatedBdr.status === 'ready') {
      toast.success(`Download ready! ${updatedBdr.artwork_count} artworks`);
    } else if (updatedBdr.status === 'failed') {
      toast.error(`Download failed: ${updatedBdr.error_message || 'Unknown error'}`);
    }
  }, []);

  // SSE connection
  usePMDSSE({
    enabled: true, // Could be tied to page visibility
    onBDRUpdate: handleBDRUpdate,
    onConnect: () => setSseConnected(true),
    onDisconnect: () => setSseConnected(false),
    onError: (error) => {
      console.error('SSE error:', error);
      // Could show a toast or status indicator
    },
  });

  // ... rest of component
}
```

---

## SSE Event Types

| Event | Description | Data |
|-------|-------------|------|
| `connected` | Connection established | `{ message: string }` |
| `bdr_update` | BDR status changed | `BDRItem` object |
| `timeout` | Server-side timeout | `{ message: string }` |

---

## Error Handling

### Backend Errors

1. **Authentication failure**: Return 401, don't stream
2. **Database errors**: Log and continue polling
3. **Connection timeout**: Send `timeout` event, close stream

### Frontend Errors

1. **Connection refused**: Retry with exponential backoff (max 5 attempts)
2. **Parse errors**: Log and ignore malformed events
3. **Auth expired**: Close connection, redirect to login

---

## Testing SSE

### Manual Testing with curl

```bash
# Test SSE connection
curl -N -H "Cookie: access_token=..." \
  "http://localhost:8000/api/pmd/bdr/sse"
```

### Expected Output

```
event: bdr_update
data: {"id":"abc123","status":"pending","artwork_count":5,...}

event: connected
data: {"message":"SSE connection established"}

: keepalive

event: bdr_update
data: {"id":"abc123","status":"ready","artwork_count":5,...}
```

---

## Performance Considerations

1. **Connection limit**: Each SSE connection holds a database connection. Consider connection pooling.

2. **Proxy buffering**: Ensure nginx/reverse proxy doesn't buffer SSE. Use headers:
   ```
   X-Accel-Buffering: no
   ```

3. **Timeout**: 5-minute server timeout prevents zombie connections. Client should reconnect.

4. **Memory**: `last_states` dict is bounded by number of BDRs per user (max 20).

---

## Future Enhancements (Out of Scope)

1. **Redis pub/sub**: For horizontal scaling, workers could publish to Redis, SSE endpoints subscribe
2. **WebSocket**: For bidirectional communication (not needed for PMD)
3. **Page visibility**: Pause SSE when tab is hidden to save resources

# Piskel Integration Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           User's Browser                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────┐         postMessage         ┌────────────────┐ │
│  │                     │  ◄────────────────────────► │                │ │
│  │   Makapix Club      │                             │   Piskel       │ │
│  │   (Next.js)         │                             │   (Vanilla JS) │ │
│  │                     │                             │                │ │
│  │   dev.makapix.club  │                             │ piskel.makapix │ │
│  │                     │                             │   .club        │ │
│  └─────────────────────┘                             └────────────────┘ │
│           │                                                   │         │
└───────────┼───────────────────────────────────────────────────┼─────────┘
            │                                                   │
            ▼                                                   ▼
    ┌───────────────┐                                   ┌───────────────┐
    │ Makapix API   │                                   │ Static Files  │
    │ /api/post/*   │                                   │ (Caddy)       │
    └───────────────┘                                   └───────────────┘
```

## Data Flow Scenarios

### Scenario 1: Create New Artwork

```
User clicks 🖌️ → Makapix checks auth → Redirect to Piskel with auth context
                                              │
                                              ▼
                                        User creates art
                                              │
                                              ▼
                                     User clicks "Publish"
                                              │
                                              ▼
                          Piskel generates GIF blob + sends postMessage
                                              │
                                              ▼
                 Makapix /submit receives blob → pre-populates form
                                              │
                                              ▼
                              User fills metadata → Submit
                                              │
                                              ▼
                                    POST /api/post/upload
```

### Scenario 2: Edit Existing Artwork

```
User views artwork → Clicks "Edit in Piskel" → Makapix stores post info
                                                        │
                                                        ▼
                               Redirect to Piskel with artwork URL + post sqid
                                                        │
                                                        ▼
                                      Piskel loads and imports image
                                                        │
                                                        ▼
                                              User edits artwork
                                                        │
                                                        ▼
                                      User clicks "Save to Makapix"
                                                        │
                                                        ▼
                                 Dialog: "Replace original" or "New post"
                                                        │
                           ┌────────────────────────────┼────────────────────────────┐
                           ▼                                                         ▼
                    Replace: POST with                                    New: Redirect to /submit
                    original post ID                                      with blob (same as Scenario 1)
```

## postMessage Protocol

### Messages from Piskel → Makapix

```typescript
// Export artwork for publishing
interface PiskelExportMessage {
  type: 'PISKEL_EXPORT';
  blob: Blob;           // GIF image data
  name: string;         // Artwork name from Piskel
  width: number;        // Canvas width
  height: number;       // Canvas height
  frameCount: number;   // Number of animation frames
  fps: number;          // Frames per second
}

// Replace existing artwork
interface PiskelReplaceMessage {
  type: 'PISKEL_REPLACE';
  blob: Blob;
  originalPostSqid: string;  // The post being replaced
  name: string;
  width: number;
  height: number;
  frameCount: number;
  fps: number;
}

// Piskel ready notification
interface PiskelReadyMessage {
  type: 'PISKEL_READY';
}

// Request auth token refresh
interface PiskelAuthRefreshRequest {
  type: 'PISKEL_AUTH_REFRESH_REQUEST';
}
```

### Messages from Makapix → Piskel

```typescript
// Initialize Piskel with context
interface MakapixInitMessage {
  type: 'MAKAPIX_INIT';
  accessToken: string;
  userSqid: string;
  editMode?: {
    postSqid: string;
    artworkUrl: string;
    title: string;
  };
}

// Auth token refreshed
interface MakapixAuthRefreshedMessage {
  type: 'MAKAPIX_AUTH_REFRESHED';
  accessToken: string;
}

// Cancel/close editor
interface MakapixCloseMessage {
  type: 'MAKAPIX_CLOSE';
}
```

## Authentication Flow

### Initial Auth Check (Makapix Side)

1. User clicks 🖌️ button in header
2. Check if `access_token` exists in localStorage
3. If not authenticated → redirect to `/auth?redirect=/editor`
4. If authenticated → navigate to `/editor` (Piskel iframe page)

### Token Passing to Piskel

1. Makapix `/editor` page loads Piskel in iframe
2. On `PISKEL_READY` message, send `MAKAPIX_INIT` with current access token
3. Piskel stores token for API calls

### Long Session Token Refresh

```
Piskel detects token expired (or proactive check)
                    │
                    ▼
    postMessage: PISKEL_AUTH_REFRESH_REQUEST
                    │
                    ▼
    Makapix calls refreshAccessToken() from lib/api.ts
                    │
                    ▼
    On success: postMessage MAKAPIX_AUTH_REFRESHED with new token
                    │
                    ▼
    Piskel updates stored token
```

### Proactive Token Refresh

To handle users who spend hours drawing:

1. Piskel checks token expiry every 5 minutes
2. If token expires within 10 minutes, request refresh
3. Makapix's existing refresh mechanism handles the actual refresh
4. This ensures seamless experience during long sessions

## File Format Considerations

### Export Format: GIF

Piskel natively exports animated GIFs. Makapix accepts:
- PNG (static)
- GIF (animated)
- WebP (static or animated)

**Decision**: Use GIF as the transfer format since:
1. Piskel has robust GIF export via gif.js library
2. Makapix API accepts GIF (`image/gif` in `ALLOWED_MIME_TYPES`)
3. Preserves animation frames and timing

### Dimension Constraints

Makapix has specific dimension rules:
- Maximum: 256×256
- Under 128×128: Only specific sizes allowed (8×8, 16×16, 32×32, etc.)
- 128×128 to 256×256: Any size allowed

**Implementation**:
- Piskel's `Constants.MAX_WIDTH` and `Constants.MAX_HEIGHT` set to 256
- UI warning/validation for non-standard sizes under 128×128

## Security Considerations

### Origin Validation

All postMessage handlers must validate origin:

```javascript
// Makapix side
window.addEventListener('message', (event) => {
  if (event.origin !== 'https://piskel.makapix.club') return;
  // Handle message
});

// Piskel side
window.addEventListener('message', (event) => {
  if (event.origin !== 'https://dev.makapix.club') return;
  // Handle message
});
```

### Token Security

- Access tokens are short-lived (passed via postMessage, not URL)
- Refresh tokens remain in HttpOnly cookies (handled by Makapix)
- Piskel never sees refresh tokens
- Token refresh is proxied through Makapix

### CORS Configuration

Piskel at `piskel.makapix.club` may need to load artwork images from:
- `dev.makapix.club/api/vault/...` (HTTPS vault)

Existing vault CORS headers should suffice:
```
Access-Control-Allow-Origin: *
```

## State Management

### Browser Storage (Piskel side)

```javascript
// Piskel uses IndexedDB for auto-save
// We add Makapix-specific state in sessionStorage:
sessionStorage.setItem('makapix_access_token', token);
sessionStorage.setItem('makapix_edit_mode', JSON.stringify({
  postSqid: '...',
  artworkUrl: '...',
  title: '...'
}));
```

### URL Parameters (for direct links)

```
https://piskel.makapix.club/?edit=<post_sqid>
```

When `edit` parameter present:
1. Piskel waits for MAKAPIX_INIT message
2. Uses artwork URL from init message to load image
3. Enables "Save" options that include "Replace original"

## Error Handling

### Network Failures

| Scenario | Handling |
|----------|----------|
| Piskel fails to load | Show error in iframe container with retry button |
| Token refresh fails (transient) | Retry with exponential backoff |
| Token refresh fails (auth) | Show "Session expired" → redirect to /auth |
| Export upload fails | Show error in submit form, allow retry |

### User Abandonment

- Piskel has built-in auto-save to IndexedDB
- Unsaved work warning via `beforeunload` event
- Recovery available via "Browse Local" in Piskel


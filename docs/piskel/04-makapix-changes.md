# Makapix Club Changes

This document details all modifications to be made to the Makapix Club codebase for Piskel integration.

## File Changes Overview

```
web/src/
├── components/
│   └── Layout.tsx              # MODIFIED: Add 🖌️ button
├── pages/
│   ├── editor.tsx              # NEW: Piskel iframe host page
│   ├── submit.tsx              # MODIFIED: Accept pre-attached images
│   └── p/
│       └── [sqid].tsx          # MODIFIED: Add "Edit in Piskel" button
└── lib/
    └── piskel-messages.ts      # NEW: postMessage type definitions

api/app/
└── routers/
    └── posts.py                # MODIFIED: Add replace-artwork endpoint
```

---

## New Files

### 1. `web/src/pages/editor.tsx`

```tsx
import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/router';
import Head from 'next/head';
import { 
  authenticatedFetch, 
  refreshAccessToken, 
  getAccessToken, 
  clearTokens 
} from '../lib/api';

const PISKEL_ORIGIN = 'https://piskel.makapix.club';

interface EditContext {
  postSqid: string;
  artworkUrl: string;
  title: string;
}

interface Post {
  id: number;
  public_sqid: string;
  title: string;
  art_url: string;
}

export default function EditorPage() {
  const router = useRouter();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editContext, setEditContext] = useState<EditContext | null>(null);
  const [piskelReady, setPiskelReady] = useState(false);

  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Check authentication on mount
  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      // Redirect to auth with return URL
      router.push(`/auth?redirect=${encodeURIComponent('/editor' + window.location.search)}`);
      return;
    }
    setIsAuthenticated(true);
  }, [router]);

  // Load edit context if editing existing artwork
  useEffect(() => {
    if (!isAuthenticated) return;

    const editSqid = router.query.edit as string;
    if (!editSqid) {
      setIsLoading(false);
      return;
    }

    // Fetch post data
    authenticatedFetch(`${API_BASE_URL}/api/p/${editSqid}`)
      .then(res => {
        if (res.status === 401) {
          clearTokens();
          router.push('/auth');
          return null;
        }
        if (!res.ok) throw new Error('Failed to load artwork');
        return res.json();
      })
      .then((post: Post | null) => {
        if (post) {
          setEditContext({
            postSqid: post.public_sqid,
            artworkUrl: post.art_url,
            title: post.title,
          });
        }
        setIsLoading(false);
      })
      .catch(err => {
        console.error('Failed to load edit context:', err);
        setError('Failed to load artwork for editing');
        setIsLoading(false);
      });
  }, [isAuthenticated, router.query.edit, API_BASE_URL, router]);

  // Handle messages from Piskel
  useEffect(() => {
    const handleMessage = async (event: MessageEvent) => {
      if (event.origin !== PISKEL_ORIGIN) return;

      const data = event.data;
      if (!data || !data.type) return;

      switch (data.type) {
        case 'PISKEL_READY':
          setPiskelReady(true);
          sendInitMessage();
          break;

        case 'PISKEL_AUTH_REFRESH_REQUEST':
          await handleAuthRefresh();
          break;

        case 'PISKEL_EXPORT':
          await handleExport(data);
          break;

        case 'PISKEL_REPLACE':
          await handleReplace(data);
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [editContext]);

  const sendInitMessage = useCallback(() => {
    const token = getAccessToken();
    const publicSqid = localStorage.getItem('public_sqid');

    if (!iframeRef.current?.contentWindow || !token) return;

    const message: any = {
      type: 'MAKAPIX_INIT',
      accessToken: token,
      userSqid: publicSqid,
    };

    if (editContext) {
      message.editMode = editContext;
    }

    iframeRef.current.contentWindow.postMessage(message, PISKEL_ORIGIN);
  }, [editContext]);

  const handleAuthRefresh = async () => {
    const success = await refreshAccessToken();
    
    if (success) {
      const newToken = getAccessToken();
      if (iframeRef.current?.contentWindow && newToken) {
        iframeRef.current.contentWindow.postMessage({
          type: 'MAKAPIX_AUTH_REFRESHED',
          accessToken: newToken,
        }, PISKEL_ORIGIN);
      }
    } else {
      // Refresh failed - redirect to auth
      clearTokens();
      router.push(`/auth?redirect=${encodeURIComponent('/editor')}`);
    }
  };

  const handleExport = async (data: any) => {
    // Store export data in sessionStorage for submit page
    try {
      // Convert blob to base64 for storage
      const reader = new FileReader();
      reader.onload = () => {
        const exportData = {
          imageData: reader.result,
          name: data.name,
          width: data.width,
          height: data.height,
          frameCount: data.frameCount,
          fps: data.fps,
          timestamp: Date.now(),
        };
        sessionStorage.setItem('piskel_export', JSON.stringify(exportData));
        router.push('/submit?from=piskel');
      };
      reader.readAsDataURL(data.blob);
    } catch (err) {
      console.error('Failed to process export:', err);
      alert('Failed to process artwork. Please try again.');
    }
  };

  const handleReplace = async (data: any) => {
    if (!data.originalPostSqid) {
      console.error('No original post to replace');
      return;
    }

    try {
      // First, get the post ID from sqid
      const postRes = await authenticatedFetch(`${API_BASE_URL}/api/p/${data.originalPostSqid}`);
      if (!postRes.ok) throw new Error('Failed to find original post');
      const post = await postRes.json();

      // Upload replacement
      const formData = new FormData();
      formData.append('image', data.blob, `${data.name || 'artwork'}.gif`);

      const response = await authenticatedFetch(
        `${API_BASE_URL}/api/post/${post.id}/replace-artwork`,
        {
          method: 'POST',
          body: formData,
        }
      );

      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Replace failed' }));
        throw new Error(errorData.detail || 'Replace failed');
      }

      // Success - navigate to the post
      router.push(`/p/${data.originalPostSqid}`);
    } catch (err) {
      console.error('Failed to replace artwork:', err);
      alert(err instanceof Error ? err.message : 'Failed to replace artwork');
    }
  };

  // Send init message when Piskel becomes ready and edit context is loaded
  useEffect(() => {
    if (piskelReady && !isLoading) {
      sendInitMessage();
    }
  }, [piskelReady, isLoading, sendInitMessage]);

  if (!isAuthenticated) {
    return (
      <div className="editor-loading">
        <p>Checking authentication...</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="editor-loading">
        <div className="spinner"></div>
        <p>Loading editor...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="editor-error">
        <p>{error}</p>
        <button onClick={() => router.push('/')}>Go Home</button>
      </div>
    );
  }

  const piskelUrl = editContext 
    ? `${PISKEL_ORIGIN}/?edit=${editContext.postSqid}`
    : PISKEL_ORIGIN;

  return (
    <>
      <Head>
        <title>Pixel Art Editor - Makapix Club</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className="editor-container">
        <iframe
          ref={iframeRef}
          src={piskelUrl}
          className="piskel-iframe"
          title="Piskel Editor"
          allow="clipboard-write"
        />
      </div>

      <style jsx>{`
        .editor-container {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: #000;
        }

        .piskel-iframe {
          width: 100%;
          height: 100%;
          border: none;
        }

        .editor-loading,
        .editor-error {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          height: 100vh;
          background: #000;
          color: #fff;
          gap: 16px;
        }

        .spinner {
          width: 40px;
          height: 40px;
          border: 3px solid #333;
          border-top-color: #00d4ff;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .editor-error button {
          padding: 12px 24px;
          background: #00d4ff;
          color: #000;
          border: none;
          border-radius: 8px;
          font-weight: 600;
          cursor: pointer;
        }
      `}</style>
    </>
  );
}
```

### 2. `web/src/lib/piskel-messages.ts`

```typescript
/**
 * Type definitions for Piskel ↔ Makapix postMessage protocol
 */

// Messages FROM Piskel TO Makapix
export interface PiskelReadyMessage {
  type: 'PISKEL_READY';
}

export interface PiskelExportMessage {
  type: 'PISKEL_EXPORT';
  blob: Blob;
  name: string;
  width: number;
  height: number;
  frameCount: number;
  fps: number;
}

export interface PiskelReplaceMessage {
  type: 'PISKEL_REPLACE';
  blob: Blob;
  originalPostSqid: string;
  name: string;
  width: number;
  height: number;
  frameCount: number;
  fps: number;
}

export interface PiskelAuthRefreshRequest {
  type: 'PISKEL_AUTH_REFRESH_REQUEST';
}

export type PiskelMessage = 
  | PiskelReadyMessage 
  | PiskelExportMessage 
  | PiskelReplaceMessage 
  | PiskelAuthRefreshRequest;

// Messages FROM Makapix TO Piskel
export interface MakapixInitMessage {
  type: 'MAKAPIX_INIT';
  accessToken: string;
  userSqid: string | null;
  editMode?: {
    postSqid: string;
    artworkUrl: string;
    title: string;
  };
}

export interface MakapixAuthRefreshedMessage {
  type: 'MAKAPIX_AUTH_REFRESHED';
  accessToken: string;
}

export interface MakapixCloseMessage {
  type: 'MAKAPIX_CLOSE';
}

export type MakapixMessage = 
  | MakapixInitMessage 
  | MakapixAuthRefreshedMessage 
  | MakapixCloseMessage;

// Constants
export const PISKEL_ORIGIN = 'https://piskel.makapix.club';
```

---

## Modified Files

### 3. `web/src/components/Layout.tsx`

**Changes:**
- Add 🖌️ "Create" button to header navigation
- Position it prominently in the nav section

```diff
 const navItems: NavItem[] = [
+  { 
+    href: '/editor', 
+    icon: '🖌️', 
+    label: 'Create',
+    matchPaths: ['/editor']
+  },
   { 
     href: '/submit', 
     icon: '➕', 
     label: 'Submit',
     matchPaths: ['/submit']
   },
```

Also update the click handler to require authentication for the editor:

```diff
 {navItems.map((item) => {
   const active = isActive(item);
-  // For Recent artworks (/), redirect unauthenticated users to /welcome
   const handleClick = (e: React.MouseEvent) => {
     if (item.href === '/' && !isLoggedIn) {
       e.preventDefault();
       markWelcomeAsInternalNav();
       router.push('/welcome');
     }
+    // Editor requires authentication
+    if (item.href === '/editor' && !isLoggedIn) {
+      e.preventDefault();
+      router.push('/auth?redirect=/editor');
+    }
   };
```

### 4. `web/src/pages/submit.tsx`

**Changes:**
- Accept pre-attached image from Piskel export
- Auto-populate form fields

Add at the top of the component:

```diff
 export default function SubmitPage() {
   const router = useRouter();
   const fileInputRef = useRef<HTMLInputElement>(null);
+  const [fromPiskel, setFromPiskel] = useState(false);
   
   // ... existing state ...

+  // Check for Piskel export data
+  useEffect(() => {
+    if (router.query.from !== 'piskel') return;
+    
+    try {
+      const exportDataStr = sessionStorage.getItem('piskel_export');
+      if (!exportDataStr) return;
+      
+      const exportData = JSON.parse(exportDataStr);
+      
+      // Check if data is recent (within 5 minutes)
+      if (Date.now() - exportData.timestamp > 5 * 60 * 1000) {
+        sessionStorage.removeItem('piskel_export');
+        return;
+      }
+      
+      setFromPiskel(true);
+      
+      // Convert base64 back to File
+      const byteString = atob(exportData.imageData.split(',')[1]);
+      const mimeType = exportData.imageData.split(',')[0].split(':')[1].split(';')[0];
+      const ab = new ArrayBuffer(byteString.length);
+      const ia = new Uint8Array(ab);
+      for (let i = 0; i < byteString.length; i++) {
+        ia[i] = byteString.charCodeAt(i);
+      }
+      const blob = new Blob([ab], { type: mimeType });
+      const file = new File([blob], `${exportData.name || 'artwork'}.gif`, { type: mimeType });
+      
+      // Set file and preview
+      setSelectedFile(file);
+      setPreviewUrl(exportData.imageData);
+      setImageDimensions({ width: exportData.width, height: exportData.height });
+      setTitle(exportData.name || '');
+      
+      // Validate
+      const fileErrors = validateFile(file);
+      const dimErrors = validateImageDimensions(exportData.width, exportData.height);
+      setValidationErrors([...fileErrors, ...dimErrors]);
+      
+      // Clear the stored data
+      sessionStorage.removeItem('piskel_export');
+    } catch (err) {
+      console.error('Failed to load Piskel export:', err);
+    }
+  }, [router.query.from, validateFile, validateImageDimensions]);
```

Update the UI to show Piskel origin:

```diff
 return (
   <Layout title="Submit Artwork" description="Upload your pixel art">
     <div className="submit-container">
-      <h1 className="page-title">Submit Artwork</h1>
+      <h1 className="page-title">
+        {fromPiskel ? '🖌️ Publish Artwork' : 'Submit Artwork'}
+      </h1>
+      
+      {fromPiskel && (
+        <div className="piskel-notice">
+          <span>✨ Artwork from Piskel ready to publish!</span>
+        </div>
+      )}

       <div className="import-row">
```

Add styling:

```diff
+        .piskel-notice {
+          text-align: center;
+          margin-bottom: 20px;
+          padding: 12px 16px;
+          background: linear-gradient(135deg, rgba(255, 110, 180, 0.15), rgba(180, 78, 255, 0.15));
+          border: 1px solid rgba(255, 110, 180, 0.3);
+          border-radius: 12px;
+          color: var(--accent-pink);
+          font-weight: 500;
+        }
```

### 5. `web/src/pages/p/[sqid].tsx`

**Changes:**
- Add "Edit in Piskel" button for artwork owners

Find the owner actions section and add the edit button:

```diff
           {isOwner && !isEditing && (
             <div className="owner-actions">
+              <button
+                onClick={() => router.push(`/editor?edit=${post.public_sqid}`)}
+                className="action-button piskel-edit"
+                title="Edit in Piskel"
+              >
+                🖌️ Edit in Piskel
+              </button>
               <button
                 onClick={handleHide}
```

Add styling:

```diff
+            .action-button.piskel-edit {
+              background: linear-gradient(135deg, rgba(255, 110, 180, 0.2), rgba(180, 78, 255, 0.2));
+              border: 1px solid rgba(255, 110, 180, 0.4);
+              color: var(--accent-pink);
+            }
+
+            .action-button.piskel-edit:hover {
+              background: linear-gradient(135deg, rgba(255, 110, 180, 0.3), rgba(180, 78, 255, 0.3));
+              box-shadow: 0 0 20px rgba(255, 110, 180, 0.3);
+            }
```

---

## Backend Changes

### 6. `api/app/routers/posts.py`

**Add new endpoint for replacing artwork:**

```python
@router.post(
    "/{id}/replace-artwork",
    response_model=schemas.Post,
    status_code=status.HTTP_200_OK,
)
async def replace_artwork(
    request: Request,
    id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Post:
    """
    Replace the artwork image for an existing post.
    
    Only the owner can replace their artwork.
    Metadata (title, description, hashtags) is preserved.
    """
    # Find the post
    post = db.query(models.Post).filter(models.Post.id == id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    
    # Check ownership
    if post.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify this post")
    
    # Read and validate the new image
    file_content = await image.read()
    file_size = len(file_content)
    
    # Validate file size
    is_valid, error = validate_file_size(file_size)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    
    # Determine MIME type
    mime_type = image.content_type
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_MIME_TYPES.keys())}",
        )
    
    # Get image dimensions
    try:
        img = Image.open(io.BytesIO(file_content))
        width, height = img.size
        frame_count = getattr(img, 'n_frames', 1)
        
        # For GIFs, get frame duration
        min_frame_duration_ms = None
        if hasattr(img, 'info') and 'duration' in img.info:
            min_frame_duration_ms = img.info.get('duration', 100)
        
        # Check for transparency
        uses_transparency = img.mode in ('RGBA', 'LA', 'P')
        uses_alpha = img.mode == 'RGBA'
    except Exception as e:
        logger.error(f"Failed to process image: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted image file",
        )
    
    # Validate dimensions
    is_valid, error = validate_image_dimensions(width, height)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)
    
    # Calculate file hash
    file_hash = hashlib.sha256(file_content).hexdigest()
    
    # Save to vault (overwrites existing file)
    try:
        extension = ALLOWED_MIME_TYPES[mime_type]
        save_artwork_to_vault(post.storage_key, file_content, mime_type)
        art_url = get_artwork_url(post.storage_key, extension)
    except Exception as e:
        logger.error(f"Failed to save artwork to vault: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save artwork. Please try again.",
        )
    
    # Update post
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    
    post.art_url = art_url
    post.canvas = f"{width}x{height}"
    post.width = width
    post.height = height
    post.file_bytes = file_size
    post.frame_count = frame_count
    post.min_frame_duration_ms = min_frame_duration_ms
    post.uses_transparency = uses_transparency
    post.uses_alpha = uses_alpha
    post.expected_hash = file_hash
    post.mime_type = mime_type
    post.artwork_modified_at = now
    
    db.commit()
    db.refresh(post)
    
    # Invalidate relevant caches
    cache_invalidate(f"post:{post.id}")
    cache_invalidate(f"post:{post.public_sqid}")
    
    return schemas.Post.model_validate(post)
```

**Add necessary imports at the top:**

```python
import hashlib
import io
from PIL import Image
```

---

## Testing Checklist

### Layout.tsx
- [ ] 🖌️ button appears in header nav
- [ ] Button redirects to /auth if not logged in
- [ ] Button navigates to /editor if logged in
- [ ] Active state works when on /editor

### editor.tsx
- [ ] Auth check redirects unauthenticated users
- [ ] Iframe loads Piskel successfully
- [ ] MAKAPIX_INIT sent on PISKEL_READY
- [ ] Token refresh works for long sessions
- [ ] Export navigates to submit with data
- [ ] Replace updates existing artwork

### submit.tsx
- [ ] Receives Piskel export data
- [ ] Pre-populates image and title
- [ ] Shows "from Piskel" indicator
- [ ] Normal upload still works
- [ ] Validation runs on Piskel exports

### p/[sqid].tsx
- [ ] "Edit in Piskel" button appears for owners
- [ ] Button navigates to /editor?edit=<sqid>
- [ ] Non-owners don't see the button

### API replace-artwork
- [ ] Only owner can replace
- [ ] Validates image properly
- [ ] Updates all relevant fields
- [ ] Preserves metadata
- [ ] Returns updated post


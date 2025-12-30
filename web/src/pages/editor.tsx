import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/router';
import Head from 'next/head';
import { 
  authenticatedFetch, 
  refreshAccessToken, 
  getAccessToken, 
  clearTokens 
} from '../lib/api';
import { 
  decodeWebPAnimation, 
  DecodingProgress 
} from '../utils/webpDecoder';

const PISKEL_ORIGIN = 'https://piskel.makapix.club';

interface EditContext {
  postSqid: string;
  artworkUrl: string;
  title: string;
  // Animated WebP frames are sent via a separate postMessage with transferables.
  hasRgbaFrames?: boolean;
  frameCount?: number;
  width?: number;
  height?: number;
  fps?: number;
}

interface Post {
  id: number;
  public_sqid: string;
  title: string;
  art_url: string;
  mime_type?: string;
}

export default function EditorPage() {
  const router = useRouter();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const frameRgbaBuffersRef = useRef<ArrayBuffer[] | null>(null);
  const frameDurationsMsRef = useRef<number[] | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editContext, setEditContext] = useState<EditContext | null>(null);
  const [piskelReady, setPiskelReady] = useState(false);
  const [decodingProgress, setDecodingProgress] = useState<DecodingProgress | null>(null);

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

    let cancelled = false;

    // Fetch and process artwork for editing
    (async () => {
      try {
        // Fetch post data
        const res = await authenticatedFetch(`${API_BASE_URL}/api/p/${editSqid}`);
        
        if (res.status === 401) {
          clearTokens();
          router.push('/auth');
          return;
        }
        
        if (!res.ok) {
          throw new Error('Failed to load artwork');
        }
        
        const post: Post = await res.json();
        
        if (cancelled) return;

        // Convert relative URL to absolute
        const artworkUrl = post.art_url.startsWith('/') 
          ? `${API_BASE_URL}${post.art_url}` 
          : post.art_url;

        // Check if it's a WebP file
        const isWebP = post.mime_type === 'image/webp' || artworkUrl.toLowerCase().endsWith('.webp');

        if (cancelled) return;

        // Helper to convert URL to data URL (avoids CORS issues in Piskel iframe)
        const urlToDataUrl = async (url: string): Promise<string> => {
          const response = await fetch(url);
          const blob = await response.blob();
          return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result as string);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
          });
        };

        if (isWebP) {
          // Try to decode WebP animation with progress tracking
          setDecodingProgress({ current: 0, total: 1, phase: 'fetching' });

          try {
            const decoded = await decodeWebPAnimation(artworkUrl, (progress) => {
              if (!cancelled) {
                setDecodingProgress(progress);
              }
            });

            if (cancelled) return;

            if (decoded.isAnimated && decoded.frames.length > 0) {
              // Animated WebP: keep RGBA buffers in a ref and send them via transferables.
              frameRgbaBuffersRef.current = decoded.frames.map((f) => f.rgba);
              frameDurationsMsRef.current = decoded.frames.map((f) => f.duration);

              // Set edit context metadata only (serializable).
              setEditContext({
                postSqid: post.public_sqid,
                artworkUrl,
                title: post.title,
                hasRgbaFrames: true,
                frameCount: decoded.frames.length,
                width: decoded.width,
                height: decoded.height,
                fps: decoded.averageFps,
              });
            } else {
              // Not animated - convert to data URL to avoid CORS in Piskel
              const dataUrl = await urlToDataUrl(artworkUrl);
              if (cancelled) return;
              
              setEditContext({
                postSqid: post.public_sqid,
                artworkUrl: dataUrl,
                title: post.title,
              });
            }
          } catch {
            // WebP decoding failed - try to convert to data URL anyway
            try {
              const dataUrl = await urlToDataUrl(artworkUrl);
              if (cancelled) return;
              
              setEditContext({
                postSqid: post.public_sqid,
                artworkUrl: dataUrl,
                title: post.title,
              });
            } catch {
              // Even data URL conversion failed - pass original URL as last resort
              setEditContext({
                postSqid: post.public_sqid,
                artworkUrl,
                title: post.title,
              });
            }
          }

          setDecodingProgress(null);
        } else {
          // Non-WebP - convert to data URL to avoid CORS in Piskel
          try {
            const dataUrl = await urlToDataUrl(artworkUrl);
            if (cancelled) return;
            
            setEditContext({
              postSqid: post.public_sqid,
              artworkUrl: dataUrl,
              title: post.title,
            });
          } catch {
            // Conversion failed - pass original URL as fallback
            setEditContext({
              postSqid: post.public_sqid,
              artworkUrl,
              title: post.title,
            });
          }
        }

        setIsLoading(false);
      } catch (err) {
        if (cancelled) return;
        console.error('Failed to load edit context:', err);
        setError(err instanceof Error ? err.message : 'Failed to load artwork for editing');
        setIsLoading(false);
        setDecodingProgress(null);
      }
    })();

    return () => {
      cancelled = true;
    };
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
          // Don't call sendInitMessage here - let the useEffect at the bottom handle it
          // to ensure editContext is loaded first
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

    // Send RGBA frames as a separate message with transferables to avoid giant data URLs.
    if (editContext?.hasRgbaFrames && frameRgbaBuffersRef.current?.length) {
      const buffers = frameRgbaBuffersRef.current;
      const durations = frameDurationsMsRef.current || [];

      const framesMessage: any = {
        type: 'MAKAPIX_EDIT_FRAMES_RGBA',
        postSqid: editContext.postSqid,
        width: editContext.width,
        height: editContext.height,
        fps: editContext.fps,
        frameDurationsMs: durations,
        frameRgbaBuffers: buffers,
      };

      iframeRef.current.contentWindow.postMessage(framesMessage, PISKEL_ORIGIN, buffers);
      // Release memory on parent side after transfer.
      frameRgbaBuffersRef.current = null;
      frameDurationsMsRef.current = null;
    }
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
        
        {decodingProgress && (
          <div className="decoding-overlay">
            <div className="decoding-panel">
              <div className="spinner"></div>
              <div className="decoding-text">
                {decodingProgress.phase === 'fetching' && 'Fetching artwork...'}
                {decodingProgress.phase === 'decoding' && (
                  <>Loading animation... Frame {decodingProgress.current}/{decodingProgress.total}</>
                )}
                {decodingProgress.phase === 'converting' && (
                  <>Converting frames... {decodingProgress.current}/{decodingProgress.total}</>
                )}
              </div>
            </div>
          </div>
        )}
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

        .decoding-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.8);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 10000;
        }

        .decoding-panel {
          background: #1a1a1a;
          border: 2px solid #00d4ff;
          border-radius: 12px;
          padding: 32px 48px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 20px;
          min-width: 300px;
        }

        .decoding-text {
          color: #fff;
          font-size: 16px;
          text-align: center;
          font-weight: 500;
        }
      `}</style>
    </>
  );
}


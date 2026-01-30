import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/router';
import Head from 'next/head';
import {
  authenticatedFetch,
  getAccessToken,
  clearTokens
} from '../lib/api';

const PIXELC_ORIGIN = process.env.NEXT_PUBLIC_PIXELC_ORIGIN || 'https://pixelc-dev.makapix.club';

interface EditContext {
  postSqid: string;
}

interface Post {
  id: number;
  public_sqid: string;
  title: string;
  art_url: string;
  mime_type?: string;
  frame_count?: number;
  file_format?: string;
}

export default function PixelcPage() {
  const router = useRouter();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const webpDataRef = useRef<ArrayBuffer | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editContext, setEditContext] = useState<EditContext | null>(null);
  const [pixelcReady, setPixelcReady] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState<string | null>(null);

  const API_BASE_URL = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Check authentication on mount
  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      router.push(`/auth?redirect=${encodeURIComponent('/pixelc' + window.location.search)}`);
      return;
    }
    setIsAuthenticated(true);
  }, [router]);

  // Load edit context if editing existing artwork
  useEffect(() => {
    if (!isAuthenticated) return;

    const editSqid = router.query.edit as string;
    if (!editSqid) {
      // No edit mode - just load Pixelc normally
      setIsLoading(false);
      return;
    }

    let cancelled = false;

    // Fetch artwork for editing
    (async () => {
      try {
        setLoadingStatus('Loading artwork info...');

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

        // Check if it's an animated WebP
        const isWebP = post.mime_type === 'image/webp' ||
          post.file_format === 'webp' ||
          artworkUrl.toLowerCase().endsWith('.webp');
        const isAnimated = (post.frame_count ?? 1) > 1;

        if (!isWebP || !isAnimated) {
          throw new Error('Edit in Pixelc only supports animated WebP files');
        }

        // Fetch raw WebP bytes (no decoding needed - Pixelc will handle it)
        setLoadingStatus('Fetching artwork...');
        const webpRes = await authenticatedFetch(artworkUrl);
        if (!webpRes.ok) {
          throw new Error('Failed to fetch artwork file');
        }

        const webpData = await webpRes.arrayBuffer();

        if (cancelled) return;

        // Store raw WebP bytes
        webpDataRef.current = webpData;

        // Set edit context
        setEditContext({
          postSqid: post.public_sqid,
        });

        setLoadingStatus(null);
        setIsLoading(false);
      } catch (err) {
        if (cancelled) return;
        console.error('Failed to load edit context:', err);
        setError(err instanceof Error ? err.message : 'Failed to load artwork for editing');
        setIsLoading(false);
        setLoadingStatus(null);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, router.query.edit, API_BASE_URL, router]);

  const sendInitMessage = useCallback(() => {
    const token = getAccessToken();
    const publicSqid = localStorage.getItem('public_sqid');

    if (!iframeRef.current?.contentWindow || !token) return;

    // Send init message first
    iframeRef.current.contentWindow.postMessage({
      type: 'MAKAPIX_INIT',
      accessToken: token,
      userSqid: publicSqid,
    }, PIXELC_ORIGIN);

    // If we have WebP data to send, send it as a separate message
    if (editContext && webpDataRef.current) {
      const webpData = webpDataRef.current;

      const editMessage = {
        type: 'MAKAPIX_EDIT_WEBP',
        postSqid: editContext.postSqid,
        webpData: webpData,
        webpDataSize: webpData.byteLength,
      };

      // Send with transferable (zero-copy transfer of ArrayBuffer)
      iframeRef.current.contentWindow.postMessage(editMessage, PIXELC_ORIGIN, [webpData]);

      // Release memory on parent side after transfer
      webpDataRef.current = null;
    }
  }, [editContext]);

  const handleExport = useCallback(async (data: any) => {
    try {
      const reader = new FileReader();
      reader.onload = () => {
        const exportData = {
          imageData: reader.result,
          name: data.name,
          width: data.width,
          height: data.height,
          frameCount: data.frameCount || 1,
          timestamp: Date.now(),
        };
        sessionStorage.setItem('pixelc_export', JSON.stringify(exportData));
        router.push('/submit?from=pixelc');
      };
      reader.readAsDataURL(data.blob);
    } catch (err) {
      console.error('Failed to process export:', err);
      alert('Failed to process artwork. Please try again.');
    }
  }, [router]);

  // Handle messages from Pixelc
  useEffect(() => {
    const handleMessage = async (event: MessageEvent) => {
      if (event.origin !== PIXELC_ORIGIN) return;

      const data = event.data;
      if (!data || !data.type) return;

      switch (data.type) {
        case 'PIXELC_READY':
          setPixelcReady(true);
          break;

        case 'PIXELC_EXPORT':
          await handleExport(data);
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [handleExport]);

  // Send init message when Pixelc becomes ready and edit context is loaded
  useEffect(() => {
    if (pixelcReady && !isLoading) {
      sendInitMessage();
    }
  }, [pixelcReady, isLoading, sendInitMessage]);

  if (!isAuthenticated) {
    return (
      <>
        <Head>
          <title>Pixelc Editor - Makapix Club</title>
        </Head>
        <div className="editor-loading">
          <div className="spinner"></div>
          <p>Checking authentication...</p>
        </div>
        <style jsx>{`
          .editor-loading {
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
        `}</style>
      </>
    );
  }

  if (isLoading) {
    return (
      <>
        <Head>
          <title>Pixelc Editor - Makapix Club</title>
        </Head>
        <div className="editor-loading">
          <div className="spinner"></div>
          <p>{loadingStatus || 'Loading editor...'}</p>
        </div>
        <style jsx>{`
          .editor-loading {
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
        `}</style>
      </>
    );
  }

  if (error) {
    return (
      <>
        <Head>
          <title>Pixelc Editor - Makapix Club</title>
        </Head>
        <div className="editor-error">
          <p>{error}</p>
          <button onClick={() => router.push('/')}>Go Home</button>
        </div>
        <style jsx>{`
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

  return (
    <>
      <Head>
        <title>Pixelc Editor - Makapix Club</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className="editor-container">
        <iframe
          ref={iframeRef}
          src={PIXELC_ORIGIN}
          className="pixelc-iframe"
          title="Pixelc Editor"
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
        .pixelc-iframe {
          width: 100%;
          height: 100%;
          border: none;
        }
      `}</style>
    </>
  );
}

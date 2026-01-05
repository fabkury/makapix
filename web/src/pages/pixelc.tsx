import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/router';
import Head from 'next/head';
import { getAccessToken } from '../lib/api';

const PIXELC_ORIGIN = 'https://pixelc.makapix.club';

export default function PixelcPage() {
  const router = useRouter();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [pixelcReady, setPixelcReady] = useState(false);

  // Check authentication on mount
  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      router.push(`/auth?redirect=${encodeURIComponent('/pixelc')}`);
      return;
    }
    setIsAuthenticated(true);
  }, [router]);

  const sendInitMessage = useCallback(() => {
    const token = getAccessToken();
    const publicSqid = localStorage.getItem('public_sqid');

    if (!iframeRef.current?.contentWindow || !token) return;

    iframeRef.current.contentWindow.postMessage({
      type: 'MAKAPIX_INIT',
      accessToken: token,
      userSqid: publicSqid,
    }, PIXELC_ORIGIN);
  }, []);

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
          sendInitMessage();
          break;

        case 'PIXELC_EXPORT':
          await handleExport(data);
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [sendInitMessage, handleExport]);

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

import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Head from 'next/head';
import Layout from '../components/Layout';

type DeviceTab = 'desktop' | 'mobile';

export default function ContributePage() {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [activeTab, setActiveTab] = useState<DeviceTab | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/auth?redirect=/contribute');
    } else {
      setIsAuthenticated(true);
    }
  }, [router]);

  if (!isAuthenticated) {
    return (
      <Layout title="Contribute" description="Submit your pixel art">
        <div className="contribute-container">
          <div className="loading-state">Loading...</div>
        </div>
        <style jsx>{`
          .contribute-container {
            max-width: 600px;
            margin: 0 auto;
            padding: 24px;
          }
          .loading-state {
            text-align: center;
            padding: 48px;
            color: var(--text-muted);
          }
        `}</style>
      </Layout>
    );
  }

  return (
    <Layout title="Contribute" description="Submit your pixel art">
      <Head>
        <link
          rel="preload"
          href="/piskel/piskel_logo_transparent_small_compact.png"
          as="image"
        />
      </Head>
      <div className="contribute-container">
        <h1 className="page-title">Contribute</h1>
        <p className="page-subtitle">
          <Link href="/size_rules" className="size-rules-link">See size rules.</Link>
        </p>

        {/* Device Selection */}
        <div className="device-question">
          <h2 className="question-text">Which device are you using?</h2>
          <div className="device-tabs">
            <button
              className={`device-tab ${activeTab === 'mobile' ? 'active' : ''}`}
              onClick={() => setActiveTab('mobile')}
            >
              <span className="tab-icon">📱</span>
              <span className="tab-label">I am on a smartphone</span>
            </button>
            <button
              className={`device-tab ${activeTab === 'desktop' ? 'active' : ''}`}
              onClick={() => setActiveTab('desktop')}
            >
              <span className="tab-icon">🖥️</span>
              <span className="tab-label">I am on a desktop</span>
            </button>
          </div>
        </div>

        {/* Options based on selected tab */}
        {activeTab && (
          <div className="options-grid">
            {activeTab === 'desktop' && (
              <>
                <Link href="/editor" className="option-card">
                  <div className="option-icon">
                    <img
                      src="/piskel/piskel_logo_transparent_small_compact.png"
                      alt="Piskel"
                      className="piskel-logo"
                    />
                  </div>
                  <h2 className="option-title">Draw in Piskel</h2>
                  <p className="option-description">Create pixel art using the Piskel editor</p>
                </Link>

                <Link href="/divoom-import" className="option-card">
                  <div className="option-icon option-icon-emoji">☁️</div>
                  <h2 className="option-title">Import from Divoom</h2>
                  <p className="option-description">Import artworks from your Divoom account</p>
                </Link>

                <Link href="/submit" className="option-card">
                  <div className="option-icon option-icon-emoji">➕</div>
                  <h2 className="option-title">Upload File</h2>
                  <p className="option-description">Upload PNG, GIF, WebP, or BMP directly</p>
                </Link>
              </>
            )}

            {activeTab === 'mobile' && (
              <>
                <Link href="/pixelc" className="option-card">
                  <div className="option-icon option-icon-emoji">🖌️</div>
                  <h2 className="option-title">Draw in Pixelc</h2>
                  <p className="option-description">Create pixel art using the Pixelc editor</p>
                </Link>

                <Link href="/divoom-import" className="option-card">
                  <div className="option-icon option-icon-emoji">☁️</div>
                  <h2 className="option-title">Import from Divoom</h2>
                  <p className="option-description">Import artworks from your Divoom account</p>
                </Link>

                <Link href="/submit" className="option-card">
                  <div className="option-icon option-icon-emoji">➕</div>
                  <h2 className="option-title">Upload File</h2>
                  <p className="option-description">Upload PNG, GIF, WebP, or BMP directly</p>
                </Link>
              </>
            )}
          </div>
        )}
      </div>

      <style jsx>{`
        .contribute-container {
          max-width: 600px;
          margin: 0 auto;
          padding: 24px;
        }

        .page-title {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          margin-bottom: 8px;
          text-align: center;
        }

        .page-subtitle {
          font-size: 1rem;
          color: var(--text-secondary);
          text-align: center;
          margin-bottom: 32px;
        }

        .page-subtitle :global(.size-rules-link) {
          color: var(--accent-cyan);
          text-decoration: none;
        }

        .page-subtitle :global(.size-rules-link:hover) {
          text-decoration: underline;
        }

        .device-question {
          text-align: center;
          margin-bottom: 32px;
        }

        .question-text {
          font-size: 1.25rem;
          font-weight: 600;
          color: var(--text-primary);
          margin-bottom: 20px;
        }

        .device-tabs {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .device-tab {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
          padding: 20px 24px;
          background: var(--bg-secondary);
          border: 2px solid var(--bg-tertiary);
          border-radius: 12px;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .device-tab:hover {
          border-color: var(--accent-cyan);
          background: rgba(0, 212, 255, 0.05);
        }

        .device-tab.active {
          border-color: var(--accent-cyan);
          background: rgba(0, 212, 255, 0.1);
          box-shadow: 0 0 20px rgba(0, 212, 255, 0.2);
        }

        .tab-icon {
          font-size: 1.5rem;
        }

        .tab-label {
          font-size: 1.1rem;
          font-weight: 500;
          color: var(--text-primary);
        }

        .options-grid {
          display: flex;
          flex-direction: column;
          gap: 16px;
          animation: fadeIn 0.3s ease;
          padding-bottom: 50vh;
        }

        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .contribute-container :global(.option-card) {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
          padding: 32px 24px;
          background: var(--bg-secondary);
          border: 1px solid var(--bg-tertiary);
          border-radius: 16px;
          text-decoration: none;
          transition: all var(--transition-fast);
        }

        .contribute-container :global(.option-card:hover) {
          border-color: var(--accent-cyan);
          background: rgba(0, 212, 255, 0.05);
          box-shadow: 0 0 24px rgba(0, 212, 255, 0.2);
          transform: translateY(-2px);
        }

        .option-icon {
          width: 80px;
          height: 80px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .option-icon-emoji {
          font-size: 4rem;
          line-height: 1;
        }

        .piskel-logo {
          width: 100%;
          height: 100%;
          object-fit: contain;
          image-rendering: -webkit-optimize-contrast;
          image-rendering: -moz-crisp-edges;
          image-rendering: crisp-edges;
          image-rendering: pixelated;
          -ms-interpolation-mode: nearest-neighbor;
        }

        .option-title {
          font-size: 1.25rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0;
        }

        .option-description {
          font-size: 0.9rem;
          color: var(--text-secondary);
          margin: 0;
          text-align: center;
        }

        @media (max-width: 480px) {
          .contribute-container {
            padding: 16px;
          }

          .page-title {
            font-size: 1.5rem;
          }

          .question-text {
            font-size: 1.1rem;
          }

          .device-tab {
            padding: 16px 20px;
          }

          .tab-label {
            font-size: 1rem;
          }

          .contribute-container :global(.option-card) {
            padding: 24px 16px;
          }

          .option-icon {
            width: 64px;
            height: 64px;
          }

          .option-icon-emoji {
            font-size: 3rem;
          }
        }
      `}</style>
    </Layout>
  );
}

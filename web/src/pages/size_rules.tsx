import Link from 'next/link';
import Layout from '../components/Layout';

export default function SizeRulesPage() {
  return (
    <Layout title="Size Rules" description="Canvas and file size guidelines for Makapix Club">
      <div className="size-rules-container">
        <h1 className="page-title">Size Rules</h1>
        <p className="page-subtitle">Canvas and file size guidelines for uploading artwork</p>

        <section className="rules-section">
          <h2>File Size</h2>
          <p>Maximum file size: <strong>5 MiB</strong> per artwork.</p>
        </section>

        <section className="rules-section">
          <h2>Supported Formats</h2>
          <p>PNG, GIF, WebP, and BMP files are accepted.</p>
          <p>Transparency and alpha are allowed in PNG, GIF and WebP.</p>
          <p>GIF and WebP are allowed to be animated. APNG is not supported.</p>
        </section>

        <section className="rules-section">
          <h2>Canvas Dimensions</h2>
          <p>Maximum canvas size is <strong>256x256 pixels</strong>.</p>

          <h3>Large Canvas (128-256 pixels)</h3>
          <p>Any rectangular or square size is allowed within this range.</p>

          <h3>Small Canvas (under 128 pixels)</h3>
          <p>Only specific sizes are supported:</p>
          <ul className="size-list">
            <li><strong>8px base:</strong> 8x8, 8x16, 16x8, 8x32, 32x8</li>
            <li><strong>16px base:</strong> 16x16, 16x32, 32x16</li>
            <li><strong>32px base:</strong> 32x32, 32x64, 64x32</li>
            <li><strong>64px base:</strong> 64x64, 64x128, 128x64</li>
          </ul>
        </section>

        <div className="back-link">
          <Link href="/contribute">Back to Contribute</Link>
        </div>
      </div>

      <style jsx>{`
        .size-rules-container {
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

        .rules-section {
          background: var(--bg-secondary);
          border: 1px solid var(--bg-tertiary);
          border-radius: 12px;
          padding: 20px 24px;
          margin-bottom: 16px;
        }

        .rules-section h2 {
          font-size: 1.1rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0 0 12px 0;
        }

        .rules-section h3 {
          font-size: 0.95rem;
          font-weight: 600;
          color: var(--text-secondary);
          margin: 16px 0 8px 0;
        }

        .rules-section p {
          font-size: 0.95rem;
          color: var(--text-secondary);
          margin: 0 0 8px 0;
          line-height: 1.5;
        }

        .rules-section p:last-child {
          margin-bottom: 0;
        }

        .size-list {
          margin: 8px 0 0 0;
          padding-left: 20px;
          color: var(--text-secondary);
          font-size: 0.9rem;
          line-height: 1.8;
        }

        .size-list li {
          margin: 4px 0;
        }

        .size-list strong {
          color: var(--text-primary);
        }

        .back-link {
          text-align: center;
          margin-top: 24px;
        }

        .back-link :global(a) {
          color: var(--accent-cyan);
          text-decoration: none;
          font-size: 0.95rem;
        }

        .back-link :global(a:hover) {
          text-decoration: underline;
        }

        @media (max-width: 480px) {
          .size-rules-container {
            padding: 16px;
          }

          .page-title {
            font-size: 1.5rem;
          }

          .rules-section {
            padding: 16px;
          }
        }
      `}</style>
    </Layout>
  );
}

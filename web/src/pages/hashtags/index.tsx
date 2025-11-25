import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';

interface HashtagInfo {
  tag: string;
  count: number;
}

export default function HashtagsPage() {
  const router = useRouter();
  const [hashtags, setHashtags] = useState<HashtagInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
    : '';

  // Check authentication on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/auth');
    }
  }, [router]);

  useEffect(() => {
    const fetchHashtags = async () => {
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.push('/auth');
        return;
      }

      setLoading(true);
      setError(null);

      try {
        // Fetch popular hashtags from the API
        const response = await fetch(`${API_BASE_URL}/api/categories?limit=50`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });

        if (response.status === 401) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('user_id');
          router.push('/auth');
          return;
        }

        // Handle 404 or empty responses gracefully
        if (response.status === 404) {
          setHashtags([]);
          setLoading(false);
          return;
        }

        if (!response.ok) {
          // Don't show error for common "no data" cases
          if (response.status >= 500) {
            throw new Error(`Server error: ${response.statusText}`);
          }
          // For other errors, just show empty state
          setHashtags([]);
          setLoading(false);
          return;
        }

        const data = await response.json();
        
        // Transform the response - categories endpoint returns tag info
        // Handle various response formats gracefully
        let tagList: HashtagInfo[] = [];
        
        if (Array.isArray(data)) {
          tagList = data.map((item: any) => ({
            tag: item.name || item.tag || String(item),
            count: item.post_count || item.count || 0
          }));
        } else if (data.items && Array.isArray(data.items)) {
          tagList = data.items.map((item: any) => ({
            tag: item.name || item.tag || String(item),
            count: item.post_count || item.count || 0
          }));
        }

        // Filter out empty tags and sort by count descending
        tagList = tagList.filter(t => t.tag && t.tag.trim());
        tagList.sort((a, b) => b.count - a.count);
        
        setHashtags(tagList);
      } catch (err) {
        console.error('Error fetching hashtags:', err);
        // Only show error for actual server errors, not empty data
        if (err instanceof Error && err.message.includes('Server error')) {
          setError(err.message);
        } else {
          // For network errors or parsing issues, show empty state
          setHashtags([]);
        }
      } finally {
        setLoading(false);
      }
    };

    if (API_BASE_URL) {
      fetchHashtags();
    }
  }, [API_BASE_URL, router]);

  return (
    <Layout title="Browse Hashtags" description="Explore trending and popular hashtags">
      <div className="hashtags-container">
        {error && (
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            <p>{error}</p>
            <button onClick={() => window.location.reload()} className="retry-button">
              Retry
            </button>
          </div>
        )}

        {loading && (
          <div className="loading-state">
            <div className="loading-spinner"></div>
          </div>
        )}

        {!loading && !error && hashtags.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon-container">
              <span className="empty-icon">#</span>
            </div>
            <h2>No hashtags yet</h2>
            <p className="empty-hint">
              Be the first to add hashtags to your artworks!
            </p>
            <Link href="/" className="browse-link">
              Browse Recent Art →
            </Link>
          </div>
        )}

        {!loading && !error && hashtags.length > 0 && (
          <div className="hashtags-grid">
            {hashtags.map((hashtag) => (
              <Link 
                key={hashtag.tag} 
                href={`/hashtags/${encodeURIComponent(hashtag.tag)}`}
                className="hashtag-card"
              >
                <span className="hashtag-symbol">#</span>
                <span className="hashtag-name">{hashtag.tag}</span>
                {hashtag.count > 0 && (
                  <span className="hashtag-count">{hashtag.count}</span>
                )}
              </Link>
            ))}
          </div>
        )}
      </div>

      <style jsx>{`
        .hashtags-container {
          width: 100%;
          min-height: calc(100vh - var(--header-height));
          padding: 24px;
        }

        .error-message {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 3rem;
          text-align: center;
          color: var(--text-secondary);
        }

        .error-icon {
          font-size: 3rem;
          margin-bottom: 1rem;
        }

        .retry-button {
          margin-top: 1rem;
          padding: 0.75rem 1.5rem;
          background: var(--accent-pink);
          color: var(--bg-primary);
          border-radius: 8px;
          font-weight: 600;
          transition: all var(--transition-fast);
        }

        .retry-button:hover {
          box-shadow: var(--glow-pink);
        }

        .loading-state {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 4rem;
        }

        .loading-spinner {
          width: 40px;
          height: 40px;
          border: 3px solid var(--bg-tertiary);
          border-top-color: var(--accent-cyan);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 4rem 2rem;
          text-align: center;
          max-width: 500px;
          margin: 0 auto;
        }

        .empty-icon-container {
          width: 120px;
          height: 120px;
          border-radius: 50%;
          background: var(--bg-secondary);
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 24px;
        }

        .empty-icon {
          font-size: 4rem;
          font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
          font-weight: 700;
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .empty-state h2 {
          font-size: 1.5rem;
          color: var(--text-primary);
          margin: 0 0 12px 0;
        }

        .empty-description {
          font-size: 1rem;
          color: var(--text-secondary);
          line-height: 1.6;
          margin: 0 0 8px 0;
        }

        .empty-hint {
          font-size: 0.9rem;
          color: var(--text-muted);
          margin: 0 0 24px 0;
        }

        .browse-link {
          display: inline-block;
          padding: 12px 24px;
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          color: white;
          font-weight: 600;
          border-radius: 10px;
          transition: all var(--transition-fast);
        }

        .browse-link:hover {
          box-shadow: var(--glow-purple);
          transform: translateY(-2px);
        }

        .hashtags-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
          gap: 12px;
          max-width: 1200px;
          margin: 0 auto;
        }

        @media (min-width: 768px) {
          .hashtags-grid {
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
          }
        }

        .hashtag-card {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 16px 20px;
          background: var(--bg-secondary);
          border-radius: 12px;
          text-decoration: none;
          transition: all var(--transition-fast);
          border: 1px solid transparent;
        }

        .hashtag-card:hover {
          background: var(--bg-tertiary);
          border-color: var(--accent-purple);
          box-shadow: var(--glow-purple);
          transform: translateY(-2px);
        }

        .hashtag-symbol {
          font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
          font-weight: 700;
          font-size: 1.25rem;
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .hashtag-name {
          flex: 1;
          font-size: 0.95rem;
          font-weight: 500;
          color: var(--text-primary);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .hashtag-count {
          font-size: 0.8rem;
          color: var(--text-muted);
          background: var(--bg-primary);
          padding: 2px 8px;
          border-radius: 10px;
        }
      `}</style>
    </Layout>
  );
}

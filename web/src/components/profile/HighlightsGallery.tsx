/**
 * HighlightsGallery component - horizontally scrolling gallery of featured posts.
 */

import Link from 'next/link';
import { UserHighlightItem } from '../../types/profile';

interface HighlightsGalleryProps {
  highlights: UserHighlightItem[];
}

export default function HighlightsGallery({ highlights }: HighlightsGalleryProps) {
  if (highlights.length === 0) {
    return null;
  }

  return (
    <div className="highlights-section">
      <h2 className="highlights-title">💎</h2>
      <div className="highlights-scroll">
        {highlights.map((highlight) => (
          <Link
            key={highlight.id}
            href={`/a/${highlight.post_public_sqid}`}
            className="highlight-item"
          >
            <div className="highlight-image-container">
              <img
                src={highlight.post_art_url}
                alt={highlight.post_title}
                className="highlight-image"
                loading="lazy"
              />
            </div>
            <div className="highlight-info">
              <span className="highlight-title">{highlight.post_title}</span>
            </div>
          </Link>
        ))}
      </div>

      <style jsx>{`
        .highlights-section {
          margin-bottom: 32px;
        }
        .highlights-title {
          font-size: 1.1rem;
          margin-bottom: 16px;
          filter: drop-shadow(0 4px 12px rgba(255, 255, 255, 0.6));
        }
        .highlights-scroll {
          display: flex;
          gap: 12px;
          overflow-x: auto;
          padding-bottom: 8px;
          scrollbar-width: none;
          -ms-overflow-style: none;
        }
        .highlights-scroll::-webkit-scrollbar {
          display: none;
        }
        :global(.highlight-item) {
          flex-shrink: 0;
          text-decoration: none;
          color: inherit;
          transition: transform 0.2s ease;
        }
        :global(.highlight-item:hover) {
          transform: scale(1.02);
        }
        .highlight-image-container {
          width: 128px;
          height: 128px;
          overflow: hidden;
          border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .highlight-image {
          width: 100%;
          height: 100%;
          object-fit: cover;
          image-rendering: pixelated;
        }
        .highlight-info {
          padding: 8px 4px;
          width: 128px;
        }
        .highlight-title {
          font-size: 0.85rem;
          color: var(--text-primary);
          display: block;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      `}</style>
    </div>
  );
}

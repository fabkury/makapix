import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import Layout from "../components/Layout";
import {
  getMyRemixes,
  RemixReceivedItem,
} from "../lib/api";
import { ensureCompatibleArtUrl } from "../utils/imageCompat";

/**
 * Remixes page (docs/artwork-provenance/ L12): the aggregate, private
 * "Remixes of my works" view — every visible Remix of any artwork the
 * logged-in user owns, newest first, with the specific source works named.
 */
export default function RemixesPage() {
  const router = useRouter();
  const [authed, setAuthed] = useState(false);
  const [items, setItems] = useState<RemixReceivedItem[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!localStorage.getItem("access_token")) {
      router.push("/auth?redirect=/remixes");
      return;
    }
    setAuthed(true);
  }, [router]);

  useEffect(() => {
    if (!authed) return;
    getMyRemixes()
      .then((page) => {
        setItems(page.items);
        setNextCursor(page.next_cursor);
      })
      .catch((err) => {
        console.error("Failed to load remixes:", err);
        setError("Failed to load remixes.");
      })
      .finally(() => setLoading(false));
  }, [authed]);

  const loadMore = useCallback(async () => {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const page = await getMyRemixes(nextCursor);
      setItems((prev) => [...prev, ...page.items]);
      setNextCursor(page.next_cursor);
    } catch (err) {
      console.error("Failed to load more remixes:", err);
    } finally {
      setLoadingMore(false);
    }
  }, [nextCursor, loadingMore]);

  return (
    <Layout title="Remixes of my works">
      <div className="remixes-page">
        <h1 className="page-title">🎨 Remixes of my works</h1>
        <p className="page-subtitle">
          When someone remixes one of your artworks, it appears here (you also
          get a notification).
        </p>

        {loading ? (
          <p className="muted">Loading…</p>
        ) : error ? (
          <p className="muted">{error}</p>
        ) : items.length === 0 ? (
          <p className="muted">
            No remixes of your works yet. Artworks marked Remixable can be
            remixed by other members — when that happens, you&apos;ll see it
            here.
          </p>
        ) : (
          <div className="remix-list">
            {items.map((item) => (
              <div key={item.post.id} className="remix-card">
                <Link href={`/p/${item.post.public_sqid}`} className="thumb-link">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={ensureCompatibleArtUrl(item.post.art_url)}
                    alt={item.post.title}
                    className="thumb"
                  />
                </Link>
                <div className="remix-info">
                  <Link
                    href={`/p/${item.post.public_sqid}`}
                    className="remix-title"
                  >
                    {item.post.title}
                  </Link>
                  {item.post.owner && (
                    <Link
                      href={`/u/${item.post.owner.public_sqid}`}
                      className="remix-author"
                    >
                      by @{item.post.owner.handle}
                    </Link>
                  )}
                  <span className="remix-sources">
                    remix of{" "}
                    {item.my_parent_sqids.map((sqid, i) => (
                      <span key={sqid}>
                        {i > 0 && ", "}
                        <Link href={`/p/${sqid}`} className="source-link">
                          your artwork {sqid}
                        </Link>
                      </span>
                    ))}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}

        {nextCursor && (
          <button type="button" className="load-more" onClick={loadMore}>
            {loadingMore ? "Loading…" : "Load more"}
          </button>
        )}
      </div>

      <style jsx>{`
        .remixes-page {
          max-width: 720px;
          margin: 0 auto;
          padding: 24px 16px;
        }

        .page-title {
          font-size: 1.4rem;
          margin: 0 0 4px;
        }

        .page-subtitle {
          color: var(--text-muted);
          font-size: 0.9rem;
          margin: 0 0 20px;
        }

        .muted {
          color: var(--text-muted);
          font-style: italic;
        }

        .remix-list {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }

        .remix-card {
          display: flex;
          gap: 12px;
          padding: 12px;
          border-radius: 10px;
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.06);
        }

        .remix-card :global(.thumb-link) {
          flex-shrink: 0;
        }

        .remix-card :global(.thumb) {
          width: 64px;
          height: 64px;
          object-fit: contain;
          image-rendering: pixelated;
          border-radius: 6px;
          background: rgba(0, 0, 0, 0.3);
        }

        .remix-info {
          display: flex;
          flex-direction: column;
          gap: 2px;
          min-width: 0;
        }

        .remix-info :global(.remix-title) {
          font-weight: 600;
          color: inherit;
          text-decoration: none;
        }

        .remix-info :global(.remix-title:hover) {
          text-decoration: underline;
        }

        .remix-info :global(.remix-author) {
          font-size: 0.85rem;
          color: var(--text-muted);
          text-decoration: none;
        }

        .remix-sources {
          font-size: 0.8rem;
          color: var(--text-muted);
        }

        .remix-sources :global(.source-link) {
          color: rgba(168, 85, 247, 0.9);
          text-decoration: none;
        }

        .remix-sources :global(.source-link:hover) {
          text-decoration: underline;
        }

        .load-more {
          margin-top: 16px;
          padding: 8px 20px;
          border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.15);
          background: transparent;
          color: var(--text-muted);
          cursor: pointer;
        }
      `}</style>
    </Layout>
  );
}

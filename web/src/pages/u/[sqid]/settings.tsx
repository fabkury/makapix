import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../../components/Layout';
import {
  authenticatedFetch,
  clearTokens,
  getMyBlocks,
  unblockUser,
  BlockedUserEntry,
} from '../../../lib/api';
import { MONITORED_HASHTAGS } from '../../../lib/constants';

export default function ContentSettingsPage() {
  const router = useRouter();
  const { sqid } = router.query;
  const sqidStr = typeof sqid === 'string' ? sqid : null;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userKey, setUserKey] = useState<string | null>(null);

  // `selected` is the working set of approved tags; `initial` is what's persisted
  // server-side, used to detect unsaved changes.
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [initial, setInitial] = useState<Set<string>>(new Set());

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Blocked-users management (docs/ugc-safety/)
  const [blocks, setBlocks] = useState<BlockedUserEntry[]>([]);
  const [blocksLoading, setBlocksLoading] = useState(true);
  const [blocksError, setBlocksError] = useState<string | null>(null);
  const [blocksCursor, setBlocksCursor] = useState<string | null>(null);
  const [unblocking, setUnblocking] = useState<string | null>(null);

  const API_BASE_URL =
    typeof window !== 'undefined'
      ? process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin
      : '';

  useEffect(() => {
    if (!sqidStr) return;

    const loadMe = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await authenticatedFetch(`${API_BASE_URL}/api/auth/me`);

        if (response.status === 401) {
          clearTokens();
          router.push('/auth');
          return;
        }
        if (!response.ok) {
          setError('Failed to load your settings');
          return;
        }

        const meData = await response.json();
        const me = meData.user;

        // Content preferences are personal: only the owner edits their own.
        if (!me || me.public_sqid !== sqidStr) {
          setError('You can only change your own content settings');
          return;
        }

        setUserKey(me.user_key);
        const approved = new Set<string>(
          (me.approved_hashtags || []).filter((t: string) =>
            MONITORED_HASHTAGS.some((h) => h.tag === t)
          )
        );
        setSelected(approved);
        setInitial(approved);
      } catch (err: any) {
        setError(err.message || 'Failed to load your settings');
      } finally {
        setLoading(false);
      }
    };

    loadMe();
  }, [sqidStr, API_BASE_URL]);

  // Load the caller's blocked-users list once ownership is confirmed.
  useEffect(() => {
    if (!userKey) return;
    let cancelled = false;
    const loadBlocks = async () => {
      setBlocksLoading(true);
      setBlocksError(null);
      try {
        const page = await getMyBlocks();
        if (cancelled) return;
        setBlocks(page.items);
        setBlocksCursor(page.next_cursor);
      } catch (err) {
        if (cancelled) return;
        console.error('Failed to load blocked users:', err);
        setBlocksError('Could not load your blocked users.');
      } finally {
        if (!cancelled) setBlocksLoading(false);
      }
    };
    loadBlocks();
    return () => {
      cancelled = true;
    };
  }, [userKey]);

  const loadMoreBlocks = async () => {
    if (!blocksCursor) return;
    try {
      const page = await getMyBlocks(blocksCursor);
      setBlocks((prev) => [...prev, ...page.items]);
      setBlocksCursor(page.next_cursor);
    } catch (err) {
      console.error('Failed to load more blocked users:', err);
      setBlocksError('Could not load more blocked users.');
    }
  };

  const handleUnblock = async (publicSqid: string) => {
    setUnblocking(publicSqid);
    setBlocksError(null);
    try {
      await unblockUser(publicSqid);
      setBlocks((prev) => prev.filter((b) => b.public_sqid !== publicSqid));
    } catch (err) {
      console.error('Failed to unblock user:', err);
      setBlocksError('Could not unblock that user. Please try again.');
    } finally {
      setUnblocking(null);
    }
  };

  const toggle = (tag: string) => {
    setSaveSuccess(false);
    setSaveError(null);
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(tag)) {
        next.delete(tag);
      } else {
        next.add(tag);
      }
      return next;
    });
  };

  const isDirty =
    selected.size !== initial.size ||
    [...selected].some((t) => !initial.has(t));

  const handleSave = async () => {
    if (!userKey || !isDirty) return;

    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/user/${userKey}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved_hashtags: [...selected] }),
      });

      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        setSaveError(errData.detail || 'Failed to save changes');
        return;
      }

      const updated = await response.json();
      const approved = new Set<string>(updated.approved_hashtags || []);
      setSelected(approved);
      setInitial(approved);
      setSaveSuccess(true);
    } catch (err: any) {
      setSaveError(err.message || 'Failed to save changes');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Layout title="Loading...">
        <div className="loading-container">
          <div className="loading-spinner"></div>
        </div>
        <style jsx>{`
          .loading-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - var(--header-offset));
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
        `}</style>
      </Layout>
    );
  }

  if (error) {
    return (
      <Layout title="Access Denied">
        <div className="error-container">
          <span className="error-icon">🔒</span>
          <h1>{error}</h1>
        </div>
        <style jsx>{`
          .error-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - var(--header-offset));
            padding: 2rem;
            text-align: center;
          }
          .error-icon {
            font-size: 4rem;
            margin-bottom: 1rem;
          }
          h1 {
            font-size: 1.5rem;
            color: var(--text-primary);
          }
        `}</style>
      </Layout>
    );
  }

  return (
    <Layout title="User Settings">
      <div className="settings-container">
        <div className="page-header">
          <h1>User Settings</h1>
        </div>

        <section className="settings-card">
          <h2>Monitored hashtags</h2>
          <p className="section-intro">
            Artworks tagged with these hashtags are hidden by default across feeds,
            search and your players. Enable a hashtag to allow that content to appear
            for you. This applies to the web interface and any connected player devices.
          </p>

          <div className="tag-list">
            {MONITORED_HASHTAGS.map(({ tag, label, description }) => {
              const checked = selected.has(tag);
              return (
                <label
                  key={tag}
                  className={`tag-row ${checked ? 'is-on' : ''}`}
                  htmlFor={`tag-${tag}`}
                >
                  <input
                    id={`tag-${tag}`}
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(tag)}
                  />
                  <span className="tag-text">
                    <span className="tag-label">{label}</span>
                    <span className="tag-desc">{description}</span>
                  </span>
                  <span className="tag-state">{checked ? 'Shown' : 'Hidden'}</span>
                </label>
              );
            })}
          </div>

          {saveError && <p className="save-error">{saveError}</p>}
          {saveSuccess && <p className="save-success">Saved.</p>}

          <div className="actions">
            <button
              className="save-btn"
              onClick={handleSave}
              disabled={!isDirty || saving}
            >
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </section>

        <section className="settings-card">
          <h2>Blocked users</h2>
          <p className="section-intro">
            People you&apos;ve blocked can&apos;t comment on your work, react to it,
            or follow you, and you won&apos;t see their content. Unblock someone to
            undo this.
          </p>

          {blocksError && <p className="save-error">{blocksError}</p>}

          {blocksLoading ? (
            <p className="blocks-empty">Loading…</p>
          ) : blocks.length === 0 ? (
            <p className="blocks-empty">You haven&apos;t blocked anyone.</p>
          ) : (
            <div className="blocks-list">
              {blocks.map((b) => (
                <div key={b.public_sqid} className="block-row">
                  <div className="block-user">
                    {b.avatar_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={b.avatar_url}
                        alt={b.handle}
                        className="block-avatar"
                      />
                    ) : (
                      <span className="block-avatar placeholder">
                        {b.handle.charAt(0).toUpperCase()}
                      </span>
                    )}
                    <span className="block-handle">{b.handle}</span>
                  </div>
                  <button
                    className="unblock-btn"
                    onClick={() => handleUnblock(b.public_sqid)}
                    disabled={unblocking === b.public_sqid}
                  >
                    {unblocking === b.public_sqid ? 'Unblocking…' : 'Unblock'}
                  </button>
                </div>
              ))}
              {blocksCursor && (
                <button className="load-more-blocks" onClick={loadMoreBlocks}>
                  Load more
                </button>
              )}
            </div>
          )}
        </section>
      </div>

      <style jsx>{`
        .settings-container {
          max-width: 720px;
          margin: 0 auto;
          padding: 24px;
        }

        .page-header {
          margin-bottom: 24px;
        }

        .page-header h1 {
          font-size: 2rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0;
        }

        .settings-card {
          background: var(--bg-secondary);
          border-radius: 16px;
          padding: 24px;
        }

        .settings-card + .settings-card {
          margin-top: 24px;
        }

        .settings-card h2 {
          font-size: 1.25rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0 0 8px 0;
        }

        .section-intro {
          color: var(--text-secondary);
          margin: 0 0 20px 0;
          line-height: 1.5;
        }

        .tag-list {
          display: flex;
          flex-direction: column;
        }
        .tag-list > :global(* + *) {
          margin-top: 12px;
        }

        .tag-row {
          display: flex;
          align-items: center;
          padding: 14px 16px;
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 12px;
          background: var(--bg-tertiary);
          cursor: pointer;
          transition: all var(--transition-fast);
        }
        .tag-row:hover {
          border-color: var(--accent-cyan);
        }
        .tag-row.is-on {
          border-color: var(--accent-cyan);
          background: rgba(0, 209, 255, 0.06);
        }

        .tag-row input[type='checkbox'] {
          width: 18px;
          height: 18px;
          margin: 0 14px 0 0;
          accent-color: var(--accent-cyan);
          cursor: pointer;
          flex-shrink: 0;
        }

        .tag-text {
          display: flex;
          flex-direction: column;
          flex: 1;
        }

        .tag-label {
          font-weight: 600;
          color: var(--text-primary);
          font-family: var(--font-mono, monospace);
        }

        .tag-desc {
          font-size: 0.85rem;
          color: var(--text-muted);
          margin-top: 2px;
        }

        .tag-state {
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          color: var(--text-muted);
          flex-shrink: 0;
          margin-left: 12px;
        }
        .tag-row.is-on .tag-state {
          color: var(--accent-cyan);
        }

        .save-error {
          color: var(--accent-pink, #ff6b6b);
          margin: 16px 0 0 0;
        }
        .save-success {
          color: var(--accent-cyan);
          margin: 16px 0 0 0;
        }

        .actions {
          margin-top: 24px;
        }

        .save-btn {
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          border: none;
          border-radius: 8px;
          padding: 12px 24px;
          font-size: 1rem;
          font-weight: 600;
          cursor: pointer;
          transition: all var(--transition-fast);
        }
        .save-btn:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 4px 20px rgba(255, 110, 180, 0.4);
        }
        .save-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .blocks-empty {
          color: var(--text-muted);
          margin: 0;
        }

        .blocks-list {
          display: flex;
          flex-direction: column;
        }
        .blocks-list > :global(* + *) {
          margin-top: 12px;
        }

        .block-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 16px;
          border: 1px solid rgba(255, 255, 255, 0.12);
          border-radius: 12px;
          background: var(--bg-tertiary);
        }

        .block-user {
          display: flex;
          align-items: center;
          min-width: 0;
        }
        .block-user > :global(* + *) {
          margin-left: 12px;
        }

        .block-avatar {
          width: 36px;
          height: 36px;
          border-radius: 8px;
          object-fit: cover;
          flex-shrink: 0;
          image-rendering: pixelated;
        }

        .block-avatar.placeholder {
          display: flex;
          align-items: center;
          justify-content: center;
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          color: white;
          font-weight: 700;
          text-transform: uppercase;
        }

        .block-handle {
          font-weight: 600;
          color: var(--text-primary);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .unblock-btn {
          background: var(--bg-secondary);
          color: var(--text-primary);
          border: 1px solid rgba(255, 255, 255, 0.18);
          border-radius: 8px;
          padding: 8px 16px;
          font-size: 0.9rem;
          font-weight: 600;
          cursor: pointer;
          flex-shrink: 0;
          transition: all var(--transition-fast);
        }
        .unblock-btn:hover:not(:disabled) {
          border-color: var(--accent-cyan);
          color: var(--accent-cyan);
        }
        .unblock-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .load-more-blocks {
          align-self: flex-start;
          background: none;
          border: none;
          color: var(--accent-cyan);
          font-size: 0.9rem;
          cursor: pointer;
          padding: 8px 0;
        }
      `}</style>
    </Layout>
  );
}

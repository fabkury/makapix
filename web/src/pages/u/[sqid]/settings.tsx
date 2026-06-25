import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../../components/Layout';
import { authenticatedFetch, clearTokens } from '../../../lib/api';

// Mirrors the backend source of truth: api/app/constants.py:MONITORED_HASHTAGS.
// Posts carrying any of these tags are hidden in feeds/search/players unless the
// user has explicitly opted into seeing that tag here.
const MONITORED_HASHTAGS: { tag: string; label: string; description: string }[] = [
  { tag: 'politics', label: '#politics', description: 'Political content' },
  { tag: 'nsfw', label: '#nsfw', description: 'Not safe for work' },
  { tag: 'explicit', label: '#explicit', description: 'Explicit content' },
  { tag: '13plus', label: '#13plus', description: 'Intended for ages 13 and up' },
  { tag: 'violence', label: '#violence', description: 'Depictions of violence' },
];

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
      `}</style>
    </Layout>
  );
}

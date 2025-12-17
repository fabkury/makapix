import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';
import { authenticatedFetch } from '../lib/api';

interface NotificationPreferences {
  notify_on_post_reactions: boolean;
  notify_on_post_comments: boolean;
  notify_on_blog_reactions: boolean;
  notify_on_blog_comments: boolean;
  aggregate_same_type: boolean;
}

export default function AccountSettingsPage() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [preferences, setPreferences] = useState<NotificationPreferences>({
    notify_on_post_reactions: true,
    notify_on_post_comments: true,
    notify_on_blog_reactions: true,
    notify_on_blog_comments: true,
    aggregate_same_type: true,
  });

  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  useEffect(() => {
    const storedUserId = localStorage.getItem('user_id');
    if (!storedUserId) {
      router.push('/auth');
      return;
    }
    setUserId(storedUserId);
  }, [router]);

  useEffect(() => {
    if (!userId) return;

    const fetchPreferences = async () => {
      try {
        const response = await authenticatedFetch(`${API_BASE_URL}/api/notifications/preferences`);
        if (response.ok) {
          const data = await response.json();
          setPreferences(data);
        }
      } catch (error) {
        console.error('Failed to fetch preferences:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchPreferences();
  }, [userId, API_BASE_URL]);

  const handleToggle = (key: keyof NotificationPreferences) => {
    setPreferences(prev => ({
      ...prev,
      [key]: !prev[key],
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveMessage(null);

    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/notifications/preferences`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(preferences),
      });

      if (response.ok) {
        setSaveMessage('Preferences saved successfully!');
        setTimeout(() => setSaveMessage(null), 3000);
      } else {
        setSaveMessage('Failed to save preferences. Please try again.');
      }
    } catch (error) {
      console.error('Failed to save preferences:', error);
      setSaveMessage('Failed to save preferences. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  if (!userId) {
    return null;
  }

  return (
    <Layout title="Account Settings">
      <div className="settings-page">
        <div className="settings-header">
          <h1>Account Settings</h1>
        </div>

        <div className="settings-section">
          <h2>Notification Preferences</h2>
          <p className="section-description">
            Choose which types of notifications you want to receive
          </p>

          {loading ? (
            <div className="loading">Loading preferences...</div>
          ) : (
            <div className="preferences-list">
              <div className="preference-item">
                <label>
                  <input
                    type="checkbox"
                    checked={preferences.notify_on_post_reactions}
                    onChange={() => handleToggle('notify_on_post_reactions')}
                  />
                  <span className="preference-label">Artwork Reactions</span>
                  <span className="preference-description">
                    Get notified when someone reacts to your artwork
                  </span>
                </label>
              </div>

              <div className="preference-item">
                <label>
                  <input
                    type="checkbox"
                    checked={preferences.notify_on_post_comments}
                    onChange={() => handleToggle('notify_on_post_comments')}
                  />
                  <span className="preference-label">Artwork Comments</span>
                  <span className="preference-description">
                    Get notified when someone comments on your artwork
                  </span>
                </label>
              </div>

              <div className="preference-item">
                <label>
                  <input
                    type="checkbox"
                    checked={preferences.notify_on_blog_reactions}
                    onChange={() => handleToggle('notify_on_blog_reactions')}
                  />
                  <span className="preference-label">Blog Post Reactions</span>
                  <span className="preference-description">
                    Get notified when someone reacts to your blog posts
                  </span>
                </label>
              </div>

              <div className="preference-item">
                <label>
                  <input
                    type="checkbox"
                    checked={preferences.notify_on_blog_comments}
                    onChange={() => handleToggle('notify_on_blog_comments')}
                  />
                  <span className="preference-label">Blog Post Comments</span>
                  <span className="preference-description">
                    Get notified when someone comments on your blog posts
                  </span>
                </label>
              </div>
            </div>
          )}

          <div className="actions">
            <button
              onClick={handleSave}
              disabled={saving || loading}
              className="save-button"
            >
              {saving ? 'Saving...' : 'Save Preferences'}
            </button>
            {saveMessage && (
              <div className={`save-message ${saveMessage.includes('success') ? 'success' : 'error'}`}>
                {saveMessage}
              </div>
            )}
          </div>
        </div>

        <style jsx>{`
          .settings-page {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
          }

          .settings-header {
            margin-bottom: 32px;
          }

          .settings-header h1 {
            font-size: 28px;
            font-weight: 600;
            margin: 0;
            color: var(--text-primary);
          }

          .settings-section {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
          }

          .settings-section h2 {
            font-size: 20px;
            font-weight: 600;
            margin: 0 0 8px 0;
            color: var(--text-primary);
          }

          .section-description {
            font-size: 14px;
            color: var(--text-secondary);
            margin: 0 0 24px 0;
          }

          .loading {
            text-align: center;
            padding: 40px;
            color: var(--text-secondary);
          }

          .preferences-list {
            display: flex;
            flex-direction: column;
            gap: 16px;
            margin-bottom: 24px;
          }

          .preference-item {
            padding: 16px;
            background: var(--bg-primary);
            border-radius: 8px;
            transition: background-color 0.2s;
          }

          .preference-item:hover {
            background: var(--bg-tertiary);
          }

          .preference-item label {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            cursor: pointer;
          }

          .preference-item input[type="checkbox"] {
            margin-top: 2px;
            cursor: pointer;
            width: 18px;
            height: 18px;
            flex-shrink: 0;
          }

          .preference-label {
            font-size: 15px;
            font-weight: 500;
            color: var(--text-primary);
            display: block;
            margin-bottom: 4px;
          }

          .preference-description {
            font-size: 13px;
            color: var(--text-secondary);
            display: block;
          }

          .actions {
            display: flex;
            align-items: center;
            gap: 16px;
          }

          .save-button {
            background: var(--accent);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 15px;
            font-weight: 500;
            transition: opacity 0.2s;
          }

          .save-button:hover:not(:disabled) {
            opacity: 0.8;
          }

          .save-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }

          .save-message {
            font-size: 14px;
            padding: 8px 12px;
            border-radius: 6px;
          }

          .save-message.success {
            color: #2e7d32;
            background: #e8f5e9;
          }

          .save-message.error {
            color: #c62828;
            background: #ffebee;
          }

          @media (max-width: 768px) {
            .settings-page {
              padding: 12px;
            }

            .settings-header h1 {
              font-size: 22px;
            }

            .settings-section {
              padding: 16px;
            }
          }
        `}</style>
      </div>
    </Layout>
  );
}

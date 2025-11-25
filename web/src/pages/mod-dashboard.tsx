import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';

interface User {
  id: string;
  handle: string;
  display_name: string;
  email?: string;
  roles: string[];
  created_at: string;
  reputation: number;
  hidden_by_mod?: boolean;
  banned_until?: string | null;
}

interface Post {
  id: string;
  title: string;
  description?: string;
  owner_id: string;
  created_at: string;
  promoted?: boolean;
  hidden_by_mod?: boolean;
  visible?: boolean;
}

interface Report {
  id: string;
  target_type: 'user' | 'post' | 'comment';
  target_id: string;
  reason_code: string;
  notes?: string;
  status: 'open' | 'triaged' | 'resolved';
  action_taken?: string;
  created_at: string;
}

interface AuditLogEntry {
  id: string;
  actor_id: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  reason_code: string | null;
  note: string | null;
  created_at: string;
}

interface AdminNote {
  id: string;
  note: string;
  created_by: string;
  created_at: string;
}

interface PageResponse<T> {
  items: T[];
  next_cursor: string | null;
}

type Tab = 'reports' | 'posts' | 'profiles' | 'audit' | 'notes';

export default function ModDashboardPage() {
  const router = useRouter();
  const [isModerator, setIsModerator] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('reports');
  
  const [reports, setReports] = useState<Report[]>([]);
  const [reportsCursor, setReportsCursor] = useState<string | null>(null);
  const [reportsLoading, setReportsLoading] = useState(false);
  
  const [posts, setPosts] = useState<Post[]>([]);
  const [postsCursor, setPostsCursor] = useState<string | null>(null);
  const [postsLoading, setPostsLoading] = useState(false);
  
  const [profiles, setProfiles] = useState<User[]>([]);
  const [profilesCursor, setProfilesCursor] = useState<string | null>(null);
  const [profilesLoading, setProfilesLoading] = useState(false);
  
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [auditCursor, setAuditCursor] = useState<string | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  
  const [selectedPostId, setSelectedPostId] = useState<string | null>(null);
  const [adminNotes, setAdminNotes] = useState<AdminNote[]>([]);
  const [noteText, setNoteText] = useState('');
  const [addingNote, setAddingNote] = useState(false);

  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
    : '';

  useEffect(() => {
    if (typeof window !== 'undefined') {
      checkModeratorStatus();
    }
  }, []);

  useEffect(() => {
    if (isModerator) {
      loadTabData(activeTab);
    }
  }, [isModerator, activeTab]);

  useEffect(() => {
    if (selectedPostId && activeTab === 'notes') {
      loadAdminNotes(selectedPostId);
    }
  }, [selectedPostId, activeTab]);

  const checkModeratorStatus = async () => {
    try {
      const accessToken = localStorage.getItem('access_token');
      if (!accessToken) {
        router.push('/');
        return;
      }

      const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });

      if (!response.ok) {
        router.push('/');
        return;
      }

      const data = await response.json();
      const roles = data.roles || [];
      
      if (roles.includes('moderator') || roles.includes('owner')) {
        setIsModerator(true);
      } else {
        router.push('/');
      }
    } catch (error) {
      console.error('Error checking moderator status:', error);
      router.push('/');
    } finally {
      setLoading(false);
    }
  };

  const loadTabData = async (tab: Tab) => {
    switch (tab) {
      case 'reports': await loadReports(); break;
      case 'posts': await loadRecentPosts(); break;
      case 'profiles': await loadRecentProfiles(); break;
      case 'audit': await loadAuditLog(); break;
    }
  };

  const loadReports = async () => {
    if (reportsLoading) return;
    setReportsLoading(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      const url = `${API_BASE_URL}/api/reports?status=open&limit=50${reportsCursor ? `&cursor=${reportsCursor}` : ''}`;
      const response = await fetch(url, { headers: { 'Authorization': `Bearer ${accessToken}` } });
      if (response.ok) {
        const data: PageResponse<Report> = await response.json();
        setReports([...reports, ...data.items]);
        setReportsCursor(data.next_cursor);
      }
    } catch (error) {
      console.error('Error loading reports:', error);
    } finally {
      setReportsLoading(false);
    }
  };

  const loadRecentPosts = async () => {
    if (postsLoading) return;
    setPostsLoading(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      const url = `${API_BASE_URL}/api/admin/recent-posts?limit=50${postsCursor ? `&cursor=${postsCursor}` : ''}`;
      const response = await fetch(url, { headers: { 'Authorization': `Bearer ${accessToken}` } });
      if (response.ok) {
        const data: PageResponse<Post> = await response.json();
        setPosts([...posts, ...data.items]);
        setPostsCursor(data.next_cursor);
      }
    } catch (error) {
      console.error('Error loading posts:', error);
    } finally {
      setPostsLoading(false);
    }
  };

  const loadRecentProfiles = async () => {
    if (profilesLoading) return;
    setProfilesLoading(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      const url = `${API_BASE_URL}/api/admin/recent-profiles?limit=50${profilesCursor ? `&cursor=${profilesCursor}` : ''}`;
      const response = await fetch(url, { headers: { 'Authorization': `Bearer ${accessToken}` } });
      if (response.ok) {
        const data: PageResponse<User> = await response.json();
        setProfiles([...profiles, ...data.items]);
        setProfilesCursor(data.next_cursor);
      }
    } catch (error) {
      console.error('Error loading profiles:', error);
    } finally {
      setProfilesLoading(false);
    }
  };

  const loadAuditLog = async () => {
    if (auditLoading) return;
    setAuditLoading(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      const url = `${API_BASE_URL}/api/admin/audit-log?limit=50${auditCursor ? `&cursor=${auditCursor}` : ''}`;
      const response = await fetch(url, { headers: { 'Authorization': `Bearer ${accessToken}` } });
      if (response.ok) {
        const data: PageResponse<AuditLogEntry> = await response.json();
        setAuditLog([...auditLog, ...data.items]);
        setAuditCursor(data.next_cursor);
      }
    } catch (error) {
      console.error('Error loading audit log:', error);
    } finally {
      setAuditLoading(false);
    }
  };

  const loadAdminNotes = async (postId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/api/posts/${postId}/admin-notes`, {
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });
      if (response.ok) {
        const data = await response.json();
        setAdminNotes(data.items || []);
      }
    } catch (error) {
      console.error('Error loading admin notes:', error);
    }
  };

  const resolveReport = async (reportId: string, action: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/api/reports/${reportId}`, {
        method: 'PATCH',
        headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'resolved', action_taken: action, notes: `Action: ${action}` })
      });
      if (response.ok) {
        setReports(reports.filter(r => r.id !== reportId));
      }
    } catch (error) {
      console.error('Error resolving report:', error);
    }
  };

  const promotePost = async (postId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      await fetch(`${API_BASE_URL}/api/posts/${postId}/promote`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ category: 'frontpage' })
      });
      setPosts([]);
      setPostsCursor(null);
      loadRecentPosts();
    } catch (error) {
      console.error('Error promoting post:', error);
    }
  };

  const hidePost = async (postId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      await fetch(`${API_BASE_URL}/api/posts/${postId}/hide`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ by: 'mod' })
      });
      setPosts([]);
      setPostsCursor(null);
      loadRecentPosts();
    } catch (error) {
      console.error('Error hiding post:', error);
    }
  };

  const banUser = async (userId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      await fetch(`${API_BASE_URL}/api/admin/users/${userId}/ban`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ duration_days: 7 })
      });
      setProfiles([]);
      setProfilesCursor(null);
      loadRecentProfiles();
    } catch (error) {
      console.error('Error banning user:', error);
    }
  };

  const addAdminNote = async () => {
    if (!selectedPostId || !noteText.trim()) return;
    setAddingNote(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/api/posts/${selectedPostId}/admin-notes`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ note: noteText })
      });
      if (response.ok) {
        setNoteText('');
        await loadAdminNotes(selectedPostId);
      }
    } catch (error) {
      console.error('Error adding admin note:', error);
    } finally {
      setAddingNote(false);
    }
  };

  if (loading) {
    return (
      <Layout title="Moderator Dashboard">
        <div className="loading-container">
          <div className="loading-spinner"></div>
        </div>
        <style jsx>{`
          .loading-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - var(--header-height));
          }
          .loading-spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--bg-tertiary);
            border-top-color: var(--accent-cyan);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
          }
          @keyframes spin { to { transform: rotate(360deg); } }
        `}</style>
      </Layout>
    );
  }

  if (!isModerator) return null;

  const tabs: Tab[] = ['reports', 'posts', 'profiles', 'audit', 'notes'];

  return (
    <Layout title="Moderator Dashboard">
      <div className="dashboard">
        <h1>Moderator Dashboard</h1>
        
        <div className="tabs">
          {tabs.map(tab => (
            <button
              key={tab}
              onClick={() => {
                setActiveTab(tab);
                if (tab === 'reports') { setReports([]); setReportsCursor(null); }
                if (tab === 'posts') { setPosts([]); setPostsCursor(null); }
                if (tab === 'profiles') { setProfiles([]); setProfilesCursor(null); }
                if (tab === 'audit') { setAuditLog([]); setAuditCursor(null); }
              }}
              className={`tab ${activeTab === tab ? 'active' : ''}`}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="tab-content">
          {activeTab === 'reports' && (
            <div className="section">
              <h2>Reports Queue</h2>
              {reports.length === 0 && !reportsLoading ? (
                <p className="empty">No open reports</p>
              ) : (
                <>
                  {reports.map(report => (
                    <div key={report.id} className="item-card">
                      <div className="item-info">
                        <strong>{report.target_type}</strong> - {report.reason_code}
                        {report.notes && <p className="item-notes">{report.notes}</p>}
                        <p className="item-date">{new Date(report.created_at).toLocaleString()}</p>
                      </div>
                      <div className="item-actions">
                        <button onClick={() => resolveReport(report.id, 'hide')} className="action-btn">Hide</button>
                        <button onClick={() => resolveReport(report.id, 'delete')} className="action-btn danger">Delete</button>
                        <button onClick={() => resolveReport(report.id, 'none')} className="action-btn secondary">Dismiss</button>
                      </div>
                    </div>
                  ))}
                  {reportsCursor && (
                    <button onClick={loadReports} disabled={reportsLoading} className="load-more">
                      {reportsLoading ? 'Loading...' : 'Load More'}
                    </button>
                  )}
                </>
              )}
            </div>
          )}

          {activeTab === 'posts' && (
            <div className="section">
              <h2>Recent Posts</h2>
              {posts.length === 0 && !postsLoading ? (
                <p className="empty">No posts found</p>
              ) : (
                <>
                  {posts.map(post => (
                    <div key={post.id} className="item-card">
                      <div className="item-info">
                        <h3>{post.title}</h3>
                        {post.description && <p className="item-notes">{post.description}</p>}
                        <p className="item-date">{new Date(post.created_at).toLocaleString()}</p>
                      </div>
                      <div className="item-actions">
                        {!post.promoted && <button onClick={() => promotePost(post.id)} className="action-btn success">Promote</button>}
                        {!post.hidden_by_mod && <button onClick={() => hidePost(post.id)} className="action-btn">Hide</button>}
                      </div>
                    </div>
                  ))}
                  {postsCursor && (
                    <button onClick={loadRecentPosts} disabled={postsLoading} className="load-more">
                      {postsLoading ? 'Loading...' : 'Load More'}
                    </button>
                  )}
                </>
              )}
            </div>
          )}

          {activeTab === 'profiles' && (
            <div className="section">
              <h2>Recent Profiles</h2>
              {profiles.length === 0 && !profilesLoading ? (
                <p className="empty">No profiles found</p>
              ) : (
                <>
                  {profiles.map(profile => (
                    <div key={profile.id} className="item-card">
                      <div className="item-info">
                        <h3>{profile.display_name} <span className="handle">@{profile.handle}</span></h3>
                        <p className="item-notes">Reputation: {profile.reputation}</p>
                        <p className="item-date">Joined {new Date(profile.created_at).toLocaleString()}</p>
                      </div>
                      <div className="item-actions">
                        <button onClick={() => banUser(profile.id)} className="action-btn danger">Ban</button>
                      </div>
                    </div>
                  ))}
                  {profilesCursor && (
                    <button onClick={loadRecentProfiles} disabled={profilesLoading} className="load-more">
                      {profilesLoading ? 'Loading...' : 'Load More'}
                    </button>
                  )}
                </>
              )}
            </div>
          )}

          {activeTab === 'audit' && (
            <div className="section">
              <h2>Audit Log</h2>
              {auditLog.length === 0 && !auditLoading ? (
                <p className="empty">No audit log entries</p>
              ) : (
                <>
                  {auditLog.map(entry => (
                    <div key={entry.id} className="item-card">
                      <div className="item-info">
                        <strong>{entry.action}</strong> - {entry.target_type || 'N/A'}
                        {entry.reason_code && <span className="badge">{entry.reason_code}</span>}
                        {entry.note && <p className="item-notes">{entry.note}</p>}
                        <p className="item-date">{new Date(entry.created_at).toLocaleString()}</p>
                      </div>
                    </div>
                  ))}
                  {auditCursor && (
                    <button onClick={loadAuditLog} disabled={auditLoading} className="load-more">
                      {auditLoading ? 'Loading...' : 'Load More'}
                    </button>
                  )}
                </>
              )}
            </div>
          )}

          {activeTab === 'notes' && (
            <div className="section">
              <h2>Admin Notes</h2>
              <div className="notes-search">
                <input
                  type="text"
                  placeholder="Enter post ID"
                  value={selectedPostId || ''}
                  onChange={(e) => setSelectedPostId(e.target.value)}
                />
                <button onClick={() => selectedPostId && loadAdminNotes(selectedPostId)} className="action-btn">
                  Load Notes
                </button>
              </div>
              {selectedPostId && (
                <>
                  <div className="note-form">
                    <textarea
                      value={noteText}
                      onChange={(e) => setNoteText(e.target.value)}
                      placeholder="Add admin note..."
                    />
                    <button onClick={addAdminNote} disabled={addingNote || !noteText.trim()} className="action-btn success">
                      {addingNote ? 'Adding...' : 'Add Note'}
                    </button>
                  </div>
                  <div className="notes-list">
                    <h3>Notes for Post {selectedPostId}</h3>
                    {adminNotes.length === 0 ? (
                      <p className="empty">No notes yet</p>
                    ) : (
                      adminNotes.map(note => (
                        <div key={note.id} className="item-card">
                          <p>{note.note}</p>
                          <p className="item-date">{new Date(note.created_at).toLocaleString()}</p>
                        </div>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .dashboard {
          max-width: 1200px;
          margin: 0 auto;
          padding: 24px;
        }

        h1 {
          font-size: 1.75rem;
          color: var(--text-primary);
          margin-bottom: 24px;
        }

        .tabs {
          display: flex;
          gap: 8px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          margin-bottom: 24px;
          padding-bottom: 12px;
          flex-wrap: wrap;
        }

        .tab {
          padding: 10px 20px;
          background: transparent;
          color: var(--text-muted);
          border-radius: 8px;
          text-transform: capitalize;
          transition: all var(--transition-fast);
        }

        .tab:hover {
          background: var(--bg-tertiary);
          color: var(--text-secondary);
        }

        .tab.active {
          background: var(--accent-cyan);
          color: var(--bg-primary);
        }

        .section h2 {
          font-size: 1.25rem;
          color: var(--text-primary);
          margin-bottom: 16px;
        }

        .section h3 {
          font-size: 1rem;
          color: var(--text-primary);
          margin: 0;
        }

        .handle {
          color: var(--text-muted);
          font-weight: normal;
        }

        .empty {
          color: var(--text-muted);
          text-align: center;
          padding: 32px;
        }

        .item-card {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 16px;
          background: var(--bg-secondary);
          border-radius: 12px;
          padding: 16px;
          margin-bottom: 12px;
        }

        .item-info {
          flex: 1;
        }

        .item-notes {
          color: var(--text-secondary);
          font-size: 0.9rem;
          margin: 8px 0;
        }

        .item-date {
          color: var(--text-muted);
          font-size: 0.8rem;
          margin: 4px 0 0 0;
        }

        .item-actions {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }

        .action-btn {
          padding: 8px 16px;
          background: var(--bg-tertiary);
          color: var(--text-secondary);
          border-radius: 6px;
          font-size: 0.85rem;
          transition: all var(--transition-fast);
        }

        .action-btn:hover {
          background: var(--accent-cyan);
          color: var(--bg-primary);
        }

        .action-btn.danger:hover {
          background: #ef4444;
        }

        .action-btn.success:hover {
          background: #10b981;
        }

        .action-btn.secondary:hover {
          background: var(--text-muted);
        }

        .badge {
          margin-left: 8px;
          padding: 2px 8px;
          background: var(--bg-tertiary);
          border-radius: 4px;
          font-size: 0.8rem;
          color: var(--text-muted);
        }

        .load-more {
          display: block;
          width: 100%;
          padding: 12px;
          background: var(--bg-secondary);
          color: var(--accent-cyan);
          border-radius: 8px;
          margin-top: 16px;
          transition: all var(--transition-fast);
        }

        .load-more:hover:not(:disabled) {
          background: var(--bg-tertiary);
        }

        .load-more:disabled {
          opacity: 0.5;
        }

        .notes-search {
          display: flex;
          gap: 12px;
          margin-bottom: 20px;
        }

        .notes-search input {
          flex: 1;
          padding: 12px 16px;
        }

        .note-form {
          margin-bottom: 24px;
        }

        .note-form textarea {
          width: 100%;
          min-height: 100px;
          padding: 12px;
          margin-bottom: 12px;
          resize: vertical;
        }

        .notes-list h3 {
          margin-bottom: 12px;
        }
      `}</style>
    </Layout>
  );
}

import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Layout from '../components/Layout';
import StatsPanel from '../components/StatsPanel';

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
  auto_public_approval?: boolean;
}

interface Post {
  id: string;
  title: string;
  description?: string;
  owner_id: string;
  art_url?: string;
  created_at: string;
  promoted?: boolean;
  hidden_by_mod?: boolean;
  visible?: boolean;
  public_visibility?: boolean;
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

type Tab = 'pending' | 'reports' | 'posts' | 'profiles' | 'audit' | 'notes';

export default function ModDashboardPage() {
  const router = useRouter();
  const [isModerator, setIsModerator] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('pending');
  
  const [pendingPosts, setPendingPosts] = useState<Post[]>([]);
  const [pendingCursor, setPendingCursor] = useState<string | null>(null);
  const [pendingLoading, setPendingLoading] = useState(false);
  
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
  
  // Stats panel state
  const [statsPostId, setStatsPostId] = useState<string | null>(null);
  const [showStats, setShowStats] = useState(false);

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

  const loadTabData = async (tab: Tab, reset = true) => {
    switch (tab) {
      case 'pending': await loadPendingApproval(reset); break;
      case 'reports': await loadReports(reset); break;
      case 'posts': await loadRecentPosts(reset); break;
      case 'profiles': await loadRecentProfiles(reset); break;
      case 'audit': await loadAuditLog(reset); break;
    }
  };

  const loadPendingApproval = async (reset = false) => {
    if (pendingLoading) return;
    setPendingLoading(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      const cursor = reset ? null : pendingCursor;
      const url = `${API_BASE_URL}/api/admin/pending-approval?limit=50${cursor ? `&cursor=${cursor}` : ''}`;
      const response = await fetch(url, { headers: { 'Authorization': `Bearer ${accessToken}` } });
      if (response.ok) {
        const data: PageResponse<Post> = await response.json();
        if (reset) {
          setPendingPosts(data.items);
        } else {
          setPendingPosts(prev => [...prev, ...data.items]);
        }
        setPendingCursor(data.next_cursor);
      }
    } catch (error) {
      console.error('Error loading pending approvals:', error);
    } finally {
      setPendingLoading(false);
    }
  };

  const approvePublicVisibility = async (postId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/api/posts/${postId}/approve-public`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });
      if (response.ok) {
        // Remove from pending list
        setPendingPosts(pendingPosts.filter(p => p.id !== postId));
      }
    } catch (error) {
      console.error('Error approving post:', error);
    }
  };

  const rejectPublicVisibility = async (postId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/api/posts/${postId}/approve-public`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });
      if (response.ok) {
        // Remove from pending list (it's already not public)
        setPendingPosts(pendingPosts.filter(p => p.id !== postId));
      }
    } catch (error) {
      console.error('Error rejecting post:', error);
    }
  };

  const loadReports = async (reset = false) => {
    if (reportsLoading) return;
    setReportsLoading(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      const cursor = reset ? null : reportsCursor;
      const url = `${API_BASE_URL}/api/reports?status=open&limit=50${cursor ? `&cursor=${cursor}` : ''}`;
      const response = await fetch(url, { headers: { 'Authorization': `Bearer ${accessToken}` } });
      if (response.ok) {
        const data: PageResponse<Report> = await response.json();
        if (reset) {
          setReports(data.items);
        } else {
          setReports(prev => [...prev, ...data.items]);
        }
        setReportsCursor(data.next_cursor);
      }
    } catch (error) {
      console.error('Error loading reports:', error);
    } finally {
      setReportsLoading(false);
    }
  };

  const loadRecentPosts = async (reset = false) => {
    if (postsLoading) return;
    setPostsLoading(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      const cursor = reset ? null : postsCursor;
      const url = `${API_BASE_URL}/api/admin/recent-posts?limit=50${cursor ? `&cursor=${cursor}` : ''}`;
      const response = await fetch(url, { headers: { 'Authorization': `Bearer ${accessToken}` } });
      if (response.ok) {
        const data: PageResponse<Post> = await response.json();
        if (reset) {
          setPosts(data.items);
          setPostsCursor(data.next_cursor);
        } else {
          setPosts(prev => [...prev, ...data.items]);
          setPostsCursor(data.next_cursor);
        }
      }
    } catch (error) {
      console.error('Error loading posts:', error);
    } finally {
      setPostsLoading(false);
    }
  };

  const loadRecentProfiles = async (reset = false) => {
    if (profilesLoading) return;
    setProfilesLoading(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      const cursor = reset ? null : profilesCursor;
      const url = `${API_BASE_URL}/api/admin/recent-profiles?limit=50${cursor ? `&cursor=${cursor}` : ''}`;
      const response = await fetch(url, { headers: { 'Authorization': `Bearer ${accessToken}` } });
      if (response.ok) {
        const data: PageResponse<User> = await response.json();
        if (reset) {
          setProfiles(data.items);
        } else {
          setProfiles(prev => [...prev, ...data.items]);
        }
        setProfilesCursor(data.next_cursor);
      }
    } catch (error) {
      console.error('Error loading profiles:', error);
    } finally {
      setProfilesLoading(false);
    }
  };

  const loadAuditLog = async (reset = false) => {
    if (auditLoading) return;
    setAuditLoading(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      const cursor = reset ? null : auditCursor;
      const url = `${API_BASE_URL}/api/admin/audit-log?limit=50${cursor ? `&cursor=${cursor}` : ''}`;
      const response = await fetch(url, { headers: { 'Authorization': `Bearer ${accessToken}` } });
      if (response.ok) {
        const data: PageResponse<AuditLogEntry> = await response.json();
        if (reset) {
          setAuditLog(data.items);
        } else {
          setAuditLog(prev => [...prev, ...data.items]);
        }
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
      await loadRecentPosts(true);
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
      await loadRecentPosts(true);
    } catch (error) {
      console.error('Error hiding post:', error);
    }
  };

  const unhidePost = async (postId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      await fetch(`${API_BASE_URL}/api/posts/${postId}/unhide`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ by: 'mod' })
      });
      await loadRecentPosts(true);
    } catch (error) {
      console.error('Error unhiding post:', error);
    }
  };

  const demotePost = async (postId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      await fetch(`${API_BASE_URL}/api/posts/${postId}/demote`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });
      await loadRecentPosts(true);
    } catch (error) {
      console.error('Error demoting post:', error);
    }
  };

  const deletePostPermanently = async (postId: string) => {
    if (!confirm('Are you sure you want to permanently delete this post? This action cannot be undone.')) {
      return;
    }
    try {
      const accessToken = localStorage.getItem('access_token');
      await fetch(`${API_BASE_URL}/api/posts/${postId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });
      await loadRecentPosts(true);
    } catch (error) {
      console.error('Error deleting post:', error);
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
      await loadRecentProfiles(true);
    } catch (error) {
      console.error('Error banning user:', error);
    }
  };

  const trustUser = async (userId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      await fetch(`${API_BASE_URL}/api/admin/users/${userId}/auto-approval`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });
      await loadRecentProfiles(true);
    } catch (error) {
      console.error('Error trusting user:', error);
    }
  };

  const distrustUser = async (userId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      await fetch(`${API_BASE_URL}/api/admin/users/${userId}/auto-approval`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });
      await loadRecentProfiles(true);
    } catch (error) {
      console.error('Error distrusting user:', error);
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

  const tabs: Tab[] = ['pending', 'reports', 'posts', 'profiles', 'audit', 'notes'];
  const tabLabels: Record<Tab, string> = {
    pending: 'Pending Approval',
    reports: 'Reports',
    posts: 'Posts',
    profiles: 'Profiles',
    audit: 'Audit',
    notes: 'Notes'
  };

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
                // Reset data when switching tabs - loadTabData will reload fresh
                if (tab === 'pending') { setPendingPosts([]); setPendingCursor(null); }
                else if (tab === 'reports') { setReports([]); setReportsCursor(null); }
                else if (tab === 'posts') { setPosts([]); setPostsCursor(null); }
                else if (tab === 'profiles') { setProfiles([]); setProfilesCursor(null); }
                else if (tab === 'audit') { setAuditLog([]); setAuditCursor(null); }
              }}
              className={`tab ${activeTab === tab ? 'active' : ''}`}
            >
              {tabLabels[tab]}
            </button>
          ))}
        </div>

        <div className="tab-content">
          {activeTab === 'pending' && (
            <div className="section">
              <h2>Pending Public Visibility Approval</h2>
              <p className="section-description">
                These artworks are waiting for moderator approval before appearing in Recent Artworks and search results.
              </p>
              {pendingPosts.length === 0 && !pendingLoading ? (
                <p className="empty">No pending approvals</p>
              ) : (
                <>
                  {pendingPosts.map(post => (
                    <div key={post.id} className="item-card pending-card">
                      {post.art_url && (
                        <div className="pending-thumbnail">
                          <img src={post.art_url} alt={post.title} className="pixel-art" />
                        </div>
                      )}
                      <div className="item-info">
                        <h3>
                          <a href={`/posts/${post.id}`} target="_blank" rel="noopener noreferrer">
                            {post.title}
                          </a>
                        </h3>
                        {post.description && <p className="item-notes">{post.description}</p>}
                        <p className="item-date">{new Date(post.created_at).toLocaleString()}</p>
                      </div>
                      <div className="item-actions">
                        <button onClick={() => { setStatsPostId(post.id); setShowStats(true); }} className="action-btn stats" title="View Statistics">📈</button>
                        <button onClick={() => approvePublicVisibility(post.id)} className="action-btn success">
                          Approve
                        </button>
                        <button onClick={() => rejectPublicVisibility(post.id)} className="action-btn danger">
                          Reject
                        </button>
                      </div>
                    </div>
                  ))}
                  {pendingCursor && (
                    <button onClick={loadPendingApproval} disabled={pendingLoading} className="load-more">
                      {pendingLoading ? 'Loading...' : 'Load More'}
                    </button>
                  )}
                </>
              )}
            </div>
          )}

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
                    <div key={post.id} className="item-card pending-card">
                      {post.art_url && (
                        <div className="pending-thumbnail">
                          <img src={post.art_url} alt={post.title} className="pixel-art" />
                        </div>
                      )}
                      <div className="item-info">
                        <h3>
                          <Link href={`/posts/${post.id}`} className="post-title-link">
                            {post.title}
                          </Link>
                        </h3>
                        {post.description && <p className="item-notes">{post.description}</p>}
                        <p className="item-date">{new Date(post.created_at).toLocaleString()}</p>
                      </div>
                      <div className="item-actions">
                        <button onClick={() => { setStatsPostId(post.id); setShowStats(true); }} className="action-btn stats" title="View Statistics">📈</button>
                        {!post.promoted && <button onClick={() => promotePost(post.id)} className="action-btn success">⭐ Promote</button>}
                        {post.promoted && <button onClick={() => demotePost(post.id)} className="action-btn">⬇️ Demote</button>}
                        {!post.hidden_by_mod && <button onClick={() => hidePost(post.id)} className="action-btn">🙈 Hide</button>}
                        {post.hidden_by_mod && <button onClick={() => unhidePost(post.id)} className="action-btn success">👁️ Unhide</button>}
                        {post.hidden_by_mod && <button onClick={() => deletePostPermanently(post.id)} className="action-btn danger">Delete</button>}
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
                        <h3>
                          <Link href={`/users/${profile.id}`} className="profile-link">
                            {profile.display_name} <span className="handle">@{profile.handle}</span>
                          </Link>
                        </h3>
                        <p className="item-notes">Reputation: {profile.reputation}</p>
                        <p className="item-date">Joined {new Date(profile.created_at).toLocaleString()}</p>
                      </div>
                      <div className="item-actions">
                        {profile.auto_public_approval ? (
                          <button onClick={() => distrustUser(profile.id)} className="action-btn danger">⚠️ Distrust</button>
                        ) : (
                          <button onClick={() => trustUser(profile.id)} className="action-btn success">🫱🏽‍🫲🏼 Trust</button>
                        )}
                        <button onClick={() => banUser(profile.id)} className="action-btn danger">🚷 Ban</button>
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

      {/* Stats Panel Modal */}
      {statsPostId && (
        <StatsPanel
          postId={statsPostId}
          isOpen={showStats}
          onClose={() => { setShowStats(false); setStatsPostId(null); }}
        />
      )}

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

        .post-title-link {
          color: var(--text-primary);
          text-decoration: none;
          transition: color var(--transition-fast);
        }

        .post-title-link:hover {
          color: var(--accent-cyan);
        }

        .profile-link {
          color: var(--text-primary);
          text-decoration: none;
          transition: color var(--transition-fast);
        }

        .profile-link:hover {
          color: var(--accent-cyan);
        }

        .profile-link:hover .handle {
          color: var(--accent-cyan);
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

        .pending-card {
          align-items: center;
        }

        .pending-thumbnail {
          width: 64px;
          height: 64px;
          border-radius: 8px;
          overflow: hidden;
          background: var(--bg-tertiary);
          flex-shrink: 0;
        }

        .pending-thumbnail img {
          width: 100%;
          height: 100%;
          object-fit: contain;
          image-rendering: pixelated;
          image-rendering: -moz-crisp-edges;
          image-rendering: crisp-edges;
        }

        .section-description {
          color: var(--text-muted);
          font-size: 0.9rem;
          margin-bottom: 20px;
        }

        .section h3 a {
          color: var(--text-primary);
          text-decoration: none;
          transition: color var(--transition-fast);
        }

        .section h3 a:hover {
          color: var(--accent-cyan);
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

        .action-btn.stats {
          background: rgba(180, 78, 255, 0.2);
          color: #b44eff;
        }

        .action-btn.stats:hover {
          background: rgba(180, 78, 255, 0.3);
          box-shadow: 0 0 8px rgba(180, 78, 255, 0.3);
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

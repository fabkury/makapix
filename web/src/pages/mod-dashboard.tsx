import { useState, useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

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
  
  // Reports state
  const [reports, setReports] = useState<Report[]>([]);
  const [reportsCursor, setReportsCursor] = useState<string | null>(null);
  const [reportsLoading, setReportsLoading] = useState(false);
  
  // Posts state
  const [posts, setPosts] = useState<Post[]>([]);
  const [postsCursor, setPostsCursor] = useState<string | null>(null);
  const [postsLoading, setPostsLoading] = useState(false);
  
  // Profiles state
  const [profiles, setProfiles] = useState<User[]>([]);
  const [profilesCursor, setProfilesCursor] = useState<string | null>(null);
  const [profilesLoading, setProfilesLoading] = useState(false);
  
  // Audit log state
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([]);
  const [auditCursor, setAuditCursor] = useState<string | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  
  // Admin notes state
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
      case 'reports':
        await loadReports();
        break;
      case 'posts':
        await loadRecentPosts();
        break;
      case 'profiles':
        await loadRecentProfiles();
        break;
      case 'audit':
        await loadAuditLog();
        break;
    }
  };

  const loadReports = async () => {
    if (reportsLoading) return;
    setReportsLoading(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      const url = `${API_BASE_URL}/api/reports?status=open&limit=50${reportsCursor ? `&cursor=${reportsCursor}` : ''}`;
      const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });
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
      const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });
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
      const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });
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
      const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });
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
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          status: 'resolved',
          action_taken: action,
          notes: `Action: ${action}`
        })
      });
      if (response.ok) {
        setReports(reports.filter(r => r.id !== reportId));
        await loadReports();
      }
    } catch (error) {
      console.error('Error resolving report:', error);
    }
  };

  const promotePost = async (postId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/api/posts/${postId}/promote`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ category: 'frontpage' })
      });
      if (response.ok) {
        await loadRecentPosts();
      }
    } catch (error) {
      console.error('Error promoting post:', error);
    }
  };

  const hidePost = async (postId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/api/posts/${postId}/hide`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ by: 'mod' })
      });
      if (response.ok) {
        await loadRecentPosts();
      }
    } catch (error) {
      console.error('Error hiding post:', error);
    }
  };

  const banUser = async (userId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/api/admin/users/${userId}/ban`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ duration_days: 7 })
      });
      if (response.ok) {
        await loadRecentProfiles();
      }
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
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
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
    return <div style={{ padding: '20px' }}>Loading...</div>;
  }

  if (!isModerator) {
    return null;
  }

  return (
    <>
      <Head>
        <title>Moderator Dashboard - Makapix</title>
      </Head>
      <div style={{ padding: '20px', maxWidth: '1400px', margin: '0 auto' }}>
        <h1>Moderator Dashboard</h1>
        
        {/* Tabs */}
        <div style={{ borderBottom: '1px solid #ccc', marginBottom: '20px' }}>
          {(['reports', 'posts', 'profiles', 'audit', 'notes'] as Tab[]).map(tab => (
            <button
              key={tab}
              onClick={() => {
                setActiveTab(tab);
                if (tab === 'reports') setReports([]);
                if (tab === 'posts') setPosts([]);
                if (tab === 'profiles') setProfiles([]);
                if (tab === 'audit') setAuditLog([]);
              }}
              style={{
                padding: '10px 20px',
                marginRight: '10px',
                border: 'none',
                background: activeTab === tab ? '#0070f3' : 'transparent',
                color: activeTab === tab ? 'white' : '#0070f3',
                cursor: 'pointer',
                textTransform: 'capitalize'
              }}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Reports Tab */}
        {activeTab === 'reports' && (
          <div>
            <h2>Reports Queue</h2>
            {reports.length === 0 && !reportsLoading ? (
              <p>No open reports</p>
            ) : (
              <>
                {reports.map(report => (
                  <div key={report.id} style={{ border: '1px solid #ccc', padding: '15px', marginBottom: '10px', borderRadius: '5px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                      <div>
                        <strong>{report.target_type}</strong> - {report.reason_code}
                        {report.notes && <p style={{ marginTop: '5px', color: '#666' }}>{report.notes}</p>}
                        <p style={{ fontSize: '0.9em', color: '#999' }}>Reported {new Date(report.created_at).toLocaleString()}</p>
                      </div>
                      <div>
                        <button onClick={() => resolveReport(report.id, 'hide')} style={{ marginRight: '5px', padding: '5px 10px' }}>Hide</button>
                        <button onClick={() => resolveReport(report.id, 'delete')} style={{ marginRight: '5px', padding: '5px 10px' }}>Delete</button>
                        <button onClick={() => resolveReport(report.id, 'none')} style={{ padding: '5px 10px' }}>Dismiss</button>
                      </div>
                    </div>
                  </div>
                ))}
                {reportsCursor && (
                  <button onClick={loadReports} disabled={reportsLoading} style={{ marginTop: '10px' }}>
                    {reportsLoading ? 'Loading...' : 'Load More'}
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {/* Posts Tab */}
        {activeTab === 'posts' && (
          <div>
            <h2>Recent Posts</h2>
            {posts.length === 0 && !postsLoading ? (
              <p>No posts found</p>
            ) : (
              <>
                {posts.map(post => (
                  <div key={post.id} style={{ border: '1px solid #ccc', padding: '15px', marginBottom: '10px', borderRadius: '5px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                      <div>
                        <h3>{post.title}</h3>
                        {post.description && <p>{post.description}</p>}
                        <p style={{ fontSize: '0.9em', color: '#999' }}>Created {new Date(post.created_at).toLocaleString()}</p>
                      </div>
                      <div>
                        {!post.promoted && (
                          <button onClick={() => promotePost(post.id)} style={{ marginRight: '5px', padding: '5px 10px' }}>Promote</button>
                        )}
                        {!post.hidden_by_mod && (
                          <button onClick={() => hidePost(post.id)} style={{ padding: '5px 10px' }}>Hide</button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                {postsCursor && (
                  <button onClick={loadRecentPosts} disabled={postsLoading} style={{ marginTop: '10px' }}>
                    {postsLoading ? 'Loading...' : 'Load More'}
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {/* Profiles Tab */}
        {activeTab === 'profiles' && (
          <div>
            <h2>Recent Profiles</h2>
            {profiles.length === 0 && !profilesLoading ? (
              <p>No profiles found</p>
            ) : (
              <>
                {profiles.map(profile => (
                  <div key={profile.id} style={{ border: '1px solid #ccc', padding: '15px', marginBottom: '10px', borderRadius: '5px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                      <div>
                        <h3>{profile.display_name} (@{profile.handle})</h3>
                        <p>Reputation: {profile.reputation}</p>
                        <p style={{ fontSize: '0.9em', color: '#999' }}>Joined {new Date(profile.created_at).toLocaleString()}</p>
                      </div>
                      <div>
                        <button onClick={() => banUser(profile.id)} style={{ padding: '5px 10px' }}>Ban</button>
                      </div>
                    </div>
                  </div>
                ))}
                {profilesCursor && (
                  <button onClick={loadRecentProfiles} disabled={profilesLoading} style={{ marginTop: '10px' }}>
                    {profilesLoading ? 'Loading...' : 'Load More'}
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {/* Audit Log Tab */}
        {activeTab === 'audit' && (
          <div>
            <h2>Audit Log</h2>
            {auditLog.length === 0 && !auditLoading ? (
              <p>No audit log entries</p>
            ) : (
              <>
                {auditLog.map(entry => (
                  <div key={entry.id} style={{ border: '1px solid #ccc', padding: '15px', marginBottom: '10px', borderRadius: '5px' }}>
                    <div>
                      <strong>{entry.action}</strong> - {entry.target_type || 'N/A'}
                      {entry.reason_code && <span style={{ marginLeft: '10px', color: '#666' }}>({entry.reason_code})</span>}
                      {entry.note && <p style={{ marginTop: '5px', color: '#666' }}>{entry.note}</p>}
                      <p style={{ fontSize: '0.9em', color: '#999' }}>{new Date(entry.created_at).toLocaleString()}</p>
                    </div>
                  </div>
                ))}
                {auditCursor && (
                  <button onClick={loadAuditLog} disabled={auditLoading} style={{ marginTop: '10px' }}>
                    {auditLoading ? 'Loading...' : 'Load More'}
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {/* Admin Notes Tab */}
        {activeTab === 'notes' && (
          <div>
            <h2>Admin Notes</h2>
            <div style={{ marginBottom: '20px' }}>
              <input
                type="text"
                placeholder="Enter post ID"
                value={selectedPostId || ''}
                onChange={(e) => setSelectedPostId(e.target.value)}
                style={{ padding: '8px', marginRight: '10px', width: '300px' }}
              />
              <button onClick={() => selectedPostId && loadAdminNotes(selectedPostId)}>Load Notes</button>
            </div>
            {selectedPostId && (
              <>
                <div style={{ marginBottom: '20px' }}>
                  <textarea
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                    placeholder="Add admin note..."
                    style={{ width: '100%', padding: '8px', minHeight: '80px' }}
                  />
                  <button onClick={addAdminNote} disabled={addingNote || !noteText.trim()} style={{ marginTop: '10px' }}>
                    {addingNote ? 'Adding...' : 'Add Note'}
                  </button>
                </div>
                <div>
                  <h3>Notes for Post {selectedPostId}</h3>
                  {adminNotes.length === 0 ? (
                    <p>No notes yet</p>
                  ) : (
                    adminNotes.map(note => (
                      <div key={note.id} style={{ border: '1px solid #ccc', padding: '10px', marginBottom: '10px', borderRadius: '5px' }}>
                        <p>{note.note}</p>
                        <p style={{ fontSize: '0.9em', color: '#999' }}>{new Date(note.created_at).toLocaleString()}</p>
                      </div>
                    ))
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </>
  );
}











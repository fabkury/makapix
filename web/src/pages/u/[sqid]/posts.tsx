import { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import { GetServerSideProps } from 'next';
import Layout from '../../../components/Layout';
import { PostTable, PMDPost } from '../../../components/pmd/PostTable';
import { BulkActionsPanel } from '../../../components/pmd/BulkActionsPanel';
import { DownloadRequestsPanel } from '../../../components/pmd/DownloadRequestsPanel';
import { usePMDSSE, BDRItem } from '../../../hooks/usePMDSSE';
import { authenticatedFetch } from '../../../lib/api';

// Force server-side rendering (no static generation)
export const getServerSideProps: GetServerSideProps = async () => {
  return { props: {} };
};

export default function PostManagementDashboard() {
  const router = useRouter();
  const { sqid, bdr: highlightedBdrId } = router.query;

  // Loading states
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Data
  const [posts, setPosts] = useState<PMDPost[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [bdrs, setBdrs] = useState<BDRItem[]>([]);

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Pagination state (for UI display - we load all data progressively)
  const [currentPage, setCurrentPage] = useState(0);
  const itemsPerPage = 16;

  // Auth check - redirect if not own profile or not moderator
  const [isOwnProfile, setIsOwnProfile] = useState<boolean | null>(null);
  const [targetSqid, setTargetSqid] = useState<string | null>(null);  // For moderator cross-user access
  const [error, setError] = useState<string | null>(null);

  const API_BASE_URL = useMemo(
    () =>
      typeof window !== 'undefined'
        ? process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin
        : '',
    []
  );

  // Check authorization
  useEffect(() => {
    if (!sqid) return;

    const checkAuth = async () => {
      try {
        const meResponse = await authenticatedFetch(`${API_BASE_URL}/api/auth/me`);
        if (meResponse.ok) {
          const meData = await meResponse.json();
          const userSqid = meData.user?.public_sqid;
          const roles = meData.roles || [];
          const viewerIsModerator = roles.includes('moderator') || roles.includes('owner');

          if (userSqid === sqid) {
            // Own profile
            setIsOwnProfile(true);
            setTargetSqid(null);
          } else if (viewerIsModerator) {
            // Moderator viewing another user - check if target is owner
            const profileResponse = await authenticatedFetch(`${API_BASE_URL}/api/user/u/${sqid}/profile`);
            if (!profileResponse.ok) {
              router.push(`/u/${sqid}`);
              return;
            }
            const profileData = await profileResponse.json();
            const targetIsOwner = profileData.badges?.some((b: { badge: string }) => b.badge === 'owner');

            if (targetIsOwner) {
              // Cannot access owner's PMD
              router.push(`/u/${sqid}`);
              return;
            }

            setIsOwnProfile(false);
            setTargetSqid(sqid as string);  // Store for API calls
          } else {
            // Not own profile and not moderator
            router.push(`/u/${sqid}`);
          }
        } else {
          router.push('/auth');
        }
      } catch {
        router.push('/auth');
      }
    };

    checkAuth();
  }, [sqid, API_BASE_URL, router]);

  // Load posts progressively
  const loadPosts = useCallback(
    async (cursor?: string | null) => {
      if (cursor) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }

      try {
        const params = new URLSearchParams({ limit: '512' });
        if (cursor) params.append('cursor', cursor);
        if (targetSqid) params.append('target_sqid', targetSqid);

        const response = await authenticatedFetch(
          `${API_BASE_URL}/api/pmd/posts?${params}`
        );

        if (!response.ok) {
          throw new Error('Failed to load posts');
        }

        const data = await response.json();

        if (cursor) {
          setPosts((prev) => [...prev, ...data.items]);
        } else {
          setPosts(data.items);
          setTotalCount(data.total_count);
        }

        setNextCursor(data.next_cursor);

        // Auto-load more if there's more data
        if (data.next_cursor) {
          // Small delay to not overwhelm the server
          setTimeout(() => loadPosts(data.next_cursor), 100);
        }
      } catch (err) {
        console.error('Error loading posts:', err);
        setError('Failed to load posts');
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [API_BASE_URL, targetSqid]
  );

  // Load BDRs
  const loadBDRs = useCallback(async () => {
    try {
      const url = targetSqid
        ? `${API_BASE_URL}/api/pmd/bdr?target_sqid=${encodeURIComponent(targetSqid)}`
        : `${API_BASE_URL}/api/pmd/bdr`;
      const response = await authenticatedFetch(url);
      if (response.ok) {
        const data = await response.json();
        setBdrs(data.items);
      }
    } catch (err) {
      console.error('Error loading BDRs:', err);
    }
  }, [API_BASE_URL, targetSqid]);

  // Initial load
  useEffect(() => {
    if (isOwnProfile === true || targetSqid !== null) {
      loadPosts();
      loadBDRs();
    }
  }, [isOwnProfile, targetSqid, loadPosts, loadBDRs]);

  // SSE for BDR updates
  const handleBDRUpdate = useCallback((updatedBdr: BDRItem) => {
    setBdrs((prev) => {
      const index = prev.findIndex((b) => b.id === updatedBdr.id);
      if (index >= 0) {
        const newBdrs = [...prev];
        newBdrs[index] = updatedBdr;
        return newBdrs;
      }
      return [updatedBdr, ...prev];
    });

    if (updatedBdr.status === 'ready') {
      alert(`Download ready! ${updatedBdr.artwork_count} artworks`);
    } else if (updatedBdr.status === 'failed') {
      alert(`Download failed: ${updatedBdr.error_message || 'Unknown error'}`);
    }
  }, []);

  usePMDSSE({
    enabled: isOwnProfile === true || targetSqid !== null,
    targetSqid: targetSqid,
    onBDRUpdate: handleBDRUpdate,
  });

  // Batch action handlers
  const handleBatchAction = useCallback(
    async (action: 'hide' | 'unhide' | 'delete', postIds: number[]) => {
      setActionLoading(true);

      // Chunk into batches of 128
      const chunks: number[][] = [];
      for (let i = 0; i < postIds.length; i += 128) {
        chunks.push(postIds.slice(i, i + 128));
      }

      let totalAffected = 0;

      try {
        for (let i = 0; i < chunks.length; i++) {
          const chunk = chunks[i];

          if (chunks.length > 1) {
            console.log(`Processing batch ${i + 1} of ${chunks.length}...`);
          }

          const url = targetSqid
            ? `${API_BASE_URL}/api/pmd/action?target_sqid=${encodeURIComponent(targetSqid)}`
            : `${API_BASE_URL}/api/pmd/action`;
          const response = await authenticatedFetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, post_ids: chunk }),
          });

          if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Action failed');
          }

          const result = await response.json();
          totalAffected += result.affected_count;

          // Update local state
          if (action === 'delete') {
            setPosts((prev) => prev.filter((p) => !chunk.includes(p.id)));
          } else {
            setPosts((prev) =>
              prev.map((p) =>
                chunk.includes(p.id) ? { ...p, hidden_by_user: action === 'hide' } : p
              )
            );
          }
        }

        // Clear selection
        setSelectedIds(new Set());

        // Show success message
        const actionName =
          action === 'hide' ? 'hidden' : action === 'unhide' ? 'unhidden' : 'deleted';
        alert(`Successfully ${actionName} ${totalAffected} post(s)`);
      } catch (err) {
        console.error('Batch action error:', err);
        alert(err instanceof Error ? err.message : 'Action failed');
      } finally {
        setActionLoading(false);
      }
    },
    [API_BASE_URL, targetSqid]
  );

  // Single post hide/unhide toggle
  const handleToggleHide = useCallback(
    async (postId: number) => {
      const post = posts.find((p) => p.id === postId);
      if (!post) return;

      const action = post.hidden_by_user ? 'unhide' : 'hide';

      try {
        const url = targetSqid
          ? `${API_BASE_URL}/api/pmd/action?target_sqid=${encodeURIComponent(targetSqid)}`
          : `${API_BASE_URL}/api/pmd/action`;
        const response = await authenticatedFetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action, post_ids: [postId] }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Action failed');
        }

        // Update local state
        setPosts((prev) =>
          prev.map((p) =>
            p.id === postId ? { ...p, hidden_by_user: !p.hidden_by_user } : p
          )
        );
      } catch (err) {
        console.error('Toggle hide error:', err);
        alert(err instanceof Error ? err.message : 'Action failed');
      }
    },
    [API_BASE_URL, posts, targetSqid]
  );

  // Single post delete
  const handleDeleteSingle = useCallback(
    async (postId: number) => {
      try {
        const url = targetSqid
          ? `${API_BASE_URL}/api/pmd/action?target_sqid=${encodeURIComponent(targetSqid)}`
          : `${API_BASE_URL}/api/pmd/action`;
        const response = await authenticatedFetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'delete', post_ids: [postId] }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Action failed');
        }

        // Update local state
        setPosts((prev) => prev.filter((p) => p.id !== postId));
        // Clear from selection if selected
        setSelectedIds((prev) => {
          const newSet = new Set(prev);
          newSet.delete(postId);
          return newSet;
        });
      } catch (err) {
        console.error('Delete error:', err);
        alert(err instanceof Error ? err.message : 'Action failed');
      }
    },
    [API_BASE_URL, targetSqid]
  );

  // BDR request handler
  const handleRequestDownload = useCallback(
    async (
      postIds: number[],
      includeCommentsAndReactions: boolean,
      sendEmail: boolean
    ) => {
      setActionLoading(true);

      try {
        const url = targetSqid
          ? `${API_BASE_URL}/api/pmd/bdr?target_sqid=${encodeURIComponent(targetSqid)}`
          : `${API_BASE_URL}/api/pmd/bdr`;
        const response = await authenticatedFetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            post_ids: postIds,
            include_comments: includeCommentsAndReactions,
            include_reactions: includeCommentsAndReactions,
            send_email: sendEmail,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Request failed');
        }

        const result = await response.json();

        // Add to local BDR list
        setBdrs((prev) => [
          {
            id: result.id,
            status: result.status,
            artwork_count: result.artwork_count,
            created_at: result.created_at,
            completed_at: null,
            expires_at: null,
            error_message: null,
            download_url: null,
          },
          ...prev,
        ]);
      } catch (err) {
        console.error('BDR request error:', err);
        alert(err instanceof Error ? err.message : 'Request failed');
      } finally {
        setActionLoading(false);
      }
    },
    [API_BASE_URL, targetSqid]
  );

  // Loading state - wait for auth check to complete
  if (loading || (isOwnProfile === null && targetSqid === null)) {
    return (
      <Layout title="Post Management">
        <div className="loading-container">
          <div className="loading-spinner"></div>
        </div>
        <style jsx>{`
          .loading-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - 200px);
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

  // Error state
  if (error) {
    return (
      <Layout title="Post Management">
        <div className="error-container">
          <p>{error}</p>
          <Link href={`/u/${sqid}`}>Back to Profile</Link>
        </div>
        <style jsx>{`
          .error-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - 200px);
            gap: 16px;
          }

          .error-container p {
            color: #ef4444;
          }

          .error-container a {
            color: var(--accent-cyan);
          }
        `}</style>
      </Layout>
    );
  }

  const pageTitle = targetSqid ? `PMD - ${sqid}` : 'Post Management Dashboard';

  return (
    <Layout title={pageTitle}>
      <div className="pmd-container">
        <div className="pmd-header">
          <Link href={`/u/${sqid}`} className="back-link">
            &#8592; Back to Profile
          </Link>
          <h1>{targetSqid ? `Post Management Dashboard - ${sqid}` : 'Post Management Dashboard'}</h1>
          <p className="total-count">{totalCount} total posts</p>
        </div>

        <div className="pmd-main">
          <PostTable
            posts={posts}
            selectedIds={selectedIds}
            setSelectedIds={setSelectedIds}
            currentPage={currentPage}
            setCurrentPage={setCurrentPage}
            itemsPerPage={itemsPerPage}
            loading={loadingMore}
            onToggleHide={handleToggleHide}
            onDelete={handleDeleteSingle}
          />

          <BulkActionsPanel
            selectedCount={selectedIds.size}
            selectedIds={selectedIds}
            onHide={() => handleBatchAction('hide', Array.from(selectedIds))}
            onUnhide={() => handleBatchAction('unhide', Array.from(selectedIds))}
            onDelete={() => handleBatchAction('delete', Array.from(selectedIds))}
            onRequestDownload={handleRequestDownload}
            loading={actionLoading}
          />
        </div>

        <DownloadRequestsPanel bdrs={bdrs} />
      </div>

      <style jsx>{`
        .pmd-container {
          max-width: 1024px;
          margin: 0 auto;
          padding: 24px;
        }

        .pmd-header {
          margin-bottom: 24px;
        }

        .back-link {
          color: var(--accent-cyan);
          font-size: 0.9rem;
          display: inline-block;
          margin-bottom: 16px;
          text-decoration: none;
        }

        .back-link:hover {
          text-decoration: underline;
        }

        h1 {
          font-size: 1.75rem;
          color: var(--text-primary);
          margin: 0 0 8px 0;
        }

        .total-count {
          color: var(--text-secondary);
          font-size: 0.9rem;
          margin: 0;
        }

        .pmd-main {
          background: var(--bg-secondary);
          border-radius: 8px;
          border: 1px solid rgba(255, 255, 255, 0.1);
          overflow: hidden;
        }

        @media (max-width: 1024px) {
          .pmd-container {
            padding: 0;
          }

          .pmd-header {
            padding: 16px;
            margin-bottom: 0;
          }

          .pmd-main {
            border-radius: 0;
            border-left: none;
            border-right: none;
          }
        }
      `}</style>
    </Layout>
  );
}

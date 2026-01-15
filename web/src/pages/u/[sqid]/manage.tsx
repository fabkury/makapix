/**
 * User Management Dashboard (UMD) page.
 * Moderator-only page for managing individual users.
 * Access: /u/{sqid}/manage
 */

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/router';
import Layout from '../../../components/Layout';
import { authenticatedFetch } from '../../../lib/api';
import {
  ReputationPanel,
  BadgePanel,
  RecentCommentsPanel,
  ViolationsPanel,
  ModeratorActionsPanel,
  OwnerPanel,
} from '../../../components/umd';

interface BadgeGrant {
  badge: string;
  granted_at: string;
}

interface UMDUserData {
  id: number;
  user_key: string;
  public_sqid: string;
  handle: string;
  avatar_url: string | null;
  reputation: number;
  badges: BadgeGrant[];
  auto_public_approval: boolean;
  hidden_by_mod: boolean;
  banned_until: string | null;
  roles: string[];
  created_at: string;
}

export default function UserManagementDashboard() {
  const router = useRouter();
  const { sqid } = router.query;

  const [userData, setUserData] = useState<UMDUserData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModerator, setIsModerator] = useState(false);
  const [isViewerOwner, setIsViewerOwner] = useState(false);
  const [checkedAuth, setCheckedAuth] = useState(false);

  const API_BASE_URL = useMemo(
    () => typeof window !== 'undefined'
      ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
      : '',
    []
  );

  // Check if current user is a moderator/owner
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await authenticatedFetch(`${API_BASE_URL}/api/auth/me`);
        if (response.ok) {
          const data = await response.json();
          const roles = data.roles as string[] || [];
          const isMod = roles.includes('moderator') || roles.includes('owner');
          const isOwner = roles.includes('owner');
          setIsModerator(isMod);
          setIsViewerOwner(isOwner);
          if (!isMod) {
            router.push('/');
          }
        } else {
          router.push('/auth');
        }
      } catch {
        router.push('/auth');
      } finally {
        setCheckedAuth(true);
      }
    };
    checkAuth();
  }, [API_BASE_URL, router]);

  // Fetch user data for management
  useEffect(() => {
    if (!sqid || typeof sqid !== 'string' || !checkedAuth || !isModerator) return;

    const fetchUserData = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await authenticatedFetch(
          `${API_BASE_URL}/api/admin/user/${sqid}/manage`
        );

        if (!response.ok) {
          if (response.status === 401) {
            router.push('/auth');
            return;
          } else if (response.status === 403) {
            // Target is owner, redirect to their profile
            router.push(`/u/${sqid}`);
            return;
          } else if (response.status === 404) {
            setError('User not found');
          } else {
            setError('Failed to load user data');
          }
          setLoading(false);
          return;
        }

        const data = await response.json();
        setUserData(data);
      } catch (err) {
        setError('Failed to load user data');
      } finally {
        setLoading(false);
      }
    };

    fetchUserData();
  }, [sqid, checkedAuth, isModerator, API_BASE_URL, router]);

  // Show loading while checking auth
  if (!checkedAuth) {
    return (
      <Layout title="User Management">
        <div className="loading-container">
          <div className="loading">Checking permissions...</div>
        </div>
        <style jsx>{`
          .loading-container {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 50vh;
          }
          .loading {
            color: var(--text-muted);
          }
        `}</style>
      </Layout>
    );
  }

  // Non-moderator - will redirect
  if (!isModerator) {
    return null;
  }

  // Handle reputation change
  const handleReputationChange = (newReputation: number) => {
    if (userData) {
      setUserData({ ...userData, reputation: newReputation });
    }
  };

  // Handle badges change
  const handleBadgesChange = (badges: BadgeGrant[]) => {
    if (userData) {
      setUserData({ ...userData, badges });
    }
  };

  // Handle trust change
  const handleTrustChange = (trusted: boolean) => {
    if (userData) {
      setUserData({ ...userData, auto_public_approval: trusted });
    }
  };

  // Handle hidden change
  const handleHiddenChange = (hidden: boolean) => {
    if (userData) {
      setUserData({ ...userData, hidden_by_mod: hidden });
    }
  };

  // Handle ban change
  const handleBanChange = (bannedUntil: string | null) => {
    if (userData) {
      setUserData({ ...userData, banned_until: bannedUntil });
    }
  };

  // Handle moderator status change (owner only)
  const handleModeratorChange = (isMod: boolean) => {
    if (userData) {
      const newRoles = isMod
        ? [...userData.roles.filter(r => r !== 'moderator'), 'moderator']
        : userData.roles.filter(r => r !== 'moderator');
      setUserData({ ...userData, roles: newRoles });
    }
  };

  const isBanned = userData?.banned_until
    ? new Date(userData.banned_until) > new Date()
    : false;

  // Check if target user is a moderator
  const isTargetModerator = userData?.roles?.includes('moderator') || false;

  return (
    <Layout title={userData ? `Manage ${userData.handle}` : 'User Management'}>
      <div className="umd-container">
        {/* Header */}
        <header className="umd-header">
          <div className="header-content">
            <div className="header-text">
              <h1>User Management</h1>
              {userData && (
                <p className="managing-label">Managing: {userData.handle}</p>
              )}
            </div>
            {userData?.avatar_url && (
              <img
                src={userData.avatar_url}
                alt={`${userData.handle}'s avatar`}
                className="user-avatar"
              />
            )}
          </div>
        </header>

        {/* Content */}
        <main className="umd-main">
          {loading ? (
            <div className="loading">Loading user data...</div>
          ) : error ? (
            <div className="error">{error}</div>
          ) : userData ? (
            <div className="panels">
              <ReputationPanel
                sqid={userData.public_sqid}
                currentReputation={userData.reputation}
                onReputationChange={handleReputationChange}
              />
              <BadgePanel
                sqid={userData.public_sqid}
                currentBadges={userData.badges}
                onBadgesChange={handleBadgesChange}
              />
              <RecentCommentsPanel sqid={userData.public_sqid} />
              <ViolationsPanel sqid={userData.public_sqid} />
              <ModeratorActionsPanel
                sqid={userData.public_sqid}
                isTrusted={userData.auto_public_approval}
                isHidden={userData.hidden_by_mod}
                isBanned={isBanned}
                bannedUntil={userData.banned_until}
                onTrustChange={handleTrustChange}
                onHiddenChange={handleHiddenChange}
                onBanChange={handleBanChange}
              />
              {/* Owner Panel - only visible to site owner */}
              {isViewerOwner && (
                <OwnerPanel
                  userKey={userData.user_key}
                  isModerator={isTargetModerator}
                  onModeratorChange={handleModeratorChange}
                />
              )}
            </div>
          ) : null}
        </main>
      </div>

      <style jsx>{`
        .umd-container {
          min-height: 100vh;
          background: var(--bg-primary);
          padding-bottom: 32px;
        }
        .umd-header {
          position: sticky;
          top: var(--header-offset, 56px);
          z-index: 10;
          background: var(--bg-primary);
          border-bottom: 1px solid var(--border-color);
          box-shadow: 0 4px 16px rgba(0, 212, 255, 0.1);
          padding: 16px;
        }
        .header-content {
          max-width: 800px;
          margin: 0 auto;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .header-text h1 {
          font-size: 1.25rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0;
        }
        .managing-label {
          font-size: 0.9rem;
          color: var(--text-secondary);
          margin: 4px 0 0;
        }
        .user-avatar {
          width: 56px;
          height: 56px;
          border-radius: 50%;
          object-fit: cover;
          border: 2px solid var(--border-color);
        }
        .umd-main {
          max-width: 800px;
          margin: 0 auto;
          padding: 16px;
        }
        .loading, .error {
          text-align: center;
          padding: 48px 16px;
          color: var(--text-muted);
        }
        .error {
          color: var(--accent-pink);
        }
        .panels {
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        @media (max-width: 600px) {
          .umd-header {
            padding: 12px;
          }
          .header-text h1 {
            font-size: 1.1rem;
          }
          .user-avatar {
            width: 48px;
            height: 48px;
          }
          .umd-main {
            padding: 12px;
          }
        }
      `}</style>
    </Layout>
  );
}

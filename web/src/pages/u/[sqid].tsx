import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import CardGrid from '../../components/CardGrid';
import PlayerBar from '../../components/PlayerBarDynamic';
import { FilterButton } from '../../components/FilterButton';
import { authenticatedFetch, clearTokens } from '../../lib/api';
import { usePlayerBarOptional } from '../../contexts/PlayerBarContext';
import { useFilters, FilterConfig } from '../../hooks/useFilters';
import { calculatePageSize } from '../../utils/gridUtils';
import {
  TagBadges,
  ProfileStats,
  FollowButton,
  GiftButton,
  OwnerPanel,
  HighlightsGallery,
  ProfileTabs,
  MarkdownBio,
  BadgesOverlay,
} from '../../components/profile';
import {
  UserProfileEnhanced,
  BadgeGrant,
} from '../../types/profile';

interface PostOwner {
  id: string;
  handle: string;
  avatar_url?: string | null;
  public_sqid?: string;
}

interface Post {
  id: number;
  public_sqid: string;
  title: string;
  description?: string;
  hashtags?: string[];
  art_url: string;
  width: number;
  height: number;
  owner_id: string;
  created_at: string;
  owner?: PostOwner;
}

interface PageResponse<T> {
  items: T[];
  next_cursor: string | null;
}

export default function UserProfilePage() {
  const router = useRouter();
  const { sqid } = router.query;
  const playerBarContext = usePlayerBarOptional();
  const { filters, setFilters, buildApiQuery } = useFilters();

  // Profile state
  const [profile, setProfile] = useState<UserProfileEnhanced | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [reactedPosts, setReactedPosts] = useState<Post[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [reactedNextCursor, setReactedNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [postsLoading, setPostsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [hasMoreReacted, setHasMoreReacted] = useState(true);

  // Tab state
  const [activeTab, setActiveTab] = useState<'gallery' | 'favourites'>('gallery');

  // Badge overlay state
  const [showBadgesOverlay, setShowBadgesOverlay] = useState(false);

  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editHandle, setEditHandle] = useState('');
  const [editBio, setEditBio] = useState('');
  const [editTagline, setEditTagline] = useState('');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);
  const [avatarUploadError, setAvatarUploadError] = useState<string | null>(null);
  const avatarInputRef = useRef<HTMLInputElement>(null);
  const [isAvatarDragOver, setIsAvatarDragOver] = useState(false);
  const [isModerator, setIsModerator] = useState(false);
  const [isViewerOwner, setIsViewerOwner] = useState(false);
  const [isOwner, setIsOwner] = useState(false);

  // Handle availability check state
  const [handleStatus, setHandleStatus] = useState<'idle' | 'checking' | 'available' | 'taken' | 'invalid'>('idle');
  const [handleMessage, setHandleMessage] = useState<string>('');

  // Follow state
  const [isFollowing, setIsFollowing] = useState(false);

  // Account deletion state
  const [deletionStep, setDeletionStep] = useState<'initial' | 'confirm-1' | 'confirm-2' | 'final-1' | 'final-2' | 'deleting' | 'success'>('initial');
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deletionError, setDeletionError] = useState<string | null>(null);

  const observerTarget = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);
  const hasMoreReactedRef = useRef(true);
  const nextCursorRef = useRef<string | null>(null);
  const reactedNextCursorRef = useRef<string | null>(null);
  const pageSizeRef = useRef(20);
  const filtersRef = useRef(filters);

  const API_BASE_URL = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Calculate page size on mount (client-side only)
  useEffect(() => {
    pageSizeRef.current = calculatePageSize();
  }, []);

  // Fetch enhanced user profile
  useEffect(() => {
    if (!sqid || typeof sqid !== 'string') return;

    const fetchProfile = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await authenticatedFetch(`${API_BASE_URL}/api/user/u/${sqid}/profile`);

        if (response.status === 401) {
          // Token refresh failed - treat as unauthenticated
          setIsModerator(false);
          setIsViewerOwner(false);
        }

        if (!response.ok) {
          if (response.status === 404) {
            setError('User not found');
          } else {
            setError(`Failed to load profile: ${response.statusText}`);
          }
          setLoading(false);
          return;
        }

        const data: UserProfileEnhanced = await response.json();
        setProfile(data);
        setEditHandle(data.handle);
        setEditBio(data.bio || '');
        setEditTagline(data.tagline || '');
        setIsOwner(data.badges?.some((b: BadgeGrant) => b.badge === 'owner') || false);
        setIsFollowing(data.is_following);

        // Check viewer moderator status
        if (!data.is_own_profile) {
          try {
            const meResponse = await authenticatedFetch(`${API_BASE_URL}/api/auth/me`);
            if (meResponse.ok) {
              const meData = await meResponse.json();
              const roles = meData.roles || [];
              setIsModerator(roles.includes('moderator') || roles.includes('owner'));
              setIsViewerOwner(roles.includes('owner'));
            } else {
              setIsModerator(false);
              setIsViewerOwner(false);
            }
          } catch (err) {
            console.error('Error checking moderator status:', err);
            setIsModerator(false);
            setIsViewerOwner(false);
          }
        }
      } catch (err) {
        setError('Failed to load profile');
        console.error('Error fetching profile:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, [sqid, API_BASE_URL]);

  // Set current channel for PlayerBar
  useEffect(() => {
    if (playerBarContext && profile && sqid && typeof sqid === 'string') {
      playerBarContext.setCurrentChannel({
        displayName: profile.handle,
        userSqid: sqid,
        userHandle: profile.handle,
      });
    }
    return () => {
      if (playerBarContext) {
        playerBarContext.setCurrentChannel(null);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile, sqid]);

  // Handle filter changes
  const handleFilterChange = useCallback((newFilters: FilterConfig) => {
    setFilters(newFilters);
  }, [setFilters]);

  // Load user's posts
  const loadPosts = useCallback(async (cursor: string | null = null) => {
    if (!profile) return;
    if (loadingRef.current || (cursor !== null && !hasMoreRef.current)) return;

    loadingRef.current = true;
    setPostsLoading(true);

    try {
      const baseParams: Record<string, string> = {
        owner_id: profile.user_key,
        limit: String(pageSizeRef.current),
      };
      if (!filters.sortBy) {
        baseParams.sort = 'created_at';
        baseParams.order = 'desc';
      }
      const queryString = buildApiQuery(baseParams);
      const url = `${API_BASE_URL}/api/post?${queryString}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
      const response = await authenticatedFetch(url);

      if (!response.ok) {
        throw new Error('Failed to load posts');
      }

      const data: PageResponse<Post> = await response.json();

      if (cursor) {
        setPosts(prev => [...prev, ...data.items]);
      } else {
        setPosts(data.items);
      }

      setNextCursor(data.next_cursor);
      nextCursorRef.current = data.next_cursor;
      const hasMoreValue = data.next_cursor !== null;
      hasMoreRef.current = hasMoreValue;
      setHasMore(hasMoreValue);
    } catch (err) {
      console.error('Error loading posts:', err);
    } finally {
      loadingRef.current = false;
      setPostsLoading(false);
    }
  }, [profile, API_BASE_URL, buildApiQuery, filters.sortBy]);

  // Load reacted posts (favourites)
  const loadReactedPosts = useCallback(async (cursor: string | null = null) => {
    if (!profile) return;
    if (loadingRef.current || (cursor !== null && !hasMoreReactedRef.current)) return;

    loadingRef.current = true;
    setPostsLoading(true);

    try {
      const url = `${API_BASE_URL}/api/user/u/${profile.public_sqid}/reacted-posts?limit=${pageSizeRef.current}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
      const response = await authenticatedFetch(url);

      if (!response.ok) {
        throw new Error('Failed to load reacted posts');
      }

      const data: PageResponse<Post> = await response.json();

      if (cursor) {
        setReactedPosts(prev => [...prev, ...data.items]);
      } else {
        setReactedPosts(data.items);
      }

      setReactedNextCursor(data.next_cursor);
      reactedNextCursorRef.current = data.next_cursor;
      const hasMoreValue = data.next_cursor !== null;
      hasMoreReactedRef.current = hasMoreValue;
      setHasMoreReacted(hasMoreValue);
    } catch (err) {
      console.error('Error loading reacted posts:', err);
    } finally {
      loadingRef.current = false;
      setPostsLoading(false);
    }
  }, [profile, API_BASE_URL]);

  // Load posts when profile is loaded
  useEffect(() => {
    if (profile) {
      loadPosts();
    }
  }, [profile, loadPosts]);

  // Load reacted posts when switching to favourites tab
  useEffect(() => {
    if (profile && activeTab === 'favourites' && reactedPosts.length === 0) {
      loadReactedPosts();
    }
  }, [profile, activeTab, reactedPosts.length, loadReactedPosts]);

  // Reset posts when filters change
  useEffect(() => {
    const prevFilters = filtersRef.current;
    const filtersChanged = JSON.stringify(prevFilters) !== JSON.stringify(filters);

    if (filtersChanged && profile) {
      filtersRef.current = filters;
      setPosts([]);
      setNextCursor(null);
      nextCursorRef.current = null;
      hasMoreRef.current = true;
      setHasMore(true);
      loadPosts();
    }
  }, [filters, profile, loadPosts]);

  // Handle tab change
  const handleTabChange = (tab: 'gallery' | 'favourites') => {
    setActiveTab(tab);
  };

  // Handle entering edit mode
  const handleEditClick = () => {
    if (profile) {
      setEditHandle(profile.handle);
      setEditBio(profile.bio || '');
      setEditTagline(profile.tagline || '');
      setSaveError(null);
      setAvatarUploadError(null);
      setHandleStatus('idle');
      setHandleMessage('');
      setIsEditing(true);
    }
  };

  // Handle canceling edit mode
  const handleCancelEdit = () => {
    if (profile) {
      setEditHandle(profile.handle);
      setEditBio(profile.bio || '');
      setEditTagline(profile.tagline || '');
      setSaveError(null);
      setAvatarUploadError(null);
      setHandleStatus('idle');
      setHandleMessage('');
      resetDeletionState();
      setIsEditing(false);
    }
  };

  // Check handle availability
  const checkHandleAvailability = async () => {
    if (!editHandle.trim()) {
      setHandleStatus('invalid');
      setHandleMessage('Handle cannot be empty');
      return;
    }

    setHandleStatus('checking');
    setHandleMessage('');

    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/auth/check-handle-availability`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ handle: editHandle.trim() }),
      });

      if (!response.ok) {
        throw new Error('Failed to check handle availability');
      }

      const data = await response.json();

      if (data.available) {
        setHandleStatus('available');
        setHandleMessage(data.message);
      } else {
        setHandleStatus(data.message.includes('Invalid') ? 'invalid' : 'taken');
        setHandleMessage(data.message);
      }
    } catch (err) {
      console.error('Error checking handle:', err);
      setHandleStatus('invalid');
      setHandleMessage('Failed to check availability');
    }
  };

  // Reset handle status when handle changes
  useEffect(() => {
    if (profile && editHandle !== profile.handle) {
      setHandleStatus('idle');
      setHandleMessage('');
    }
  }, [editHandle, profile]);

  const uploadAvatarFile = async (file: File) => {
    if (!profile) return;
    setAvatarUploadError(null);
    setIsUploadingAvatar(true);
    try {
      const form = new FormData();
      form.append('image', file);
      const res = await authenticatedFetch(`${API_BASE_URL}/api/user/${profile.user_key}/avatar`, {
        method: 'POST',
        body: form,
      });
      if (res.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setAvatarUploadError(err.detail || 'Failed to upload avatar');
        return;
      }
      const updatedUser = await res.json();
      setProfile(prev => prev ? { ...prev, avatar_url: updatedUser.avatar_url } : prev);
      window.dispatchEvent(
        new CustomEvent('makapix:user-updated', { detail: { avatar_url: updatedUser.avatar_url ?? null } })
      );
    } catch (e) {
      console.error('Error uploading avatar:', e);
      setAvatarUploadError('Failed to upload avatar');
    } finally {
      setIsUploadingAvatar(false);
      setIsAvatarDragOver(false);
    }
  };

  const removeAvatar = async () => {
    if (!profile) return;
    setAvatarUploadError(null);
    setIsUploadingAvatar(true);
    try {
      const res = await authenticatedFetch(`${API_BASE_URL}/api/user/${profile.user_key}/avatar`, {
        method: 'DELETE',
      });
      if (res.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setAvatarUploadError(err.detail || 'Failed to remove avatar');
        return;
      }
      const updatedUser = await res.json();
      setProfile(prev => prev ? { ...prev, avatar_url: updatedUser.avatar_url } : prev);
      window.dispatchEvent(
        new CustomEvent('makapix:user-updated', { detail: { avatar_url: updatedUser.avatar_url ?? null } })
      );
    } catch (e) {
      console.error('Error removing avatar:', e);
      setAvatarUploadError('Failed to remove avatar');
    } finally {
      setIsUploadingAvatar(false);
      setIsAvatarDragOver(false);
    }
  };

  // Handle saving profile changes
  const handleSaveProfile = async () => {
    if (!profile) return;

    setIsSaving(true);
    setSaveError(null);

    try {
      const payload: { handle?: string; bio?: string; tagline?: string } = {};

      if (editHandle.trim() !== profile.handle) {
        payload.handle = editHandle.trim();
      }

      if (editBio !== (profile.bio || '')) {
        payload.bio = editBio;
      }

      if (editTagline !== (profile.tagline || '')) {
        payload.tagline = editTagline;
      }

      if (Object.keys(payload).length === 0) {
        setIsEditing(false);
        setIsSaving(false);
        return;
      }

      const response = await authenticatedFetch(`${API_BASE_URL}/api/user/${profile.user_key}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        if (response.status === 409) {
          setSaveError('This handle is already taken');
        } else if (response.status === 400) {
          setSaveError(errorData.detail || 'Invalid handle format');
        } else {
          setSaveError(errorData.detail || 'Failed to save changes');
        }
        setIsSaving(false);
        return;
      }

      const updatedUser = await response.json();
      setProfile(prev => prev ? {
        ...prev,
        handle: updatedUser.handle,
        bio: updatedUser.bio,
        tagline: updatedUser.tagline,
      } : prev);
      setIsEditing(false);
    } catch (err) {
      console.error('Error saving profile:', err);
      setSaveError('Failed to save changes');
    } finally {
      setIsSaving(false);
    }
  };

  // Reset deletion state
  const resetDeletionState = () => {
    setDeletionStep('initial');
    setDeleteConfirmText('');
    setDeletionError(null);
  };

  // Handle account deletion
  const handleAccountDeletion = async () => {
    if (deletionStep === 'initial') {
      setDeletionStep('confirm-1');
      return;
    }

    if (deletionStep === 'confirm-1') {
      setDeletionStep('confirm-2');
      return;
    }

    if (deletionStep === 'confirm-2') {
      // Only proceed if user typed "delete"
      if (deleteConfirmText.toLowerCase() !== 'delete') {
        return;
      }
      setDeletionStep('final-1');
      return;
    }

    if (deletionStep === 'final-1') {
      setDeletionStep('final-2');
      return;
    }

    if (deletionStep === 'final-2') {
      // Actually delete the account
      setDeletionStep('deleting');
      setDeletionError(null);

      try {
        const response = await authenticatedFetch(`${API_BASE_URL}/api/user/delete-account`, {
          method: 'POST',
        });

        if (response.status === 401) {
          clearTokens();
          router.push('/auth');
          return;
        }

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          setDeletionError(errorData.detail || 'Failed to delete account');
          setDeletionStep('final-1');
          return;
        }

        setDeletionStep('success');

        // Clear tokens and redirect after 5 seconds
        setTimeout(() => {
          clearTokens();
          window.location.href = 'https://makapix.club/';
        }, 5000);

      } catch (err) {
        console.error('Error deleting account:', err);
        setDeletionError('Failed to delete account. Please try again.');
        setDeletionStep('final-1');
      }
    }
  };

  // Intersection Observer for infinite scroll
  useEffect(() => {
    if (!profile) return;

    const currentPosts = activeTab === 'gallery' ? posts : reactedPosts;
    const currentHasMore = activeTab === 'gallery' ? hasMoreRef.current : hasMoreReactedRef.current;

    if (currentPosts.length === 0 || !currentHasMore) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loadingRef.current) {
          if (activeTab === 'gallery' && hasMoreRef.current) {
            loadPosts(nextCursorRef.current);
          } else if (activeTab === 'favourites' && hasMoreReactedRef.current) {
            loadReactedPosts(reactedNextCursorRef.current);
          }
        }
      },
      { threshold: 0.1, root: null }
    );

    const currentTarget = observerTarget.current;
    if (currentTarget) {
      observer.observe(currentTarget);
    }

    return () => {
      if (currentTarget) {
        observer.unobserve(currentTarget);
      }
    };
  }, [profile, posts.length, reactedPosts.length, activeTab, loadPosts, loadReactedPosts]);

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
          @keyframes spin { to { transform: rotate(360deg); } }
        `}</style>
      </Layout>
    );
  }

  if (error || !profile) {
    return (
      <Layout title="Not Found">
        <div className="error-container">
          <span className="error-icon">😢</span>
          <h1>{error || 'User not found'}</h1>
          <Link href="/" className="back-link">← Back to Home</Link>
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
            margin-bottom: 1rem;
          }
          :global(.back-link) {
            color: var(--accent-cyan);
            font-size: 1rem;
          }
        `}</style>
      </Layout>
    );
  }

  const currentPosts = activeTab === 'gallery' ? posts : reactedPosts;
  const currentHasMore = activeTab === 'gallery' ? hasMore : hasMoreReacted;

  return (
    <Layout title={profile.handle} description={profile.bio || `${profile.handle}'s profile on Makapix Club`}>
      <FilterButton
        onFilterChange={handleFilterChange}
        initialFilters={filters}
        isLoading={loading}
      />
      <div className="profile-container">
        {/* Profile Header */}
        <div className="profile-header-wrapper">
          <div className="profile-header">
            {/* Identity Row: Avatar + Info + Desktop Action Buttons */}
            <div className="identity-row">
              {/* Avatar */}
              <div className="avatar-container">
                {profile.avatar_url ? (
                  <img src={profile.avatar_url} alt={profile.handle} className="avatar" />
                ) : (
                  <div className="avatar-placeholder">
                    {profile.handle.charAt(0).toUpperCase()}
                  </div>
                )}

                {isEditing && (
                  <>
                    <input
                      ref={avatarInputRef}
                      type="file"
                      accept="image/png,image/jpeg,image/jpg,image/gif,image/webp"
                      style={{ display: 'none' }}
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) void uploadAvatarFile(f);
                        e.currentTarget.value = '';
                      }}
                    />
                    <div
                      className={`avatar-dropzone ${isAvatarDragOver ? 'dragover' : ''}`}
                      onDragOver={(e) => { e.preventDefault(); setIsAvatarDragOver(true); }}
                      onDragLeave={() => setIsAvatarDragOver(false)}
                      onDrop={(e) => {
                        e.preventDefault();
                        const f = e.dataTransfer.files?.[0];
                        if (f) void uploadAvatarFile(f);
                      }}
                      onClick={() => avatarInputRef.current?.click()}
                      role="button"
                      tabIndex={0}
                      aria-label="Upload profile picture"
                      title="Drop an image or click to upload"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          avatarInputRef.current?.click();
                        }
                      }}
                    >
                      {isUploadingAvatar ? 'Uploading...' : 'Drop image or click'}
                    </div>
                    {profile.avatar_url && (
                      <button
                        type="button"
                        className="avatar-remove"
                        onClick={(e) => { e.preventDefault(); e.stopPropagation(); void removeAvatar(); }}
                        disabled={isUploadingAvatar}
                      >
                        Remove picture
                      </button>
                    )}
                  </>
                )}
              </div>

              {/* Name + Badges + Tagline */}
              <div className="identity-info">
                {isEditing ? (
                  <>
                    {!isOwner && (
                      <div className="handle-edit-row">
                        <input
                          type="text"
                          className={`edit-handle-input ${handleStatus === 'available' ? 'valid' : handleStatus === 'taken' || handleStatus === 'invalid' ? 'invalid' : ''}`}
                          value={editHandle}
                          onChange={(e) => setEditHandle(e.target.value)}
                          placeholder="Handle"
                          maxLength={32}
                        />
                        <button
                          type="button"
                          className="check-handle-btn"
                          onClick={checkHandleAvailability}
                          disabled={handleStatus === 'checking' || !editHandle.trim()}
                        >
                          {handleStatus === 'checking' ? '...' : 'Check'}
                        </button>
                      </div>
                    )}
                    {!isOwner && handleMessage && (
                      <p className={`handle-status ${handleStatus === 'available' ? 'success' : 'error'}`}>
                        {handleStatus === 'available' ? '✓' : '✗'} {handleMessage}
                      </p>
                    )}
                    {isOwner && <h1 className="display-name">{profile.handle}</h1>}

                    <input
                      type="text"
                      className="edit-tagline-input"
                      value={editTagline}
                      onChange={(e) => setEditTagline(e.target.value)}
                      placeholder="Tagline (appears under your name)"
                      maxLength={100}
                    />

                    <textarea
                      className="edit-bio-input"
                      value={editBio}
                      onChange={(e) => setEditBio(e.target.value)}
                      placeholder="Write something about yourself..."
                      maxLength={1000}
                      rows={3}
                    />
                    {avatarUploadError && <p className="save-error">{avatarUploadError}</p>}
                    {saveError && <p className="save-error">{saveError}</p>}

                    <div className="edit-actions">
                      <button className="save-btn" onClick={handleSaveProfile} disabled={isSaving}>
                        {isSaving ? 'Saving...' : 'Save changes'}
                      </button>
                      <button className="cancel-btn" onClick={handleCancelEdit} disabled={isSaving}>
                        Cancel
                      </button>
                    </div>

                    {/* Danger Zone - only visible on own profile and not for site owner */}
                    {profile.is_own_profile && !isOwner && (
                      <div className="danger-zone">
                        <h3 className="danger-zone-title">Danger Zone</h3>

                        {/* Success Overlay */}
                        {deletionStep === 'success' && (
                          <div className="deletion-overlay">
                            <div className="deletion-overlay-content">
                              <p>Your account will now be deleted.</p>
                              <p>You will be logged out.</p>
                            </div>
                          </div>
                        )}

                        {/* Initial state */}
                        {deletionStep === 'initial' && (
                          <button
                            type="button"
                            className="danger-btn danger-btn-initial"
                            onClick={handleAccountDeletion}
                          >
                            Delete this account
                          </button>
                        )}

                        {/* First confirmation */}
                        {deletionStep === 'confirm-1' && (
                          <button
                            type="button"
                            className="danger-btn danger-btn-confirm"
                            onClick={handleAccountDeletion}
                          >
                            Click again to confirm
                          </button>
                        )}

                        {/* Second confirmation with text input */}
                        {deletionStep === 'confirm-2' && (
                          <div className="delete-confirmation-box">
                            <p className="delete-warning-text">
                              This action is <strong>permanent</strong> and cannot be undone.
                              All your posts, comments, reactions, and profile data will be permanently deleted.
                            </p>
                            <label className="delete-confirm-label">
                              Type <strong>delete</strong> to confirm:
                              <input
                                type="text"
                                className="delete-confirm-input"
                                value={deleteConfirmText}
                                onChange={(e) => setDeleteConfirmText(e.target.value)}
                                placeholder="delete"
                                autoComplete="off"
                              />
                            </label>
                            <button
                              type="button"
                              className="danger-btn danger-btn-final"
                              onClick={handleAccountDeletion}
                              disabled={deleteConfirmText.toLowerCase() !== 'delete'}
                            >
                              Delete forever
                            </button>
                          </div>
                        )}

                        {/* Final confirmation */}
                        {deletionStep === 'final-1' && (
                          <>
                            {deletionError && <p className="deletion-error">{deletionError}</p>}
                            <button
                              type="button"
                              className="danger-btn danger-btn-final"
                              onClick={handleAccountDeletion}
                            >
                              Click again to confirm
                            </button>
                          </>
                        )}

                        {/* Very final confirmation */}
                        {deletionStep === 'final-2' && (
                          <button
                            type="button"
                            className="danger-btn danger-btn-final danger-btn-pulsing"
                            onClick={handleAccountDeletion}
                          >
                            Confirm permanent deletion
                          </button>
                        )}

                        {/* Deleting state */}
                        {deletionStep === 'deleting' && (
                          <div className="deleting-state">
                            <div className="loading-spinner-small"></div>
                            <p>Deleting your account...</p>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                ) : (
                  <>
                    <h1 className="display-name">{profile.handle}</h1>
                    <TagBadges
                      badges={profile.tag_badges || []}
                      onAreaClick={() => setShowBadgesOverlay(true)}
                    />
                    {profile.tagline && (
                      <p className="tagline">{profile.tagline}</p>
                    )}
                  </>
                )}
              </div>

              {/* Desktop Action Buttons (visitors only) */}
              {!isEditing && !profile.is_own_profile && (
                <div className="desktop-actions">
                  <FollowButton
                    userSqid={profile.public_sqid || ''}
                    initialFollowing={profile.is_following}
                    onFollowChange={(following, newCount) => {
                      setIsFollowing(following);
                      setProfile(prev => prev ? {
                        ...prev,
                        stats: { ...prev.stats, follower_count: newCount },
                        is_following: following,
                      } : prev);
                    }}
                  />
                  <GiftButton userSqid={profile.public_sqid || ''} />
                </div>
              )}
            </div>

            {/* Stats Row */}
            <ProfileStats stats={profile.stats} reputation={profile.reputation} />

            {/* Owner Panel (own profile or moderators) */}
            {!isEditing && (profile.is_own_profile || isModerator) && (
              <OwnerPanel
                userSqid={profile.public_sqid || ''}
                onEditClick={handleEditClick}
                isOwner={profile.is_own_profile}
                isModerator={isModerator}
                isTargetOwner={isOwner}
              />
            )}

            {/* Moderation Buttons */}
            {!isEditing && isModerator && (
              <div className="moderation-row">
                {/* UMD link - visible for self OR non-owner targets */}
                {(profile.is_own_profile || !isOwner) && (
                  <Link href={`/u/${profile.public_sqid}/manage`} className="mod-btn" title="User Management">
                    🛠️
                  </Link>
                )}
                {/* Edit button - only for others, not self */}
                {!profile.is_own_profile && (isViewerOwner || !(profile.badges?.some(b => b.badge === 'moderator' || b.badge === 'owner'))) && (
                  <button className="mod-btn" onClick={handleEditClick}>
                    ✏️ Edit
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Bio Section - separate panel */}
        {profile.bio && !isEditing && (
          <div className="bio-section-wrapper">
            <div className="bio-section">
              <MarkdownBio bio={profile.bio} />
            </div>
          </div>
        )}

        {/* Mobile Action Buttons (below bio, visitors only) */}
        {!isEditing && !profile.is_own_profile && (
          <div className="mobile-actions">
            <FollowButton
              userSqid={profile.public_sqid || ''}
              initialFollowing={profile.is_following}
              onFollowChange={(following, newCount) => {
                setIsFollowing(following);
                setProfile(prev => prev ? {
                  ...prev,
                  stats: { ...prev.stats, follower_count: newCount },
                  is_following: following,
                } : prev);
              }}
            />
            <GiftButton userSqid={profile.public_sqid || ''} />
          </div>
        )}

        {/* Highlights Gallery */}
        {profile.highlights && profile.highlights.length > 0 && (
          <HighlightsGallery highlights={profile.highlights} />
        )}

        {/* Tabs */}
        <ProfileTabs activeTab={activeTab} onTabChange={handleTabChange} />

        {/* Artworks Section */}
        <div className="artworks-section">
          {currentPosts.length === 0 && postsLoading && (
            <div className="loading-state">
              <div className="loading-spinner-small"></div>
              <p>Loading posts...</p>
            </div>
          )}

          {currentPosts.length === 0 && !postsLoading && (
            <div className="empty-state">
              <span className="empty-icon">{activeTab === 'gallery' ? '🎨' : '⚡'}</span>
              <p>{activeTab === 'gallery' ? 'No artworks yet' : 'No favourites yet'}</p>
            </div>
          )}

          {currentPosts.length > 0 && (
            <CardGrid
              key={activeTab}
              posts={currentPosts}
              API_BASE_URL={API_BASE_URL}
              source={{ type: 'profile', id: profile ? String(profile.id) : undefined }}
              cursor={activeTab === 'gallery' ? nextCursor : reactedNextCursor}
            />
          )}

          {currentPosts.length > 0 && (
            <div ref={observerTarget} className="load-more-trigger">
              {postsLoading && (
                <div className="loading-indicator">
                  <div className="loading-spinner-small"></div>
                </div>
              )}
              {!currentHasMore && (
                <div className="end-message">
                  <span>✨</span>
                  <div className="end-spacer" aria-hidden="true" />
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Badges Overlay */}
      <BadgesOverlay
        isOpen={showBadgesOverlay}
        onClose={() => setShowBadgesOverlay(false)}
        userBadges={profile.badges || []}
      />

      <style jsx>{`
        .profile-container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 0 24px 24px 24px;
        }

        .profile-header-wrapper {
          position: relative;
          left: 50%;
          right: 50%;
          width: 100vw;
          margin-left: -50vw;
          margin-right: -50vw;
          margin-top: 0;
          margin-bottom: 0;
          background: transparent;
        }

        .profile-header {
          max-width: 1200px;
          margin: 0 auto;
          padding: 24px;
        }

        .identity-row {
          display: flex;
          align-items: flex-end;
          justify-content: space-between;
          gap: 16px;
        }

        @media (max-width: 768px) {
          .identity-row {
            flex-wrap: wrap;
          }
        }

        .avatar-container {
          flex-shrink: 0;
          position: relative;
          width: 128px;
          height: 128px;
        }

        .avatar {
          width: 128px;
          height: 128px;
          border-radius: 0;
          object-fit: cover;
          border: 3px solid var(--bg-tertiary);
          image-rendering: pixelated;
        }

        .avatar-dropzone {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(0, 0, 0, 0.45);
          color: white;
          font-size: 0.8rem;
          font-weight: 600;
          text-align: center;
          padding: 10px;
          cursor: pointer;
          opacity: 0;
          transition: opacity var(--transition-fast), background var(--transition-fast);
        }

        .avatar-container:hover .avatar-dropzone {
          opacity: 1;
        }

        .avatar-dropzone.dragover {
          opacity: 1;
          background: rgba(0, 0, 0, 0.65);
        }

        .avatar-remove {
          position: absolute;
          left: 8px;
          right: 8px;
          bottom: 8px;
          z-index: 2;
          background: rgba(0, 0, 0, 0.7);
          border: 1px solid rgba(255, 255, 255, 0.18);
          color: rgba(255, 255, 255, 0.92);
          border-radius: 10px;
          padding: 6px 10px;
          font-size: 0.8rem;
          font-weight: 600;
          cursor: pointer;
          transition: background var(--transition-fast), border-color var(--transition-fast);
        }

        .avatar-remove:hover:enabled {
          background: rgba(0, 0, 0, 0.82);
          border-color: rgba(255, 255, 255, 0.28);
        }

        .avatar-remove:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .avatar-placeholder {
          width: 128px;
          height: 128px;
          border-radius: 0;
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 3rem;
          font-weight: 700;
          color: white;
          text-transform: uppercase;
        }

        .identity-info {
          flex: 1;
          min-width: 0;
          padding-bottom: 8px;
        }

        .desktop-actions {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-shrink: 0;
        }

        @media (max-width: 768px) {
          .desktop-actions {
            display: none;
          }
        }

        .mobile-actions {
          display: none;
          gap: 8px;
          margin-bottom: 24px;
        }

        @media (max-width: 768px) {
          .mobile-actions {
            display: flex;
          }
        }

        .moderation-row {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 16px;
        }

        .display-name {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0;
          line-height: 1.2;
        }

        .tagline {
          font-size: 0.95rem;
          color: var(--accent-cyan);
          margin: 0 0 12px 0;
          font-style: italic;
        }

        .bio-section-wrapper {
          position: relative;
          left: 50%;
          right: 50%;
          width: 100vw;
          margin-left: -50vw;
          margin-right: -50vw;
          margin-bottom: 24px;
          background: rgba(255, 255, 255, 0.05);
          border-top: 1px solid rgba(255, 255, 255, 0.1);
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .bio-section {
          max-width: 1200px;
          margin: 0 auto;
          padding: 16px 24px;
        }

        @media (max-width: 768px) {
          .bio-section-wrapper {
            border-radius: 0;
          }
          .bio-section {
            padding: 16px;
          }
        }

        :global(.mod-btn) {
          background: transparent;
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 6px;
          padding: 8px 12px;
          font-size: 1rem;
          cursor: pointer;
          color: var(--text-primary);
          text-decoration: none;
          transition: all var(--transition-fast);
        }

        :global(.mod-btn:hover) {
          background: rgba(255, 255, 255, 0.1);
          border-color: var(--accent-cyan);
        }

        .handle-edit-row {
          display: flex;
          gap: 8px;
          align-items: center;
          margin-bottom: 8px;
          max-width: 350px;
        }

        .edit-handle-input {
          font-size: 1.5rem;
          font-weight: 700;
          color: var(--text-primary);
          background: var(--bg-tertiary);
          border: 2px solid var(--bg-tertiary);
          border-radius: 8px;
          padding: 8px 12px;
          flex: 1;
          min-width: 0;
          transition: border-color var(--transition-fast);
        }

        .edit-handle-input:focus {
          outline: none;
          border-color: var(--accent-cyan);
        }

        .edit-handle-input.valid { border-color: #4ade80; color: #4ade80; }
        .edit-handle-input.invalid { border-color: #f87171; color: #f87171; }

        .check-handle-btn {
          padding: 8px 16px;
          background: var(--bg-tertiary);
          border: 2px solid var(--border-color);
          border-radius: 8px;
          color: var(--text-primary);
          font-size: 0.9rem;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
          white-space: nowrap;
        }

        .check-handle-btn:hover:not(:disabled) {
          border-color: var(--accent-cyan);
          color: var(--accent-cyan);
        }

        .check-handle-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .handle-status {
          font-size: 0.85rem;
          margin: 0 0 8px 0;
        }

        .handle-status.success { color: #4ade80; }
        .handle-status.error { color: #f87171; }

        .edit-tagline-input {
          font-size: 0.95rem;
          color: var(--accent-cyan);
          background: var(--bg-tertiary);
          border: 2px solid var(--bg-tertiary);
          border-radius: 8px;
          padding: 8px 12px;
          width: 100%;
          max-width: 400px;
          margin-bottom: 12px;
          font-style: italic;
          transition: border-color var(--transition-fast);
        }

        .edit-tagline-input:focus {
          outline: none;
          border-color: var(--accent-cyan);
        }

        .edit-bio-input {
          font-size: 1rem;
          color: var(--text-secondary);
          background: var(--bg-tertiary);
          border: 2px solid var(--bg-tertiary);
          border-radius: 8px;
          padding: 12px;
          width: 100%;
          max-width: 600px;
          resize: vertical;
          min-height: 80px;
          margin-bottom: 12px;
          font-family: inherit;
          line-height: 1.6;
          transition: border-color var(--transition-fast);
        }

        .edit-bio-input:focus {
          outline: none;
          border-color: var(--accent-cyan);
        }

        .save-error {
          color: var(--accent-pink);
          font-size: 0.9rem;
          margin: 0 0 12px 0;
        }

        .edit-actions {
          display: flex;
          gap: 12px;
          margin-top: 8px;
        }

        .save-btn {
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          border: none;
          border-radius: 8px;
          padding: 12px 32px;
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
          opacity: 0.6;
          cursor: not-allowed;
        }

        .cancel-btn {
          background: var(--bg-tertiary);
          color: var(--text-secondary);
          border: none;
          border-radius: 8px;
          padding: 12px 24px;
          font-size: 1rem;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .cancel-btn:hover:not(:disabled) {
          background: var(--bg-secondary);
          color: var(--text-primary);
        }

        .cancel-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        /* Danger Zone Styles */
        .danger-zone {
          margin-top: 32px;
          padding: 20px;
          border: 2px solid rgba(239, 68, 68, 0.3);
          border-radius: 12px;
          background: rgba(239, 68, 68, 0.05);
          max-width: 600px;
        }

        .danger-zone-title {
          font-size: 1rem;
          font-weight: 600;
          color: #ef4444;
          margin: 0 0 16px 0;
        }

        .danger-btn {
          padding: 12px 24px;
          font-size: 0.95rem;
          font-weight: 600;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .danger-btn-initial {
          background: transparent;
          border: 2px solid #ef4444;
          color: #ef4444;
        }

        .danger-btn-initial:hover {
          background: rgba(239, 68, 68, 0.1);
        }

        .danger-btn-confirm {
          background: rgba(245, 158, 11, 0.15);
          border: 2px solid #f59e0b;
          color: #f59e0b;
        }

        .danger-btn-confirm:hover {
          background: rgba(245, 158, 11, 0.25);
        }

        .danger-btn-final {
          background: #ef4444;
          border: 2px solid #ef4444;
          color: white;
        }

        .danger-btn-final:hover:not(:disabled) {
          background: #dc2626;
          border-color: #dc2626;
        }

        .danger-btn-final:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .danger-btn-pulsing {
          animation: pulse-danger 1s ease-in-out infinite;
        }

        @keyframes pulse-danger {
          0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
          50% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
        }

        .delete-confirmation-box {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .delete-warning-text {
          color: var(--text-secondary);
          font-size: 0.9rem;
          line-height: 1.5;
          margin: 0;
        }

        .delete-confirm-label {
          display: flex;
          flex-direction: column;
          gap: 8px;
          font-size: 0.9rem;
          color: var(--text-secondary);
        }

        .delete-confirm-input {
          padding: 10px 14px;
          background: var(--bg-tertiary);
          border: 2px solid var(--bg-tertiary);
          border-radius: 8px;
          font-size: 0.95rem;
          color: var(--text-primary);
          transition: border-color 0.2s ease;
          max-width: 200px;
        }

        .delete-confirm-input:focus {
          outline: none;
          border-color: #ef4444;
        }

        .deletion-error {
          color: #ef4444;
          font-size: 0.9rem;
          margin: 0 0 12px 0;
        }

        .deleting-state {
          display: flex;
          align-items: center;
          gap: 12px;
          color: var(--text-secondary);
        }

        .deletion-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.9);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 10000;
        }

        .deletion-overlay-content {
          text-align: center;
          color: var(--text-primary);
          font-size: 1.25rem;
          line-height: 2;
        }

        .artworks-section {
          min-height: 400px;
          margin-top: 0;
          position: relative;
          z-index: 1;
          /* Break out of profile-container to use full viewport width */
          left: 50%;
          right: 50%;
          width: 100vw;
          margin-left: -50vw;
          margin-right: -50vw;
        }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 4rem 2rem;
          text-align: center;
          color: var(--text-muted);
        }

        .empty-icon {
          font-size: 4rem;
          margin-bottom: 1rem;
          opacity: 0.5;
        }

        .loading-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 4rem 2rem;
          text-align: center;
          color: var(--text-muted);
          gap: 16px;
        }

        .load-more-trigger {
          min-height: 100px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .loading-indicator {
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .loading-spinner-small {
          width: 32px;
          height: 32px;
          border: 3px solid var(--bg-tertiary);
          border-top-color: var(--accent-cyan);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .end-message {
          color: var(--text-muted);
          font-size: 1.5rem;
          display: flex;
          flex-direction: column;
          align-items: center;
          padding-top: 24px;
        }

        .end-spacer {
          height: max(25vh, 200px);
          width: 1px;
        }
      `}</style>

      <PlayerBar />
    </Layout>
  );
}

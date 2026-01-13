# Profile Page Implementation

## Status: ⬜ Not Started

## Overview

This document describes the complete redesign of the user profile page at `web/src/pages/u/[sqid].tsx`.

---

## Design Reference

The Figma mock-up is at: `inbox/mpx-user-profile/src/app/App.tsx`

Key design elements from the mock-up:
- Dark theme (black background)
- Neon accent colors: `#00F5FF` (cyan) and `#FF006E` (pink)
- 5xl max-width container
- Responsive layout with 1024px breakpoint

---

## Page Structure

```
┌─────────────────────────────────────────────────────────────┐
│                        IDENTITY SECTION                      │
│  ┌──────┐                                                    │
│  │Avatar│  Username                                          │
│  │      │  [tag badges]  (click → badges overlay)            │
│  │      │  Tagline text here                                 │
│  └──────┘                                      [👣] [🎁]     │
│                                                              │
│  👤 24.5K | 🖼️ 342 | 👁️ 1.2M | 🧮 18.3K                      │
│                                                              │
│  [📊] [🗂️] [📺]    [✏️] [🚪]  (owner panel, own profile only)│
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                    MARKDOWN BIO                          │ │
│  │  Exploring the intersection of **digital art**...        │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  [👣] [🎁]  (mobile action buttons, below bio on mobile)     │
├─────────────────────────────────────────────────────────────┤
│  🖼️    ⚡    (tabs)                                          │
│  ───────────                                                 │
├─────────────────────────────────────────────────────────────┤
│  💎 HIGHLIGHTS (only if user has highlights)                 │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ → scroll          │
│  │     │ │     │ │     │ │     │ │     │                     │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  MAIN CONTENT (CardGrid)                                     │
│  ┌────┬────┬────┬────┬────┬────┬────┬────┐                  │
│  │    │    │    │    │    │    │    │    │                  │
│  ├────┼────┼────┼────┼────┼────┼────┼────┤                  │
│  │    │    │    │    │    │    │    │    │                  │
│  └────┴────┴────┴────┴────┴────┴────┴────┘                  │
│                    ∞ scroll                                  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## State Management

### Page State

```typescript
interface ProfilePageState {
  // User data
  user: User | null;
  loading: boolean;
  error: string | null;
  
  // Profile stats (from cached API)
  stats: UserProfileStats | null;
  
  // Tab state
  activeTab: 'gallery' | 'reactions';
  
  // Gallery tab data
  posts: Post[];
  postsNextCursor: string | null;
  postsLoading: boolean;
  postsHasMore: boolean;
  
  // Reactions tab data
  reactedPosts: Post[];
  reactedNextCursor: string | null;
  reactedLoading: boolean;
  reactedHasMore: boolean;
  
  // Highlights
  highlights: Highlight[];
  highlightsLoading: boolean;
  
  // Badges overlay
  showBadgesOverlay: boolean;
  
  // Edit mode
  isEditing: boolean;
  editHandle: string;
  editBio: string;
  editTagline: string;
  
  // Follow state
  isFollowing: boolean;
  followLoading: boolean;
  
  // Auth state
  isOwnProfile: boolean;
  isLoggedIn: boolean;
  isModerator: boolean;
}
```

---

## Data Fetching

### On Page Load

1. **Fetch user profile** (`GET /api/user/u/{sqid}`)
   - Includes `stats`, `tag_badges`, `tagline`, `badges`
   
2. **Fetch highlights** (`GET /api/user/u/{sqid}/highlights`)
   - Only if viewing profile (not editing)
   
3. **Fetch follow status** (`GET /api/user/u/{sqid}/follow-status`)
   - Only if logged in and not own profile
   
4. **Fetch initial posts** (`GET /api/post?owner_id={user_key}&limit=N`)
   - Using existing post endpoint with owner filter

### On Tab Switch to Reactions

1. **Fetch reacted posts** (`GET /api/user/u/{sqid}/reacted-posts`)
   - Paginated, loaded on first switch
   - Subsequent pages loaded on scroll

---

## Component Integration

### Identity Section

```tsx
<div className="identity-section">
  {/* Avatar */}
  <button className="avatar-button" onClick={handleAvatarClick}>
    <img src={user.avatar_url || defaultAvatar} />
  </button>
  
  {/* Name, badges, tagline */}
  <div className="identity-info">
    <h1>{user.handle}</h1>
    <TagBadges 
      badges={user.tag_badges} 
      onAreaClick={() => setShowBadgesOverlay(true)} 
    />
    {user.tagline && <p className="tagline">{user.tagline}</p>}
  </div>
  
  {/* Action buttons (desktop) */}
  {!isOwnProfile && (
    <div className="action-buttons desktop-only">
      <FollowButton 
        userSqid={sqid}
        isFollowing={isFollowing}
        isOwnProfile={isOwnProfile}
        isLoggedIn={isLoggedIn}
      />
      <GiftButton userSqid={sqid} isOwnProfile={isOwnProfile} />
    </div>
  )}
</div>
```

### Stats Section

```tsx
<ProfileStats
  followerCount={stats?.follower_count ?? 0}
  postCount={stats?.post_count ?? 0}
  viewCount={stats?.total_views ?? 0}
  reputation={user.reputation}
/>
```

### Owner Panel (Own Profile Only)

```tsx
{isOwnProfile && !isEditing && (
  <OwnerPanel
    userSqid={sqid}
    onEditClick={() => setIsEditing(true)}
    onLogoutClick={handleLogout}
  />
)}
```

### Bio Section

```tsx
<div className="bio-section">
  {isEditing ? (
    <textarea
      value={editBio}
      onChange={(e) => setEditBio(e.target.value)}
      placeholder="Write something about yourself..."
      maxLength={1000}
    />
  ) : (
    <MarkdownBio content={user.bio || ''} />
  )}
</div>
```

### Tabs

```tsx
<ProfileTabs
  activeTab={activeTab}
  onTabChange={(tab) => {
    setActiveTab(tab);
    if (tab === 'reactions' && reactedPosts.length === 0) {
      fetchReactedPosts();
    }
  }}
/>
```

### Highlights (Conditional)

```tsx
{highlights.length > 0 && (
  <div className="highlights-section">
    <h2 className="highlights-header">💎</h2>
    <HighlightsGallery
      highlights={highlights}
      onPostClick={(sqid) => router.push(`/p/${sqid}`)}
    />
  </div>
)}
```

### Main Content Area

```tsx
<div className="content-area">
  {activeTab === 'gallery' ? (
    <>
      {posts.length === 0 && !postsLoading && (
        <EmptyState icon="🎨" message="No artworks yet" />
      )}
      {posts.length > 0 && (
        <CardGrid posts={posts} API_BASE_URL={API_BASE_URL} source={source} />
      )}
    </>
  ) : (
    <>
      {reactedPosts.length === 0 && !reactedLoading && (
        <EmptyState icon="⚡" message="No reactions yet" />
      )}
      {reactedPosts.length > 0 && (
        <CardGrid posts={reactedPosts} API_BASE_URL={API_BASE_URL} source={reactedSource} />
      )}
    </>
  )}
  
  {/* Infinite scroll trigger */}
  <div ref={observerTarget} className="load-more-trigger">
    {(postsLoading || reactedLoading) && <LoadingSpinner />}
  </div>
</div>
```

---

## Responsive Design

### Breakpoint: 1024px

**Desktop (≥1024px)**:
- Action buttons (follow, gift) appear next to identity info
- Wider layout with more columns in CardGrid
- Stats in single horizontal row

**Mobile (<1024px)**:
- Action buttons appear below the bio section
- Narrower layout
- Stats may wrap to multiple rows if needed
- Larger touch targets

### CSS Structure

```css
/* Mobile-first approach */
.profile-container {
  max-width: 1280px;  /* 5xl equivalent */
  margin: 0 auto;
  padding: 0 16px;
}

/* Identity section */
.identity-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (min-width: 1024px) {
  .identity-section {
    flex-direction: row;
    align-items: flex-end;
    justify-content: space-between;
  }
}

/* Action buttons */
.action-buttons.desktop-only {
  display: none;
}

.action-buttons.mobile-only {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

@media (min-width: 1024px) {
  .action-buttons.desktop-only {
    display: flex;
    gap: 8px;
  }
  
  .action-buttons.mobile-only {
    display: none;
  }
}
```

---

## Edit Mode

When user clicks ✏️ edit button:

1. Switch to edit mode (`isEditing = true`)
2. Show editable fields:
   - Handle (if not owner)
   - Tagline (new)
   - Bio (existing)
   - Avatar upload (existing)
3. Show Save/Cancel buttons
4. On save, call `PATCH /api/user/{user_key}` with updated fields

### Edit Form Fields

```tsx
{isEditing && (
  <div className="edit-form">
    {/* Handle edit (existing logic) */}
    {!isOwner && (
      <input
        value={editHandle}
        onChange={(e) => setEditHandle(e.target.value)}
        maxLength={32}
      />
    )}
    
    {/* Tagline edit (new) */}
    <input
      value={editTagline}
      onChange={(e) => setEditTagline(e.target.value)}
      placeholder="Short tagline (48 chars max)"
      maxLength={48}
    />
    
    {/* Bio edit (existing) */}
    <textarea
      value={editBio}
      onChange={(e) => setEditBio(e.target.value)}
      placeholder="Bio with Markdown support..."
      maxLength={1000}
    />
    
    <div className="edit-actions">
      <button onClick={handleSave}>Save</button>
      <button onClick={handleCancel}>Cancel</button>
    </div>
  </div>
)}
```

---

## Badges Overlay Integration

```tsx
<BadgesOverlay
  badges={user.badges.map(grant => ({
    badge: grant.badge,
    label: grant.definition?.label ?? grant.badge,
    description: grant.definition?.description,
    icon_url_64: grant.definition?.icon_url_64 ?? `/badges/${grant.badge}_64.png`,
    granted_at: grant.granted_at,
  }))}
  isOpen={showBadgesOverlay}
  onClose={() => setShowBadgesOverlay(false)}
  username={user.handle}
/>
```

---

## API Integration

### New API Calls Needed

```typescript
// Follow/Unfollow
async function followUser(sqid: string): Promise<void> {
  await authenticatedFetch(`/api/user/u/${sqid}/follow`, { method: 'POST' });
}

async function unfollowUser(sqid: string): Promise<void> {
  await authenticatedFetch(`/api/user/u/${sqid}/follow`, { method: 'DELETE' });
}

async function getFollowStatus(sqid: string): Promise<{ is_following: boolean }> {
  const res = await authenticatedFetch(`/api/user/u/${sqid}/follow-status`);
  return res.json();
}

// Highlights
async function getHighlights(sqid: string): Promise<{ items: Highlight[] }> {
  const res = await authenticatedFetch(`/api/user/u/${sqid}/highlights`);
  return res.json();
}

// Reacted posts
async function getReactedPosts(sqid: string, cursor?: string): Promise<Page<Post>> {
  const url = `/api/user/u/${sqid}/reacted-posts${cursor ? `?cursor=${cursor}` : ''}`;
  const res = await authenticatedFetch(url);
  return res.json();
}
```

---

## Migration from Existing Page

### Keep
- Layout structure
- CardGrid integration
- Infinite scroll logic
- Edit mode avatar upload
- Moderation buttons (trust, ban)
- Filter button

### Remove
- Old stats display (artworks count from posts.length, reputation, joined year)
- Old profile actions layout

### Add
- All new components (see components doc)
- Tab switching
- Highlights section
- New stats row
- Follow/gift buttons
- Markdown bio
- Tag badges

---

## Completion Checklist

- [ ] Page structure updated to match Figma
- [ ] Identity section with avatar, username, tag badges, tagline
- [ ] ProfileStats component integrated
- [ ] OwnerPanel component integrated
- [ ] MarkdownBio component integrated
- [ ] Follow/Gift buttons integrated
- [ ] ProfileTabs component integrated
- [ ] HighlightsGallery conditionally rendered
- [ ] Tab switching works (gallery ↔ reactions)
- [ ] Reacted posts fetch and display
- [ ] Badges overlay opens on tag badges click
- [ ] Edit mode includes tagline field
- [ ] Responsive design at 1024px breakpoint
- [ ] All existing functionality preserved (edit, moderation, etc.)

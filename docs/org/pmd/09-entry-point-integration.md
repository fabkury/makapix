# PMD Entry Point Integration

## Overview

Users access the Post Management Dashboard via a 🗂️ button on their profile page. This button only appears when viewing one's own profile.

---

## Implementation

### File to Modify

`web/src/pages/u/[sqid].tsx`

### Locate Action Buttons Section

Find the existing profile action buttons (dashboard, players, edit-profile, logout). The PMD button should be added alongside these.

### Add PMD Button

```tsx
// In the action buttons section (around line 240-270 in existing code)
// Add this alongside other action buttons, visible only for own profile

{isOwnProfile && (
  <Link href={`/u/${sqid}/posts`}>
    <button className="pmd-btn action-btn" title="Post Management Dashboard">
      🗂️
    </button>
  </Link>
)}
```

### Button Styling

Add styling that matches existing action buttons:

```css
/* Add to the <style jsx> block */
.pmd-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  background: var(--bg-secondary);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.pmd-btn:hover {
  background: var(--bg-tertiary);
  border-color: var(--accent-cyan);
  box-shadow: var(--glow-cyan);
  transform: translateY(-2px);
}
```

---

## Button Placement

### Current Profile Button Order

Based on the existing profile page, buttons appear in this order:
1. 📊 Dashboard (moderators only)
2. 🎮 Players
3. ✏️ Edit Profile
4. 🗂️ **Post Management (NEW)**
5. 🚪 Logout

### Alternative Placement (Recommended)

Place the PMD button between "Edit Profile" and "Logout" for logical grouping of user-specific actions:

```tsx
<div className="action-buttons">
  {/* ... existing buttons ... */}
  
  {isOwnProfile && (
    <>
      <Link href={`/u/${sqid}/edit`}>
        <button className="edit-profile-btn action-btn" title="Edit Profile">
          ✏️
        </button>
      </Link>
      
      {/* NEW: Post Management Dashboard */}
      <Link href={`/u/${sqid}/posts`}>
        <button className="pmd-btn action-btn" title="Post Management">
          🗂️
        </button>
      </Link>
      
      <button className="logout-btn action-btn" onClick={handleLogout} title="Logout">
        🚪
      </button>
    </>
  )}
</div>
```

---

## Tooltip Enhancement (Optional)

For better discoverability, add a more descriptive tooltip:

```tsx
<button 
  className="pmd-btn action-btn" 
  title="Post Management Dashboard - Bulk actions for your posts"
>
  🗂️
</button>
```

---

## Deep Linking

### URL Parameters

The PMD page can accept a `bdr` query parameter to highlight a specific batch download request:

```
/u/{sqid}/posts?bdr={bdr_id}
```

This is useful when:
1. User clicks email notification link
2. User shares a download link (own use)

### Implementation in PMD Page

```tsx
// In posts.tsx
const { sqid, bdr: highlightedBdrId } = router.query;

// Use to scroll to/highlight specific BDR in DownloadRequestsPanel
useEffect(() => {
  if (highlightedBdrId && typeof highlightedBdrId === 'string') {
    // Scroll to BDR section
    const bdrSection = document.getElementById('bdr-section');
    bdrSection?.scrollIntoView({ behavior: 'smooth' });
    
    // Could also highlight the specific BDR
  }
}, [highlightedBdrId]);
```

---

## Navigation Breadcrumb (Optional)

For better navigation UX, the PMD page includes a back link:

```tsx
<Link href={`/u/${sqid}`} className="back-link">
  ← Back to Profile
</Link>
```

This appears at the top of the PMD page for easy return to the profile.

---

## Mobile Considerations

On mobile, the action buttons may wrap to multiple rows. Ensure the PMD button is included in the responsive layout:

```css
@media (max-width: 640px) {
  .action-buttons {
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
  }
  
  .action-btn {
    width: 44px;  /* Larger tap target on mobile */
    height: 44px;
  }
}
```

---

## Analytics (Optional)

Track PMD usage for product insights:

```tsx
// When user opens PMD
const handlePMDClick = () => {
  // If you have analytics
  analytics?.track('pmd_opened', {
    total_posts: postsCount,
    user_id: userId,
  });
};

<Link href={`/u/${sqid}/posts`}>
  <button onClick={handlePMDClick} className="pmd-btn action-btn">
    🗂️
  </button>
</Link>
```

---

## Testing the Integration

| Test | Steps | Expected Result |
|------|-------|-----------------|
| Button visibility (own profile) | Login, view own profile | 🗂️ button visible |
| Button visibility (other profile) | View another user's profile | No 🗂️ button |
| Button click | Click 🗂️ | Navigate to /u/{sqid}/posts |
| Tooltip | Hover over button | "Post Management Dashboard" tooltip |
| Back navigation | Click "← Back to Profile" in PMD | Return to profile page |
| Deep link | Navigate to /u/{sqid}/posts?bdr=abc123 | PMD opens, BDR section shown |

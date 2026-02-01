# PMD Frontend Components

## Overview

The PMD frontend consists of a new page and several components. The design is adapted from the Figma mock-up in `inbox/Post Management Dashboard/` to match Makapix Club's dark theme with neon accents.

---

## File Structure

```
web/src/
├── pages/
│   └── u/
│       └── [sqid]/
│           └── posts.tsx         # PMD page (NEW)
├── components/
│   └── pmd/                      # NEW directory
│       ├── PostTable.tsx         # Main table with sorting/selection
│       ├── BulkActionsPanel.tsx  # Actions panel (hide/unhide/delete/download)
│       ├── DownloadRequestsPanel.tsx  # BDR list with status
│       └── SelectionControls.tsx # Selection badges and page navigation
└── hooks/
    └── usePMDSSE.ts              # SSE hook (see 04-sse-implementation.md)
```

---

## Page: `/u/[sqid]/posts.tsx`

Main PMD page. Only accessible to the user viewing their own profile.

### Key Features

1. **Access Control**: Redirect if not own profile
2. **Progressive Loading**: Load posts in batches of 512
3. **State Management**: Selection, sorting, pagination
4. **SSE Integration**: Real-time BDR updates
5. **Toast Notifications**: Feedback for actions

### Implementation Skeleton

```tsx
import { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Layout from '../../../components/Layout';
import { PostTable } from '../../../components/pmd/PostTable';
import { BulkActionsPanel } from '../../../components/pmd/BulkActionsPanel';
import { DownloadRequestsPanel } from '../../../components/pmd/DownloadRequestsPanel';
import { usePMDSSE, BDRItem } from '../../../hooks/usePMDSSE';
import { authenticatedFetch } from '../../../lib/api';
import { toast, Toaster } from 'sonner'; // Or your preferred toast library

interface PMDPost {
  id: number;
  public_sqid: string;
  title: string;
  description: string | null;
  created_at: string;
  width: number;
  height: number;
  frame_count: number;
  file_format: string | null;
  file_bytes: number | null;
  art_url: string;
  hidden_by_user: boolean;
  reaction_count: number;
  comment_count: number;
  view_count: number;
}

export default function PostManagementDashboard() {
  const router = useRouter();
  const { sqid } = router.query;
  
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
  
  // Pagination state (for UI display, not API - we load all)
  const [currentPage, setCurrentPage] = useState(0);
  const itemsPerPage = 16;
  
  // Auth check - redirect if not own profile
  const [isOwnProfile, setIsOwnProfile] = useState<boolean | null>(null);

  const API_BASE_URL = useMemo(
    () => typeof window !== 'undefined'
      ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
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
          setIsOwnProfile(userSqid === sqid);
          
          if (userSqid !== sqid) {
            // Not own profile - redirect back
            router.push(`/u/${sqid}`);
          }
        } else {
          router.push('/auth');
        }
      } catch (error) {
        router.push('/auth');
      }
    };
    
    checkAuth();
  }, [sqid, API_BASE_URL, router]);

  // Load posts
  const loadPosts = useCallback(async (cursor?: string | null) => {
    if (cursor) {
      setLoadingMore(true);
    } else {
      setLoading(true);
    }
    
    try {
      const params = new URLSearchParams({ limit: '512' });
      if (cursor) params.append('cursor', cursor);
      
      const response = await authenticatedFetch(
        `${API_BASE_URL}/api/pmd/posts?${params}`
      );
      
      if (!response.ok) {
        throw new Error('Failed to load posts');
      }
      
      const data = await response.json();
      
      if (cursor) {
        setPosts(prev => [...prev, ...data.items]);
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
    } catch (error) {
      console.error('Error loading posts:', error);
      toast.error('Failed to load posts');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [API_BASE_URL]);

  // Initial load
  useEffect(() => {
    if (isOwnProfile) {
      loadPosts();
      loadBDRs();
    }
  }, [isOwnProfile, loadPosts]);

  // Load BDRs
  const loadBDRs = useCallback(async () => {
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/pmd/bdr`);
      if (response.ok) {
        const data = await response.json();
        setBdrs(data.items);
      }
    } catch (error) {
      console.error('Error loading BDRs:', error);
    }
  }, [API_BASE_URL]);

  // SSE for BDR updates
  const handleBDRUpdate = useCallback((updatedBdr: BDRItem) => {
    setBdrs(prev => {
      const index = prev.findIndex(b => b.id === updatedBdr.id);
      if (index >= 0) {
        const newBdrs = [...prev];
        newBdrs[index] = updatedBdr;
        return newBdrs;
      }
      return [updatedBdr, ...prev];
    });

    if (updatedBdr.status === 'ready') {
      toast.success(`Download ready! ${updatedBdr.artwork_count} artworks`);
    } else if (updatedBdr.status === 'failed') {
      toast.error(`Download failed: ${updatedBdr.error_message || 'Unknown error'}`);
    }
  }, []);

  usePMDSSE({
    enabled: isOwnProfile === true,
    onBDRUpdate: handleBDRUpdate,
  });

  // Batch action handlers
  const handleBatchAction = useCallback(async (
    action: 'hide' | 'unhide' | 'delete',
    postIds: number[]
  ) => {
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
          toast.info(`Processing batch ${i + 1} of ${chunks.length}...`);
        }
        
        const response = await authenticatedFetch(`${API_BASE_URL}/api/pmd/action`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action, post_ids: chunk }),
        });
        
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Action failed');
        }
        
        const result = await response.json();
        totalAffected += result.affected_count;
        
        // Update local state
        if (action === 'delete') {
          setPosts(prev => prev.filter(p => !chunk.includes(p.id)));
        } else {
          setPosts(prev => prev.map(p => 
            chunk.includes(p.id) 
              ? { ...p, hidden_by_user: action === 'hide' }
              : p
          ));
        }
      }
      
      // Clear selection
      setSelectedIds(new Set());
      
      // Show success message
      const actionName = action === 'hide' ? 'hidden' : action === 'unhide' ? 'unhidden' : 'deleted';
      toast.success(`Successfully ${actionName} ${totalAffected} post(s)`);
      
    } catch (error) {
      console.error('Batch action error:', error);
      toast.error(error instanceof Error ? error.message : 'Action failed');
    } finally {
      setActionLoading(false);
    }
  }, [API_BASE_URL]);

  // BDR request handler
  const handleRequestDownload = useCallback(async (
    postIds: number[],
    includeComments: boolean,
    includeReactions: boolean,
    sendEmail: boolean
  ) => {
    setActionLoading(true);
    
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/pmd/bdr`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          post_ids: postIds,
          include_comments: includeComments,
          include_reactions: includeReactions,
          send_email: sendEmail,
        }),
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Request failed');
      }
      
      const result = await response.json();
      toast.success(result.message);
      
      // Add to local BDR list
      setBdrs(prev => [{
        id: result.id,
        status: result.status,
        artwork_count: result.artwork_count,
        created_at: result.created_at,
        completed_at: null,
        expires_at: null,
        error_message: null,
        download_url: null,
      }, ...prev]);
      
    } catch (error) {
      console.error('BDR request error:', error);
      toast.error(error instanceof Error ? error.message : 'Request failed');
    } finally {
      setActionLoading(false);
    }
  }, [API_BASE_URL]);

  // Loading state
  if (loading || isOwnProfile === null) {
    return (
      <Layout title="Post Management">
        <div className="loading-container">
          <div className="loading-spinner"></div>
        </div>
        {/* ... loading styles ... */}
      </Layout>
    );
  }

  return (
    <Layout title="Post Management Dashboard">
      <div className="pmd-container">
        <div className="pmd-header">
          <Link href={`/u/${sqid}`} className="back-link">
            ← Back to Profile
          </Link>
          <h1>Post Management Dashboard</h1>
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
      
      <Toaster position="bottom-right" richColors />
      
      <style jsx>{`
        .pmd-container {
          max-width: 1200px;
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
          to { transform: rotate(360deg); }
        }
      `}</style>
    </Layout>
  );
}
```

---

## Component: PostTable

Displays posts in a sortable, selectable table with resizable columns.

### Props

```typescript
interface PostTableProps {
  posts: PMDPost[];
  selectedIds: Set<number>;
  setSelectedIds: (ids: Set<number>) => void;
  currentPage: number;
  setCurrentPage: (page: number) => void;
  itemsPerPage: number;
  loading: boolean;
}
```

### Key Features

1. **Column Sorting**: Click headers to sort asc/desc
2. **Column Resizing**: Drag column borders
3. **Row Selection**: Checkbox per row + select all
4. **Pagination**: Client-side pagination of loaded data
5. **Hidden Post Styling**: Opacity/background change for hidden posts

### Column Configuration

| Column | Width | Sortable | Content |
|--------|-------|----------|---------|
| Checkbox | 48px | No | Selection checkbox |
| Visibility | 60px | Yes | Eye icon button |
| Thumbnail | 48px | No | Post image |
| Title | 300px | Yes | Post title (truncated) |
| Description | 400px | Yes | Description (truncated) |
| Upload Date | 140px | Yes | Formatted date |
| Frames | 60px | Yes | 🖼️ Frame count |
| Format | 70px | Yes | 📄 File format |
| Size | 90px | Yes | 💾 File size |
| Width | 70px | Yes | ↔️ Pixel width |
| Height | 70px | Yes | ↕️ Pixel height |
| Reactions | 60px | Yes | ⚡ Count |
| Comments | 60px | Yes | 💬 Count |
| Views | 60px | Yes | 👁️ Count |
| Delete | 60px | No | 🗑️ Delete button |

### Implementation Reference

Port from `inbox/Post Management Dashboard/src/app/components/ArtworkTable.tsx`, adapting:
- Colors to Makapix dark theme
- Typography to match globals.css
- Remove Tailwind, use JSX styles

---

## Component: BulkActionsPanel

Shows selection state and action buttons.

### Props

```typescript
interface BulkActionsPanelProps {
  selectedCount: number;
  selectedIds: Set<number>;
  onHide: () => void;
  onUnhide: () => void;
  onDelete: () => void;
  onRequestDownload: (
    postIds: number[],
    includeComments: boolean,
    includeReactions: boolean,
    sendEmail: boolean
  ) => void;
  loading: boolean;
}
```

### Sections

1. **Selection State**: Shows count of selected posts
2. **Batch Actions**: Hide, Unhide, Delete buttons
3. **Batch Download**: Checkboxes + Download button

### Button States

| Button | Disabled When |
|--------|---------------|
| Hide | selectedCount === 0 |
| Unhide | selectedCount === 0 |
| Delete | selectedCount === 0 OR selectedCount > 32 |
| Download | selectedCount === 0 OR selectedCount > 128 |

### Delete Confirmation

Use a confirmation dialog before delete:

```tsx
// Simple confirm (or use a modal component)
const handleDeleteClick = () => {
  if (window.confirm(`Delete ${selectedCount} post(s)? This action cannot be undone.`)) {
    onDelete();
  }
};
```

---

## Component: DownloadRequestsPanel

Displays user's batch download requests with status.

### Props

```typescript
interface DownloadRequestsPanelProps {
  bdrs: BDRItem[];
}
```

### Status Display

| Status | Icon | Background | Action Button |
|--------|------|------------|---------------|
| pending | ⏳ | Yellow tint | None |
| processing | 🔄 | Blue tint | None |
| ready | ✅ | Green tint | "Download" |
| failed | ❌ | Red tint | Shows error |
| expired | 🕐 | Gray tint | "Expired" (disabled) |

### Date Formatting

```typescript
const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
};
```

---

## Component: SelectionControls

Badges and input for selection management.

### Features

1. "Select all" (current page)
2. "Unselect all" (current page)
3. "Select all (all pages)"
4. "Unselect all (all pages)"
5. "Go to page" input + button

---

## Styling Guidelines

### Use CSS Variables

Reference `web/src/styles/globals.css`:

```css
/* Backgrounds */
var(--bg-primary)    /* #000000 */
var(--bg-secondary)  /* #12121a */
var(--bg-tertiary)   /* #1a1a24 */
var(--bg-card)       /* #16161f */

/* Text */
var(--text-primary)   /* #e8e8f0 */
var(--text-secondary) /* #a0a0b8 */
var(--text-muted)     /* #6a6a80 */

/* Accents */
var(--accent-pink)   /* #ff6eb4 */
var(--accent-cyan)   /* #00d4ff */
var(--accent-purple) /* #b44eff */
var(--accent-blue)   /* #4e9fff */
```

### Button Styles

Primary action (gradient):
```css
background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
```

Secondary action:
```css
background: var(--bg-tertiary);
border: 1px solid rgba(255, 255, 255, 0.1);
```

Danger action:
```css
color: #ef4444;
border-color: #ef4444;
```

### Table Styles

```css
.table-header {
  background: var(--bg-tertiary);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.table-row {
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.table-row:hover {
  background: var(--bg-tertiary);
}

.table-row.hidden {
  opacity: 0.5;
  background: rgba(255, 255, 255, 0.02);
}
```

---

## Toast Notifications

Use the `sonner` library (already used in mock-up) or adapt to existing toast system.

```bash
npm install sonner
```

Configure with dark theme:
```tsx
<Toaster 
  position="bottom-right" 
  richColors 
  theme="dark"
/>
```

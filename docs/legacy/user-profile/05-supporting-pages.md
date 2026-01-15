# Supporting Pages

## Status: ⬜ Not Started

## Overview

This document describes additional pages that need to be created or modified to support the new profile features.

---

## 1. Gift Page (Placeholder)

### File: `web/src/pages/u/[sqid]/gift.tsx` (NEW)

A placeholder page for the future gift functionality.

### Route
`/u/{sqid}/gift`

### Design

Simple centered page with:
- User avatar and name at top (the recipient)
- Message explaining the feature isn't ready yet
- Back button to return to profile

### Layout

```
┌─────────────────────────────────────────┐
│              🎁                         │
│                                         │
│        [Avatar]                         │
│        username                         │
│                                         │
│   This feature will be implemented      │
│   in the future. Please check back      │
│   later!                                │
│                                         │
│        [← Back to Profile]              │
│                                         │
└─────────────────────────────────────────┘
```

### Implementation

```tsx
import { useRouter } from 'next/router';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import Layout from '../../../components/Layout';
import { authenticatedFetch } from '../../../lib/api';

interface User {
  handle: string;
  avatar_url?: string;
  public_sqid: string;
}

export default function GiftPage() {
  const router = useRouter();
  const { sqid } = router.query;
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sqid) return;
    
    async function fetchUser() {
      try {
        const res = await authenticatedFetch(`/api/user/u/${sqid}`);
        if (res.ok) {
          setUser(await res.json());
        }
      } finally {
        setLoading(false);
      }
    }
    
    fetchUser();
  }, [sqid]);

  if (loading) {
    return (
      <Layout title="Gift">
        <div className="loading-container">
          <div className="loading-spinner" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout title={user ? `Gift to ${user.handle}` : 'Gift'}>
      <div className="gift-container">
        <div className="gift-icon">🎁</div>
        
        {user && (
          <div className="recipient">
            {user.avatar_url ? (
              <img src={user.avatar_url} alt={user.handle} className="avatar" />
            ) : (
              <div className="avatar-placeholder">
                {user.handle.charAt(0).toUpperCase()}
              </div>
            )}
            <h2>{user.handle}</h2>
          </div>
        )}
        
        <p className="message">
          This feature will be implemented in the future.
          <br />
          Please check back later!
        </p>
        
        <Link href={`/u/${sqid}`} className="back-link">
          ← Back to Profile
        </Link>
      </div>
      
      <style jsx>{`
        .gift-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          min-height: calc(100vh - var(--header-offset) - 100px);
          padding: 2rem;
          text-align: center;
        }
        
        .gift-icon {
          font-size: 4rem;
          margin-bottom: 2rem;
        }
        
        .recipient {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 1rem;
          margin-bottom: 2rem;
        }
        
        .avatar {
          width: 96px;
          height: 96px;
          border-radius: 50%;
          object-fit: cover;
          border: 3px solid var(--bg-tertiary);
        }
        
        .avatar-placeholder {
          width: 96px;
          height: 96px;
          border-radius: 50%;
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 2.5rem;
          font-weight: 700;
          color: white;
        }
        
        .recipient h2 {
          font-size: 1.5rem;
          color: var(--text-primary);
          margin: 0;
        }
        
        .message {
          font-size: 1.1rem;
          color: var(--text-secondary);
          line-height: 1.8;
          margin-bottom: 2rem;
          max-width: 400px;
        }
        
        .back-link {
          color: var(--accent-cyan);
          font-size: 1rem;
          text-decoration: none;
          padding: 12px 24px;
          border: 1px solid var(--accent-cyan);
          border-radius: 8px;
          transition: all 0.15s ease;
        }
        
        .back-link:hover {
          background: var(--accent-cyan);
          color: var(--bg-primary);
        }
      `}</style>
    </Layout>
  );
}
```

---

## 2. Highlights Management (Future Enhancement)

**Note**: This is NOT required for the initial implementation but documented for future reference.

### Route (Future)
`/u/{sqid}/highlights` (or integrated into existing posts management page)

### Features
- View all highlights
- Remove highlights
- Reorder highlights via drag-and-drop
- Add new highlights from post selection

This could be integrated into the existing Post Management Dashboard at `/u/{sqid}/posts`.

---

## 3. API Route Updates

No new Next.js API routes are needed. All API calls go to the FastAPI backend.

---

## 4. Navigation Updates

### Header Component

If there's a user dropdown/menu, ensure it links to the profile page correctly.

### Profile Links

Ensure all existing profile links (`/u/{sqid}`) continue to work:
- Post author links
- Comment author links
- Search results
- Notifications

---

## 5. Types File Updates

### File: `web/src/types/index.ts` (or appropriate types file)

Add or update types:

```typescript
export interface UserProfileStats {
  follower_count: number;
  following_count: number;
  post_count: number;
  total_views: number;
  total_reactions: number;
}

export interface TagBadge {
  badge: string;
  icon_url_16: string;
}

export interface BadgeDefinition {
  badge: string;
  label: string;
  description?: string;
  icon_url_64: string;
  icon_url_16?: string;
  is_tag_badge: boolean;
}

export interface BadgeGrant {
  badge: string;
  granted_at: string;
  definition?: BadgeDefinition;
}

export interface UserHighlight {
  id: number;
  position: number;
  post: {
    id: number;
    public_sqid: string;
    title: string;
    art_url: string;
    canvas: string;
    width: number;
    height: number;
    reaction_count: number;
    comment_count: number;
    view_count: number;
  };
}

export interface User {
  id: number;
  user_key: string;
  public_sqid: string | null;
  handle: string;
  tagline?: string;
  bio?: string;
  avatar_url?: string;
  reputation: number;
  created_at: string;
  roles?: string[];
  badges?: BadgeGrant[];
  tag_badges?: TagBadge[];
  stats?: UserProfileStats;
  // ... existing fields
}
```

---

## Completion Checklist

- [ ] Gift page created at `web/src/pages/u/[sqid]/gift.tsx`
- [ ] Gift page styled appropriately
- [ ] Gift page fetches and displays user info
- [ ] Types updated in appropriate types file
- [ ] All profile links throughout the app still work

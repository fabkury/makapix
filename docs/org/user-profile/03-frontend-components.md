# Frontend Components

## Status: ⬜ Not Started

## Overview

This document describes all new React components needed for the user profile redesign.

---

## 1. MarkdownBio Component

### File: `web/src/components/MarkdownBio.tsx` (NEW)

Renders user bio with Markdown support including custom color syntax.

### Features
- Standard Markdown (bold, italic, links, code, lists)
- Custom color syntax: `[text]{color:red}` or `[text]{color:#ff0000}`
- XSS sanitization
- External links open in new tab with `rel="noopener noreferrer"`

### Props
```typescript
interface MarkdownBioProps {
  content: string;
  className?: string;
}
```

### Color Syntax Implementation

Use a custom remark/rehype plugin or post-process the HTML:

1. **Parse**: Regex to find `[text]{color:value}`
2. **Validate**: Check if color is a valid CSS color name or hex code
3. **Transform**: Convert to `<span style="color: value">text</span>`
4. **Sanitize**: Use DOMPurify or similar to strip dangerous HTML

### Allowed Colors
- All CSS named colors (red, blue, cyan, magenta, etc.)
- Hex colors: `#rgb`, `#rrggbb`
- NO rgba(), hsl(), or other formats (security)

### Styling
- Links: Underlined, `--accent-cyan` color, hover to `--accent-pink`
- Code: `--accent-cyan` color, `--bg-tertiary` background
- Strong: White/primary text color
- Emphasis: `--accent-cyan` color

### Dependencies
- `react-markdown` (already in project)
- `remark-gfm` for GitHub Flavored Markdown (optional)
- `DOMPurify` for sanitization (add if not present)

---

## 2. TagBadges Component

### File: `web/src/components/TagBadges.tsx` (NEW)

Displays tag badges under the username, clickable to open badges overlay.

### Props
```typescript
interface TagBadge {
  badge: string;
  icon_url_16: string;
}

interface TagBadgesProps {
  badges: TagBadge[];
  onAreaClick: () => void;  // Opens badges overlay
}
```

### Behavior
- Each badge is 16x16 CSS pixels
- If no badges, show 🛡️ emoji at 16x16 size as placeholder
- Clicking anywhere in the badges area (including empty space) triggers `onAreaClick`
- Badges displayed horizontally with small gap (4px)

### Styling
```css
.tag-badges-area {
  display: flex;
  align-items: center;
  gap: 4px;
  min-height: 16px;
  cursor: pointer;
  padding: 4px;
}

.tag-badge-img {
  width: 16px;
  height: 16px;
  image-rendering: pixelated;
}

.tag-badge-placeholder {
  font-size: 16px;
  line-height: 16px;
}
```

---

## 3. BadgesOverlay Component

### File: `web/src/components/BadgesOverlay.tsx` (NEW)

Modal overlay showing all badges a user has at 64x64 size.

### Props
```typescript
interface Badge {
  badge: string;
  label: string;
  description?: string;
  icon_url_64: string;
  granted_at: string;
}

interface BadgesOverlayProps {
  badges: Badge[];
  isOpen: boolean;
  onClose: () => void;
  username: string;  // For the header
}
```

### Layout
- Centered modal with dark backdrop
- Click backdrop to close
- Header: "{username}'s Badges"
- Grid of badges, each 64x64
- Hover on badge shows tooltip with label and description
- If no badges, show message "No badges yet"

### Styling
- Backdrop: `rgba(0, 0, 0, 0.8)`, click to dismiss
- Modal: `--bg-secondary` background, rounded corners
- Badge images: 64x64, pixelated rendering
- Animation: Fade in on open

---

## 4. HighlightsGallery Component

### File: `web/src/components/HighlightsGallery.tsx` (NEW)

Horizontally scrolling gallery of highlighted posts.

### Props
```typescript
interface HighlightPost {
  id: number;
  public_sqid: string;
  title: string;
  art_url: string;
  reaction_count: number;
  comment_count: number;
  view_count: number;
}

interface HighlightsGalleryProps {
  highlights: HighlightPost[];
  onPostClick: (sqid: string) => void;
}
```

### Layout
- Horizontal scroll container
- Each card: 128x128 artwork + metadata below
- Metadata shows: title (truncated), reaction/comment/view counts
- Hide scrollbar on all platforms (CSS)

### Card Structure
```
┌──────────────┐
│   Artwork    │  128x128
│   (image)    │
├──────────────┤
│ Title...     │  truncated
│ ❤️ 1.2K 💬 89 │  counts
└──────────────┘
```

### Styling
- Gap between cards: 12px
- Scroll snap: optional for better UX
- Selected state: Ring around card (if implementing selection)
- Hover: Scale up slightly

### Notes
- If user has no highlights, the entire component should NOT render
- The parent (profile page) should conditionally render this

---

## 5. ProfileStats Component

### File: `web/src/components/ProfileStats.tsx` (NEW)

Displays the stats row with emoji labels.

### Props
```typescript
interface ProfileStatsProps {
  followerCount: number;
  postCount: number;
  viewCount: number;
  reputation: number;
}
```

### Layout
```
👤 24.5K | 🖼️ 342 | 👁️ 1.2M | 🧮 18.3K
```

### Number Formatting
Create utility function:
```typescript
function formatCount(n: number): string {
  if (n >= 1_000_000) {
    const val = n / 1_000_000;
    return val % 1 === 0 ? `${val}M` : `${val.toFixed(1)}M`;
  }
  if (n >= 1_000) {
    const val = n / 1_000;
    return val % 1 === 0 ? `${val}K` : `${val.toFixed(1)}K`;
  }
  return n.toString();
}
```

### Styling
- Emoji slightly muted (`opacity: 0.7`)
- Numbers in primary text color
- Vertical dividers between stats (`|` or thin line)
- Responsive: Stack vertically on very narrow screens if needed

---

## 6. ProfileTabs Component

### File: `web/src/components/ProfileTabs.tsx` (NEW)

Tab switcher for gallery vs. reacted posts.

### Props
```typescript
type TabType = 'gallery' | 'reactions';

interface ProfileTabsProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
}
```

### Layout
```
🖼️    ⚡
───────
```

### Behavior
- Active tab has underline gradient (pink to cyan)
- Active tab emoji has glow effect (`drop-shadow`)
- Inactive tab is muted

### Styling (from Figma mock-up)
```css
.tab-button {
  padding-bottom: 12px;
  padding-inline: 4px;
  position: relative;
  transition: color 0.15s ease;
}

.tab-button.active {
  filter: drop-shadow(0 4px 12px rgba(255, 255, 255, 0.6));
}

.tab-button.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(to right, #FF006E, #00F5FF);
}
```

---

## 7. FollowButton Component

### File: `web/src/components/FollowButton.tsx` (NEW)

Follow/unfollow button with appropriate state handling.

### Props
```typescript
interface FollowButtonProps {
  userSqid: string;
  isFollowing: boolean;
  isOwnProfile: boolean;
  isLoggedIn: boolean;
  onFollowChange?: (isFollowing: boolean) => void;
}
```

### States
1. **Own profile**: Don't render (or render disabled)
2. **Not logged in**: Render, click redirects to `/auth`
3. **Logged in, not following**: Show 👣 with cyan glow
4. **Logged in, following**: Show 👣 with pink glow (or different icon)

### Behavior
- Optimistic UI: Toggle immediately, revert on error
- Loading state during API call
- Error handling with toast/alert

### Styling
```css
.follow-button {
  padding: 10px 24px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 6px;
  font-size: 1.25rem;
  transition: all 0.15s ease;
}

.follow-button:hover {
  background: rgba(255, 255, 255, 0.1);
}

.follow-button .emoji {
  filter: drop-shadow(0 0 8px rgba(0, 245, 255, 0.8));
}
```

---

## 8. GiftButton Component

### File: `web/src/components/GiftButton.tsx` (NEW)

Gift button that links to the gift page.

### Props
```typescript
interface GiftButtonProps {
  userSqid: string;
  isOwnProfile: boolean;
}
```

### Behavior
- Don't render on own profile
- Click navigates to `/u/{userSqid}/gift`
- Uses Gift icon from lucide-react (already in mock-up)

### Styling
- Similar to follow button but smaller
- Cyan accent color on icon

---

## 9. OwnerPanel Component

### File: `web/src/components/OwnerPanel.tsx` (NEW)

Panel of buttons shown only to profile owner.

### Props
```typescript
interface OwnerPanelProps {
  userSqid: string;
  onEditClick: () => void;
  onLogoutClick: () => void;
}
```

### Buttons
1. 📊 Artist Dashboard → `/u/{sqid}/dashboard`
2. 🗂️ Post Management → `/u/{sqid}/posts`
3. 📺 Manage Players → `/u/{sqid}/player`
4. (spacer)
5. ✏️ Edit Profile → triggers `onEditClick`
6. 🚪 Logout → triggers `onLogoutClick`

### Layout
- Horizontal flex with wrap
- Spacer creates visual gap between navigation and actions
- Each button is a bordered box with hover effect

---

## 10. Utility: formatCount

### File: `web/src/utils/formatCount.ts` (NEW)

```typescript
/**
 * Format large numbers for display.
 * @example formatCount(24500) // "24.5K"
 * @example formatCount(1200000) // "1.2M"
 * @example formatCount(500) // "500"
 */
export function formatCount(n: number): string {
  if (n >= 1_000_000) {
    const val = n / 1_000_000;
    const formatted = val.toFixed(1);
    return formatted.endsWith('.0') 
      ? `${Math.floor(val)}M` 
      : `${formatted}M`;
  }
  if (n >= 1_000) {
    const val = n / 1_000;
    const formatted = val.toFixed(1);
    return formatted.endsWith('.0') 
      ? `${Math.floor(val)}K` 
      : `${formatted}K`;
  }
  return n.toString();
}
```

---

## Badge Image Assets

### Location: `web/public/badges/`

Create placeholder badge images:
- `early-adopter_64.png` (64x64)
- `early-adopter_16.png` (16x16)
- `top-contributor_64.png` (64x64)
- `top-contributor_16.png` (16x16)
- `moderator_64.png` (64x64)
- `moderator_16.png` (16x16)

**Note**: These can be simple colored squares or basic icons initially. Real artwork can be added later.

---

## Completion Checklist

- [ ] `MarkdownBio` component created
- [ ] `TagBadges` component created
- [ ] `BadgesOverlay` component created
- [ ] `HighlightsGallery` component created
- [ ] `ProfileStats` component created
- [ ] `ProfileTabs` component created
- [ ] `FollowButton` component created
- [ ] `GiftButton` component created
- [ ] `OwnerPanel` component created
- [ ] `formatCount` utility created
- [ ] Badge placeholder images created
- [ ] All components have proper TypeScript types
- [ ] All components have appropriate styling

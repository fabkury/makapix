# Visual Design Specification for Card-Roller Layout

## Overview
This document describes the visual structure of the refactored hashtag search results page.

## Page Structure

```
┌────────────────────────────────────────────────────────────────┐
│ Header (existing layout - unchanged)                           │
└────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────┐
│ Tab Navigation: 🔍 Search | # Hashtags | 👥 Users              │
└────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────┐
│ Controls Section (bg-secondary)                                │
│ ┌──────────────────────────────┐  ┌──────────┬──────────┐    │
│ │ 🔍 [Search hashtags...]  [X]  │  │ Popular │ │   A-Z   │    │
│ │            [Search Button]     │  └──────────┴──────────┘    │
│ └──────────────────────────────┘                               │
└────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────┐
│ Card-Roller #1 (margin-bottom: 32px)                           │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ Card-Roller-Header (padding: 16px 24px)                    │ │
│ │ # hashtag1              ⚡123  💬45  🎨12                 │ │
│ └────────────────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ Card-Roller-Body (horizontal scroll, padding: 16px 24px)   │ │
│ │ ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ...    │ │
│ │ │ [🎨] │  │ [🎨] │  │ [🎨] │  │ [🎨] │  │ [🎨] │         │ │
│ │ │ ⚡💬 │  │ ⚡💬 │  │ ⚡💬 │  │ ⚡💬 │  │ ⚡💬 │ ─────▶ │ │
│ │ │ 👍   │  │ 👍   │  │ 👍   │  │ 👍   │  │ 👍   │         │ │
│ │ │@user │  │@user │  │@user │  │@user │  │@user │         │ │
│ │ │title │  │title │  │title │  │title │  │title │         │ │
│ │ └──────┘  └──────┘  └──────┘  └──────┘  └──────┘         │ │
│ │          gap: 16px between cards                            │ │
│ └────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────┐
│ Card-Roller #2 (margin-bottom: 32px)                           │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ # hashtag2              ⚡456  💬89  🎨23                 │ │
│ └────────────────────────────────────────────────────────────┘ │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐  ...              │ │
│ │ │ [🎨] │  │ [🎨] │  │ [🎨] │  │ [🎨] │                  │ │
│ │ └──────┘  └──────┘  └──────┘  └──────┘                    │ │
│ └────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
...
(Up to 15 card-rollers, then vertical scroll loads more)
```

## Component Details

### Card-Roller (entire row)
- **Background**: Same as page background
- **Margin-bottom**: 32px (spacing between rollers)
- **Width**: 100%

### Card-Roller-Header
- **Layout**: Flexbox, space-between
- **Padding**: 16px 24px
- **Background**: var(--bg-secondary)
- **Border-bottom**: 1px solid rgba(255,255,255,0.05)

**Left Side:**
- Hashtag symbol (#) in gradient purple-to-blue
- Font-size: 1.5rem for symbol
- Font-size: 1.2rem for name
- Clickable link to individual hashtag page
- Hover effect: translateX(4px)

**Right Side:**
- Three stat items in a row
- Gap: 16px between stats
- Each stat: emoji + count
- Format: ⚡ {reactions} 💬 {comments} 🎨 {artworks}
- Font-size: 0.9rem

### Card-Roller-Body
- **Overflow-x**: auto (horizontal scroll)
- **Padding**: 16px 24px
- **Min-height**: 210px
- **Scrollbar**: Thin, styled with theme colors

### Artwork Cards (within roller)
- **Dimensions**: 178px × 178px (same as CardGrid)
- **Flex-shrink**: 0 (prevent squishing)
- **Gap**: 16px between cards
- **Layout**: Same as existing CardGrid cards
  - Top section (128px): artwork + stats panel
  - Bottom section (49px): author + title

### Horizontal Scroll Behavior
- Smooth scrolling with momentum
- Sentinel element at the end for infinite scroll
- Loading spinner appears during fetch
- Loads 20 more posts when sentinel comes into view

### Vertical Scroll Behavior
- 15 hashtags load initially
- Sentinel at page bottom triggers next batch
- Loading spinner during fetch
- "That's all!" message when no more hashtags

## Color Scheme
All colors from existing theme:
- **Primary background**: var(--bg-primary) #0a0a0f
- **Secondary background**: var(--bg-secondary) #12121a
- **Tertiary background**: var(--bg-tertiary) #1a1a24
- **Text primary**: var(--text-primary) #e8e8f0
- **Text secondary**: var(--text-secondary) #a0a0b8
- **Accent cyan**: var(--accent-cyan) #00d4ff
- **Accent purple**: var(--accent-purple) #b44eff
- **Accent pink**: var(--accent-pink) #ff6eb4

## Responsive Behavior

### Desktop (>768px)
- Full width card-rollers
- Controls in single row
- Comfortable spacing

### Tablet (768px)
- Controls stack vertically
- Card-rollers remain horizontal scroll
- Hashtag stats may stack below name

### Mobile (<768px)
- All controls stack
- Card-rollers with horizontal scroll
- Single card visible at start, swipe to see more
- Compact header layout

## Interaction States

### Search Input
- **Default**: Border subtle, cyan on focus
- **Focus**: Border-color cyan, box-shadow glow
- **With content**: Show clear (X) button

### Search Button
- **Default**: Cyan background
- **Hover**: Glow effect, translateY(-2px)
- **Active**: Slightly darker

### Sort Buttons
- **Inactive**: Tertiary background, secondary text
- **Active**: Purple background, white text
- **Hover**: Secondary background

### Hashtag Link (in header)
- **Default**: Purple gradient text
- **Hover**: translateX(4px), brighter gradient

### Artwork Cards
- **Default**: Neutral background
- **Hover**: Cyan glow, z-index increase
- **Transition**: 0.15s ease

### Like Button
- **Default**: Tertiary border, secondary background
- **Hover**: Pink border, scale(1.1)
- **Liked**: Pink background, pink border
- **Disabled**: 0.6 opacity, no-cursor

## Loading States

### Initial Hashtag Load
- Centered spinner (40px)
- Purple gradient animation
- Message: Loading hashtags...

### Horizontal Scroll Loading
- Small spinner in sentinel area (24px)
- Appears at end of card list
- Disappears when posts loaded

### Vertical Scroll Loading
- Spinner below last card-roller
- Same style as initial load
- "That's all!" when complete

## Empty States

### No Hashtags Found
- Large # symbol (4rem)
- Gradient purple-to-blue
- Message below
- "Clear Search" button if query present

### Card-Roller with No Posts
- Should not render (filtered out)
- Backend ensures only hashtags with posts returned

## Accessibility

### Keyboard Navigation
- Tab through search input → submit button → sort buttons
- Enter in search input submits form
- Arrow keys scroll card-rollers when focused
- Tab cycles through cards within focused roller

### Screen Readers
- aria-label on like buttons
- Semantic HTML structure
- Alt text on images (from post title)
- Role="button" on interactive elements

### Focus Indicators
- 2px solid cyan outline
- 2px offset from element
- Visible on all interactive elements

## Performance Targets

### Initial Page Load
- <500ms to first hashtag render
- Progressive rendering (show as data arrives)
- Lazy load images in cards

### Horizontal Scroll
- <200ms to load next batch of posts
- Prefetch on near-end (not just at-end)
- Smooth 60fps scrolling

### Vertical Scroll
- <300ms to load next hashtags
- No jank when new rollers mount
- Maintain scroll position during load

### Memory
- Each card-roller maintains own post list
- Cleanup on unmount
- No memory leaks from observers

## Animation Timings

- **Transitions**: 0.15s ease (--transition-fast)
- **Hover effects**: 0.15s ease
- **Loading spinners**: 0.8s linear infinite
- **Scroll behavior**: smooth (native CSS)

## Z-Index Stack

1. Base layer: card-rollers (z-index: auto)
2. Hovered cards: z-index: 1
3. Header sticky: z-index: 50
4. Modals/overlays: z-index: 100 (if any)

This maintains proper layering without conflicts.

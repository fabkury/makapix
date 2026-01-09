# Porting Figma Mock-up to Makapix Club

## Overview

The Figma mock-up in `inbox/Post Management Dashboard/` provides the functional design and UX patterns. This document describes how to adapt it to Makapix Club's design language.

---

## Source Files Reference

```
inbox/Post Management Dashboard/src/app/
├── App.tsx                        # Main layout structure
└── components/
    ├── ArtworkTable.tsx           # Table with sorting, resizing
    ├── BulkActionsPanel.tsx       # Action buttons and checkboxes
    ├── DownloadRequestsPanel.tsx  # Download status display
    ├── figma/
    │   └── ImageWithFallback.tsx  # Image loading with fallback
    └── ui/
        ├── button.tsx             # Button component
        ├── checkbox.tsx           # Checkbox component
        ├── input.tsx              # Input component
        ├── badge.tsx              # Badge/tag component
        ├── alert-dialog.tsx       # Confirmation dialog
        └── sonner.tsx             # Toast notifications
```

---

## Design System Comparison

### Colors

| Element | Mock-up (Light) | Makapix (Dark) |
|---------|-----------------|----------------|
| Page background | `#f3f4f6` (gray-50) | `var(--bg-primary)` #0a0a0f |
| Card background | `#ffffff` | `var(--bg-secondary)` #12121a |
| Table header | `#f9fafb` (gray-50) | `var(--bg-tertiary)` #1a1a24 |
| Text primary | `#111827` (gray-900) | `var(--text-primary)` #e8e8f0 |
| Text secondary | `#6b7280` (gray-500) | `var(--text-secondary)` #a0a0b8 |
| Text muted | `#9ca3af` (gray-400) | `var(--text-muted)` #6a6a80 |
| Primary button | `#3b82f6` (blue-500) | `linear-gradient(var(--accent-pink), var(--accent-purple))` |
| Danger button | `#ef4444` (red-500) | Same `#ef4444` |
| Success state | `#3b82f6` (blue-50/200) | `#10b981` (emerald) |

### Typography

| Element | Mock-up | Makapix |
|---------|---------|---------|
| Font family | System fonts | 'Noto Sans', 'Open Sans' |
| Page title | 24px, semibold | 28px (1.75rem), bold |
| Section title | 14px, semibold | 16px, semibold |
| Table text | 14px | 14px (0.875rem) |
| Small text | 12px | 12px (0.75rem) |

### Borders & Shadows

| Element | Mock-up | Makapix |
|---------|---------|---------|
| Card border | None | `1px solid rgba(255,255,255,0.1)` |
| Card shadow | `shadow` (box-shadow) | None (borders instead) |
| Border radius | 8px | 8px |
| Divider | `#e5e7eb` (gray-200) | `rgba(255,255,255,0.1)` |

---

## Component-by-Component Porting Guide

### 1. Page Layout (App.tsx → posts.tsx)

**Mock-up:**
```jsx
<div className="min-h-screen bg-gray-50 lg:p-8">
  <div className="max-w-[1024px] mx-auto">
```

**Makapix:**
```jsx
<Layout title="Post Management Dashboard">
  <div className="pmd-container">
    {/* max-width: 1200px; margin: 0 auto; padding: 24px; */}
```

### 2. PostTable (ArtworkTable.tsx)

#### Remove Tailwind Classes

Replace with CSS-in-JSX or styled-jsx:

```jsx
// Mock-up (Tailwind)
<th className="px-4 relative cursor-pointer hover:bg-gray-100">

// Makapix (styled-jsx)
<th className="sortable-header">
  {/* ... */}
</th>
<style jsx>{`
  .sortable-header {
    padding: 0 16px;
    position: relative;
    cursor: pointer;
    transition: background var(--transition-fast);
  }
  .sortable-header:hover {
    background: var(--bg-primary);
  }
`}</style>
```

#### Adapt Row Hover State

```css
/* Mock-up */
.table-row:hover { background: #f9fafb; }

/* Makapix */
.table-row:hover { background: var(--bg-tertiary); }
```

#### Hidden Post Styling

```css
/* Mock-up */
.hidden-row { opacity: 0.5; background: #f3f4f6; }

/* Makapix */
.hidden-row {
  opacity: 0.5;
  background: rgba(255, 255, 255, 0.02);
}
```

### 3. BulkActionsPanel

#### Button Styling

**Primary Button (Download):**
```css
/* Makapix */
.btn-primary {
  background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
  color: white;
  border: none;
  border-radius: 8px;
  padding: 10px 16px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: var(--glow-pink);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}
```

**Secondary Button (Hide/Unhide):**
```css
.btn-secondary {
  background: var(--bg-tertiary);
  color: var(--text-primary);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 10px 16px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-secondary:hover:not(:disabled) {
  background: var(--bg-primary);
  border-color: var(--accent-cyan);
}
```

**Danger Button (Delete):**
```css
.btn-danger {
  background: transparent;
  color: #ef4444;
  border: 1px solid #ef4444;
  border-radius: 8px;
  padding: 10px 16px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.1);
}

.btn-danger:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
```

#### Checkbox Styling

Port the shadcn/ui checkbox or use existing Makapix checkbox component if available.

```css
/* Makapix checkbox */
.checkbox {
  width: 18px;
  height: 18px;
  border: 2px solid var(--text-muted);
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  transition: all 0.15s ease;
}

.checkbox:checked {
  background: var(--accent-cyan);
  border-color: var(--accent-cyan);
}

.checkbox:hover:not(:disabled) {
  border-color: var(--accent-cyan);
}
```

### 4. DownloadRequestsPanel

#### Status Backgrounds

```css
.bdr-item {
  padding: 16px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.bdr-pending {
  background: rgba(234, 179, 8, 0.1);
  border: 1px solid rgba(234, 179, 8, 0.3);
}

.bdr-processing {
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.3);
}

.bdr-ready {
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.bdr-failed {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.bdr-expired {
  background: rgba(107, 114, 128, 0.1);
  border: 1px solid rgba(107, 114, 128, 0.3);
}
```

### 5. Selection Badges

```css
.badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 16px;
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.badge:hover {
  background: var(--bg-primary);
  color: var(--text-primary);
  border-color: var(--accent-cyan);
}
```

---

## Icons

The mock-up uses `lucide-react` icons. Makapix can either:

1. **Install lucide-react** (recommended for consistency with mock-up):
   ```bash
   npm install lucide-react
   ```

2. **Use emoji equivalents** (already done in mock-up for some columns):
   - 🖼️ for frames
   - 📄 for format
   - 💾 for file size
   - ↔️ for width
   - ↕️ for height
   - ⚡ for reactions
   - 💬 for comments
   - 👁️ for views

---

## Animation Porting

### Transitions

The mock-up uses Tailwind transitions. Convert to CSS variables:

```css
/* Makapix defines these in globals.css */
--transition-fast: 0.15s ease;
--transition-normal: 0.25s ease;

/* Usage */
transition: all var(--transition-fast);
```

### Hover States

Add subtle scale/glow effects that match existing Makapix patterns:

```css
/* Button hover */
.btn:hover {
  transform: translateY(-2px);
  box-shadow: var(--glow-cyan);
}

/* Row hover */
.row:hover {
  background: var(--bg-tertiary);
}
```

---

## Responsive Considerations

The mock-up has minimal responsive design. For Makapix:

### Mobile (< 768px)

1. Table scrolls horizontally
2. Action buttons stack vertically
3. Column widths adjust (hide some columns)

```css
@media (max-width: 768px) {
  .table-wrapper {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  
  .action-buttons {
    flex-direction: column;
    gap: 8px;
  }
  
  /* Hide less important columns on mobile */
  .col-description,
  .col-filesize,
  .col-dimensions {
    display: none;
  }
}
```

---

## Accessibility

Maintain accessibility from mock-up:

1. **Keyboard navigation**: Tab through rows and buttons
2. **ARIA labels**: On icon-only buttons
3. **Focus states**: Visible focus rings

```css
:focus-visible {
  outline: 2px solid var(--accent-cyan);
  outline-offset: 2px;
}
```

---

## Testing the Port

1. **Visual comparison**: Screenshot mock-up vs. implementation
2. **Theme consistency**: Check against other Makapix pages
3. **Interaction parity**: All features from mock-up work
4. **Dark mode**: Verify readability and contrast

---

## Key Differences Summary

| Aspect | Mock-up | Makapix Port |
|--------|---------|--------------|
| Theme | Light | Dark |
| Styling | Tailwind CSS | styled-jsx / CSS modules |
| Background | White/gray | Near-black with borders |
| Accents | Blue | Pink/cyan gradient |
| Shadows | Box shadows | Border highlights |
| Font | System | Noto Sans |

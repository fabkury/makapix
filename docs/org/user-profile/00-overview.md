# User Profile Pages - Implementation Plan

## Overview

This document series outlines the complete implementation plan for the new user profile pages at Makapix Club (MPX). The implementation involves database migrations, backend API development, and frontend redesign.

## Document Index

| Document | Description | Status |
|----------|-------------|--------|
| [01-database-migrations.md](./01-database-migrations.md) | Database schema changes and Alembic migrations | ⬜ Not Started |
| [02-backend-api.md](./02-backend-api.md) | New API endpoints and modifications | ⬜ Not Started |
| [03-frontend-components.md](./03-frontend-components.md) | New React components to create | ⬜ Not Started |
| [04-profile-page.md](./04-profile-page.md) | Main profile page implementation | ⬜ Not Started |
| [05-supporting-pages.md](./05-supporting-pages.md) | Gift page and other supporting pages | ⬜ Not Started |
| [06-deployment.md](./06-deployment.md) | Deployment and testing checklist | ⬜ Not Started |

## Key Decisions Summary

### Emoji Meanings (Profile Stats & Buttons)
- ⚡ Lightning: Count of all reactions received (any emoji type)
- 🖼️ Picture frame: Count of all posts
- 👤 Person: Count of followers
- 👁️ Eye: Count of total views across all posts
- 👣 Footprints: Follow/unfollow button
- 🧮 Abacus: Reputation points
- 🗂️ Folder: Post management dashboard button
- 💎 Diamond: Highlights gallery section
- 🎁 Gift: Gift button (placeholder functionality)

### Technical Decisions
1. **Badge definitions**: Stored in database table (not hardcoded)
2. **Tag badges**: Subset of badges with `is_tag_badge=true`, having both 64x64 and 16x16 artwork
3. **Highlights/Diamonds**: Separate `user_highlights` table, max 128 per user, reorderable
4. **User stats**: Cached in Redis with 5-minute TTL
5. **Reacted posts tab**: Limited to last 8192 reactions for performance
6. **Markdown bio**: Custom color syntax `[text]{color:red}`, sanitized HTML, external links open in new tab
7. **Profile tabs**: Client-side tab switching (no URL change)
8. **Responsive breakpoint**: 1024px (mobile below, desktop above)

### Files Reference
- **Figma mock-up**: `inbox/mpx-user-profile/src/app/App.tsx`
- **Current profile page**: `web/src/pages/u/[sqid].tsx`
- **Database models**: `api/app/models.py`
- **Deployment guide**: `deploy/stack/README.stack.md`

## Completion Criteria

All sections marked with ✅ indicate completion. The implementation is complete when:
1. All database migrations run successfully
2. All API endpoints are functional and tested
3. Frontend profile page matches the Figma mock-up design
4. Stack has been rebuilt and deployed to dev.makapix.club
5. Manual testing confirms all features work correctly

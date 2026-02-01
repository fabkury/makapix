# Deployment & Testing

## Status: ⬜ Not Started

## Overview

This document describes the deployment process and testing checklist for the new user profile features.

---

## Pre-Deployment Checklist

### Code Quality
- [ ] All TypeScript files compile without errors
- [ ] All Python files pass linting
- [ ] No console errors in browser dev tools
- [ ] All new components have proper TypeScript types

### Database
- [ ] All migrations created in `api/alembic/versions/`
- [ ] Migration files follow naming convention: `YYYYMMDD######_description.py`
- [ ] Migrations tested locally
- [ ] Badge definitions seed data prepared

---

## Deployment Steps

### 1. Run Database Migrations

From the VPS, navigate to the API container and run migrations:

```bash
cd /opt/makapix/deploy/stack
docker compose exec api alembic upgrade head
```

Or from the host:

```bash
docker exec makapix-api alembic upgrade head
```

### 2. Seed Badge Definitions

If not done in migration, seed initial badges:

```bash
docker exec makapix-api python -c "
from app.db import SessionLocal
from app.models import BadgeDefinition

db = SessionLocal()

badges = [
    BadgeDefinition(
        badge='early-adopter',
        label='Early Adopter',
        description='Joined during beta',
        icon_url_64='/badges/early-adopter_64.png',
        icon_url_16='/badges/early-adopter_16.png',
        is_tag_badge=True
    ),
    BadgeDefinition(
        badge='top-contributor',
        label='Top Contributor',
        description='Posted 100+ artworks',
        icon_url_64='/badges/top-contributor_64.png',
        icon_url_16=None,
        is_tag_badge=False
    ),
    BadgeDefinition(
        badge='moderator',
        label='Moderator',
        description='Community moderator',
        icon_url_64='/badges/moderator_64.png',
        icon_url_16='/badges/moderator_16.png',
        is_tag_badge=True
    ),
]

for badge in badges:
    existing = db.query(BadgeDefinition).filter_by(badge=badge.badge).first()
    if not existing:
        db.add(badge)
        print(f'Added badge: {badge.badge}')

db.commit()
db.close()
"
```

### 3. Rebuild and Deploy Web Container

From the deploy/stack directory:

```bash
cd /opt/makapix/deploy/stack

# Build with cache (faster, use for code changes only)
docker compose build web && docker compose up -d web

# OR build without cache (use after Dockerfile changes)
docker compose down web && docker compose build --no-cache web && docker compose up -d web
```

### 4. Rebuild and Deploy API Container (if API changes)

```bash
cd /opt/makapix/deploy/stack
docker compose build api && docker compose up -d api
```

### 5. Verify Deployment

```bash
# Check containers are running
docker ps | grep makapix

# Check web logs
docker logs -f makapix-web

# Check API logs
docker logs -f makapix-api
```

---

## Testing Checklist

### Profile Page - Visual

- [ ] Profile page loads without errors
- [ ] Avatar displays correctly
- [ ] Username displays correctly
- [ ] Tag badges display under username (or shield emoji if none)
- [ ] Tagline displays if set
- [ ] Stats row shows formatted numbers
- [ ] Bio renders with Markdown
- [ ] Colors in bio work (`[text]{color:red}`)
- [ ] Links in bio open in new tab
- [ ] Highlights gallery displays if user has highlights
- [ ] Tab switching works (gallery ↔ reactions)
- [ ] CardGrid displays posts
- [ ] Infinite scroll works

### Profile Page - Responsive

- [ ] Desktop layout correct (≥1024px)
- [ ] Mobile layout correct (<1024px)
- [ ] Action buttons in correct position per breakpoint
- [ ] Touch targets appropriately sized on mobile

### Follow Functionality

- [ ] Follow button appears for logged-in users (not own profile)
- [ ] Follow button shows login redirect for anonymous users
- [ ] Clicking follow creates follow relationship
- [ ] Button state updates after follow/unfollow
- [ ] Follower count updates (may require cache TTL)

### Gift Page

- [ ] Gift button appears (not on own profile)
- [ ] Gift page loads at `/u/{sqid}/gift`
- [ ] Shows user avatar and name
- [ ] Shows placeholder message
- [ ] Back button returns to profile

### Badges Overlay

- [ ] Clicking tag badges area opens overlay
- [ ] Overlay shows all user badges at 64x64
- [ ] Badge tooltips show label and description
- [ ] Backdrop click closes overlay
- [ ] Empty state message if no badges

### Highlights

- [ ] Highlights section hidden if no highlights
- [ ] Highlights display in correct order
- [ ] Clicking highlight navigates to post
- [ ] Horizontal scroll works

### Reactions Tab

- [ ] Tab switches to reactions view
- [ ] Shows posts user has reacted to
- [ ] Infinite scroll works
- [ ] Empty state if no reactions

### Edit Mode

- [ ] Edit button shows for profile owner
- [ ] Edit mode shows handle, tagline, bio fields
- [ ] Tagline field has 48 char limit
- [ ] Save updates all fields
- [ ] Cancel reverts changes
- [ ] Avatar upload still works

### Owner Panel

- [ ] Dashboard link works
- [ ] Post management link works
- [ ] Players link works
- [ ] Edit button works
- [ ] Logout button works

### API Endpoints

Test with curl or httpie:

```bash
# Get user profile with stats
curl https://makapix.club/api/user/u/{sqid}

# Get highlights
curl https://makapix.club/api/user/u/{sqid}/highlights

# Get reacted posts
curl https://makapix.club/api/user/u/{sqid}/reacted-posts

# Follow (authenticated)
curl -X POST https://makapix.club/api/user/u/{sqid}/follow \
  -H "Authorization: Bearer {token}"

# Get follow status (authenticated)
curl https://makapix.club/api/user/u/{sqid}/follow-status \
  -H "Authorization: Bearer {token}"

# Get badge definitions
curl https://makapix.club/api/badge
```

---

## Rollback Plan

If issues are found:

### Quick Rollback (Code Only)

```bash
cd /opt/makapix
git checkout HEAD~1  # or specific commit
cd deploy/stack
docker compose build web && docker compose up -d web
```

### Database Rollback

```bash
# Downgrade one migration
docker exec makapix-api alembic downgrade -1

# Or downgrade to specific revision
docker exec makapix-api alembic downgrade {revision_id}
```

**Warning**: Database rollback may cause data loss for new features. Only do this if absolutely necessary.

---

## Post-Deployment Monitoring

- [ ] Check error logs for 500 errors
- [ ] Monitor Redis for cache operations
- [ ] Check database query performance
- [ ] Verify no memory leaks in containers
- [ ] Test on multiple devices/browsers

---

## Final Sign-Off

- [ ] All tests pass
- [ ] No critical bugs
- [ ] Performance acceptable
- [ ] Ready for production

**Deployment completed by**: _______________

**Date**: _______________

# Database Migrations

## Status: ⬜ Not Started

## Overview

This document describes all database schema changes required for the new user profile features.

---

## Migration 1: Add User Tagline Field

**File**: `api/alembic/versions/YYYYMMDD000001_add_user_tagline.py`

### Changes

Add a new `tagline` column to the `users` table:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `tagline` | `String(48)` | `nullable=True` | Short tagline displayed under username, full Unicode support |

### Implementation Notes
- Maximum 48 characters
- Must support full Unicode (emojis, CJK characters, etc.)
- PostgreSQL handles UTF-8 natively, no special encoding needed

---

## Migration 2: Badge Definitions Table

**File**: `api/alembic/versions/YYYYMMDD000002_add_badge_definitions.py`

### New Table: `badge_definitions`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `Integer` | `primary_key`, `autoincrement` | Internal ID |
| `badge` | `String(50)` | `unique`, `not null`, `index` | Badge identifier (e.g., "early-adopter") |
| `label` | `String(100)` | `not null` | Display name (e.g., "Early Adopter") |
| `description` | `Text` | `nullable` | Badge description |
| `icon_url_64` | `String(500)` | `not null` | URL to 64x64 badge artwork |
| `icon_url_16` | `String(500)` | `nullable` | URL to 16x16 badge artwork (only for tag badges) |
| `is_tag_badge` | `Boolean` | `not null`, `default=False` | Whether this badge appears under username |
| `created_at` | `DateTime(timezone=True)` | `server_default=func.now()` | Creation timestamp |

### Implementation Notes
- Badge artwork stored at `/public/badges/{badge_name}_64.png` and `/public/badges/{badge_name}_16.png`
- `is_tag_badge=True` badges MUST have `icon_url_16` populated
- Seed the table with existing badges: `early-adopter`, `top-contributor`, `moderator`

### Relationship Update
- Update `BadgeGrant` model to add relationship to `BadgeDefinition`
- Add foreign key constraint: `BadgeGrant.badge` → `badge_definitions.badge`

---

## Migration 3: User Highlights Table

**File**: `api/alembic/versions/YYYYMMDD000003_add_user_highlights.py`

### New Table: `user_highlights`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `Integer` | `primary_key`, `autoincrement` | Internal ID |
| `user_id` | `Integer` | `ForeignKey("users.id")`, `not null`, `index` | Owner of the highlight |
| `post_id` | `Integer` | `ForeignKey("posts.id", ondelete="CASCADE")`, `not null`, `index` | Highlighted post |
| `position` | `Integer` | `not null` | Display order (0-indexed) |
| `created_at` | `DateTime(timezone=True)` | `server_default=func.now()` | When added to highlights |

### Constraints
- `UniqueConstraint("user_id", "post_id")` - A post can only be highlighted once per user
- `UniqueConstraint("user_id", "position")` - Positions must be unique per user

### Indexes
- `Index("ix_user_highlights_user_position", user_id, position)` for ordered retrieval

### Implementation Notes
- Maximum 128 highlights per user (enforced in API, not database)
- When a highlighted post is deleted, the highlight is automatically removed (CASCADE)
- Positions should be kept contiguous (0, 1, 2, ...) after deletions

---

## Migration 4: Reactions User Index

**File**: `api/alembic/versions/YYYYMMDD000004_add_reactions_user_index.py`

### New Index

Add index for efficient "posts user reacted to" queries:

```sql
CREATE INDEX ix_reactions_user_created ON reactions (user_id, created_at DESC);
```

### Implementation Notes
- This supports the "lightning tab" showing posts the user reacted to
- Query will be limited to last 8192 reactions for performance

---

## Migration 5: User Profile Stats Cache Table (Optional)

**File**: `api/alembic/versions/YYYYMMDD000005_add_user_stats_cache.py`

### New Table: `user_stats_cache`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `Integer` | `primary_key`, `autoincrement` | Internal ID |
| `user_id` | `Integer` | `ForeignKey("users.id")`, `unique`, `not null` | User this cache belongs to |
| `stats_json` | `JSON` | `not null` | Cached statistics |
| `computed_at` | `DateTime(timezone=True)` | `not null` | When stats were computed |
| `expires_at` | `DateTime(timezone=True)` | `not null`, `index` | Cache expiration time |

### Implementation Notes
- This is a **fallback** cache; primary caching uses Redis
- Only used when Redis is unavailable
- Can be omitted if Redis is always available (check with infrastructure)

---

## Model Updates Required

### File: `api/app/models.py`

1. **Add `BadgeDefinition` model** (new class)
2. **Update `User` model**:
   - Add `tagline = Column(String(48), nullable=True)`
   - Add `highlights` relationship to `UserHighlight`
3. **Add `UserHighlight` model** (new class)
4. **Update `BadgeGrant` model**:
   - Add relationship to `BadgeDefinition`
5. **Optionally add `UserStatsCache` model**

---

## Schema Updates Required

### File: `api/app/schemas.py`

1. **Update `BadgeDefinition` schema**:
   - Add `icon_url_64`, `icon_url_16`, `is_tag_badge` fields
2. **Update `BadgeGrant` schema**:
   - Add nested `definition: BadgeDefinition | None` field for badge metadata
3. **Update `UserPublic` and `UserFull` schemas**:
   - Add `tagline: str | None` field
4. **Update `UserUpdate` schema**:
   - Add `tagline: str | None = Field(None, max_length=48)` field
5. **Create `UserHighlight` schema**
6. **Create `UserProfileStats` schema** for cached stats response

---

## Execution Order

Run migrations in this exact order:
1. `YYYYMMDD000001_add_user_tagline.py`
2. `YYYYMMDD000002_add_badge_definitions.py`
3. `YYYYMMDD000003_add_user_highlights.py`
4. `YYYYMMDD000004_add_reactions_user_index.py`
5. (Optional) `YYYYMMDD000005_add_user_stats_cache.py`

---

## Completion Checklist

- [ ] Migration 1 created and tested
- [ ] Migration 2 created and tested
- [ ] Migration 3 created and tested
- [ ] Migration 4 created and tested
- [ ] Migration 5 created (if needed)
- [ ] Models updated in `models.py`
- [ ] Schemas updated in `schemas.py`
- [ ] All migrations run successfully on dev database
- [ ] Badge definitions seeded with initial data

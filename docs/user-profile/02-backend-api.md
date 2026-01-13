# Backend API Implementation

## Status: ⬜ Not Started

## Overview

This document describes all new API endpoints and modifications to existing endpoints required for the new user profile features.

---

## 1. User Profile Stats Service

### File: `api/app/services/user_profile_stats.py` (NEW)

Create a new service for computing and caching user profile statistics.

### `UserProfileStats` Dataclass

```python
@dataclass
class UserProfileStats:
    user_id: int
    follower_count: int          # Number of users following this user
    following_count: int         # Number of users this user follows
    post_count: int              # Total number of posts (artwork kind only)
    total_views: int             # Sum of views across all posts
    total_reactions: int         # Sum of reactions received across all posts
    reputation: int              # Current reputation (denormalized for convenience)
    computed_at: str             # ISO timestamp
```

### Service Methods

```python
class UserProfileStatsService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_stats(self, user_id: int) -> UserProfileStats | None:
        """Get cached stats or compute fresh if cache miss."""
        # Cache key: user_profile_stats:{user_id}
        # TTL: 5 minutes (300 seconds)
        pass
    
    def invalidate_cache(self, user_id: int) -> None:
        """Invalidate stats cache for a user."""
        pass
    
    def _compute_stats(self, user_id: int) -> UserProfileStats:
        """Compute stats from database."""
        pass
```

### Computation Logic

1. **follower_count**: `SELECT COUNT(*) FROM follows WHERE following_id = :user_id`
2. **following_count**: `SELECT COUNT(*) FROM follows WHERE follower_id = :user_id`
3. **post_count**: `SELECT COUNT(*) FROM posts WHERE owner_id = :user_id AND kind = 'artwork' AND deleted_by_user = false`
4. **total_views**: Sum from `post_stats_daily` for all user's posts (aggregate over all dates)
5. **total_reactions**: `SELECT COUNT(*) FROM reactions r JOIN posts p ON r.post_id = p.id WHERE p.owner_id = :user_id`
6. **reputation**: Direct from `users.reputation`

---

## 2. Follow/Unfollow Endpoints

### File: `api/app/routers/users.py` (MODIFY)

Add these endpoints to the existing users router:

### `POST /api/user/u/{public_sqid}/follow`

Follow a user.

**Authentication**: Required

**Response**: `201 Created` on success, `409 Conflict` if already following

**Body**: None

**Logic**:
1. Decode `public_sqid` to get target user
2. Verify target user exists and is not the current user
3. Check if already following
4. Create `Follow` record
5. Invalidate profile stats cache for target user

### `DELETE /api/user/u/{public_sqid}/follow`

Unfollow a user.

**Authentication**: Required

**Response**: `204 No Content` on success, `404 Not Found` if not following

**Logic**:
1. Decode `public_sqid` to get target user
2. Find and delete `Follow` record
3. Invalidate profile stats cache for target user

### `GET /api/user/u/{public_sqid}/follow-status`

Check if current user follows the target user.

**Authentication**: Required

**Response**:
```json
{
  "is_following": true
}
```

---

## 3. User Highlights Endpoints

### File: `api/app/routers/users.py` (MODIFY)

### `GET /api/user/u/{public_sqid}/highlights`

Get user's highlighted posts in order.

**Authentication**: Optional

**Response**:
```json
{
  "items": [
    {
      "id": 1,
      "position": 0,
      "post": {
        "id": 123,
        "public_sqid": "abc123",
        "title": "My Artwork",
        "art_url": "/api/vault/...",
        "canvas": "64x64",
        "width": 64,
        "height": 64,
        "reaction_count": 42,
        "comment_count": 5,
        "view_count": 1000
      }
    }
  ]
}
```

**Logic**:
1. Decode `public_sqid` to get user
2. Query `user_highlights` joined with `posts`, ordered by `position`
3. Include reaction/comment/view counts for each post

### `POST /api/user/u/{public_sqid}/highlights/{post_sqid}`

Add a post to highlights.

**Authentication**: Required (must be own profile)

**Response**: `201 Created`

**Logic**:
1. Verify ownership
2. Check highlight count < 128
3. Verify post belongs to user
4. Add at next available position

### `DELETE /api/user/u/{public_sqid}/highlights/{post_sqid}`

Remove a post from highlights.

**Authentication**: Required (must be own profile)

**Response**: `204 No Content`

**Logic**:
1. Verify ownership
2. Delete the highlight
3. Recompact positions (shift down to fill gap)

### `PUT /api/user/u/{public_sqid}/highlights/reorder`

Reorder all highlights.

**Authentication**: Required (must be own profile)

**Body**:
```json
{
  "post_sqids": ["abc123", "def456", "ghi789"]
}
```

**Response**: `200 OK`

**Logic**:
1. Verify ownership
2. Verify all post_sqids are currently highlighted
3. Update positions to match array order

---

## 4. Reacted Posts Endpoint

### File: `api/app/routers/users.py` (MODIFY)

### `GET /api/user/u/{public_sqid}/reacted-posts`

Get posts the user has reacted to.

**Authentication**: Optional

**Query Parameters**:
- `cursor`: Pagination cursor
- `limit`: Page size (default 50, max 200)

**Response**: Standard paginated `Page[Post]`

**Logic**:
1. Query reactions by user, ordered by `created_at DESC`
2. Limit to last 8192 reactions
3. Join with posts to get post details
4. Filter out deleted/hidden posts
5. Deduplicate (user may have multiple reactions on same post)
6. Apply cursor pagination

```sql
SELECT DISTINCT p.* 
FROM reactions r
JOIN posts p ON r.post_id = p.id
WHERE r.user_id = :user_id
  AND p.deleted_by_user = false
  AND p.hidden_by_mod = false
ORDER BY MAX(r.created_at) DESC
LIMIT :limit;
```

---

## 5. Enhanced User Profile Endpoint

### File: `api/app/routers/users.py` (MODIFY)

### Modify `GET /api/user/u/{public_sqid}`

Enhance the existing endpoint to include profile stats.

**Add to response**:
```json
{
  // ... existing fields ...
  "tagline": "Digital artist • Pixel dreams",
  "stats": {
    "follower_count": 24500,
    "following_count": 150,
    "post_count": 342,
    "total_views": 1200000,
    "total_reactions": 18300
  },
  "tag_badges": [
    {
      "badge": "early-adopter",
      "icon_url_16": "/badges/early-adopter_16.png"
    }
  ]
}
```

**Logic**:
1. Fetch existing user data
2. Fetch profile stats from cache/service
3. Filter badges to only include `is_tag_badge=true` ones
4. Return combined response

---

## 6. Badge Definitions Endpoint Updates

### File: `api/app/routers/badges.py` (MODIFY)

### Update `GET /api/badge`

Change from hardcoded list to database query.

**Response**:
```json
{
  "items": [
    {
      "badge": "early-adopter",
      "label": "Early Adopter",
      "description": "Joined during beta",
      "icon_url_64": "/badges/early-adopter_64.png",
      "icon_url_16": "/badges/early-adopter_16.png",
      "is_tag_badge": true
    }
  ]
}
```

### Add `POST /api/badge` (Admin only)

Create a new badge definition.

**Authentication**: Required (moderator/owner)

**Body**:
```json
{
  "badge": "new-badge",
  "label": "New Badge",
  "description": "Description here",
  "icon_url_64": "/badges/new-badge_64.png",
  "icon_url_16": "/badges/new-badge_16.png",
  "is_tag_badge": false
}
```

---

## 7. Schema Updates

### File: `api/app/schemas.py`

### New Schemas

```python
class UserProfileStats(BaseModel):
    """Cached user profile statistics."""
    follower_count: int
    following_count: int
    post_count: int
    total_views: int
    total_reactions: int

class UserHighlightPost(BaseModel):
    """Post data for highlights display."""
    id: int
    public_sqid: str
    title: str
    art_url: str
    canvas: str
    width: int
    height: int
    reaction_count: int = 0
    comment_count: int = 0
    view_count: int = 0

class UserHighlight(BaseModel):
    """A highlighted post."""
    id: int
    position: int
    post: UserHighlightPost

class UserHighlightList(BaseModel):
    """List of highlights."""
    items: list[UserHighlight]

class HighlightReorderRequest(BaseModel):
    """Request to reorder highlights."""
    post_sqids: list[str]

class TagBadge(BaseModel):
    """Badge displayed under username."""
    badge: str
    icon_url_16: str

class FollowStatus(BaseModel):
    """Follow status response."""
    is_following: bool
```

### Modified Schemas

```python
class UserPublic(BaseModel):
    # ... existing fields ...
    tagline: str | None = None
    stats: UserProfileStats | None = None
    tag_badges: list[TagBadge] = []

class UserUpdate(BaseModel):
    # ... existing fields ...
    tagline: str | None = Field(None, max_length=48)

class BadgeDefinition(BaseModel):
    badge: str
    label: str
    description: str | None = None
    icon_url_64: str
    icon_url_16: str | None = None
    is_tag_badge: bool = False
```

---

## 8. Number Formatting Utility

### File: `api/app/utils/formatting.py` (NEW)

Create utility for formatting large numbers.

```python
def format_count(n: int) -> str:
    """Format large numbers for display (e.g., 24500 -> '24.5K')."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".rstrip('0').rstrip('.')
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K".rstrip('0').rstrip('.')
    return str(n)
```

**Note**: This formatting should happen on the **frontend**, not backend. The API returns raw integers; the frontend formats them for display.

---

## Completion Checklist

- [ ] `UserProfileStatsService` created
- [ ] Follow/unfollow endpoints implemented
- [ ] Follow status endpoint implemented
- [ ] Highlights endpoints implemented (list, add, remove, reorder)
- [ ] Reacted posts endpoint implemented
- [ ] User profile endpoint enhanced with stats and tag badges
- [ ] Badge definitions endpoint updated to use database
- [ ] All new schemas added
- [ ] All endpoints tested with curl/httpie
- [ ] Cache invalidation working correctly

# Priority 1 Implementation Guide
## Standardizing Token Refresh Across Frontend

**Status**: Ready for Implementation  
**Effort**: 6-10 hours  
**Risk**: Low (additive changes only)  
**Impact**: Eliminates remaining 25% of session loss issues

---

## Overview

This guide provides step-by-step instructions for completing Priority 1: Standardizing the use of `authenticatedFetch` helpers across all frontend pages.

## Goal

Replace all instances of direct `localStorage.getItem('access_token')` + manual `fetch()` calls with the automatic token refresh helpers provided in `/web/src/lib/api.ts`.

---

## Files Requiring Updates

### High Priority (User-Facing Pages)

1. **`/web/src/pages/u/[sqid].tsx`** - User profile page
   - ~8 fetch calls to update
   - Most complex file
   - High traffic

2. **`/web/src/pages/search.tsx`**
   - `HashtagsTab` component (line 641)
   - `UsersTab` component (line 1183)
   - Medium complexity

3. **`/web/src/pages/mod-dashboard.tsx`** - Moderator dashboard
   - ~5 fetch calls to update
   - Admin-only but critical

4. **`/web/src/pages/index.tsx`** - Homepage
   - High traffic
   - Public facing

5. **`/web/src/pages/post/[id].tsx`** - Individual post view
   - High traffic
   - Core functionality

### Medium Priority

6. `/web/src/pages/blog/[id].tsx`
7. `/web/src/pages/blog/index.tsx`
8. `/web/src/pages/blog/write.tsx`
9. `/web/src/pages/p/[sqid].tsx`
10. `/web/src/pages/b/[sqid].tsx`
11. `/web/src/pages/hashtags/[tag].tsx`
12. `/web/src/pages/recommended.tsx`
13. `/web/src/pages/submit.tsx`
14. `/web/src/pages/u/[sqid]/player.tsx`
15. `/web/src/pages/user/[id].tsx`
16. `/web/src/pages/user/[id]/player.tsx`

### Low Priority (Admin/Debug)

17. `/web/src/pages/owner-dashboard.tsx`
18. `/web/src/pages/setup.tsx`
19. `/web/src/pages/github-app-setup.tsx`
20. `/web/src/pages/debug-env.tsx`

---

## Implementation Pattern

### Current Pattern (Problematic)

```typescript
// ❌ BAD - No automatic token refresh
const token = localStorage.getItem('access_token');
const headers: HeadersInit = token ? { 'Authorization': `Bearer ${token}` } : {};
const response = await fetch(`${API_BASE_URL}/api/user/u/${sqid}`, { headers });

if (!response.ok) {
  // Handle error (but token might have expired)
  throw new Error(`Failed: ${response.statusText}`);
}

const data = await response.json();
```

### New Pattern (Correct)

#### Option 1: Using `authenticatedFetch`

```typescript
// ✅ GOOD - Automatic token refresh
import { authenticatedFetch, clearTokens } from '../lib/api';

const response = await authenticatedFetch(`${API_BASE_URL}/api/user/u/${sqid}`);

if (response.status === 401) {
  // Token refresh failed - clear tokens and redirect
  clearTokens();
  router.push('/auth');
  return;
}

if (!response.ok) {
  throw new Error(`Failed: ${response.statusText}`);
}

const data = await response.json();
```

#### Option 2: Using `authenticatedRequestJson` (Simpler)

```typescript
// ✅ BEST - Automatic token refresh with JSON parsing
import { authenticatedRequestJson } from '../lib/api';

try {
  const data = await authenticatedRequestJson<User>(
    `/api/user/u/${sqid}`,
    {}, // options (optional)
    'GET' // method (default: GET)
  );
  
  // Use data directly - token refresh handled automatically
} catch (error) {
  // Handle error
  if (error.message.includes('401')) {
    // Redirect to login
    router.push('/auth');
  }
}
```

#### Option 3: Using `authenticatedPostJson` (For POST Requests)

```typescript
// ✅ BEST for POST - Automatic token refresh with JSON body
import { authenticatedPostJson } from '../lib/api';

try {
  const data = await authenticatedPostJson<Response>(
    `/api/user/${user.user_key}`,
    { handle: newHandle, bio: newBio }
  );
  
  // Use data directly
} catch (error) {
  // Handle error
}
```

---

## Step-by-Step Implementation

### Step 1: Add Imports

At the top of each file, add:

```typescript
import { authenticatedFetch, authenticatedRequestJson, authenticatedPostJson, clearTokens } from '../lib/api';
// Or from '../../lib/api' depending on directory depth
```

### Step 2: Replace GET Requests

Find patterns like:
```typescript
const token = localStorage.getItem('access_token');
const response = await fetch(url, { headers: { 'Authorization': `Bearer ${token}` } });
```

Replace with:
```typescript
const response = await authenticatedFetch(url);
```

Or better yet:
```typescript
const data = await authenticatedRequestJson<DataType>(path);
```

### Step 3: Replace POST/PATCH/DELETE Requests

Find patterns like:
```typescript
const token = localStorage.getItem('access_token');
const response = await fetch(url, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(payload)
});
```

Replace with:
```typescript
const data = await authenticatedPostJson<ResponseType>(path, payload);
```

Or for other methods:
```typescript
const data = await authenticatedRequestJson<ResponseType>(
  path,
  { body: JSON.stringify(payload) },
  'PATCH' // or 'DELETE'
);
```

### Step 4: Handle 401 Errors

After any authenticated call, add:

```typescript
if (response.status === 401) {
  clearTokens();
  router.push('/auth');
  return;
}
```

This is already built into `authenticatedFetch`, but you may want to handle the redirect explicitly.

### Step 5: Remove Manual Token Retrieval

Search for and remove unnecessary:
```typescript
const token = localStorage.getItem('access_token');
```

Unless the token is used for something other than API calls (rare).

---

## Example: Complete Transformation

### Before (from `/web/src/pages/u/[sqid].tsx`)

```typescript
const fetchUser = async () => {
  try {
    const token = localStorage.getItem('access_token');
    const currentUserId = localStorage.getItem('user_id');
    const headers: HeadersInit = token ? { 'Authorization': `Bearer ${token}` } : {};
    
    const response = await fetch(`${API_BASE_URL}/api/user/u/${sqid}`, { headers });
    
    if (!response.ok) {
      if (response.status === 404) {
        setError('User not found');
      } else {
        setError(`Failed to load profile: ${response.statusText}`);
      }
      return;
    }
    
    const data = await response.json();
    setUser(data);
  } catch (err) {
    setError('Failed to load profile');
  }
};
```

### After

```typescript
import { authenticatedRequestJson, clearTokens } from '../../lib/api';

const fetchUser = async () => {
  try {
    const data = await authenticatedRequestJson<User>(`/api/user/u/${sqid}`);
    setUser(data);
  } catch (err) {
    if (err instanceof Error && err.message.includes('401')) {
      clearTokens();
      router.push('/auth');
      return;
    }
    
    if (err instanceof Error && err.message.includes('404')) {
      setError('User not found');
    } else {
      setError('Failed to load profile');
    }
  }
};
```

---

## Testing Checklist

For each file updated:

- [ ] Import `authenticatedFetch` helpers at the top
- [ ] Replace all manual `fetch` + token retrieval
- [ ] Test login flow
- [ ] Test API calls with fresh token
- [ ] Test API calls with expired token (should auto-refresh)
- [ ] Test behavior when refresh token expires (should redirect to login)
- [ ] Test authenticated and unauthenticated states
- [ ] Verify no console errors
- [ ] Check that data loads correctly

---

## Common Pitfalls

### 1. Forgetting to Handle 401 After Refresh Fails

**Problem**:
```typescript
const data = await authenticatedRequestJson<User>('/api/user');
// What if refresh failed?
```

**Solution**:
```typescript
try {
  const data = await authenticatedRequestJson<User>('/api/user');
} catch (error) {
  if (error.message.includes('401')) {
    clearTokens();
    router.push('/auth');
    return;
  }
  // Handle other errors
}
```

### 2. Using Wrong Import Path

**Problem**:
```typescript
import { authenticatedFetch } from '../lib/api'; // Wrong depth
```

**Solution**: Check the file's location relative to `/web/src/lib/api.ts`:
- Files in `/web/src/pages/`: `import from '../lib/api'`
- Files in `/web/src/pages/subdir/`: `import from '../../lib/api'`

### 3. Not Removing Old Token Retrieval

**Problem**: Leaving unused code:
```typescript
const token = localStorage.getItem('access_token'); // Unused!
const data = await authenticatedRequestJson<User>('/api/user');
```

**Solution**: Remove the unused line.

---

## Verification

After all updates:

1. **Build the project**:
   ```bash
   npm run build
   ```

2. **Run linter**:
   ```bash
   npm run lint
   ```

3. **Search for remaining instances**:
   ```bash
   grep -r "localStorage.getItem.*access_token" web/src/pages/
   ```
   
   Should only return files where token is used for display or similar (not API calls).

4. **Test manually**:
   - Log in
   - Browse the site for 4+ hours (or manually expire token in DevTools)
   - Verify no session loss occurs
   - Verify automatic token refresh happens

---

## Estimated Effort

| Task | Time |
|------|------|
| High priority files (1-5) | 3-4 hours |
| Medium priority files (6-16) | 2-3 hours |
| Low priority files (17-20) | 1 hour |
| Testing & verification | 1-2 hours |
| **Total** | **6-10 hours** |

---

## Success Criteria

✅ All 19+ files updated to use `authenticatedFetch` helpers  
✅ No remaining manual token retrieval for API calls  
✅ Build passes without errors  
✅ Linter passes  
✅ Manual testing confirms no session loss  
✅ Token refresh happens automatically  
✅ 401 errors handled gracefully with login redirect

---

## Resources

- **Reference Implementation**: `/web/src/lib/api.ts` (lines 131-220)
- **Good Example**: `/web/src/pages/search.tsx` SearchTab component (line 288)
- **API Helper Functions**:
  - `authenticatedFetch(url, options)` - Low-level fetch with token refresh
  - `authenticatedRequestJson<T>(path, options, method)` - JSON request with token refresh
  - `authenticatedPostJson<T>(path, payload)` - POST request helper
  - `clearTokens()` - Clear all auth tokens
  - `isTokenExpired(token, bufferSeconds)` - Check token expiration

---

**Document Version**: 1.0  
**Last Updated**: 2025-12-04  
**Status**: Ready for Implementation

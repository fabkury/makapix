# Session Management Issue Analysis

## Executive Summary

The Makapix Club website has a critical bug in its session management system that causes users to lose their sessions after closing their browser and returning later. The root cause has been identified as **incomplete data returned by the refresh token endpoint**, which prevents the frontend from properly restoring the user's session state.

## Problem Description

Users are losing their sessions after:
- Closing the browser and returning hours later
- Switching between tabs or leaving the browser idle
- The access token expires but the refresh token is still valid

The website is designed to keep users logged in for up to 30 days via an automatic token renewal mechanism, but this fails due to missing critical data in the token refresh response.

## Root Cause Analysis

### The Issue

The `/api/auth/refresh` endpoint (line 1364 in `/api/app/routers/auth.py`) is returning an **incomplete `OAuthTokens` response**:

```python
return schemas.OAuthTokens(
    token=access_token,
    refresh_token=new_refresh_token,
    user_id=user.id,
    expires_at=expires_at,
    # MISSING: user_key, public_sqid, user_handle
)
```

### Expected Schema

According to the `OAuthTokens` schema definition (`/api/app/schemas.py`):

```python
class OAuthTokens(BaseModel):
    """OAuth token response."""
    token: str
    refresh_token: str | None = None
    user_id: int
    user_key: UUID  # UUID for legacy URL building - REQUIRED
    public_sqid: str | None = None  # Sqids for canonical URLs
    user_handle: str | None = None  # Handle for display
    expires_at: datetime
```

### Why This Causes Session Loss

1. **Initial Login Works**: The login endpoint (`/api/auth/login`, line 266) correctly returns ALL fields:
   ```python
   return schemas.OAuthTokens(
       token=access_token,
       refresh_token=refresh_token,
       user_id=user.id,
       user_key=user.user_key,        # ✓ Included
       public_sqid=user.public_sqid,  # ✓ Included
       user_handle=user.handle,        # ✓ Included
       expires_at=expires_at,
   )
   ```

2. **Token Refresh Fails to Restore State**: When the frontend refreshes the token (after browser reopen or token expiry), it receives incomplete data:
   - The frontend code in `/web/src/lib/api.ts` (lines 124-134) stores the received fields:
   ```typescript
   if (data.user_id) {
       localStorage.setItem("user_id", String(data.user_id));
   }
   if (data.public_sqid) {
       localStorage.setItem("public_sqid", data.public_sqid);
   }
   if (data.user_handle) {
       localStorage.setItem("user_handle", data.user_handle);
   }
   ```
   
3. **Result**: When these fields are missing from the refresh response:
   - `public_sqid` is not updated → User profile links may break
   - `user_handle` is not updated → UI may not display username correctly
   - `user_key` is not updated → UUID-based operations may fail
   - This creates an **inconsistent session state** where the user appears logged in but the application lacks critical user information

4. **Frontend Token Refresh Mechanism**: The frontend has a robust token refresh system in `/web/src/pages/_app.tsx`:
   - Checks tokens on app mount (line 85)
   - Checks when tab becomes visible (line 95-100)
   - Checks on navigation (line 137-148)
   - Checks periodically every 2 minutes (line 88-90)
   
   However, this sophisticated refresh mechanism is undermined by the incomplete API response.

## Impact Assessment

### Severity: HIGH

**Affected Users**: All authenticated users who:
- Close their browser and return later (very common scenario)
- Have access tokens that expire while the browser is open
- Switch between tabs frequently

**User Experience Impact**:
- Users appear logged in but may experience broken functionality
- Profile pages may not load correctly
- Username may not display properly
- Users may need to log out and log back in to restore full functionality

**Business Impact**:
- Poor user experience leading to frustration
- Increased support requests
- Users may believe the site is unreliable
- Potential user churn

## Comparison with Working Endpoints

### ✅ Working: Login Endpoint
```python
# /api/app/routers/auth.py, line 335-343
return schemas.OAuthTokens(
    token=access_token,
    refresh_token=refresh_token,
    user_id=user.id,
    user_key=user.user_key,
    public_sqid=user.public_sqid,
    user_handle=user.handle,
    expires_at=expires_at,
)
```

### ✅ Working: GitHub OAuth Exchange
```python
# /api/app/routers/auth.py, line 1353-1361
return schemas.OAuthTokens(
    token=access_token,
    refresh_token=refresh_token,
    user_id=user.id,
    user_key=user.user_key,
    public_sqid=user.public_sqid,
    user_handle=user.handle,
    expires_at=expires_at,
)
```

### ❌ Broken: Refresh Token Endpoint
```python
# /api/app/routers/auth.py, line 1388-1393
return schemas.OAuthTokens(
    token=access_token,
    refresh_token=new_refresh_token,
    user_id=user.id,
    expires_at=expires_at,
    # MISSING: user_key, public_sqid, user_handle
)
```

## Technical Architecture Context

### Backend (Python FastAPI)
- **JWT Configuration** (`.env.example`):
  - Access tokens expire after 240 minutes (4 hours) by default
  - Refresh tokens expire after 30 days
  - Uses token rotation for security (old refresh token is revoked when used)
  
- **Token Storage**: Refresh tokens are securely stored in PostgreSQL (`refresh_tokens` table) with:
  - SHA-256 hashed token
  - Expiration timestamp
  - Revocation flag
  - User relationship

### Frontend (Next.js + TypeScript)
- **Token Storage**: localStorage (survives browser close)
  - `access_token`: JWT access token
  - `refresh_token`: Opaque refresh token
  - `user_id`, `user_key`, `public_sqid`, `user_handle`: User metadata
  
- **Refresh Logic**: Proactive and reactive
  - Pre-request check if token is expired
  - Post-401 retry with refresh
  - Periodic background checks (every 2 minutes)
  - On tab visibility change (critical for browser reopen)
  - On window focus and network reconnection

## Recommended Fix

### Primary Fix: Update Refresh Token Endpoint Response

**File**: `/api/app/routers/auth.py`  
**Location**: Line 1388-1393  
**Change Required**: Add missing fields to the return statement

```python
# Current (broken)
return schemas.OAuthTokens(
    token=access_token,
    refresh_token=new_refresh_token,
    user_id=user.id,
    expires_at=expires_at,
)

# Fixed
return schemas.OAuthTokens(
    token=access_token,
    refresh_token=new_refresh_token,
    user_id=user.id,
    user_key=user.user_key,       # ADD THIS
    public_sqid=user.public_sqid,  # ADD THIS
    user_handle=user.handle,        # ADD THIS
    expires_at=expires_at,
)
```

### Why This Fix Works

1. **Consistency**: Makes the refresh endpoint return the same data structure as login and OAuth endpoints
2. **Session Restoration**: Ensures all user metadata is refreshed along with tokens
3. **Minimal Change**: Only 3 lines need to be added
4. **No Breaking Changes**: The fields were always supposed to be there per the schema definition
5. **Frontend Already Handles It**: The frontend code already stores these fields when present

## Testing Recommendations

### Manual Testing
1. **Test Token Refresh Flow**:
   - Log in to the application
   - Wait for access token to expire (or force expiration)
   - Trigger a refresh (navigate to a protected page)
   - Verify all localStorage fields are maintained
   
2. **Test Browser Reopen**:
   - Log in to the application
   - Note the user's handle and sqid
   - Close the browser completely
   - Reopen and visit the site
   - Verify user is still logged in with correct handle displayed

3. **Test Token Rotation**:
   - Log in and capture the initial refresh_token
   - Trigger a token refresh
   - Verify a new refresh_token is issued
   - Verify the old refresh_token no longer works

### Automated Testing
1. Add integration test for refresh endpoint response schema
2. Add test to verify all OAuthTokens fields are populated
3. Add test for token refresh with expired access token

## Alternative Considerations

### Why Not Change the Schema?
- Making fields optional would break the frontend's expectation
- Would require more extensive frontend changes
- Inconsistent with login and OAuth endpoints
- Not the right fix since these fields are genuinely required

### Why Not Change Frontend to Handle Missing Fields?
- The frontend is working correctly - it stores what it receives
- The issue is on the backend not providing complete data
- Defensive coding in frontend would mask the real problem
- Other clients (mobile apps, etc.) would have the same issue

## Additional Observations

### Strong Points of Current Implementation
1. **Robust Frontend Refresh Logic**: The `_app.tsx` implementation handles multiple scenarios:
   - Tab visibility changes
   - Network reconnection
   - Periodic checks
   - Navigation-triggered checks
   
2. **Security Best Practices**:
   - Token rotation (old refresh tokens are revoked)
   - Tokens stored with SHA-256 hash in database
   - Refresh tokens have 30-day expiration
   - Proper CORS configuration
   
3. **Good Token Expiry Settings**:
   - 4-hour access tokens balance security and UX
   - 30-day refresh tokens allow long-term sessions
   - 5-minute buffer for proactive refresh

### Potential Future Enhancements
1. **Add Refresh Token Cleanup Task**: Consider adding a Celery task to clean up expired/revoked refresh tokens from the database
2. **Add Monitoring**: Track refresh token usage patterns and failure rates
3. **Add Test Coverage**: Add comprehensive tests for all auth endpoints
4. **Consider Adding User Agent Tracking**: Track which device/browser a refresh token belongs to

## Conclusion

The session management issue is caused by a simple but critical bug: the refresh token endpoint returns incomplete data. The fix is straightforward and low-risk - adding three fields to the endpoint's return statement. The frontend is already designed to handle these fields correctly, so no frontend changes are needed.

**Priority**: High - This should be fixed immediately as it affects all users' session persistence.

**Risk**: Very Low - The change is minimal and aligns with the existing schema definition.

**Effort**: Minimal - 3 lines of code + testing.

## Files Requiring Changes

1. **PRIMARY FIX**:
   - `/api/app/routers/auth.py` (line 1388-1393) - Add missing fields to refresh token response

2. **NO FRONTEND CHANGES NEEDED**: The frontend already correctly handles these fields when present.

## Next Steps

1. ✅ Investigate and identify root cause (COMPLETE)
2. ✅ Create analysis report (COMPLETE)
3. ⏳ Implement the fix in the refresh token endpoint
4. ⏳ Test manually (login, refresh, browser reopen scenarios)
5. ⏳ Run security checks (CodeQL)
6. ⏳ Deploy and monitor

---

**Report Created**: 2025-12-08  
**Author**: GitHub Copilot Workspace Agent  
**Status**: Ready for implementation

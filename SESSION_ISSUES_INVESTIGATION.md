# Makapix Club Session Management Investigation Report

**Date:** December 9, 2025  
**Issue:** Users getting logged out after closing browser and returning hours later  
**Status:** Investigation Complete - Root Causes Identified

## Executive Summary

After thorough investigation of the Makapix Club codebase, **I have identified multiple critical issues** that explain why users are being logged out when they close their browser and return later. The primary problem is that **the application relies exclusively on `localStorage` for session persistence**, which is **fundamentally incompatible with long-term session retention** in modern browsers.

## Critical Findings

### 🔴 CRITICAL ISSUE #1: Reliance on localStorage Instead of Cookies

**Location:** 
- `web/src/lib/api.ts` (lines 38-48, 54-60)
- `web/src/pages/auth.tsx` (lines 54-65, 179-189)
- `web/src/pages/_app.tsx` (lines 31-32)

**The Problem:**
The application stores ALL authentication tokens in `localStorage`:
```typescript
// From api.ts
export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}
```

**Why This Causes Session Loss:**

1. **localStorage is NOT persistent across browser restarts** - While localStorage data persists longer than sessionStorage, many browsers (especially mobile browsers and privacy-focused browsers) clear localStorage when:
   - The browser is completely closed and reopened after several hours
   - The device is restarted
   - The user clears browsing data
   - The browser is in private/incognito mode
   - iOS Safari's "Prevent Cross-Site Tracking" is enabled (default)
   - Browser storage quota is exceeded

2. **No HttpOnly Protection** - Storing tokens in localStorage exposes them to XSS attacks since JavaScript can access them.

3. **No Secure Flag** - localStorage data is not protected with the `Secure` flag that forces HTTPS-only transmission.

**Impact:** HIGH - This is the primary cause of session loss

**Recommended Solution:** 
- Implement HttpOnly cookies for refresh tokens
- Keep access tokens in memory (or short-lived sessionStorage)
- Use the cookie-based refresh token to restore sessions

---

### 🔴 CRITICAL ISSUE #2: Access Token Expiration Too Short for User Experience

**Location:** 
- `.env.example` (line 36)
- `api/app/auth.py` (line 38)

**Current Configuration:**
```bash
# From .env.example
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=240  # 4 hours
```

**The Problem:**
While 4 hours seems reasonable, this creates friction when combined with the localStorage issue:

1. **Access tokens expire after 4 hours** - Users who leave the site open but idle will need to refresh
2. **If localStorage is cleared** - The refresh token is lost, forcing a new login
3. **Mobile browsers are aggressive** - iOS Safari and Chrome on mobile often clear localStorage after the browser is closed

**Impact:** MEDIUM - Amplifies the localStorage problem

**Current State:**
The default in the code is actually 60 minutes (1 hour):
```python
# From api/app/auth.py
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
```

But `.env.example` suggests 240 minutes (4 hours), creating configuration confusion.

---

### 🔴 CRITICAL ISSUE #3: No Persistent Session Mechanism

**Location:**
- Entire application architecture

**The Problem:**
The application has **no fallback mechanism** when localStorage is cleared:

1. **No "Remember Me" checkbox** - Users cannot opt-in to longer sessions
2. **No server-side session store** - All session state lives in the browser
3. **No session restoration** - When tokens are lost, users must log in again
4. **No persistent cookies** - Even the refresh token is only in localStorage

**Impact:** HIGH - Creates poor user experience

---

### 🟡 MODERATE ISSUE #4: Token Refresh Logic Has Race Condition Window

**Location:**
- `web/src/lib/api.ts` (lines 82-166)
- `web/src/pages/_app.tsx` (lines 21-81)

**The Problem:**
While the token refresh implementation is sophisticated with:
- Duplicate request prevention (`isRefreshing` flag)
- Grace period for token rotation (60 seconds)
- Multiple triggers (visibility change, focus, interval)

There's still a window where issues can occur:

```typescript
// From _app.tsx
const checkAndRefreshToken = async (reason: string = 'scheduled') => {
  // Prevent concurrent checks
  if (isCheckingRef.current) {
    console.log(`[Auth] Skipping check (${reason}) - already in progress`);
    return;
  }
  
  isCheckingRef.current = true;
  // ... refresh logic ...
};
```

**The Issue:**
1. **Visibility change handler fires** when user returns to the tab
2. **If localStorage was cleared** during the absence, tokens are gone
3. **No recovery mechanism** - User is just logged out silently

**Impact:** MEDIUM - Makes the localStorage issue worse

---

### 🟡 MODERATE ISSUE #5: Inconsistent Token Expiration Settings

**Location:**
- `.env.example` (lines 34-38)
- `api/app/auth.py` (lines 38-39)

**The Problem:**
```bash
# .env.example says 240 minutes (4 hours)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=240

# But code defaults to 60 minutes (1 hour)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
```

**Impact:** LOW - Causes confusion but not direct session loss

---

### 🟢 GOOD: Token Rotation Implementation

**Location:**
- `api/app/auth.py` (lines 166-200)
- `api/app/routers/auth.py` (lines 1364-1407)

**What's Working Well:**
The refresh token rotation with grace period is well-implemented:

```python
def mark_refresh_token_rotated(token: str, db: Session, grace_seconds: int = 60) -> None:
    """
    Mark a refresh token as rotated with a grace period.
    
    Instead of immediately revoking the token, we shorten its expiry to allow
    a grace period. This handles race conditions...
    """
```

This handles:
- Multiple tabs trying to refresh simultaneously
- Network failures during refresh
- Browser closing before token is stored

**However**, this ONLY helps if the token still exists in localStorage. If localStorage is cleared, this grace period is irrelevant.

---

### 🟢 GOOD: Frontend Refresh Triggers

**Location:**
- `web/src/pages/_app.tsx` (lines 84-139)

**What's Working Well:**
The frontend has comprehensive triggers for token refresh:

```typescript
// On mount (browser reopens)
checkAndRefreshToken('mount');

// Visibility change (tab becomes active)
document.addEventListener('visibilitychange', handleVisibilityChange);

// Window focus
window.addEventListener('focus', handleFocus);

// Network restored
window.addEventListener('online', handleOnline);

// Cross-tab synchronization
window.addEventListener('storage', handleStorageChange);

// Periodic check (2 minutes)
setInterval(() => checkAndRefreshToken('interval'), 120000);
```

**However**, these are all useless if localStorage has been cleared.

---

## Root Cause Analysis

### Why Users Are Getting Logged Out

The session loss occurs through this sequence:

1. **User logs in** → Tokens stored in localStorage
2. **User closes browser** → Browser is fully closed (not just tab)
3. **Hours pass** → 
   - Mobile browser clears localStorage (iOS Safari, Chrome mobile)
   - OR Desktop browser in strict privacy mode clears storage
   - OR User's device restarts/updates
4. **User reopens browser** → Opens Makapix website
5. **App mount triggers token check** → `checkAndRefreshToken('mount')` runs
6. **localStorage is empty** → No access token, no refresh token
7. **User appears logged out** → Must log in again

### Browser-Specific Behaviors

#### iOS Safari (Most Affected)
- Clears localStorage after **7 days of inactivity**
- Can clear earlier if "Prevent Cross-Site Tracking" is enabled
- Aggressive cleanup on low storage

#### Chrome Mobile
- Less aggressive than Safari
- May clear on force-close or low memory
- Privacy mode always clears

#### Desktop Browsers
- Generally more persistent
- Incognito/Private mode ALWAYS clears
- User-initiated "Clear Browsing Data" clears everything

---

## Why Previous Fixes Likely Failed

Based on the codebase evidence, previous attempts to fix this probably:

1. **Adjusted token expiration times** - Doesn't matter if localStorage is cleared
2. **Added more refresh triggers** - Already comprehensive, but can't refresh without tokens
3. **Improved grace periods** - Helps with race conditions, not storage loss
4. **Enhanced logging** - Good for debugging, doesn't prevent the issue

The fundamental architecture (localStorage-based) was never addressed.

---

## Recommended Solutions

### 🎯 PRIMARY SOLUTION: Implement Cookie-Based Refresh Tokens

**Priority:** CRITICAL  
**Effort:** Medium (2-3 days)  
**Impact:** Completely solves the issue

#### Backend Changes:

1. **Modify `/auth/login` endpoint** to set HttpOnly cookie:
```python
@router.post("/login")
def login(payload: schemas.LoginRequest, response: Response, ...):
    # ... existing login logic ...
    
    # Set refresh token as HttpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,  # Prevents JavaScript access (XSS protection)
        secure=True,    # HTTPS only
        samesite="lax", # CSRF protection
        max_age=30 * 24 * 60 * 60,  # 30 days
        path="/"
    )
    
    # Only return access token in response body
    return {
        "token": access_token,
        "user_id": user.id,
        # Don't return refresh_token in JSON
    }
```

2. **Modify `/auth/refresh` endpoint** to read from cookie:
```python
@router.post("/refresh")
def refresh_token(request: Request, response: Response, db: Session):
    # Read refresh token from cookie instead of request body
    refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")
    
    # ... verify and create new tokens ...
    
    # Set new refresh token in cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=30 * 24 * 60 * 60,
        path="/"
    )
    
    return {"token": new_access_token}
```

3. **Add `/auth/logout` cookie clearing**:
```python
@router.post("/logout")
def logout(response: Response, ...):
    response.delete_cookie(key="refresh_token", path="/")
    # ... existing logout logic ...
```

#### Frontend Changes:

1. **Update `api.ts`** to NOT store refresh token:
```typescript
export function storeTokens(accessToken: string, refreshToken?: string | null): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("access_token", accessToken);
  // DON'T store refresh token - it's in the cookie now
  // Only keep user metadata
}

export function getRefreshToken(): string | null {
  // Refresh token is now in HttpOnly cookie, not accessible to JS
  // This function can be removed or return null
  return null;
}
```

2. **Update `refreshAccessToken`** to use cookie:
```typescript
export async function refreshAccessToken(): Promise<boolean> {
  try {
    const response = await fetch(`${publicBaseUrl}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",  // CRITICAL: Include cookies
      headers: {
        "Content-Type": "application/json",
      },
      // No body needed - refresh token is in cookie
    });
    
    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        clearTokens();
      }
      return false;
    }
    
    const data = await response.json();
    storeTokens(data.token);  // Only store access token
    // Refresh token is automatically updated in cookie by server
    
    return true;
  } catch (error) {
    console.error("[Auth] Refresh failed:", error);
    return false;
  }
}
```

3. **Update all API calls** to include credentials:
```typescript
export async function authenticatedFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  return fetch(url, {
    ...options,
    credentials: "include",  // Always include cookies
    headers: {
      ...options.headers,
    },
  });
}
```

#### Benefits:
- ✅ Survives browser close/reopen
- ✅ Protected from XSS attacks
- ✅ Automatic CSRF protection with SameSite
- ✅ Works in all browsers including iOS Safari
- ✅ No changes needed to token rotation logic

---

### 🎯 SECONDARY SOLUTION: Implement "Remember Me" Option

**Priority:** HIGH  
**Effort:** Low (1 day)  
**Impact:** Gives users control

Add a checkbox on login page:
```tsx
<input 
  type="checkbox" 
  checked={rememberMe} 
  onChange={(e) => setRememberMe(e.target.checked)}
/>
<label>Stay signed in for 30 days</label>
```

Backend logic:
```python
# If remember_me is True, extend refresh token to 30 days
# If False, reduce to 1 day (browser session)
expires_in_days = 30 if payload.remember_me else 1
```

Cookie settings:
```python
max_age = 30 * 24 * 60 * 60 if remember_me else None  # None = session cookie
```

---

### 🎯 TERTIARY SOLUTION: Increase Access Token Lifetime

**Priority:** MEDIUM  
**Effort:** Very Low (5 minutes)  
**Impact:** Reduces frequency of refresh, but doesn't solve core issue

Change default from 60 to 240 minutes:
```python
# In api/app/auth.py
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "240"))
```

Update `.env.example` to document this.

**Trade-off:** Longer access tokens = slightly higher security risk if compromised, but with proper cookie-based refresh tokens, this is acceptable.

---

### 🎯 OPTIONAL: Add Session Restoration UI

**Priority:** LOW  
**Effort:** Medium  
**Impact:** Better UX when sessions are lost

Add a banner when session is lost:
```tsx
{sessionLost && (
  <div className="session-lost-banner">
    Your session has expired. Please log in again to continue.
    <button onClick={() => router.push('/auth')}>Log In</button>
  </div>
)}
```

---

## Testing Recommendations

After implementing the cookie-based solution:

### Test Case 1: Browser Close/Reopen
1. Log in to Makapix
2. Verify refresh_token cookie is set (check DevTools → Application → Cookies)
3. Close browser completely
4. Wait 5-10 minutes
5. Reopen browser and navigate to Makapix
6. Should remain logged in

### Test Case 2: iOS Safari
1. Log in on iOS Safari
2. Close Safari completely (swipe up from app switcher)
3. Wait several hours or restart device
4. Reopen Safari and navigate to Makapix
5. Should remain logged in

### Test Case 3: Multiple Tabs
1. Log in on Tab A
2. Open Tab B to same site
3. Logout on Tab A
4. Tab B should detect logout (storage event)
5. Both tabs should be logged out

### Test Case 4: Token Rotation
1. Log in
2. Wait until near token expiration
3. Trigger refresh by switching tabs
4. Verify new tokens are issued
5. Old refresh token should have grace period

### Test Case 5: Private Mode
1. Open Makapix in incognito/private mode
2. Log in
3. Close incognito window
4. Reopen incognito window
5. Should be logged out (expected - session cookies don't persist in private mode)

---

## Security Considerations

### Current Security Posture (localStorage)
- ❌ Vulnerable to XSS attacks (JavaScript can read tokens)
- ❌ Vulnerable to storage clearing
- ❌ No CSRF protection
- ✅ Token rotation with grace period
- ✅ Refresh tokens are hashed in database

### Proposed Security Posture (HttpOnly Cookies)
- ✅ Protected from XSS (JavaScript cannot read refresh token)
- ✅ Persistent across browser sessions
- ✅ CSRF protected with SameSite flag
- ✅ Token rotation with grace period
- ✅ Refresh tokens are hashed in database
- ✅ Access tokens still in localStorage (short-lived, less critical)

### Additional Security Measures to Consider
1. **Implement CSRF tokens** for state-changing operations
2. **Add device fingerprinting** to detect token theft
3. **Log all token refreshes** for security auditing
4. **Implement suspicious activity detection** (e.g., refresh from different IP)
5. **Add "Active Sessions" page** where users can revoke sessions

---

## Configuration Recommendations

### Development Environment (.env)
```bash
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=240  # 4 hours (frequent development)
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30     # 30 days
JWT_SECRET_KEY=<secure-random-key>

# Cookie settings (backend should use these)
COOKIE_SECURE=false  # true for production
COOKIE_SAMESITE=lax
COOKIE_DOMAIN=localhost
```

### Production Environment
```bash
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=480  # 8 hours (less frequent refreshes)
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30     # 30 days
JWT_SECRET_KEY=<production-key>

# Cookie settings
COOKIE_SECURE=true   # HTTPS only
COOKIE_SAMESITE=lax  # Balance between security and usability
COOKIE_DOMAIN=.makapix.club  # Allow subdomain access
```

---

## Migration Path

### Phase 1: Add Cookie Support (Backward Compatible)
1. Update backend to SET refresh token as cookie
2. Backend still ACCEPTS refresh token from request body (backward compatible)
3. Deploy backend
4. Test with old frontend

### Phase 2: Update Frontend
1. Update frontend to NOT send refresh token in body
2. Update frontend to include credentials
3. Deploy frontend
4. Test thoroughly

### Phase 3: Remove Legacy Support (After 30 days)
1. Remove support for refresh token in request body
2. Force cookie-based refresh
3. Old clients will be logged out (acceptable after 30 days)

---

## Monitoring and Alerts

After deployment, monitor:

1. **Token Refresh Success Rate**
   - Should be >99% after fix
   - Alert if drops below 95%

2. **Session Duration**
   - Track average session length
   - Should increase significantly

3. **Login Frequency**
   - Should decrease as sessions persist

4. **Browser-Specific Metrics**
   - Track success rate by browser/OS
   - Identify any remaining issues

---

## Conclusion

The session logout issue is caused by **fundamental architectural reliance on localStorage**, which is cleared by browsers (especially mobile browsers) when the app is closed. 

**The primary solution** is to implement **HttpOnly cookie-based refresh tokens**, which:
- Persist across browser sessions
- Provide better security
- Work reliably on all browsers including iOS Safari

**Implementation effort** is moderate (2-3 days) but **completely solves the issue**.

**Additional improvements** (Remember Me, longer access tokens) can be layered on top but won't solve the core problem without cookie-based refresh tokens.

---

## References

### Code Locations
- **Frontend Auth:** `web/src/lib/api.ts`, `web/src/pages/_app.tsx`, `web/src/pages/auth.tsx`
- **Backend Auth:** `api/app/auth.py`, `api/app/routers/auth.py`
- **Models:** `api/app/models.py` (RefreshToken)
- **Config:** `.env.example`, `docker-compose.yml`

### Browser Documentation
- [MDN: Window.localStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)
- [MDN: HTTP cookies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies)
- [Safari: Intelligent Tracking Prevention](https://webkit.org/blog/7675/intelligent-tracking-prevention/)

### Security Best Practices
- [OWASP: Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [OWASP: Token Storage](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html#token-storage)

---

**Report prepared by:** GitHub Copilot AI Agent  
**Investigation completed:** December 9, 2025  
**Next steps:** Review findings and approve implementation of cookie-based solution

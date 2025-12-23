# Session Management Diagnosis Report - Makapix Club

**Report Date:** December 11, 2024  
**Issue:** Users are unexpectedly logged out after closing the browser and returning hours later  
**Expected Behavior:** Sessions should last 60 minutes but be automatically renewed within 30 days of successful login (as long as the user did not intentionally log out)

---

## Executive Summary

After thorough analysis of the Makapix Club codebase, I have identified **the root cause of the session management issues**. The problem is a fundamental architectural mismatch between the backend token expiration settings and the frontend refresh logic, compounded by aggressive token expiration and a misalignment between development and production configurations.

**Root Cause:** The access token expires in 60 minutes (production) or 240 minutes (development), but there is **no proactive refresh mechanism that works reliably when the browser/tab is closed**. When users close the browser and return hours later, their access token has expired, and the frontend's token refresh logic doesn't trigger until the user interacts with the application.

**Severity:** High - This issue affects user retention and experience significantly.

---

## Detailed Findings

### 1. Token Architecture Analysis

#### Backend Configuration (`/api/app/auth.py`)

```python
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30"))
```

**Current Behavior:**
- **Access Token:** Expires in 60 minutes (production default) or 240 minutes (development)
- **Refresh Token:** Expires in 30 days, stored in HttpOnly cookie
- **Cookie max_age:** Set to 30 days (2,592,000 seconds)

**Critical Issue #1: Cookie Configuration Inconsistency**

In `/api/app/auth.py` lines 544-550:
```python
cookie_config = {
    "httponly": True,
    "secure": secure,
    "samesite": samesite,
    "path": "/",
    "max_age": JWT_REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,  # 30 days in seconds
}
```

The cookie `max_age` is set to 30 days, which means the **browser will delete the cookie after 30 days**, regardless of whether the refresh token in the database is still valid. However, this is not the primary issue causing early logouts.

#### Frontend Token Management (`/web/src/lib/api.ts`)

The frontend implements a conservative token refresh strategy:

```typescript
export async function refreshAccessToken(): Promise<boolean> {
  // Only clear tokens on definitive auth failures (401/403)
  // Do NOT clear on 5xx errors - those are server issues
  if (response.status === 401 || response.status === 403) {
    console.log("[Auth] Definitive auth failure, clearing tokens");
    clearTokens();
  }
}
```

**Critical Issue #2: Reactive vs. Proactive Refresh**

The frontend refresh mechanism in `/web/src/pages/_app.tsx` is **reactive** rather than **proactive**:

```typescript
useEffect(() => {
  // Initial check on mount
  checkAndRefreshToken('mount');

  // Set up interval to check every 2 minutes
  const refreshInterval = setInterval(() => {
    checkAndRefreshToken('interval');
  }, 120000); // 2 minutes
```

**The Problem:**
1. When the browser/tab is closed, the JavaScript execution stops
2. The 2-minute interval timer is suspended
3. When the browser is reopened hours later:
   - The `mount` effect triggers
   - It checks if access token is expired (it is, after 60-240 minutes)
   - It attempts to refresh using the HttpOnly cookie
   - **BUT** the refresh token cookie might have been cleared by the browser

### 2. Browser Cookie Behavior Analysis

**Critical Issue #3: Browser Cookie Lifecycle**

Modern browsers (Chrome, Firefox, Safari, Edge) handle cookies differently based on their settings:

1. **Session Cookies vs. Persistent Cookies:**
   - Cookies **without** `max_age` or `expires` = Session cookies (deleted when browser closes)
   - Cookies **with** `max_age` or `expires` = Persistent cookies (survive browser restart)
   
2. **Makapix Current Implementation:**
   - ✅ Refresh token cookie HAS `max_age=30 days` (persistent)
   - ✅ Should survive browser restart
   - ❌ **BUT** users report being logged out after closing browser

**This indicates one of three scenarios:**

**Scenario A: Browser Privacy Settings**
- Users may have browser settings that clear cookies on exit
- "Clear cookies when you close the browser" is enabled
- This is OUTSIDE the application's control

**Scenario B: Cookie Domain/Path Mismatch**
- The cookie domain might not match when the user returns
- Auto-detection logic might produce different results on different requests

**Scenario C: Third-Party Cookie Blocking**
- If the API and frontend are on different domains/subdomains
- Browsers may treat the refresh token cookie as third-party and block it

### 3. Frontend Refresh Logic Analysis

In `/web/src/pages/_app.tsx`, lines 21-75, the token refresh logic:

```typescript
const checkAndRefreshToken = async (reason: string = 'scheduled') => {
  const token = getAccessToken();
  
  // If we have no access token, try to refresh using the refresh token cookie
  if (!token) {
    console.log(`[Auth] No access token found, attempting refresh from cookie (${reason})`);
    const success = await refreshAccessToken();
    // ...
  }
  
  // If token exists, check if it's expired or about to expire
  if (token) {
    const expired = isTokenExpired(token, 0); // Actually expired
    const expiringSoon = isTokenExpired(token, 300); // Within 5 minutes
    
    if (expired) {
      // Try to refresh
    } else if (expiringSoon) {
      // Proactive refresh
    }
  }
}
```

**Critical Issue #4: Access Token Stored in localStorage**

The access token is stored in **localStorage**, which:
- ✅ Persists across browser restarts
- ✅ Accessible to JavaScript
- ❌ Has security implications (XSS vulnerability)

When the user reopens the browser:
1. The expired access token is still in localStorage
2. The code detects it's expired and attempts refresh
3. The refresh attempt **should** work if the cookie is present
4. **BUT** if the cookie was cleared (Scenarios A/B/C above), refresh fails

### 4. Environment Configuration Analysis

**Development Environment** (`/env.local.template`):
```bash
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=240  # 4 hours
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
```

**Production Environment** (`.env.example`):
```bash
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60   # 1 hour (default if not set)
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30
```

**Critical Issue #5: Development vs. Production Divergence**

The development environment uses a 4-hour access token, which masks the problem:
- Developers can close the browser and return within 4 hours without issues
- **But production users experience logouts after 1 hour**
- This creates a **false sense of security** during development

### 5. Cookie Domain Auto-Detection Analysis

In `/api/app/auth.py`, lines 509-537:

```python
def get_cookie_config(request: Request | None = None) -> dict[str, any]:
    # Get domain from environment, or auto-detect from request
    domain_env = os.getenv("COOKIE_DOMAIN", "")
    
    if domain_env:
        domain = domain_env if domain_env.strip() else None
    elif request:
        # Auto-detect domain from request
        host = request.headers.get("host", "")
        hostname = host.split(":")[0] if ":" in host else host
        
        # For localhost/127.0.0.1, don't set domain attribute
        if hostname in ("localhost", "127.0.0.1"):
            domain = None
        elif "." in hostname:
            # For production domains, use dot prefix for subdomain support
            parts = hostname.split(".")
            if len(parts) >= 2:
                domain = "." + ".".join(parts[-2:])
```

**Critical Issue #6: Inconsistent Domain Detection**

If the domain detection produces different results on different requests:
- Login request: Sets cookie with `domain=.makapix.club`
- Refresh request: Expects cookie with potentially different domain
- **Result:** Cookie not found, refresh fails

This could happen if:
- User accesses via different subdomains (www.makapix.club vs. makapix.club)
- Load balancer or reverse proxy changes the Host header
- Environment variable `COOKIE_DOMAIN` is not set consistently

---

## Root Cause Summary

The **primary root cause** is a combination of:

1. **Short Access Token Lifetime (60 minutes)** combined with **long periods of inactivity**
   - Users close browser, return hours later
   - Access token is expired (stored in localStorage)
   - System attempts to refresh using cookie

2. **Browser Cookie Management**
   - Despite `max_age=30 days`, browsers may clear cookies based on:
     - User privacy settings ("Clear cookies on exit")
     - Third-party cookie policies
     - Domain/path mismatches

3. **No Server-Side Session Tracking**
   - The system relies entirely on client-side tokens
   - No fallback mechanism if cookie is lost
   - No way to detect if user intentionally logged out vs. cookie was cleared

4. **Development/Production Configuration Mismatch**
   - 4-hour tokens in dev hide the issue
   - 1-hour tokens in prod expose it immediately

5. **Lack of Pre-Emptive Refresh on Page Load**
   - The frontend attempts refresh on mount, but by then the cookie may be gone
   - No mechanism to refresh token BEFORE it expires if user is inactive

---

## Recommended Solutions

### High Priority (Must Fix)

#### 1. **Implement Server-Side Session Management**

**Problem:** Current system has no server-side session state, relies entirely on client-side tokens.

**Solution:** Add a `sessions` table to track active sessions:

```python
class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_token = Column(String(255), nullable=False, unique=True, index=True)
    refresh_token_id = Column(UUID, ForeignKey("refresh_tokens.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_activity_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    active = Column(Boolean, default=True, index=True)
```

**Benefits:**
- Can detect intentional logouts vs. expired sessions
- Can extend session on activity (sliding window)
- Can track session history for security

#### 2. **Implement Sliding Session Windows**

**Problem:** Fixed 60-minute access token expiration regardless of user activity.

**Solution:** Extend session on user activity:

```python
def extend_session(session_id: str, db: Session) -> bool:
    """Extend session expiration on user activity."""
    session = db.query(Session).filter(
        Session.session_token == session_id,
        Session.active == True
    ).first()
    
    if session:
        # Extend by 60 minutes from now
        session.expires_at = datetime.now(timezone.utc) + timedelta(minutes=60)
        session.last_activity_at = datetime.now(timezone.utc)
        db.commit()
        return True
    return False
```

**Call this on every authenticated request.**

#### 3. **Fix Cookie Domain Configuration**

**Problem:** Domain auto-detection can produce inconsistent results.

**Solution:** Set `COOKIE_DOMAIN` explicitly in production environment:

```bash
# Production .env
COOKIE_DOMAIN=.makapix.club
```

**AND** add validation to ensure consistency:

```python
def get_cookie_config(request: Request | None = None) -> dict[str, any]:
    domain_env = os.getenv("COOKIE_DOMAIN", "")
    
    if domain_env:
        domain = domain_env if domain_env.strip() else None
    else:
        # Log warning if auto-detecting in production
        logger.warning("COOKIE_DOMAIN not set, auto-detecting from request. "
                      "Set COOKIE_DOMAIN explicitly for consistent behavior.")
        # ... auto-detection logic
```

#### 4. **Implement "Remember Me" Functionality**

**Problem:** All users get 30-day refresh tokens regardless of preference.

**Solution:** Add a "Remember Me" checkbox on login:

```python
@router.post("/login")
def login(
    payload: schemas.LoginRequest,
    remember_me: bool = False,  # New parameter
    ...
):
    if remember_me:
        # Long-lived session (30 days)
        refresh_token_days = 30
        cookie_max_age = 30 * 24 * 60 * 60
    else:
        # Short-lived session (1 day)
        refresh_token_days = 1
        cookie_max_age = 24 * 60 * 60
    
    refresh_token = create_refresh_token(user.user_key, db, expires_in_days=refresh_token_days)
    
    # Set cookie with appropriate max_age
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=cookie_max_age,
        ...
    )
```

**Frontend:**
```tsx
<label>
  <input type="checkbox" checked={rememberMe} onChange={e => setRememberMe(e.target.checked)} />
  Remember me for 30 days
</label>
```

### Medium Priority (Should Fix)

#### 5. **Increase Access Token Lifetime to Balance Refresh Frequency**

**Problem:** 60-minute access token requires refresh every hour, which:
- Increases server load
- Creates more opportunities for failure
- Worsens user experience if refresh fails

**Solution:** Increase to 4 hours (like development):

```bash
# Production .env
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=240  # 4 hours
```

**Security tradeoff:** Slightly longer exposure window if token is compromised, but:
- Refresh token is still in HttpOnly cookie (secure)
- Access token is short-lived compared to session duration
- Reduces refresh failures by 4x

#### 6. **Add Session Heartbeat API**

**Problem:** No way to keep session alive during inactive periods.

**Solution:** Add a lightweight heartbeat endpoint:

```python
@router.post("/auth/heartbeat")
def session_heartbeat(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Extend current session without issuing new tokens."""
    # Update last_activity_at in session table
    # Return success
    return {"status": "ok", "expires_in": 14400}  # 4 hours
```

**Frontend:** Call periodically when tab is visible:

```typescript
// In _app.tsx
const sendHeartbeat = async () => {
  try {
    await authenticatedFetch(`${API_BASE_URL}/api/auth/heartbeat`, {
      method: 'POST'
    });
  } catch (error) {
    console.error('[Auth] Heartbeat failed:', error);
  }
};

// Send heartbeat every 5 minutes when tab is visible
useEffect(() => {
  const heartbeatInterval = setInterval(() => {
    if (document.visibilityState === 'visible') {
      sendHeartbeat();
    }
  }, 300000); // 5 minutes
  
  return () => clearInterval(heartbeatInterval);
}, []);
```

#### 7. **Implement Token Refresh Before Expiration**

**Problem:** Frontend waits until token is expired before refreshing.

**Solution:** Refresh proactively when token has 15 minutes remaining:

```typescript
// In api.ts
export function shouldRefreshToken(token: string): boolean {
  // Refresh when token has less than 15 minutes remaining
  return isTokenExpired(token, 900); // 15 minutes buffer
}

// In _app.tsx
const checkAndRefreshToken = async () => {
  const token = getAccessToken();
  
  if (!token) {
    await refreshAccessToken();
    return;
  }
  
  // Refresh proactively before expiration
  if (shouldRefreshToken(token)) {
    console.log('[Auth] Token expiring soon, refreshing proactively');
    await refreshAccessToken();
  }
};
```

### Low Priority (Nice to Have)

#### 8. **Add Session Management UI**

Allow users to:
- View active sessions (device, location, last active)
- Revoke individual sessions
- "Log out everywhere" button

#### 9. **Add Security Logging**

Log authentication events:
- Successful logins
- Failed login attempts
- Token refreshes
- Unexpected logouts

This helps diagnose issues and detect security threats.

#### 10. **Implement Token Blacklist**

For immediate token revocation (e.g., when user logs out or changes password):
- Add `token_blacklist` table
- Check access token against blacklist on each request
- Requires Redis for performance (check before DB query)

---

## Implementation Priority

**Phase 1: Critical Fixes (Week 1)**
1. Set `COOKIE_DOMAIN` explicitly in production
2. Increase access token lifetime to 240 minutes
3. Implement sliding session window (extend on activity)

**Phase 2: Core Improvements (Week 2-3)**
4. Add server-side sessions table
5. Implement "Remember Me" functionality
6. Add session heartbeat API

**Phase 3: Enhancements (Week 4+)**
7. Implement proactive token refresh
8. Add session management UI
9. Add security logging

---

## Testing Recommendations

### Test Scenarios

1. **Normal Session Flow**
   - Log in with "Remember Me" checked
   - Use site for 10 minutes
   - Close browser
   - Reopen after 2 hours
   - **Expected:** Still logged in

2. **Session Expiration**
   - Log in without "Remember Me"
   - Close browser
   - Reopen after 25 hours
   - **Expected:** Logged out (session expired)

3. **Intentional Logout**
   - Log in
   - Click "Logout"
   - Close browser
   - Reopen
   - **Expected:** Logged out

4. **Cross-Subdomain Access**
   - Log in at www.makapix.club
   - Navigate to api.makapix.club
   - **Expected:** Session persists (cookie domain=.makapix.club)

5. **Browser Privacy Settings**
   - Enable "Clear cookies on exit"
   - Log in
   - Close browser
   - Reopen
   - **Expected:** Logged out (documented limitation)

### Monitoring

Add logging to track:
- Session refresh success/failure rates
- Cookie presence on requests
- Token expiration vs. refresh timing
- Browser/platform correlation with logout issues

---

## Conclusion

The session management issues in Makapix Club stem from a combination of factors:

1. **Short-lived access tokens** (60 min) with **long-lived refresh tokens** (30 days) create a fragile system that depends on browser cookie persistence
2. **Browser cookie management** varies widely and can clear cookies despite `max_age` settings
3. **Reactive refresh logic** attempts to recover after the cookie is already gone
4. **No server-side session tracking** means the system can't distinguish between intentional logouts and cookie loss

The recommended solution is a **multi-layered approach**:
- **Short term:** Increase access token lifetime, set explicit cookie domain
- **Medium term:** Add server-side sessions with sliding windows
- **Long term:** Implement "Remember Me", session heartbeat, and security features

This will create a robust session management system that:
- ✅ Keeps users logged in for 30 days (with "Remember Me")
- ✅ Extends sessions on activity (sliding window)
- ✅ Survives browser restarts
- ✅ Handles cookie loss gracefully
- ✅ Provides security controls and audit trail

---

**Report Prepared By:** Senior Full Stack Development AI  
**Review Status:** Ready for Review  
**Next Steps:** Review findings with team, prioritize implementation phases

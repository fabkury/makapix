# Session Flow Diagrams

## Current Architecture (Problematic)

```
┌─────────────────────────────────────────────────────────────┐
│                        USER LOGIN                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Backend: POST /api/auth/login                              │
│  - Validates credentials                                     │
│  - Creates access token (JWT, 1 hour exp)                   │
│  - Creates refresh token (random, 30 days exp)              │
│  - Stores refresh token hash in database                    │
│                                                              │
│  Returns JSON:                                               │
│  {                                                           │
│    "token": "eyJhbGc...",                                   │
│    "refresh_token": "random_string_abc123",                 │
│    "user_id": 42,                                           │
│    "expires_at": "2025-01-08T14:00:00Z"                     │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Frontend: Receives tokens in JSON response                 │
│                                                              │
│  localStorage.setItem("access_token", token)                │
│  localStorage.setItem("refresh_token", refresh_token) ⚠️   │
│  localStorage.setItem("user_id", user_id)                   │
│                                                              │
│  Problem: All tokens stored in localStorage                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   USER CLOSES BROWSER                        │
│                   (Completely closed)                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│          HOURS PASS... (e.g., overnight)                    │
│                                                              │
│  Mobile browsers (especially iOS Safari):                    │
│  - Clear localStorage on browser close                      │
│  - Free up memory                                           │
│  - Privacy protection kicks in                              │
│                                                              │
│  Result: localStorage is EMPTY ❌                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              USER REOPENS BROWSER                            │
│              Navigates to Makapix                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Frontend: _app.tsx useEffect runs                          │
│                                                              │
│  checkAndRefreshToken('mount')                              │
│    ├─ getAccessToken() → null (localStorage empty)         │
│    ├─ getRefreshToken() → null (localStorage empty)        │
│    └─ No tokens to refresh! ❌                              │
│                                                              │
│  Result: User appears LOGGED OUT                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Proposed Architecture (Solution)

```
┌─────────────────────────────────────────────────────────────┐
│                        USER LOGIN                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Backend: POST /api/auth/login                              │
│  - Validates credentials                                     │
│  - Creates access token (JWT, 4 hours exp)                  │
│  - Creates refresh token (random, 30 days exp)              │
│  - Stores refresh token hash in database                    │
│                                                              │
│  Sets HttpOnly Cookie:                                       │
│  Set-Cookie: refresh_token=random_string_abc123;            │
│              HttpOnly; Secure; SameSite=Lax;                │
│              Max-Age=2592000; Path=/                         │
│                                                              │
│  Returns JSON (NO refresh_token):                           │
│  {                                                           │
│    "token": "eyJhbGc...",                                   │
│    "user_id": 42,                                           │
│    "expires_at": "2025-01-08T18:00:00Z"                     │
│  }                                                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Frontend: Receives tokens                                  │
│                                                              │
│  localStorage.setItem("access_token", token) ✅             │
│  localStorage.setItem("user_id", user_id) ✅                │
│                                                              │
│  Refresh token stored in HttpOnly Cookie ✅                 │
│  (JavaScript cannot access it)                              │
│                                                              │
│  Benefit: Even if localStorage is cleared,                  │
│           the cookie persists!                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   USER CLOSES BROWSER                        │
│                   (Completely closed)                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│          HOURS PASS... (e.g., overnight)                    │
│                                                              │
│  Mobile browsers may:                                        │
│  - Clear localStorage ❌ (access token lost)                │
│  - BUT keep HttpOnly cookies ✅                             │
│                                                              │
│  Result:                                                     │
│  - localStorage: EMPTY                                      │
│  - Cookies: refresh_token STILL PRESENT ✅                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              USER REOPENS BROWSER                            │
│              Navigates to Makapix                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Frontend: _app.tsx useEffect runs                          │
│                                                              │
│  checkAndRefreshToken('mount')                              │
│    ├─ getAccessToken() → null (localStorage cleared)       │
│    ├─ Cookie refresh_token → PRESENT ✅                     │
│    └─ Automatically calls /api/auth/refresh                 │
│                                                              │
│  Backend receives cookie, validates, issues new tokens      │
│  Frontend receives new access token                         │
│  User stays LOGGED IN ✅                                    │
│                                                              │
│  Result: Seamless session restoration                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Token Refresh Flow (Current vs Proposed)

### Current (Problematic)
```
Browser Reopens
     │
     ├─ Check localStorage
     │   ├─ access_token: null ❌
     │   └─ refresh_token: null ❌
     │
     └─ Can't refresh → USER LOGGED OUT
```

### Proposed (Fixed)
```
Browser Reopens
     │
     ├─ Check localStorage
     │   └─ access_token: null (cleared)
     │
     ├─ Check cookies (automatic with credentials: "include")
     │   └─ refresh_token: present ✅
     │
     ├─ POST /api/auth/refresh (with cookie)
     │   ├─ Backend validates cookie
     │   ├─ Issues new access token
     │   └─ Rotates refresh token cookie
     │
     └─ Frontend receives new tokens → USER STAYS LOGGED IN ✅
```

---

## Security Comparison

### Current (localStorage)
```
┌──────────────────────────────────────────────┐
│           Browser Memory                     │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │       localStorage                     │ │
│  │                                        │ │
│  │  access_token: "eyJhbGc..."  ⚠️       │ │
│  │  refresh_token: "random_abc"  ⚠️      │ │
│  │                                        │ │
│  │  Accessible to:                        │ │
│  │  ✅ JavaScript (intended)              │ │
│  │  ❌ XSS attacks (security risk!)       │ │
│  │  ❌ Malicious browser extensions       │ │
│  └────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

### Proposed (HttpOnly Cookies)
```
┌──────────────────────────────────────────────┐
│           Browser Memory                     │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │       localStorage                     │ │
│  │                                        │ │
│  │  access_token: "eyJhbGc..." ⚠️         │ │
│  │  (short-lived, 4 hours)                │ │
│  │                                        │ │
│  │  Accessible to JavaScript ✅           │ │
│  │  (but expires quickly)                 │ │
│  └────────────────────────────────────────┘ │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │       HTTP Cookies                     │ │
│  │                                        │ │
│  │  refresh_token: "random_abc"           │ │
│  │  - HttpOnly ✅ (JS can't access)       │ │
│  │  - Secure ✅ (HTTPS only)              │ │
│  │  - SameSite=Lax ✅ (CSRF protection)   │ │
│  │  - 30 days validity                    │ │
│  │                                        │ │
│  │  NOT accessible to:                    │ │
│  │  ❌ JavaScript                          │ │
│  │  ❌ XSS attacks                         │ │
│  │  ❌ Malicious extensions                │ │
│  └────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

---

## Browser Behavior Comparison

### iOS Safari (Most Affected)

#### Current State
```
Day 1: User logs in
       ├─ localStorage: [access_token, refresh_token]
       └─ Status: Logged In ✅

Day 1: User closes Safari
       └─ Safari keeps localStorage (temporarily)

Day 2-7: Browsing happens
       └─ localStorage still present

Day 8: Safari cleanup runs
       ├─ localStorage: CLEARED ❌
       └─ Next visit: User LOGGED OUT ❌
```

#### With Cookie Fix
```
Day 1: User logs in
       ├─ localStorage: [access_token]
       ├─ Cookie: [refresh_token]
       └─ Status: Logged In ✅

Day 1: User closes Safari
       ├─ localStorage: may be cleared
       └─ Cookie: PERSISTS ✅

Day 2-30: User returns
       ├─ localStorage: might be empty
       ├─ Cookie: STILL VALID ✅
       ├─ Auto-refresh triggered
       └─ Status: Logged In ✅
```

---

## Implementation Checklist

### Backend Changes
- [ ] Modify `POST /auth/login` to set refresh_token cookie
- [ ] Modify `POST /auth/refresh` to read from cookie
- [ ] Modify `POST /auth/logout` to clear cookie
- [ ] Add cookie configuration (HttpOnly, Secure, SameSite)
- [ ] Update response schemas (remove refresh_token from body)

### Frontend Changes
- [ ] Remove refresh_token from localStorage storage
- [ ] Add `credentials: "include"` to all authenticated requests
- [ ] Update `refreshAccessToken()` to not send refresh_token in body
- [ ] Update login handler to not store refresh_token
- [ ] Test cross-origin cookie handling

### Testing
- [ ] Test login flow with cookies
- [ ] Test token refresh with cookies
- [ ] Test browser close/reopen
- [ ] Test iOS Safari specifically
- [ ] Test private/incognito mode
- [ ] Test cross-tab synchronization
- [ ] Security audit (XSS, CSRF)

### Deployment
- [ ] Deploy backend with backward compatibility
- [ ] Deploy frontend
- [ ] Monitor token refresh success rates
- [ ] Monitor session durations
- [ ] Remove backward compatibility after 30 days

---

## Success Metrics

### Before Fix
- Session duration: ~4 hours average
- Login frequency: High (multiple times per day)
- Token refresh success: ~60% (fails when localStorage cleared)
- User complaints: Frequent

### After Fix (Expected)
- Session duration: Days to weeks
- Login frequency: Low (once per month or less)
- Token refresh success: >99%
- User complaints: Minimal to none

---

## References

- Full investigation: `SESSION_ISSUES_INVESTIGATION.md`
- Quick summary: `SESSION_ISSUES_SUMMARY.md`
- Code locations:
  - Frontend: `web/src/lib/api.ts`, `web/src/pages/_app.tsx`
  - Backend: `api/app/auth.py`, `api/app/routers/auth.py`

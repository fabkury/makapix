# Authentication & Authorization Security Audit

## Overview

Makapix Club uses a JWT-based authentication system with refresh tokens stored in HttpOnly cookies. OAuth is supported via GitHub for user authentication.

---

## Positive Security Controls ✅

### 1. JWT Implementation
**Status:** ✅ Good

```python
# api/app/auth.py
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY environment variable is required...")
if len(JWT_SECRET_KEY) < 32:
    raise RuntimeError("JWT_SECRET_KEY is too short...")
```

**Findings:**
- Secret key is required at startup (not optional)
- Minimum length of 32 characters enforced
- Algorithm is configurable (defaults to HS256)

### 2. Password Hashing
**Status:** ✅ Good

```python
# api/app/services/auth_identities.py
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
```

**Findings:**
- Using bcrypt with passlib (industry standard)
- Automatic handling of deprecated hash upgrades
- No plaintext password storage

### 3. Refresh Token Security
**Status:** ✅ Good

**Findings:**
- Refresh tokens stored as SHA256 hashes in database
- HttpOnly cookies prevent JavaScript access
- SameSite=Lax provides CSRF protection
- Secure flag set for HTTPS connections
- Token rotation with 60-second grace period

### 4. OAuth State Validation
**Status:** ✅ Good

```python
# api/app/routers/auth.py
state_nonce = secrets.token_urlsafe(24)
# ...state stored in cookie, validated on callback
if not expected_nonce or not received_nonce or expected_nonce != received_nonce:
    raise HTTPException(...)
```

**Findings:**
- OAuth state parameter used for CSRF protection
- Nonce stored in secure cookie
- State validation occurs before any GitHub API calls

### 5. User Authentication Checks
**Status:** ✅ Good

```python
# api/app/auth.py
def check_user_can_authenticate(user):
    if user.deactivated:
        raise HTTPException(...)
    if user.banned_until and user.banned_until > datetime.now(timezone.utc):
        raise HTTPException(...)
```

**Findings:**
- Deactivated and banned users are blocked
- Check is performed during login, refresh, and authenticated requests

---

## Issues Identified

### [H1] JWT Secret Key Entropy Validation
**Severity:** 🟠 HIGH

**Location:** `api/app/auth.py:28-36`

**Issue:** The current validation only checks string length, not entropy. A secret like `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` (32 'a' characters) would pass validation but has very low entropy.

**Current Code:**
```python
if len(JWT_SECRET_KEY) < 32:
    raise RuntimeError("JWT_SECRET_KEY is too short...")
```

**Recommendation:** Add a warning in documentation or consider validating that the key appears to be base64-encoded or contains sufficient character variety. At minimum, log a warning if the key looks suspicious.

**Production Mitigation:** Ensure production deployment uses a cryptographically secure key generated via:
```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

---

### [M3] Password Reset Rate Limiting
**Severity:** 🟡 MEDIUM

**Location:** `api/app/routers/auth.py:753-801`

**Issue:** Password reset rate limiting is tracked at the user level but could benefit from per-email tracking to prevent enumeration attacks.

**Current Code:**
```python
def forgot_password(...):
    # No rate limiting by IP or email address
    # Rate limit check is only in send_reset_email_for_user
```

**Recommendation:** Add rate limiting by IP address for the forgot-password endpoint itself:
```python
client_ip = get_client_ip(request)
rate_limit_key = f"ratelimit:forgot_password:{client_ip}"
allowed, remaining = check_rate_limit(rate_limit_key, limit=10, window_seconds=3600)
```

---

### [L3] Account Lockout Mechanism
**Severity:** 🟢 LOW

**Location:** `api/app/routers/auth.py:319-406`

**Issue:** While rate limiting exists for login attempts per IP, there's no per-account lockout mechanism. An attacker rotating IPs could attempt unlimited password guesses.

**Current Protection:**
```python
rate_limit_key = f"ratelimit:login:{client_ip}"
allowed, remaining = check_rate_limit(rate_limit_key, limit=10, window_seconds=300)
```

**Recommendation:** Consider implementing per-account temporary lockout after N failed attempts:
- Track failed attempts per email/user
- Implement exponential backoff
- Send notification email on suspicious activity

---

## Role-Based Access Control

### Role Hierarchy
**Status:** ✅ Good

```
owner > moderator > user
```

**Findings:**
- Owner role is protected from demotion
- Moderators cannot modify other moderators
- Proper authorization checks in admin endpoints

### Authorization Patterns Used
**Status:** ✅ Good

```python
def require_moderator(user: models.User = Depends(get_current_user)) -> models.User:
    if "moderator" not in user.roles and "owner" not in user.roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, ...)
    return user

def require_ownership(resource_owner_id: int, current_user: models.User) -> None:
    if not check_ownership(resource_owner_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, ...)
```

---

## Session Management

### Cookie Configuration
**Status:** ✅ Good

```python
cookie_config = {
    "httponly": True,           # ✅ Prevents XSS token theft
    "secure": secure,            # ✅ HTTPS only in production
    "samesite": "lax",          # ✅ CSRF protection
    "path": "/",
    "max_age": 30 * 24 * 60 * 60,  # 30 days
}
```

### Token Rotation
**Status:** ✅ Good

The refresh token rotation with grace period handles common issues:
- Race conditions from multiple tabs
- Network failures during refresh
- Browser closing before response processed

---

## Recommendations Summary

| Priority | Action |
|----------|--------|
| Pre-Launch | Verify production JWT_SECRET_KEY is securely generated |
| Pre-Launch | Review CORS_ORIGINS is properly configured for production domain |
| Post-Launch | Implement per-account lockout mechanism |
| Post-Launch | Add security event monitoring for failed auth attempts |
| Post-Launch | Consider adding multi-factor authentication option |

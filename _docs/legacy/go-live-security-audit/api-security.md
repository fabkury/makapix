# API Security Audit

## Overview

The Makapix Club API is built with FastAPI and implements various security controls including input validation, rate limiting, and comprehensive security headers.

---

## Positive Security Controls ✅

### 1. Security Headers Middleware
**Status:** ✅ Good

**Location:** `api/app/middleware.py`

```python
response.headers["X-Content-Type-Options"] = "nosniff"
response.headers["X-Frame-Options"] = "DENY"
response.headers["X-XSS-Protection"] = "1; mode=block"
response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()..."
response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
response.headers["Content-Security-Policy"] = "..."
```

**Findings:**
- Complete OWASP recommended security headers
- HSTS with preload for permanent HTTPS enforcement
- Restrictive CSP suitable for API endpoints
- Feature policy disables unnecessary browser features

### 2. SQL Injection Prevention
**Status:** ✅ Good

**Findings:**
- All database queries use SQLAlchemy ORM
- Parameterized queries throughout
- No raw SQL string concatenation found

Example:
```python
# Safe ORM query pattern used everywhere
user = db.query(models.User).filter(models.User.handle.ilike(search_term)).first()
```

### 3. Input Validation
**Status:** ✅ Good

**Findings:**
- Pydantic schemas for all request/response models
- Regex validation for enumerated parameters
- Boundary validation for numeric inputs
- Length limits on text fields

Examples:
```python
# Query parameter validation
sort: str = Query("alphabetical", regex="^(alphabetical|recent|reputation)$")
limit: int = Query(50, ge=1, le=200)

# Schema validation
title: str = Form(..., min_length=1, max_length=200)
description: str | None = Form(None, max_length=5000)
```

### 4. Path Traversal Protection
**Status:** ✅ Good

**Location:** `api/app/validation.py`

```python
def is_safe_path(base_path: Path, target_path: str) -> bool:
    try:
        base = base_path.resolve()
        target = (base_path / target_path).resolve()
        return target.is_relative_to(base)
    except (ValueError, OSError):
        return False
```

**Findings:**
- ZIP file extraction validates all paths
- Symbolic link extraction is blocked
- Absolute paths are rejected
- Parent directory references (..) are rejected

### 5. File Upload Validation
**Status:** ✅ Good

**Location:** `api/app/vault.py`, `api/app/amp/amp_inspector.py`

**Findings:**
- File size limits enforced (configurable via MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES)
- Image dimensions validated (max 256x256)
- MIME type validation
- Custom AMP inspector for deep image validation
- SHA256 hash used for deduplication

---

## Issues Identified

### [H2] Rate Limiting Fails Open
**Severity:** 🟠 HIGH

**Location:** `api/app/services/rate_limit.py:26-34`

**Issue:** When Redis is unavailable, rate limiting allows all requests through ("fails open"). This could allow brute force attacks if Redis goes down.

**Current Code:**
```python
def check_rate_limit(key: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
    client = get_redis_client()
    
    # If Redis is unavailable, allow the request (fail open)
    if not client:
        logger.warning(f"Redis unavailable, allowing request for key '{key}'")
        return True, limit
```

**Risk:** An attacker could potentially cause Redis connection issues to bypass rate limiting.

**Recommendation:**
1. Ensure Redis has high availability (replication, sentinel, or cluster)
2. Add monitoring/alerting when Redis is unavailable
3. Consider a secondary in-memory rate limit for critical endpoints during Redis outages
4. At minimum, add metrics to track when rate limiting fails open

---

### [M1] CORS Configuration Example Uses Wildcard
**Severity:** 🟡 MEDIUM

**Location:** `.env.example:53`

**Issue:** The example configuration shows development origins but the comment mentions "*" as an option. Production must have explicitly configured origins.

**Current Configuration:**
```env
# Comma-separated list of allowed origins. Use "*" only for development (insecure for production)
CORS_ORIGINS=http://localhost:3000,http://localhost
```

**Verification Required:** Confirm production .env has specific domain origins like:
```env
CORS_ORIGINS=https://makapix.club,https://makapix.club
```

---

### [M4] Player Credentials Endpoint Lacks Rate Limiting
**Severity:** 🟡 MEDIUM

**Location:** `api/app/routers/player.py:266-316`

**Issue:** The `/player/{player_key}/credentials` endpoint retrieves TLS certificates without rate limiting. While the player_key UUID provides some obscurity, the endpoint could be brute-forced.

**Current Code:**
```python
@router.get("/player/{player_key}/credentials", response_model=schemas.TLSCertBundle)
def get_player_credentials(player_key: UUID, db: Session = Depends(get_db)):
    # No rate limiting
```

**Recommendation:** Add rate limiting by IP:
```python
client_ip = get_client_ip(request)
rate_limit_key = f"ratelimit:player_creds:{client_ip}"
allowed, _ = check_rate_limit(rate_limit_key, limit=10, window_seconds=60)
```

---

### [M5] Comment Deletion by IP Address
**Severity:** 🟡 MEDIUM

**Location:** `api/app/routers/comments.py:231-274`

**Issue:** Anonymous comments can be deleted by matching IP address. This causes issues for users behind NAT where multiple users share the same IP.

**Current Code:**
```python
# Anonymous user: check by IP
if comment.author_ip != current_user.ip:
    raise HTTPException(...)
```

**Considerations:**
- Corporate networks may have hundreds of users sharing one IP
- Mobile users may have changing IPs
- One malicious user could delete other anonymous comments

**Recommendation:** Consider adding a time-limited deletion window or session-based tracking for anonymous comments.

---

### [L1] Request Correlation IDs
**Severity:** 🟢 LOW

**Issue:** No request correlation IDs are generated, making it difficult to trace requests through logs.

**Recommendation:** Add middleware to generate and propagate request IDs:
```python
class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
```

---

### [L4] Disabled Blog Posts Feature
**Severity:** 🟢 LOW

**Location:** `api/app/routers/users.py:547-605`

**Issue:** Blog posts feature is disabled via HTTP 503 responses but the code remains. This increases attack surface.

**Current Code:**
```python
def get_user_recent_blog_posts(...):
    # FEATURE POSTPONED - Remove this block to reactivate blog posts
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Blog posts are deferred to a later time"
    )
```

**Recommendation:** Consider removing unused routes entirely or document when they will be enabled.

---

## API Endpoint Security Summary

### Authentication Required Endpoints
| Endpoint | Auth | Rate Limited | Notes |
|----------|------|--------------|-------|
| POST /post | ✅ | ✅ | Artwork upload |
| PATCH /post/{id} | ✅ | - | Owner only |
| DELETE /post/{id} | ✅ | - | Owner only |
| POST /user/{id}/avatar | ✅ | - | Owner only |
| POST /player/register | ✅ | ✅ | User registration |
| GET /search | ✅ | - | Requires auth for results |

### Public Endpoints (No Auth Required)
| Endpoint | Auth | Rate Limited | Notes |
|----------|------|--------------|-------|
| GET /post/recent | ❌ | Cache | Cached response |
| GET /hashtags | ❌ | Cache | Cached response |
| POST /player/provision | ❌ | - | Device provision |

### Admin Endpoints
| Endpoint | Auth | Role | Notes |
|----------|------|------|-------|
| POST /admin/user/{id}/ban | ✅ | Moderator | Audit logged |
| POST /admin/user/{id}/moderator | ✅ | Owner | Audit logged |
| GET /admin/audit-log | ✅ | Moderator | - |

---

## Recommendations Summary

| Priority | Action |
|----------|--------|
| Pre-Launch | Ensure CORS_ORIGINS is properly configured |
| Pre-Launch | Verify Redis high availability for rate limiting |
| Post-Launch | Add rate limiting to player credentials endpoint |
| Post-Launch | Implement request correlation IDs |
| Post-Launch | Consider session-based anonymous comment tracking |

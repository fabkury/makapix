# Makapix Club Codebase Sanity Check Report

**Date**: December 2024  
**Repository**: fabkury/makapix  
**Web (Live Preview)**: https://dev.makapix.club/

---

> **⚠️ FEATURE POSTPONED: Blog Posts**
> 
> As of December 2025, blog post functionality has been postponed to an indeterminate future date.
> References to blog post issues in this report are preserved for historical context but are not
> currently active concerns. When blog posts are reactivated, these issues should be revisited.

---

## Executive Summary

This report details the findings from a comprehensive sanity check of the Makapix Club codebase. The analysis covers the Python/FastAPI backend (API), the Next.js frontend (web), and the Celery worker infrastructure.

Overall, the codebase is well-structured with clear separation of concerns. However, several areas of technical debt and inconsistencies have been identified that warrant attention.

---

## 1. Code Duplication

### 1.1 Statistics Services - Nearly Identical Files

**Severity**: High  
**Files Affected**:
- `api/app/services/stats.py` (481 lines)
- `api/app/services/blog_post_stats_service.py` (478 lines)

**Issue**: These two files are nearly identical, differing only in:
- Class names (`PostStatsService` vs `BlogPostStatsService`)
- Model references (`Post` vs `BlogPost`, `ViewEvent` vs `BlogPostViewEvent`)
- Field names (`post_id` vs `blog_post_id`)

**Impact**: 
- ~960 lines of duplicated logic
- Maintenance burden - any fix or improvement must be made in both files
- Risk of divergence as one file gets updated but not the other

**Recommendation**: Extract common logic into a generic base class or shared utility module. Use generics/type parameters to handle the differences.

### 1.2 DailyViewCount Dataclass Duplication

**Severity**: Medium  
**Files Affected**:
- `api/app/services/stats.py` (line 30)
- `api/app/services/blog_post_stats_service.py` (line 29)
- `api/app/schemas.py`

**Issue**: The `DailyViewCount` dataclass is defined identically in multiple files.

**Recommendation**: Define once in `schemas.py` and import where needed.

### 1.3 PostStats vs BlogPostStats Dataclasses

**Severity**: Medium  
**Issue**: The `PostStats` and `BlogPostStats` dataclasses in their respective service files are nearly identical (50+ fields each), differing only in field naming.

**Recommendation**: Create a generic `ContentStats` base dataclass.

---

## 2. Stubs and Placeholder Implementations

### 2.1 Manifest Validation Endpoint

**Location**: `api/app/routers/relay.py` (lines 354-374)

```python
@router.post("/validation/manifest/check")
async def validate_manifest_endpoint(payload: schemas.ManifestValidateRequest):
    """
    TODO: Fetch manifest.json from URL
    TODO: Validate JSON schema
    TODO: Check that all art URLs are accessible
    TODO: Validate canvas dimensions
    TODO: Calculate summary statistics
    """
    # PLACEHOLDER: Return valid result
    return schemas.ManifestValidationResult(
        valid=True,
        issues=[],
        summary={"art_count": 0, "canvases": [], "avg_kb": 0},
    )
```

**Impact**: Endpoint always returns `valid=True` regardless of input. Any manifest is accepted.

### 2.2 Rate Limit Status Endpoint

**Location**: `api/app/routers/mqtt.py` (lines 60-78)

```python
@router.get("/limits")
def get_rate_limits():
    """
    TODO: Implement Redis-based rate limiter
    TODO: Return actual bucket status
    TODO: Add rate limit headers to response
    """
    # PLACEHOLDER: Return unlimited
    return schemas.RateLimitStatus(
        buckets={
            "commands": {"remaining": 9999, "reset_at": "..."},
            "publishes": {"remaining": 9999, "reset_at": "..."},
        }
    )
```

**Note**: A `rate_limit.py` service exists and IS being used in `auth.py` and `player.py`, so this placeholder could potentially use the existing service.

### 2.3 Badge Definitions

**Location**: `api/app/routers/badges.py` (lines 21-35)

**Issue**: Badge definitions are hardcoded as static values with a TODO to load from database.

---

## 3. Inconsistencies and Potential Bugs

### 3.1 File Size Limit Comment/Code Mismatch

**Severity**: High  
**Location**: `api/app/routers/posts.py` (line 200)

```python
# The comment says "15 MB limit" but the actual value is 5 * 1024 KB = 5 MB
max_file_kb = 5 * 1024  # 15 MB limit  # <-- Incorrect comment!
```

**Issue**: The comment says "15 MB limit" but the calculation `5 * 1024 KB = 5,120 KB = 5 MB`.

**Related Inconsistencies**:
- `api/app/vault.py` line 23: `MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024` (5 MB)
- `api/app/schemas.py` line 68: `max_art_file_kb_default: int = 15 * 1024` (15 MB)
- `api/app/validation.py` line 8: `MAX_FILE_SIZE = 15 * 1024 * 1024` (15 MB)

**Impact**: Different parts of the codebase expect different file size limits:
- Vault enforcement: 5 MB
- Schema config: 15 MB
- Validation utility: 15 MB

**Recommendation**: Consolidate all file size limits into a single configuration source.

### 3.2 Duplicate Site Event Recording

**Severity**: Medium  
**Locations**:
- `api/app/routers/blog_posts.py` lines 245/260 (`get_blog_post_by_sqid`)
- `api/app/routers/blog_posts.py` lines 319/334 (`get_blog_post`)

**Issue**: `record_site_event(request, "page_view", user=user)` is called twice in both endpoints - once after recording the view event, and again right before returning.

**Impact**: Double-counting of page views for blog posts in sitewide statistics.

### 3.3 Inconsistent owner_id Parameter Types

**Severity**: Medium  
**Issue**: The `owner_id` parameter type differs across list endpoints:
- `posts.py` line 63: `owner_id: UUID | None`
- `playlists.py` line 47: `owner_id: UUID | None`
- `blog_posts.py` line 50: `owner_id: int | None`

Given that `User.id` is an `Integer` (not UUID), using `UUID` requires conversion logic. The `posts.py` does handle this conversion (lines 82-92), but this is inconsistent with the more straightforward `int` type used in `blog_posts.py`.

**Recommendation**: Standardize on `int` for `owner_id` (matching the actual database column type) or document the UUID-to-int conversion consistently.

### 3.4 Incomplete TODO Implementations (Not Actually Incomplete)

**Location**: `api/app/routers/posts.py`

Some TODOs in docstrings claim features are not implemented, but the code below actually implements them:

Line 619-620:
```python
    TODO: Validate ownership before allowing update
    TODO: Only moderators can update hidden_by_mod
```

But line 626 calls `require_ownership(post.owner_id, current_user)` which does validate ownership.

**Issue**: Outdated/misleading documentation.

---

## 4. Legacy Code and Unused Patterns

### 4.1 mqtt_legacy.py

**Location**: `api/app/mqtt_legacy.py`

**Issue**: This file appears to be superseded by the `api/app/mqtt/` module, but is kept for backward compatibility via import in `api/app/mqtt/__init__.py`.

**Recommendation**: Evaluate if the legacy import is still needed or can be removed.

### 4.2 Legacy API Functions in Frontend

**Location**: `web/src/lib/api.ts` (lines 276-303)

```typescript
// ============================================================================
// Legacy API functions (kept for backward compatibility)
// ============================================================================
export async function requestJson<TResponse>(...) { ... }
export async function postJson<TResponse>(...) { ... }
```

**Issue**: These legacy functions are exported but primarily used only in `demo.tsx`. The newer authenticated versions (`authenticatedFetch`, `authenticatedRequestJson`, `authenticatedPostJson`) are used throughout the rest of the codebase.

**Recommendation**: Evaluate if the legacy functions can be deprecated or made private.

### 4.3 Demo and Debug Pages

**Files**:
- `web/src/pages/demo.tsx` - MQTT demo page
- `web/src/pages/debug-env.tsx` - Environment variable debugging

**Issue**: These appear to be development/testing pages that should be disabled or removed in production.

**Recommendation**: Remove or gate these pages behind authentication/environment checks in production.

---

## 5. Architecture Observations

### 5.1 Tasks File Size

**Location**: `api/app/tasks.py`

**Issue**: This file is 1724 lines and contains:
- Celery task definitions
- HTML generation code (artwork gallery HTML)
- Database operations
- Multiple periodic tasks

**Recommendation**: Consider splitting into:
- `tasks/hash_check.py` - Hash checking tasks
- `tasks/relay.py` - Relay job processing
- `tasks/rollup.py` - Event rollup tasks
- `tasks/cleanup.py` - Cleanup tasks
- `utils/html_generator.py` - HTML generation

### 5.2 Schema File Size

**Location**: `api/app/schemas.py`

**Observation**: While large, this file follows a logical organization with clear section headers. This is an acceptable pattern for a centralized schema definition.

### 5.3 Consistent Error Handling

**Positive Observation**: The codebase consistently uses:
- FastAPI's HTTPException
- Proper HTTP status codes
- Descriptive error messages

### 5.4 Caching Strategy

**Positive Observation**: The codebase has a well-designed caching layer:
- Redis for cache
- Proper cache invalidation on data changes
- Cache TTLs appropriate for data freshness requirements

---

## 6. Outdated TODOs Summary

The following TODO comments exist throughout the codebase:

| File | Line | TODO |
|------|------|------|
| `routers/admin.py` | Various | Log in audit log, Send notification, Hide content |
| `routers/auth.py` | Various | Extract user_id from state, Include user metadata |
| `routers/badges.py` | Various | Load from database, Validate badge exists, Log audit |
| `routers/legacy.py` | 17 | Remove in production or move to /admin/tasks |
| `routers/mqtt.py` | Various | Load from env vars, Implement rate limiter |
| `routers/playlists.py` | Various | Search query, Cursor pagination, Visibility filters |
| `routers/posts.py` | Various | Queue conformance check, Re-extract hashtags |

**Note**: Some of these TODOs are actually implemented but the comments remain.

---

## 7. Recommendations Priority Matrix

### High Priority (Should Fix Soon)

1. **File size limit inconsistencies** - Could cause user confusion or rejected uploads
2. **Duplicate site event recording** - Corrupts analytics data
3. **Stats service duplication** - Maintenance risk, ~960 duplicated lines

### Medium Priority (Address When Convenient)

4. **Outdated TODO comments** - Misleading documentation
5. **owner_id type inconsistencies** - Confusing API contract
6. **DailyViewCount duplication** - Minor maintenance burden

### Low Priority (Nice to Have)

7. **Manifest validation placeholder** - May not be a used feature
8. **Legacy API function cleanup** - Low impact
9. **Demo/debug page removal** - Security consideration
10. **tasks.py refactoring** - Code organization improvement

---

## 8. Positive Patterns Observed

1. **Consistent Pydantic models** with `model_config = ConfigDict(from_attributes=True)`
2. **Proper async/await usage** where beneficial
3. **Well-organized router modules** with clear prefix/tag assignments
4. **Comprehensive audit logging** for moderation actions
5. **Proper soft-delete patterns** for user-facing content
6. **JWT token refresh mechanism** with proper error handling
7. **MQTT integration** for real-time features
8. **Sqids for user-friendly URLs** while maintaining internal integer IDs

---

## Conclusion

The Makapix Club codebase is fundamentally well-architected with good separation of concerns. The main areas requiring attention are:

1. **Code duplication** in the statistics services
2. **Configuration inconsistencies** in file size limits
3. **Minor bugs** like duplicate event recording
4. **Outdated documentation** in TODO comments

None of these issues appear to be critical or breaking, but addressing them would improve maintainability and reliability of the platform.

# Data Protection Security Audit

## Overview

This document covers data protection aspects including personally identifiable information (PII) handling, data storage security, and privacy considerations.

---

## Positive Security Controls ✅

### 1. Password Storage
**Status:** ✅ Good

**Location:** `api/app/services/auth_identities.py`

```python
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)
```

**Findings:**
- Bcrypt hashing with automatic work factor
- Plaintext passwords never stored
- Salt automatically generated per password

### 2. Token Storage
**Status:** ✅ Good

**Location:** `api/app/auth.py:119-134`

```python
# Generate secure random token
token = secrets.token_urlsafe(32)
# Hash the token for secure database storage
token_hash = hashlib.sha256(token.encode()).hexdigest()
```

**Findings:**
- Refresh tokens hashed before storage
- SHA256 ensures tokens can't be extracted from database
- Only hash comparison, never plaintext retrieval

### 3. Verification Token Hashing
**Status:** ✅ Good

**Location:** `api/app/services/email_verification.py`

```python
token_hash = hashlib.sha256(token.encode()).hexdigest()
verification = EmailVerification(
    email=email.lower(),
    token_hash=token_hash,
    ...
)
```

**Findings:**
- Email verification tokens hashed
- Password reset tokens hashed
- Prevents token extraction from database

### 4. Audit Logging
**Status:** ✅ Good

**Location:** `api/app/utils/audit.py`

```python
def log_moderation_action(
    db: Session,
    actor_id: int,
    action: str,
    target_type: str,
    target_id: int | UUID,
    reason_code: str | None = None,
    note: str | None = None,
) -> None:
```

**Logged Actions:**
- Ban/unban user
- Promote/demote moderator
- Hide/unhide content
- Approve/revoke public visibility
- Permanent deletions

### 5. Soft Delete Implementation
**Status:** ✅ Good

**Location:** `api/app/routers/posts.py:842-878`

```python
# Mark as deleted by user (frees hash for re-upload)
post.deleted_by_user = True
post.deleted_by_user_date = now

# Keep existing visibility flags for backward compatibility
post.visible = False
post.hidden_by_user = True
```

**Findings:**
- Posts soft-deleted, not immediately removed
- 7-day retention before permanent deletion
- Hash freed for re-upload (same artwork can be re-uploaded)

---

## Data Inventory

### Personally Identifiable Information (PII)

| Data Type | Storage Location | Protection |
|-----------|------------------|------------|
| Email addresses | auth_identities table | Lowercase normalized |
| IP addresses | comments.author_ip | Used for guest identification |
| GitHub user IDs | auth_identities.provider_user_id | OAuth link |
| Handles (usernames) | users.handle | Public |
| Passwords | auth_identities.secret_hash | Bcrypt hashed |

### Sensitive Application Data

| Data Type | Storage Location | Protection |
|-----------|------------------|------------|
| JWT secret key | Environment variable | Not stored in DB |
| Refresh tokens | refresh_tokens.token_hash | SHA256 hashed |
| Player certificates | players.cert_pem, key_pem | Stored in DB |
| OAuth state | Cookies | Secure, HttpOnly |

---

## Issues Identified

### [M2] Hidden Posts Accessible via Direct URL
**Severity:** 🟡 MEDIUM

**Issue:** Posts hidden by users or moderators can still be accessed if someone has the direct URL (storage_key or public_sqid).

**Current Behavior:**
- Hidden posts excluded from feeds and search
- Direct URL access still possible (relies on URL obscurity)
- Vault files served without authentication

**Risk Assessment:**
- Users may expect "hidden" means completely inaccessible
- Previously shared URLs continue working
- Deleted posts remain accessible until permanent deletion

**Recommendation:**
1. Document this behavior to users
2. Consider adding visibility checks to direct vault access
3. Implement immediate vault file deletion for user-deleted posts

---

### IP Address Storage
**Severity:** 🟢 LOW (Documentation)

**Location:** `api/app/routers/comments.py:163-170`

```python
comment = models.Comment(
    post_id=id,
    author_id=current_user.id if isinstance(current_user, models.User) else None,
    author_ip=current_user.ip if isinstance(current_user, AnonymousUser) else None,
    ...
)
```

**Considerations:**
- IP addresses stored for anonymous comment ownership
- GDPR may require data retention policy
- IP addresses are PII in EU jurisdictions

**Recommendations:**
1. Add data retention policy for anonymous comment IPs
2. Consider hashing IPs instead of storing plaintext
3. Document IP storage in privacy policy

---

### Player Certificate Storage
**Severity:** 🟢 LOW

**Location:** `api/app/models.py` (Player model)

**Current State:**
- TLS certificates stored in database
- Private keys stored in database
- Used for mTLS authentication

**Recommendations:**
1. Ensure database encryption at rest
2. Consider encrypting cert_pem and key_pem columns
3. Implement secure backup procedures

---

## Data Flow Security

### Authentication Flow
```
User Input -> [HTTPS] -> API -> [Bcrypt] -> Database
```
✅ Encrypted in transit and at rest

### OAuth Flow
```
Browser -> GitHub -> [State Validation] -> API -> Database
```
✅ State parameter prevents CSRF

### File Upload Flow
```
User -> [HTTPS] -> API -> [Validation] -> Vault Storage
```
✅ Multiple validation layers

### MQTT Device Flow
```
Device -> [mTLS] -> MQTT Broker -> [Internal] -> API
```
✅ Client certificate authentication

---

## Privacy Compliance Considerations

### GDPR Compliance Checklist

| Requirement | Status | Notes |
|-------------|--------|-------|
| Lawful basis | 🟡 | Document in privacy policy |
| Right to access | ✅ | User can view their data |
| Right to rectification | ✅ | User can update profile |
| Right to erasure | 🟡 | Soft delete, not immediate |
| Data portability | 🟡 | No export feature yet |
| Processing records | ✅ | Audit logs maintained |

### Recommendations for GDPR

1. **Privacy Policy:** Document data collection and processing
2. **Data Export:** Consider adding user data export feature
3. **Retention Policy:** Define and document data retention periods
4. **Cookie Consent:** Ensure cookie consent for non-essential cookies

---

## Email Security

### Email Handling
**Status:** ✅ Good

**Location:** `api/app/services/email.py`

**Findings:**
- Uses Resend service (reputable provider)
- No email content stored in database
- Verification/reset tokens are hashed

### Email Content Security

| Email Type | Contains PII | Time Sensitivity |
|------------|--------------|------------------|
| Verification | Handle, link | 24 hours |
| Password Reset | Handle, link | 1 hour |
| Download Ready | Handle, link | Configured expiry |

---

## Recommendations Summary

| Priority | Action |
|----------|--------|
| Pre-Launch | Review privacy policy coverage |
| Pre-Launch | Document hidden/deleted post behavior |
| Post-Launch | Implement IP address data retention policy |
| Post-Launch | Consider database encryption at rest |
| Post-Launch | Add user data export feature |
| Post-Launch | Consider encrypting stored certificates |

# Password Requirements and Rate Limiting Update

**Date:** December 5, 2025  
**Commit:** a7b5e94  
**Status:** ✅ Complete

## Summary

Updated password requirements and enabled rate limiting based on user feedback.

---

## Password Requirements Changed

### Before (Too Strict)
- Minimum 12 characters
- Required: uppercase, lowercase, digit, AND special character
- All 4 character types mandatory

### After (More Flexible)
- **Minimum 8 characters**
- **At least one letter** (uppercase OR lowercase)
- **At least one number**
- **Special characters allowed but NOT required**

---

## Backend Changes

### 1. Password Validation Function (`api/app/routers/auth.py`)

```python
def validate_password(password: str) -> tuple[bool, str | None]:
    """
    Validate password meets minimum requirements.
    
    Requirements:
    - At least 8 characters long
    - At least one letter (uppercase or lowercase)
    - At least one number
    - Special characters are allowed but not required
    """
```

**Applied to:**
- `change_password()` endpoint
- `reset_password()` endpoint

### 2. Password Generation Updated

```python
def generate_random_password(length: int = 12) -> str:
    """
    Generate a random password with letters and digits.
    
    Minimum length of 8 characters.
    May include special characters for additional security.
    """
```

**Changes:**
- Minimum reduced from 12 to 8 characters
- Ensures at least one letter and one digit (minimum requirements)
- Special characters included but not mandatory

### 3. Rate Limiting Enabled

**Registration Endpoint** (`/auth/register`):
```python
# Rate limiting: 3 registrations per hour per IP
rate_limit_key = f"ratelimit:register:{client_ip}"
allowed, remaining = check_rate_limit(rate_limit_key, limit=3, window_seconds=3600)
```

**Login Endpoint** (`/auth/login`):
```python
# Rate limiting: 5 login attempts per 5 minutes per IP
rate_limit_key = f"ratelimit:login:{client_ip}"
allowed, remaining = check_rate_limit(rate_limit_key, limit=5, window_seconds=300)
```

**Error Response:**
- Status Code: `429 Too Many Requests`
- Message: "Too many [login/registration] attempts. Please try again later."

---

## Frontend Changes

### 1. Password Validation Utility (`web/src/utils/passwordValidation.ts`)

New shared utility for consistent password validation:

```typescript
export function validatePassword(password: string): PasswordValidationResult {
  // Returns { isValid: boolean, errors: string[] }
  // Checks: length >= 8, has letter, has number
}
```

**Features:**
- Reusable across all password forms
- Returns detailed error messages
- Includes password strength indicator

### 2. Reset Password Page Updated (`web/src/pages/reset-password.tsx`)

**Changes:**
- Import and use `validatePassword()` utility
- Show validation errors before submission
- Updated description text to match new requirements

**User Experience:**
- Immediate validation feedback
- Clear error messages
- Consistent with backend validation

---

## Testing

### Backend Validation
```bash
# Valid passwords (will pass)
"abc12345"        # 8 chars, has letters and numbers
"Test1234"        # Mixed case, has numbers
"password99"      # Letters and numbers
"MyPass2024!"     # With special char (optional)

# Invalid passwords (will fail)
"abc123"          # Too short (< 8 chars)
"abcdefgh"        # No numbers
"12345678"        # No letters
```

### Frontend Validation
- Same rules as backend
- Errors shown in real-time
- Prevents unnecessary API calls

### Rate Limiting
```bash
# Test registration rate limit
curl -X POST /api/auth/register -d '{"email":"test1@example.com"}' # OK
curl -X POST /api/auth/register -d '{"email":"test2@example.com"}' # OK  
curl -X POST /api/auth/register -d '{"email":"test3@example.com"}' # OK
curl -X POST /api/auth/register -d '{"email":"test4@example.com"}' # 429 Too Many Requests

# Test login rate limit (5 attempts per 5 minutes)
for i in {1..6}; do
  curl -X POST /api/auth/login -d '{"email":"test@example.com","password":"wrong"}'
done
# 6th attempt returns 429
```

---

## Security Benefits

### Password Requirements
- ✅ Balances security with usability
- ✅ Prevents weak passwords (too short, no variety)
- ✅ Allows users flexibility (no forced special chars)
- ✅ Consistent validation (frontend + backend)

### Rate Limiting
- ✅ Prevents brute force attacks on login
- ✅ Prevents registration spam/abuse
- ✅ Per-IP tracking catches automated attacks
- ✅ Fail-open design (allows requests if Redis down)

---

## Migration Notes

### Existing Users
- **No action required** - existing passwords unchanged
- Users can change password anytime (new rules apply)
- Auto-generated passwords meet new requirements

### New Users
- Registration generates 8+ char password with letters and numbers
- Verification email includes generated password
- Can change password after email verification

---

## Configuration

### Environment Variables (No changes required)
```bash
# Redis for rate limiting (already configured)
REDIS_URL=redis://cache:6379/0
```

### Rate Limit Tuning
To adjust rate limits, modify in `api/app/routers/auth.py`:

```python
# Registration
check_rate_limit(rate_limit_key, limit=3, window_seconds=3600)
#                                    ↑              ↑
#                                  count         period

# Login
check_rate_limit(rate_limit_key, limit=5, window_seconds=300)
#                                    ↑              ↑
#                                  count         period
```

---

## Monitoring

### Rate Limit Metrics
Monitor Redis keys for abuse patterns:
```bash
# Check registration attempts from IP
redis-cli GET "ratelimit:register:192.168.1.100"

# Check login attempts from IP
redis-cli GET "ratelimit:login:192.168.1.100"
```

### Logs
Rate limit events logged:
```
WARNING: Redis unavailable, allowing request for key 'ratelimit:login:...'
```

---

## User Feedback Addressed

✅ **"Password rules are too strict"**
- Reduced from 12 to 8 characters
- Special characters now optional

✅ **"Need frontend validation"**
- Created shared validation utility
- Applied to reset-password page
- Can be added to other forms as needed

✅ **"Enable rate limiting"**
- Registration: 3 per hour per IP
- Login: 5 per 5 minutes per IP
- Redis-based implementation

---

## Next Steps (Optional Enhancements)

### 1. Add Validation to More Forms
- Change password form (user settings)
- Any custom password input forms

### 2. Rate Limit Other Endpoints
- Password reset requests
- Email verification resends
- API endpoints (posts, comments, etc.)

### 3. Enhanced Monitoring
- Dashboard for rate limit metrics
- Alerts for suspicious patterns
- IP blocklist for repeat offenders

### 4. User Experience
- Real-time password strength indicator
- Visual feedback (green checkmarks for requirements)
- Progressive disclosure of requirements

---

## Documentation Updates

Updated files:
- ✅ `SECURITY_FIXES_SUMMARY.md` - Added password and rate limiting updates
- ✅ `SECURITY_README.md` - Updated completion status
- ✅ This document (`PASSWORD_RATE_LIMIT_UPDATE.md`) - Detailed changes

---

**Questions or Issues?**
Contact: security@makapix.club

**Related Documents:**
- [SECURITY_AUDIT.md](SECURITY_AUDIT.md) - Full security audit
- [SECURITY_SETUP_GUIDE.md](SECURITY_SETUP_GUIDE.md) - Production setup
- [SECURITY_README.md](SECURITY_README.md) - Quick reference

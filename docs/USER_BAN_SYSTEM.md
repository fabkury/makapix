# User Ban System Documentation

## Overview

This document explains how the user ban system works in Makapix Club, including the backend implementation, data retention policies, and the timeline for user data removal.

## How the Ban System Works

### Ban Action Implementation

When a moderator bans a user, the following occurs:

1. **Database Field Update**
   - The `banned_until` field on the `User` model is set to a datetime value
   - For temporary bans: `banned_until` = current_time + duration_days
   - For permanent bans: `banned_until` = None (represents infinite ban)
   - Note: A None value means permanent ban, not "not banned"

2. **Audit Logging**
   - All ban actions are logged in the `audit_logs` table
   - Includes: moderator ID, action type, target user, duration, and timestamp
   - Provides accountability and tracking for moderation actions

3. **Immediate Effects**
   - Banned users cannot authenticate (login/token refresh blocked)
   - Profile becomes hidden from public view in most contexts
   - Existing content remains but may be hidden depending on other flags

### Ban Endpoints

Two API endpoints handle banning:

1. **UMD Endpoint (User Management Dashboard)**
   ```
   POST /admin/user/{sqid}/ban?duration_days=7
   ```
   - Uses public SQID for user identification
   - Optional `duration_days` parameter (1-365 days)
   - No duration = permanent ban

2. **Admin Endpoint**
   ```
   POST /admin/user/{id}/ban
   ```
   - Uses UUID (user_key) for identification
   - Accepts payload with `duration_days`, `reason_code`, and `note`
   - More detailed audit trail options

### Unban Functionality

Moderators can unban users:
```
DELETE /admin/user/{sqid}/ban
DELETE /admin/user/{id}/ban
```
- Sets `banned_until` to NULL (clearing the ban)
- Logged in audit trail
- User can immediately authenticate again

## User Profile Data Retention

### Important: Banned Profiles Are NOT Automatically Deleted

**There is currently NO automatic cleanup task for banned user profiles.**

When a user is banned:
- ✅ Authentication is blocked
- ✅ Profile is hidden from public endpoints
- ✅ Action is logged in audit trail
- ❌ **Profile data remains in database indefinitely**
- ❌ **No scheduled cleanup occurs**

### What Gets Auto-Deleted

The only automatic user cleanup that exists is:

**Unverified Accounts** (via `cleanup_unverified_accounts` task):
- Runs every 12 hours
- Deletes users where:
  - `email_verified = False`
  - `created_at` < 3 days ago
- Removes associated tokens (email verification, refresh, password reset)

### Manual Deletion Options

To permanently remove a banned user's profile, moderators would need to:
1. Use account deletion endpoints (if implemented)
2. Or perform database operations manually
3. Note: There is no built-in "delete banned users after X days" feature

## Authentication Flow

The ban check occurs in `check_user_can_authenticate()` function in `api/app/auth.py`:

```python
def check_user_can_authenticate(user: "models.User") -> None:
    # Check if account is deactivated
    if user.deactivated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account deactivated",
        )
    
    # Check if user is currently banned
    if user.banned_until and user.banned_until > datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account banned",
        )
```

This function is called during:
- Login attempts
- Token refresh operations
- Any authentication flow requiring active user status

## Database Schema

### User Model (`users` table)

Relevant fields:
```python
banned_until = Column(DateTime(timezone=True), nullable=True, index=True)
```

- **NULL**: User is not banned
- **Future datetime**: User is banned until that datetime
- **Past datetime**: Ban has expired, user can authenticate again

Note: The expiration is checked at authentication time, not by a background job.

### AuditLog Model (`audit_logs` table)

Ban actions are recorded with:
- `action`: "ban_user" or "unban_user"
- `actor_id`: Moderator who performed the action
- `target_type`: "user"
- `target_id`: Banned user's ID
- `reason_code`: Optional reason code
- `note`: Optional notes (includes duration info)
- `created_at`: Timestamp of action

## Visibility and Access Control

When a user is banned:

1. **Profile Endpoints**
   - Public profile queries filter out banned users
   - Profile appears as "not found" to non-moderators
   - Checked via: `if user.banned_until: raise HTTPException(404)`

2. **Content Visibility**
   - User's posts/comments remain in database
   - Visibility depends on other flags (`hidden_by_mod`, `deleted_by_user`, etc.)
   - Ban alone doesn't hide content

3. **Moderator View**
   - Moderators can still view banned user profiles
   - UMD (User Management Dashboard) shows ban status
   - `banned_until` field visible in admin interfaces

## Temporary vs Permanent Bans

### Temporary Ban
```
duration_days = 7  # Ban for 7 days
banned_until = current_time + timedelta(days=7)
```
- User automatically regains access after duration expires
- No cleanup job needed - checked at authentication time

### Permanent Ban
```
duration_days = None  # No duration specified
banned_until = None   # Stored as NULL
```
- User permanently cannot authenticate
- Profile remains in database
- Can only be lifted by moderator unban action

## Related Cleanup Tasks

For reference, other cleanup tasks that run in the background:

1. **`cleanup_unverified_accounts`** - Every 12 hours
   - Deletes unverified accounts after 3 days

2. **`cleanup_deleted_posts`** - Daily at 5AM UTC
   - Permanently deletes posts soft-deleted by users after 7 days

3. **`cleanup_expired_auth_tokens`** - Daily at 3AM UTC
   - Cleans up expired refresh/verification/reset tokens

4. **`cleanup_expired_player_registrations`** - Hourly
   - Removes pending player registrations with expired codes

**Note:** None of these tasks affect banned user profiles.

## Recommendations for Future Enhancement

If automatic deletion of banned users is desired, consider implementing:

1. **New Cleanup Task**: `cleanup_permanently_banned_users`
   - Run daily or weekly
   - Target: Users where `banned_until IS NULL` (permanent ban)
   - Optional grace period (e.g., 30 days after ban before deletion)
   - Actions:
     - Delete or anonymize user record
     - Clean up associated content
     - Preserve audit trail

2. **Soft Delete for Bans**
   - Add `deleted_by_mod` flag
   - Implement deletion after ban + grace period
   - Preserve moderation history

3. **GDPR Compliance**
   - Right to erasure considerations
   - Data retention policies
   - Audit trail requirements

## Security Considerations

1. **Audit Trail Preservation**
   - Even if user is deleted, audit logs should be preserved
   - Maintains accountability for moderation actions

2. **Content Attribution**
   - Consider what happens to content when user is deleted
   - Options: Anonymize, delete, or mark as [deleted user]

3. **Re-registration Prevention**
   - Email normalization prevents simple re-registration
   - Consider additional measures for repeat offenders

## Summary

**Question: After being banned by a moderator, how long does a user profile take to be removed from the database for good?**

**Answer: User profiles are NEVER automatically removed from the database after being banned. The ban only prevents authentication and hides the profile from public view. The profile data remains in the database indefinitely unless manually deleted by an administrator.**

**The ban action works by:**
1. Setting the `banned_until` field on the User model
2. Blocking authentication attempts via `check_user_can_authenticate()`
3. Hiding the profile from public endpoints
4. Logging the action in the audit trail

**For complete removal**, a separate manual or automated process would need to be implemented.

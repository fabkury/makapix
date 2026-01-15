# Makapix Club - Security Attack Scenario Analysis

**Document Version:** 1.0  
**Date:** January 14, 2026  
**Analyst:** Security Assessment Team

## Executive Summary

This document analyzes potential attack scenarios against the Makapix Club platform, examining current security controls and recommending mitigation strategies. The analysis is based on a thorough review of the codebase, including authentication systems, rate limiting, content management, and data storage mechanisms.

**Current Security Posture:** The platform has implemented several defensive measures including rate limiting, email verification, and content deduplication. However, there are opportunities to strengthen defenses against automated abuse and spam.

---

## Table of Contents

1. [Scenario 1: Automated Spam Artwork Posting](#scenario-1-automated-spam-artwork-posting)
2. [Scenario 2: Manual Profanity Spam in Comments](#scenario-2-manual-profanity-spam-in-comments)
3. [Scenario 3: Plus-Syntax Email Account Spam](#scenario-3-plus-syntax-email-account-spam)
4. [Scenario 4: Email Verification Spam Requests](#scenario-4-email-verification-spam-requests)
5. [Scenario 5: Unconfirmed Email Account Flooding](#scenario-5-unconfirmed-email-account-flooding)
6. [Scenario 6: Storage Exhaustion via Unique Artwork Variations](#scenario-6-storage-exhaustion-via-unique-artwork-variations)
7. [Scenario 7: Reputation Gaming through Coordinated Bot Networks](#scenario-7-reputation-gaming-through-coordinated-bot-networks)
8. [Summary and Recommendations](#summary-and-recommendations)

---

## Scenario 1: Automated Spam Artwork Posting

### Attack Description

User X creates multiple accounts and uses automation scripts to spam-post pixel art. Each artwork is unique (different pixel patterns) to bypass deduplication, flooding the platform with low-quality or inappropriate content.

### What Would Happen

**Current Defenses:**

1. **Email Verification Requirement**: Users must verify their email before they can authenticate and upload content (`email_verified=False` prevents login).
   - Location: `api/app/routers/auth.py:332-407`
   - Login requires `check_user_can_authenticate()` which verifies email status

2. **Hash-Based Deduplication**: The system calculates SHA256 hash of uploaded artwork and prevents exact duplicates.
   - Location: `api/app/routers/posts.py:580-593`
   - Partial unique index: `uq_posts_hash_active` (only for non-deleted posts)

3. **Auto-Public Approval Flag**: New users don't have `auto_public_approval=True`, so their posts don't appear in Recent Artworks feed until moderator approval.
   - Location: `api/app/routers/posts.py:538`
   - Default: `auto_public_approval=False` for new users

4. **File Validation**: AMP inspector validates format, dimensions, and metadata.
   - Location: `api/app/routers/posts.py:452-520`
   - Rejects invalid formats, oversized files, and improper dimensions

**Attack Impact:**

- **Moderate Impact**: Attacker could create multiple verified accounts (one per email address) and upload unique spam artwork
- Each account could upload unlimited unique artworks (no per-user rate limit on uploads)
- Spam would be hidden from public feeds initially (no auto_public_approval)
- However, spam would still:
  - Consume vault storage space (up to 5MB per file)
  - Pollute the database with posts
  - Be visible to the user and anyone with direct links
  - Require manual moderator review

**Current Gaps:**

- ❌ No rate limiting on artwork uploads per user/account
- ❌ No storage quota per user
- ❌ No automated detection of spam patterns (e.g., similar titles, rapid uploads)
- ❌ No CAPTCHA or proof-of-work on registration or upload

### Mitigation Recommendations

**High Priority:**

1. **Implement Upload Rate Limiting**
   ```python
   # In posts.py upload_artwork endpoint
   rate_limit_key = f"ratelimit:upload:{current_user.id}"
   allowed, remaining = check_rate_limit(rate_limit_key, limit=10, window_seconds=3600)
   # Allow 10 uploads per hour per user
   ```

2. **Add Per-User Storage Quota**
   ```python
   # Track storage_used_bytes in User model (already exists in schema)
   # Enforce quota check before upload
   if current_user.storage_used_bytes + file_size > USER_STORAGE_QUOTA:
       raise HTTPException(status_code=413, detail="Storage quota exceeded")
   ```

3. **Implement Progressive Rate Limits Based on Reputation**
   - New users (reputation < 100): 5 uploads/hour
   - Established users (reputation 100-500): 10 uploads/hour
   - Trusted users (reputation > 500): 20 uploads/hour

**Medium Priority:**

4. **Add CAPTCHA on Registration**
   - Use hCaptcha or reCAPTCHA to slow automated account creation
   - Consider invisible CAPTCHA for better UX

5. **Implement Automated Spam Detection**
   - Flag accounts uploading many posts with similar titles/hashtags
   - Flag rapid upload patterns (e.g., 10 posts in 5 minutes)
   - Use content similarity detection beyond exact hash matching

6. **Add Moderator Queue Dashboard**
   - Show posts from users without auto_public_approval
   - Bulk approve/reject capability
   - Flag suspicious patterns automatically

**Low Priority:**

7. **Implement IP-Based Rate Limiting for Uploads**
   - Secondary defense if user creates multiple accounts
   - Example: Max 50 uploads per hour per IP

---

## Scenario 2: Manual Profanity Spam in Comments

### Attack Description

User X manually posts profanity and offensive comments on many artworks. The attacker uses manual entry to bypass automated detection, targeting popular artworks to maximize visibility.

### What Would Happen

**Current Defenses:**

1. **Authentication Required**: Comments require verified user accounts (or anonymous with IP tracking).
   - Location: `api/app/routers/comments.py:162-170`
   - Anonymous comments track `author_ip` for accountability

2. **Comment Limit Per Post**: Maximum 1000 comments per post.
   - Location: `api/app/routers/comments.py:128-136`
   - Prevents comment flooding on individual posts

3. **Moderation Tools**: Moderators can hide comments with `hidden_by_mod` flag.
   - Location: `api/app/models.py:415`
   - Hidden comments not visible to regular users

4. **User Reporting**: Users can report inappropriate content via `/report` endpoint.
   - Location: `api/app/routers/reports.py:19-47`
   - Creates report records for moderator review

5. **Depth Limiting**: Maximum comment depth of 2 (prevents deeply nested spam threads).
   - Location: `api/app/routers/comments.py:148-160`

**Attack Impact:**

- **High Visibility Impact**: Manual profanity spam is highly disruptive as:
  - Comments are immediately visible to all users (no pre-moderation)
  - Popular posts would be targeted for maximum impact
  - Users would see offensive content before moderators can act
  - Community trust and user experience degraded

**Current Gaps:**

- ❌ No rate limiting on comment creation per user
- ❌ No profanity/content filtering
- ❌ No automated flagging of potentially offensive content
- ❌ No temporary muting/shadow-banning for repeat offenders
- ❌ No spam detection (e.g., identical comments on multiple posts)

### Mitigation Recommendations

**High Priority:**

1. **Implement Comment Rate Limiting**
   ```python
   # In comments.py create_comment endpoint
   rate_limit_key = f"ratelimit:comment:{current_user.id}"
   allowed, remaining = check_rate_limit(rate_limit_key, limit=30, window_seconds=300)
   # Allow 30 comments per 5 minutes
   ```

2. **Add Profanity/Content Filter**
   ```python
   # Use library like better_profanity or create custom filter
   # Check comment body before saving
   # Options:
   #   - Auto-reject: Block comments with profanity
   #   - Auto-flag: Allow but flag for review
   #   - Context-aware: Different strictness based on reputation
   ```

3. **Implement Temporary Muting for Repeat Offenders**
   ```python
   # If user gets multiple reports/mod actions within 24 hours
   # Set user.muted_until = datetime + timedelta(hours=24)
   # Prevent comment creation while muted
   ```

**Medium Priority:**

4. **Add Duplicate Comment Detection**
   - Hash comment body and prevent posting identical comments on multiple posts
   - Allow duplicates only after 1 hour cooldown

5. **Implement Smart Pre-Moderation**
   - New users (reputation < 50): Comments require approval
   - Users with previous violations: Temporary pre-moderation
   - Flagged comments held for review

6. **Add AI-Based Content Moderation**
   - Integrate with services like OpenAI Moderation API or Azure Content Safety
   - Auto-flag potentially toxic content for moderator review
   - Consider auto-hiding severely toxic content (hate speech, threats)

**Low Priority:**

7. **Implement Comment Edit History**
   - Track edits to prevent abuse (post profanity, then edit after seen)
   - Show "edited" indicator on modified comments

8. **Add User Reputation Impact**
   - Reduce reputation for hidden/reported comments
   - Increase rate limits for low-reputation users

---

## Scenario 3: Plus-Syntax Email Account Spam

### Attack Description

User X exploits Gmail's plus-syntax feature (e.g., `user+1@gmail.com`, `user+2@gmail.com`) to create multiple accounts, all receiving emails at the same base address (`user@gmail.com`). This bypasses the "one email per account" restriction.

### What Would Happen

**Current Defenses:**

1. **Unique Email Constraint**: Database enforces unique email addresses.
   - Location: `api/app/models.py:48-50`
   - `email = Column(String(255), unique=True, nullable=False, index=True)`

2. **Email Verification Required**: Each account needs email verification to login.
   - Location: `api/app/services/email_verification.py:29-73`

3. **Registration Rate Limiting**: 3 registrations per hour per IP.
   - Location: `api/app/routers/auth.py:216-224`

**Attack Impact:**

- **High Impact**: This attack is highly effective because:
  - Attacker can create unlimited accounts using one email address
  - Gmail (and other providers) support plus-syntax and dot-syntax
  - Examples: `user+spam1@gmail.com`, `user+spam2@gmail.com`, `u.s.e.r@gmail.com`
  - All verification emails go to same inbox
  - Each account appears unique to the system
  - IP rate limiting (3/hour) is only minor inconvenience (VPN/proxy bypass)

**Current Gaps:**

- ❌ No email address normalization (removing plus-syntax and dots for Gmail)
- ❌ No detection of suspicious patterns (many similar emails)
- ❌ IP rate limiting easily bypassed with VPN/proxy rotation

### Mitigation Recommendations

**High Priority:**

1. **Implement Email Normalization**
   ```python
   def normalize_email(email: str) -> str:
       """Normalize email to prevent plus-syntax and dot-syntax abuse."""
       local, domain = email.lower().split('@')
       
       # Gmail and Google Workspace: ignore dots and plus-suffix
       if domain in ['gmail.com', 'googlemail.com'] or domain.endswith('.google.com'):
           # Remove all dots
           local = local.replace('.', '')
           # Remove plus-suffix
           if '+' in local:
               local = local.split('+')[0]
       
       # Outlook/Hotmail: only remove plus-suffix (dots are significant)
       elif domain in ['outlook.com', 'hotmail.com', 'live.com']:
           if '+' in local:
               local = local.split('+')[0]
       
       return f"{local}@{domain}"
   
   # Check normalized email for uniqueness
   normalized = normalize_email(email)
   existing_user = db.query(models.User).filter(
       func.lower(models.User.email).like(f"%{normalized}%")
   ).first()
   ```

2. **Store Both Original and Normalized Email**
   ```python
   # In User model
   email = Column(String(255), nullable=False)  # Original email for sending
   email_normalized = Column(String(255), unique=True, nullable=False, index=True)
   # Enforce uniqueness on normalized version
   ```

**Medium Priority:**

3. **Implement Device/Browser Fingerprinting**
   - Track browser fingerprints during registration
   - Flag multiple accounts from same fingerprint
   - Use libraries like FingerprintJS

4. **Add Phone Verification (Optional)**
   - Offer phone verification as alternative
   - Required for users flagged for suspicious activity
   - Use Twilio or similar service

5. **Strengthen IP Rate Limiting**
   - Reduce to 2 registrations per 24 hours per IP
   - Track IP ranges (subnet) for VPN detection
   - Use IP reputation services to flag VPN/proxy IPs

**Low Priority:**

6. **Implement Account Linking Detection**
   - Track patterns: similar upload times, similar artwork styles
   - Flag accounts for manual review
   - Use ML for pattern detection

---

## Scenario 4: Email Verification Spam Requests

### Attack Description

User X uses automation to repeatedly request email verification emails, either to:
- Flood a victim's email inbox (using victim's email)
- Overwhelm the email sending service (cost attack)
- Discover valid email addresses (reconnaissance)

### What Would Happen

**Current Defenses:**

1. **Token-Based Rate Limiting**: Maximum 6 verification emails per hour per user.
   - Location: `api/app/services/email_verification.py:44-52`
   - `MAX_TOKENS_PER_HOUR = 6`

2. **Security-Through-Obscurity**: Verification re-send endpoint returns success even on rate limit.
   - Location: `api/app/routers/auth.py:471-485`
   - Doesn't reveal if email exists or rate limited (security best practice)

3. **Token Expiry**: Tokens expire after 24 hours.
   - Location: `api/app/services/email_verification.py:20`
   - `TOKEN_EXPIRY_HOURS = 24`

**Attack Impact:**

- **Low-Medium Impact**: Current defenses are reasonably effective:
  - 6 emails/hour limit prevents inbox flooding (only 144 emails/day per user)
  - Cannot overwhelm email service (rate limited per user)
  - Email enumeration is difficult (no error messages revealing valid emails)

**Current Gaps:**

- ❌ No IP-based rate limiting on verification re-send requests
- ❌ No CAPTCHA on re-send endpoint
- ❌ Attacker could target multiple accounts/emails (6 emails/hour × N accounts)
- ❌ No cost monitoring/alerting for email sending

### Mitigation Recommendations

**High Priority:**

1. **Add IP-Based Rate Limiting for Verification Requests**
   ```python
   # In auth.py verify-email-resend endpoint
   client_ip = get_client_ip(request)
   rate_limit_key = f"ratelimit:verify_resend_ip:{client_ip}"
   allowed, remaining = check_rate_limit(rate_limit_key, limit=20, window_seconds=3600)
   # Max 20 verification requests per hour per IP (across all emails)
   ```

2. **Implement CAPTCHA on Re-Send Verification**
   - Require CAPTCHA after 2 re-send requests
   - Prevents automated abuse

**Medium Priority:**

3. **Add Email Sending Cost Monitoring**
   ```python
   # Track daily email volume in Redis
   # Alert if exceeds threshold (e.g., 1000 emails/day)
   # Implement circuit breaker if costs spike
   ```

4. **Implement Exponential Backoff**
   ```python
   # First re-send: immediate
   # Second re-send: 5 minutes wait
   # Third re-send: 15 minutes wait
   # Fourth re-send: 1 hour wait
   ```

**Low Priority:**

5. **Add Account Age Check**
   - Newly created accounts (< 10 minutes old) have stricter limits
   - Prevents rapid account creation → spam pattern

---

## Scenario 5: Unconfirmed Email Account Flooding

### Attack Description

User X uses automation to spam-create user accounts using the same email address (or multiple emails), but never confirms any of them. The goal is to:
- Pollute the database with ghost accounts
- Consume database storage
- Block legitimate users from using those email addresses

### What Would Happen

**Current Defenses:**

1. **Unique Email Constraint**: Cannot create multiple accounts with same email.
   - Location: `api/app/models.py:48-50`
   - Database-level unique constraint

2. **Registration Rate Limiting**: 3 registrations per hour per IP.
   - Location: `api/app/routers/auth.py:216-224`

3. **Verification Tokens Expire**: 24-hour expiry on verification tokens.
   - Location: `api/app/services/email_verification.py:20`

**Attack Impact:**

- **Low Impact Due to Unique Constraint**: Attack mostly fails because:
  - First account creation with email succeeds
  - All subsequent attempts with same email fail with 409 Conflict
  - Attacker blocked from creating duplicate email accounts

- **However, Modified Attack Possible**:
  - Create accounts with different emails (email1, email2, email3...)
  - Leave all unverified
  - Goal: Pollute database, not block specific emails

**Current Gaps:**

- ❌ No cleanup of unverified accounts after expiry
- ❌ No limit on total unverified accounts from single IP
- ❌ Unverified accounts persist indefinitely in database
- ❌ No monitoring of unverified account accumulation

### Mitigation Recommendations

**High Priority:**

1. **Implement Automatic Cleanup of Expired Unverified Accounts**
   ```python
   # Background job (Celery periodic task)
   @celery.task
   def cleanup_unverified_accounts():
       """Delete accounts where email_verified=False and created > 7 days ago."""
       threshold = datetime.now(timezone.utc) - timedelta(days=7)
       
       # Find unverified accounts older than 7 days
       old_accounts = db.query(User).filter(
           User.email_verified == False,
           User.created_at < threshold
       ).all()
       
       for user in old_accounts:
           # Delete associated tokens, identities, etc.
           db.delete(user)
       
       db.commit()
       logger.info(f"Cleaned up {len(old_accounts)} unverified accounts")
   
   # Run daily
   ```

2. **Add Unverified Account Limit Per IP**
   ```python
   # In auth.py register endpoint
   # Count unverified accounts from this IP in last 24 hours
   client_ip = get_client_ip(request)
   unverified_count = db.query(func.count(User.id)).join(
       # Join with some IP tracking table or use Redis
   ).filter(
       User.email_verified == False,
       # IP matches
   ).scalar()
   
   if unverified_count >= 5:
       raise HTTPException(
           status_code=429,
           detail="Too many unverified accounts from this IP"
       )
   ```

**Medium Priority:**

3. **Add Email Reservation System**
   ```python
   # Allow legitimate user to "claim" their email if it's held by unverified account
   # After 48 hours, allow deleting old unverified account and creating new one
   if existing_user and not existing_user.email_verified:
       if existing_user.created_at < datetime.now(timezone.utc) - timedelta(hours=48):
           # Allow override/delete old account
           db.delete(existing_user)
           db.commit()
           # Continue with new account creation
   ```

4. **Implement Database Monitoring**
   - Alert on rapid growth of unverified accounts
   - Track ratio of verified:unverified accounts
   - Dashboard for admins to see unverified account trends

**Low Priority:**

5. **Add Account Creation Flow Optimization**
   - Consider sending verification code instead of link (faster to verify)
   - Shorten token expiry to 2 hours (reduce unverified period)
   - Send reminder email after 6 hours if not verified

---

## Scenario 6: Storage Exhaustion via Unique Artwork Variations

**(Invented Attack Scenario)**

### Attack Description

User X creates a sophisticated automation that generates thousands of unique pixel art variations by:
- Making minimal pixel changes (1-2 pixels different each time)
- Using different compression levels to change file hashes
- Exploiting the 5MB per-file limit to maximize storage consumption
- Each file is unique enough to bypass hash-based deduplication

The goal is to exhaust vault storage and increase infrastructure costs, leading to:
- Service degradation or outage when storage full
- Increased hosting costs for VPS storage expansion
- Denial of service for legitimate users

### What Would Happen

**Current Defenses:**

1. **Hash-Based Deduplication**: SHA256 prevents identical files.
   - Location: `api/app/routers/posts.py:580-593`
   - But doesn't help with unique variations

2. **Auto-Public Approval**: Without approval, posts hidden from public feeds.
   - Location: `api/app/routers/posts.py:538`
   - But files still consume storage

3. **File Size Limit**: 5MB per file.
   - Location: `api/app/vault.py:25`
   - `MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024`

**Attack Impact:**

- **Very High Impact**: This is a severe attack vector because:
  - Attacker could exhaust storage with just 1 account
  - Example: 1,000 files × 5MB = 5GB consumed
  - No per-user storage quotas enforced
  - Storage grows until disk full → service outage
  - Hard to detect until storage alerts trigger
  - Cleanup requires manual intervention

**Attack Scenario Example:**

```python
# Attacker's script
for i in range(10000):
    # Generate 64x64 PNG with random pixels
    img = generate_random_pixel_art(64, 64)
    # Make barely perceptible change
    img[0, 0] = (i % 256, (i // 256) % 256, 0, 255)
    # Upload
    upload_artwork(img, title=f"Art {i}")
```

**Current Gaps:**

- ❌ **CRITICAL**: No per-user storage quota enforcement
- ❌ No monitoring of rapid storage growth
- ❌ No alerts when user consumes excessive storage
- ❌ No perceptual hashing (detect similar but not identical images)
- ❌ No abuse pattern detection (many uploads, all unique)

### Mitigation Recommendations

**Critical Priority:**

1. **Implement and Enforce Per-User Storage Quota**
   ```python
   # In User model (already has storage_used_bytes field)
   USER_STORAGE_QUOTA = 100 * 1024 * 1024  # 100MB per user
   
   # In posts.py upload_artwork
   def upload_artwork(...):
       # Calculate current usage
       current_usage = db.query(func.sum(Post.file_bytes)).filter(
           Post.owner_id == current_user.id,
           Post.deleted_by_user == False
       ).scalar() or 0
       
       if current_usage + file_size > USER_STORAGE_QUOTA:
           raise HTTPException(
               status_code=413,
               detail=f"Storage quota exceeded. Used: {current_usage / 1024 / 1024:.2f}MB, Limit: {USER_STORAGE_QUOTA / 1024 / 1024}MB"
           )
       
       # After successful upload
       current_user.storage_used_bytes = current_usage + file_size
       db.commit()
   ```

2. **Implement Progressive Quotas Based on Reputation**
   ```python
   def get_user_storage_quota(user: User) -> int:
       """Get storage quota based on user reputation."""
       if user.reputation < 100:
           return 50 * 1024 * 1024  # 50MB for new users
       elif user.reputation < 500:
           return 100 * 1024 * 1024  # 100MB
       elif user.reputation < 1000:
           return 250 * 1024 * 1024  # 250MB
       else:
           return 500 * 1024 * 1024  # 500MB for trusted users
   ```

**High Priority:**

3. **Add Storage Growth Monitoring and Alerts**
   ```python
   # Celery periodic task
   @celery.task
   def monitor_storage_usage():
       """Alert on suspicious storage patterns."""
       # Check users who uploaded > 20MB in last hour
       one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
       
       high_volume_users = db.query(
           Post.owner_id,
           func.sum(Post.file_bytes).label('total_bytes')
       ).filter(
           Post.created_at >= one_hour_ago
       ).group_by(Post.owner_id).having(
           func.sum(Post.file_bytes) > 20 * 1024 * 1024
       ).all()
       
       for user_id, total_bytes in high_volume_users:
           alert_admins(f"User {user_id} uploaded {total_bytes / 1024 / 1024:.2f}MB in last hour")
   ```

4. **Implement Perceptual Hashing (pHash)**
   ```python
   # Use library like imagehash
   import imagehash
   from PIL import Image
   
   def calculate_phash(image_data) -> str:
       """Calculate perceptual hash to detect similar images."""
       img = Image.open(io.BytesIO(image_data))
       phash = imagehash.phash(img)
       return str(phash)
   
   # Store phash in Post model
   # Check for similar images (hamming distance < threshold)
   existing_similar = db.query(Post).filter(
       Post.owner_id == current_user.id,
       # Check hamming distance in SQL or application code
   ).all()
   
   for post in existing_similar:
       if imagehash.hex_to_hash(post.phash) - imagehash.hex_to_hash(new_phash) < 5:
           raise HTTPException(
               status_code=409,
               detail="Similar artwork already exists"
           )
   ```

**Medium Priority:**

5. **Add Vault Storage Monitoring**
   ```python
   # System monitoring
   def check_vault_storage():
       """Monitor vault storage usage."""
       vault_path = get_vault_location()
       stat = os.statvfs(vault_path)
       
       # Calculate usage
       total = stat.f_blocks * stat.f_frsize
       free = stat.f_bavail * stat.f_frsize
       used_percent = ((total - free) / total) * 100
       
       # Alert if > 80% full
       if used_percent > 80:
           alert_admins(f"Vault storage {used_percent:.1f}% full")
           
           # Trigger cleanup if > 90%
           if used_percent > 90:
               cleanup_deleted_posts()
   ```

6. **Implement Automatic Cleanup of Soft-Deleted Posts**
   ```python
   # Clean up posts deleted > 7 days ago
   @celery.task
   def cleanup_deleted_posts():
       threshold = datetime.now(timezone.utc) - timedelta(days=7)
       old_deleted = db.query(Post).filter(
           Post.deleted_by_user == True,
           Post.deleted_by_user_date < threshold
       ).all()
       
       for post in old_deleted:
           # Delete from vault
           delete_artwork_from_vault(post.storage_key, post.file_format)
           # Delete from database
           db.delete(post)
       
       db.commit()
   ```

---

## Scenario 7: Reputation Gaming through Coordinated Bot Networks

**(Invented Attack Scenario)**

### Attack Description

User X creates a network of bot accounts (sock puppets) to artificially inflate reputation through coordinated actions:
- Bot accounts post low-effort content
- Other bot accounts react positively (emoji reactions) to each other's posts
- Bots leave positive comments on each other's work
- The goal is to:
  - Rapidly gain reputation points
  - Unlock higher privileges (auto_public_approval, higher storage quotas)
  - Appear as trusted users to evade other protections
  - Game any reputation-based features (leaderboards, badges, etc.)

### What Would Happen

**Current System:**

1. **Reputation System Exists**: Users have reputation scores.
   - Location: `api/app/models.py:57`
   - `reputation = Column(Integer, nullable=False, default=0, index=True)`

2. **Reputation History Tracked**: Changes logged to reputation_history table.
   - Location: `api/app/models.py:98-99`
   - `reputation_history = relationship(...)`

3. **Reactions Are Per-User**: One user can react to a post (up to 5 emojis).
   - Location: Reactions system in `api/app/routers/reactions.py`

4. **Comments Create Notifications**: Comments trigger social notifications.
   - Location: `api/app/routers/comments.py:174-185`

**Attack Impact:**

- **High Impact**: Coordinated bot networks can:
  - Artificially inflate reputation quickly
  - Example: 10 bots × 100 posts each × 9 bots reacting = 9,000 reputation events
  - Unlock trusted user privileges (auto_public_approval)
  - Bypass rate limits designed for low-reputation users
  - Manipulate any reputation-based rankings or features
  - Create fake "popular" content to mislead real users

**Current Gaps:**

- ❌ No detection of coordinated behavior patterns
- ❌ No limits on reactions from same set of users
- ❌ No graph analysis to detect bot rings
- ❌ Reputation gain not throttled or validated
- ❌ No decay or anti-gaming mechanisms

### Mitigation Recommendations

**High Priority:**

1. **Implement Reputation Gain Rate Limiting**
   ```python
   # Limit reputation gains per time period
   MAX_REPUTATION_PER_DAY = 50  # For new users
   
   def award_reputation(user: User, amount: int, reason: str):
       """Award reputation with rate limiting."""
       # Calculate reputation gained today
       today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0)
       today_gains = db.query(func.sum(ReputationHistory.amount)).filter(
           ReputationHistory.user_id == user.id,
           ReputationHistory.created_at >= today_start,
           ReputationHistory.amount > 0
       ).scalar() or 0
       
       # Apply limit
       if today_gains >= MAX_REPUTATION_PER_DAY:
           logger.info(f"User {user.id} hit daily reputation limit")
           return  # Don't award more reputation today
       
       # Apply capped amount
       capped_amount = min(amount, MAX_REPUTATION_PER_DAY - today_gains)
       
       user.reputation += capped_amount
       history = ReputationHistory(
           user_id=user.id,
           amount=capped_amount,
           reason=reason
       )
       db.add(history)
       db.commit()
   ```

2. **Implement Diminishing Returns for Same-User Interactions**
   ```python
   # Track interaction history
   # First reaction from User A to User B's post: +5 reputation
   # Second reaction from User A to User B's post: +2 reputation
   # Third+ reaction from User A to User B's post: +0 reputation
   
   def get_reputation_multiplier(actor_id: int, target_id: int) -> float:
       """Get multiplier based on interaction history."""
       # Count recent interactions (last 30 days)
       recent = datetime.now(timezone.utc) - timedelta(days=30)
       interaction_count = db.query(func.count(ReputationHistory.id)).filter(
           ReputationHistory.user_id == target_id,
           ReputationHistory.reason.like(f"%user:{actor_id}%"),
           ReputationHistory.created_at >= recent
       ).scalar()
       
       if interaction_count == 0:
           return 1.0
       elif interaction_count == 1:
           return 0.5
       else:
           return 0.0  # No reputation for repeated interactions
   ```

**Medium Priority:**

3. **Implement Bot Network Detection**
   ```python
   # Celery periodic task
   @celery.task
   def detect_bot_networks():
       """Detect coordinated bot networks using graph analysis."""
       # Build interaction graph
       # Find tightly connected clusters
       # Flag accounts that:
       #   - Only interact with each other
       #   - Have reciprocal interaction patterns
       #   - Were created around the same time
       #   - Have similar behavior patterns
       
       # Use NetworkX library
       import networkx as nx
       
       G = nx.Graph()
       
       # Add edges for reactions, comments, etc.
       reactions = db.query(Reaction).all()
       for reaction in reactions:
           post = db.query(Post).filter(Post.id == reaction.post_id).first()
           if post:
               G.add_edge(reaction.user_id, post.owner_id)
       
       # Find highly connected subgraphs
       cliques = list(nx.find_cliques(G))
       suspicious_cliques = [c for c in cliques if len(c) >= 5]
       
       for clique in suspicious_cliques:
           alert_moderators(f"Suspected bot network: {clique}")
   ```

4. **Add Account Age Weighting**
   ```python
   # Reputation from new accounts (< 7 days old) worth less
   def get_reputation_value(actor: User) -> float:
       """Get reputation value multiplier based on account age."""
       age = datetime.now(timezone.utc) - actor.created_at
       if age < timedelta(days=7):
           return 0.1  # New accounts give 10% reputation value
       elif age < timedelta(days=30):
           return 0.5  # 1-month accounts give 50% reputation value
       else:
           return 1.0  # Established accounts give full value
   ```

**Low Priority:**

5. **Implement Reputation Decay**
   ```python
   # Periodic task to decay inactive user reputation
   @celery.task
   def apply_reputation_decay():
       """Reduce reputation for inactive users."""
       inactive_threshold = datetime.now(timezone.utc) - timedelta(days=90)
       
       inactive_users = db.query(User).filter(
           User.updated_at < inactive_threshold,
           User.reputation > 100
       ).all()
       
       for user in inactive_users:
           # Decay 10% of reputation for inactive users
           decay = int(user.reputation * 0.1)
           user.reputation -= decay
           
           history = ReputationHistory(
               user_id=user.id,
               amount=-decay,
               reason="inactivity_decay"
           )
           db.add(history)
       
       db.commit()
   ```

6. **Add Reputation Source Diversity Requirement**
   ```python
   # Require reputation from diverse sources to unlock privileges
   # Track reputation sources: uploads, reactions_received, comments_received, etc.
   # Require minimum threshold in each category for auto_public_approval
   
   def check_auto_approval_eligibility(user: User) -> bool:
       """Check if user should get auto_public_approval."""
       # Need 100+ total reputation AND diverse sources
       if user.reputation < 100:
           return False
       
       # Check reputation sources
       sources = db.query(
           ReputationHistory.reason,
           func.sum(ReputationHistory.amount)
       ).filter(
           ReputationHistory.user_id == user.id
       ).group_by(ReputationHistory.reason).all()
       
       # Require at least 3 different sources
       if len(sources) < 3:
           return False
       
       # Require minimum in each category
       source_dict = dict(sources)
       if source_dict.get('reactions_received', 0) < 20:
           return False
       if source_dict.get('comments_received', 0) < 10:
           return False
       if source_dict.get('posts_created', 0) < 5:
           return False
       
       return True
   ```

---

## Summary and Recommendations

### Critical Vulnerabilities

1. **No Per-User Storage Quotas** (Scenario 6)
   - **Risk**: Service outage via storage exhaustion
   - **Priority**: CRITICAL - Implement immediately
   - **Effort**: Medium (2-3 days)

2. **Email Normalization Missing** (Scenario 3)
   - **Risk**: Unlimited account creation via plus-syntax
   - **Priority**: HIGH - Implement within 1 week
   - **Effort**: Low (1 day)

3. **No Upload Rate Limiting** (Scenario 1)
   - **Risk**: Spam flooding, resource abuse
   - **Priority**: HIGH - Implement within 1 week
   - **Effort**: Low (1 day)

### High Priority Improvements

4. **Comment Rate Limiting** (Scenario 2)
   - **Priority**: HIGH
   - **Effort**: Low (1 day)

5. **Unverified Account Cleanup** (Scenario 5)
   - **Priority**: HIGH
   - **Effort**: Medium (2 days)

6. **Storage Monitoring & Alerts** (Scenario 6)
   - **Priority**: HIGH
   - **Effort**: Medium (2 days)

### Medium Priority Improvements

7. **Profanity Filter** (Scenario 2)
8. **Reputation Gaming Prevention** (Scenario 7)
9. **Perceptual Hashing** (Scenario 6)
10. **Bot Network Detection** (Scenario 7)

### Overall Security Posture

**Strengths:**
- ✅ Email verification required for authentication
- ✅ Hash-based artwork deduplication
- ✅ Basic rate limiting on registration and login
- ✅ Moderation tools for hiding content
- ✅ Auto-public approval system reduces spam visibility

**Weaknesses:**
- ❌ No per-user resource quotas (storage, uploads)
- ❌ Email normalization gaps allow account multiplication
- ❌ Limited rate limiting on content creation
- ❌ No automated abuse detection systems
- ❌ No reputation anti-gaming mechanisms

### Implementation Roadmap

**Phase 1 (Week 1): Critical Security Fixes**
- Implement per-user storage quotas with progressive limits
- Add email normalization for registration
- Add upload rate limiting per user
- Implement unverified account cleanup job

**Phase 2 (Week 2-3): High Priority Protections**
- Comment rate limiting
- Storage growth monitoring and alerts
- IP-based verification request limiting
- Profanity/content filtering

**Phase 3 (Week 4-6): Advanced Protections**
- Perceptual hashing for similar image detection
- Reputation gaming prevention
- Bot network detection
- CAPTCHA integration

**Phase 4 (Ongoing): Monitoring & Tuning**
- Monitor rate limit effectiveness
- Tune quotas based on user behavior
- Expand automated abuse detection
- Refine reputation system

### Monitoring and Alerting

**Key Metrics to Track:**
1. **Storage Growth Rate**: Alert if > 1GB/hour
2. **Account Creation Rate**: Alert if > 100/hour
3. **Unverified Account Ratio**: Alert if > 50%
4. **Upload Volume**: Alert if user uploads > 50 files/hour
5. **Comment Volume**: Alert if user posts > 100 comments/hour
6. **Reputation Changes**: Alert on rapid reputation gains
7. **Email Sending Volume**: Alert if > 1000 emails/hour

### Testing Recommendations

1. **Penetration Testing**: Hire security firm to test defenses
2. **Bug Bounty Program**: Incentivize responsible disclosure
3. **Load Testing**: Simulate abuse scenarios in staging
4. **Red Team Exercise**: Internal team attempts to break defenses

### Compliance and Legal

1. **GDPR Compliance**: Ensure data deletion for deleted accounts
2. **DMCA Process**: Document content takedown procedures
3. **Terms of Service**: Clearly prohibit automation and abuse
4. **Rate Limit Disclosure**: Document rate limits for developers

---

## Conclusion

The Makapix Club platform has implemented foundational security controls but requires additional hardening against automated abuse and spam attacks. The most critical vulnerabilities involve resource exhaustion and account multiplication.

**Key Takeaways:**

1. **Storage quotas are essential** to prevent service outages
2. **Email normalization** prevents trivial account multiplication
3. **Rate limiting** must be comprehensive (uploads, comments, reactions)
4. **Reputation systems** need anti-gaming protections
5. **Automated detection** is necessary for scaling moderation

**Estimated Implementation Effort:**
- Critical fixes: 1-2 weeks
- High priority items: 2-3 weeks
- Full roadmap: 6-8 weeks

**Business Impact:**
- Without fixes: High risk of service disruption, degraded UX
- With fixes: Sustainable growth, better user experience, reduced moderation burden

**Next Steps:**
1. Review and prioritize recommendations
2. Allocate engineering resources
3. Implement Phase 1 critical fixes
4. Monitor effectiveness and iterate

---

**Document End**

*For questions or clarifications, please contact the security team.*

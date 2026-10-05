# Admin API

Moderation and administration endpoints. All endpoints require the `moderator` role unless noted otherwise.

Base path: `/api/admin`

## Authorization

| Role | Access |
|------|--------|
| Moderator | Ban/unban, hide/unhide users and comments, manage trust, issue violations, view audit log, view pending posts, view sitewide stats |
| Owner | All moderator actions + promote/demote moderators, list all users |

All admin actions are logged to the `audit_logs` table.

---

## User Ban System

Banning prevents a user from authenticating. It does **not** delete their account, hide their content, or remove any data.

### Ban Semantics

The `banned_until` field on the User model controls ban state:

| Value | Meaning |
|-------|---------|
| `NULL` (no ban record) | Not banned |
| Future datetime | Temporarily banned until that time |
| `9999-12-31T23:59:59Z` (`PERMANENT_BAN_UNTIL`, set by ban with no duration) | Permanently banned |

Temporary bans auto-expire: the authentication check compares `banned_until` against the current time. Once expired, the user can log in again without moderator action.

### Data Retention

Banned user profiles are **never** automatically deleted. All associated data (posts, comments, reactions, followers) remains in the database indefinitely. To remove a user's data, a separate manual process would be needed.

See [Scheduled Tasks](../reference/scheduled-tasks.md) for what *is* automatically cleaned up.

### Ban User

```
POST /api/admin/user/{id}/ban
```

`{id}` is either the user's UUID (`user_key`) or their public Sqid. (Until
2026-10 these were two routes, and the Sqid one was shadowed by the UUID one,
so Sqid callers got a 422; app 0002 §7.1, docs/localized-text/.)

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` (path) | string | Yes | User's UUID or public Sqid |
| `duration_days` (query) | integer | No | Ban duration in days (1--365); used only when the body has none |
| `reason` | string | No | Ban reason (max 500 chars) |
| `duration_days` | integer | No | Ban duration in days (1--365). Omit (body and query) for permanent. |
| `reason_code` | string | No | Machine-readable reason code (max 50 chars) |
| `note` | string | No | Internal moderator note (max 1000 chars) |

Request body (JSON, optional):

```json
{
  "reason": "Repeated spam",
  "duration_days": 30,
  "reason_code": "spam",
  "note": "Third warning, escalated to 30-day ban"
}
```

Response (`201 Created`):

```json
{
  "status": "banned",
  "until": "2026-03-26T14:00:00Z"
}
```

For a permanent ban, give no duration. The `until` field is then the far-future sentinel `9999-12-31T23:59:59Z` (`models.PERMANENT_BAN_UNTIL`).

### Unban User

```
DELETE /api/admin/user/{id}/ban    # UUID or Sqid
```

Response: `204 No Content`.

Sets `banned_until = NULL`, allowing the user to authenticate immediately.

### Protection Rules

- Cannot ban the site owner (403 Forbidden, code `owner_protected`), unless the actor is the owner themselves.
- The same protection applies to hide, trust, and reputation actions.

---

## User Visibility

### Hide User Profile

```
POST /api/admin/user/{id}/hide          # UUID or Sqid
```

Response: `201 Created`, body `{"status": "hidden"}`.

### Unhide User Profile

```
DELETE /api/admin/user/{id}/hide         # UUID or Sqid
```

Response: `204 No Content`.

---

## Trust (Auto-Approval)

Users with auto-approval have their uploaded artworks immediately visible in public listings without moderator review.

### Grant Auto-Approval

```
POST /api/admin/user/{id}/auto-approval     # UUID: returns AutoApprovalResponse
POST /api/admin/user/{sqid}/trust           # Sqids: returns {"status": "trusted", ...}
```

Both grant paths send the user a `trust_granted` notification.

### Revoke Auto-Approval

```
DELETE /api/admin/user/{id}/auto-approval   # UUID: returns AutoApprovalResponse
DELETE /api/admin/user/{sqid}/trust         # Sqids: 204 No Content
```

---

## Moderator Management (Owner Only)

### Promote to Moderator

```
POST /api/admin/user/{user_key}/moderator
```

Requires `owner` role. The target user must have at least one auth identity. Returns `201 Created` with `{"user_id": ..., "role": "moderator"}`.

A `moderator_granted` system notification is sent to the promoted user.

### Demote from Moderator

```
DELETE /api/admin/user/{user_key}/moderator
```

Requires `owner` role. Cannot demote a user with the `owner` role. Returns `204 No Content`.

A `moderator_revoked` system notification is sent to the demoted user.

---

## Reputation

### Adjust Reputation

```
POST /api/admin/user/{sqid}/reputation
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `delta` | integer | Yes | Amount to add/subtract (-1000 to +1000) |
| `reason` | string | Yes | Reason (min 8 chars) |

Response: `{"new_total": 150}`.

---

## Violations

### Issue Violation

```
POST /api/admin/user/{sqid}/violation
```

Body: `{"reason": "Spam posting in comments"}`. Response: `{"status": "issued", "id": 42}`.

### List User Violations

```
GET /api/admin/user/{sqid}/violations?cursor=...&limit=5
```

Returns paginated violation list with moderator handles.

### Delete Violation

```
DELETE /api/admin/violation/{violation_id}
```

Response: `204 No Content`.

---

## Comment Moderation

### Hide Comment

```
POST /api/admin/comment/{comment_id}/hide
```

Response: `{"status": "hidden"}`.

### Unhide Comment

```
DELETE /api/admin/comment/{comment_id}/hide
```

Response: `204 No Content`.

### Delete Comment

```
DELETE /api/admin/comment/{comment_id}
```

Permanently deletes the comment. Response: `204 No Content`.

---

## Listings

### Pending Approval

```
GET /api/admin/pending-approval?cursor=...&limit=50
```

Posts with `public_visibility = false` that need moderator review. Cursor-paginated.

### Recent Profiles

```
GET /api/admin/recent-profiles?cursor=...&limit=50
```

All user profiles, newest first. Returns `UserFull` schema.

### Recent Posts

```
GET /api/admin/recent-posts?cursor=...&limit=50
```

All posts, newest first.

### Authenticated Users (Owner Only)

```
GET /api/admin/owner/user?cursor=...&limit=50
```

Users with at least one auth identity, alphabetical by handle.

### Anonymous Users (Owner Only)

```
GET /api/admin/owner/user/anonymous?cursor=...&limit=50
```

Users without any auth identity, alphabetical by handle.

---

## User Management Dashboard (UMD)

The UMD page provides a single view of a user's moderation state.

```
GET /api/admin/user/{sqid}/manage
```

Returns `UMDUserData` with profile, badges, moderation flags (`banned_until`, `hidden_by_mod`, `auto_public_approval`), and roles.

### Badges

```
GET  /api/admin/badges                          # List all badge definitions
POST /api/admin/user/{sqid}/badge/{badge}       # Grant badge (201)
DELETE /api/admin/user/{sqid}/badge/{badge}      # Revoke badge (204)
```

### User Comments

```
GET /api/admin/user/{sqid}/comments?cursor=...&limit=10
```

Paginated list of a user's comments with post context.

### Email Reveal

```
GET /api/admin/user/{sqid}/email
```

Returns the user's email address. This action is logged to the audit log.

---

## Sitewide Statistics

```
GET /api/admin/sitewide-stats?refresh=false
```

Returns comprehensive site metrics for the past 14 days: page views, signups, posts, API calls, errors, hourly/daily breakdowns, device/country/referrer distributions, player statistics, and authenticated-user breakdowns. Cached in Redis for 5 minutes; set `refresh=true` to force recalculation.

---

## Online Players

```
GET /api/admin/online-players
```

Returns list of currently connected players with device info and owner handles.

---

## Audit Log

```
GET /api/admin/audit-log?cursor=...&limit=50
```

Optional filters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `actor_id` | UUID | Filter by moderator who performed the action |
| `action` | string | Filter by action type (e.g. `ban_user`, `hide_comment`) |
| `target_type` | string | Filter by target type (`user`, `comment`, `post`) |

Response fields per entry:

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Entry ID |
| `actor_id` | integer | Moderator's user ID |
| `action` | string | Action performed |
| `target_type` | string | Type of target |
| `target_id` | string | Target entity ID |
| `reason_code` | string | Machine-readable reason (if applicable) |
| `note` | string | Moderator note (if applicable) |
| `created_at` | datetime | When the action occurred |

# Error Codes

HTTP status codes and error messages returned by the API.

## HTTP Status Codes

| Status | Meaning |
|--------|---------|
| 200 | OK - Request succeeded |
| 201 | Created - Resource created |
| 204 | No Content - Success with no response body |
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 409 | Conflict - Resource already exists |
| 413 | Payload Too Large - File or quota exceeded |
| 429 | Too Many Requests - Rate limited |
| 500 | Internal Server Error - Server-side failure |

## Error Response Format

App-facing routes under `/api/v1` return a stable code and a display message:

```json
{
  "error": {
    "code": "post_not_found",
    "message": "Post not found"
  }
}
```

An optional `details` object supplies structured context. Unversioned management routes use `detail` with a sibling `code`; player RPC uses its own protocol envelope (see below). Validation errors can return 422.

Branch on the stable code and HTTP status, not exact message text. The tables below describe common messages rather than an exhaustive code list. The app-facing codes are defined in [`api/app/errors.py`](../../api/app/errors.py).

## Authentication Errors

### 401 Unauthorized

| Detail | Cause |
|--------|-------|
| Invalid email or password | Wrong credentials |
| User not found | Account doesn't exist |
| Invalid or expired refresh token | Token needs renewal |
| No refresh token found in cookie | Missing cookie |
| Current password is incorrect | Wrong password on change |

### 403 Forbidden

| Detail | Cause |
|--------|-------|
| Email not verified. Please check your email for verification link. | Unverified email |
| Email verification required to change handle. | Handle change blocked |
| The site owner's handle cannot be changed | Protected account |
| Moderator role required to hide posts as moderator | Missing role |
| Not authorized to modify this post | Wrong owner |

### 409 Conflict

| Detail | Cause |
|--------|-------|
| An account with this email already exists | Duplicate email |
| An account with this email already exists. Please log in with your existing account. | OAuth conflict |
| This handle is already taken | Duplicate handle |
| pending_verification | Account exists, unverified |

### 429 Too Many Requests

| Detail | Cause |
|--------|-------|
| Too many registration attempts. Please try again later. | Registration rate limit |
| Too many login attempts. Please try again later. | Login rate limit |
| Too many verification requests. Please try again later. | Verification rate limit |
| Too many password reset requests. Please try again later. | Reset rate limit |

## Post/Artwork Errors

### 400 Bad Request

| Detail | Cause |
|--------|-------|
| Invalid image dimensions/format | Image doesn't meet requirements |
| File size exceeds limit | Over the configured artwork limit (default 5 MiB) |
| Invalid license_id | Unknown license |
| Artwork is identical to current artwork | Redundant replacement |
| User-deleted posts cannot be restored | Restoration blocked |
| Deleted posts cannot be restored | Restoration blocked |

### 404 Not Found

| Detail | Cause |
|--------|-------|
| Post not found | Invalid ID or no access |

### 409 Conflict

| Detail | Cause |
|--------|-------|
| Artwork already exists | Duplicate hash |

### 413 Payload Too Large

| Detail | Cause |
|--------|-------|
| Storage quota exceeded. Used X MB of Y MB. | Quota full |

### 429 Too Many Requests

| Detail | Cause |
|--------|-------|
| Upload rate limit exceeded. Please try again later. | Too many uploads |

## Player Errors

### 400 Bad Request

| Detail | Cause |
|--------|-------|
| Maximum 128 players allowed per user | Player limit reached |
| Player already registered | Re-registration attempt |
| post_id is required for show_artwork command | Missing parameter |
| play_channel requires one of: channel_name, hashtag, or user_sqid | Missing parameter |
| playset_name is required for play_playset command | Missing parameter |
| Certificate is still valid for X days. Renewal only available within 90 days of expiry. | Early renewal |

### 403 Forbidden

| Detail | Cause |
|--------|-------|
| Post is not visible | Hidden or non-conformant post |

### 404 Not Found

| Detail | Cause |
|--------|-------|
| User not found | Invalid user ID |
| Player not found | Invalid player ID |
| Player not found or not registered | Unregistered device |
| Invalid or expired registration code | Bad or expired code |
| Post not found | Invalid post ID |
| Playset 'name' not found | Invalid playset |
| No registered players found | No devices |

### 429 Too Many Requests

| Detail | Cause |
|--------|-------|
| Too many credential requests. Please try again later. | Credential rate limit (30/min/IP) |
| Rate limit exceeded for player (300 commands/minute) | Command limit per player |
| Rate limit exceeded for user (1000 commands/minute) | Command limit per user |

### 500 Internal Server Error

| Detail | Cause |
|--------|-------|
| Invalid MQTT configuration | Server misconfiguration |
| Invalid player configuration | Invalid player_key |
| CA certificate not found | Missing CA cert |
| CA certificate files not found | Missing CA files |
| Failed to generate certificate | Cert generation failed |

## MQTT Error Codes

MQTT request responses and HTTPS player RPC share lowercase protocol codes:

```json
{
  "request_id": "req-001",
  "success": false,
  "error": "Post not found",
  "error_code": "not_found"
}
```

| Code | Description |
|------|-------------|
| `invalid_request` | Malformed request payload |
| `invalid_criteria` | Invalid artwork filter criteria |
| `not_found` | Requested resource does not exist |
| `rate_limited` / `rate_limit_exceeded` | Request quota exceeded |
| `internal_error` | Server-side failure |

See [Player RPC error handling](../http-api/player-rpc.md#error-handling) and each [request type](../mqtt-api/player-requests.md) for operation-specific codes. HTTPS also supplies an HTTP status; MQTT supplies the reply on the request's response topic.

### Validation Errors

| Message | Cause |
|---------|-------|
| Operator 'X' not valid for numeric field 'Y' | Wrong operator type |
| Operator 'X' not valid for boolean field 'Y' | Wrong operator type |
| Operator 'X' not valid for enum field 'Y' | Wrong operator type |
| Field 'X' is not nullable | Using is_null on non-nullable |
| Invalid value for field 'X' | Wrong value type |

## OAuth Errors

### 400 Bad Request

| Detail | Cause |
|--------|-------|
| Invalid OAuth state. Please try again. | State verification failed |
| GitHub OAuth error: description | GitHub API error |
| Failed to authenticate with GitHub: error | Network error |

### 500 Internal Server Error

| Detail | Cause |
|--------|-------|
| GitHub OAuth not configured | Missing OAuth credentials |
| User account not found | Database inconsistency |
| Failed to create user account. Please try again. | User creation failed |
| Failed to create authentication identity. Please try again. | Identity creation failed |
| Failed to generate authentication tokens. Please try again. | Token generation failed |
| An unexpected error occurred during authentication. Please try again. | Unhandled error |

## Rate Limits Reference

| Operation | Limit | Window |
|-----------|-------|--------|
| Registration | 30 | 1 hour per IP |
| Login | 20 | 5 minutes per IP |
| Email verification | 20 | 1 hour per IP |
| Password reset | 15 | 1 hour per IP |
| Credential fetch | 30 | 1 minute per IP |
| Upload (rep < 100) | 4 | 1 hour |
| Upload (rep 100-499) | 16 | 1 hour |
| Upload (rep 500+) | 64 | 1 hour |
| Player commands | 300 | 1 minute per player |
| User commands | 1000 | 1 minute per user |

## Handling Errors

### Retry Strategy

For 429 errors, honor `Retry-After` when provided. Otherwise use exponential backoff with random jitter:

```
Wait time = min(2^attempt * base_delay, max_delay)
```

Suggested values:

- `base_delay`: 1 second
- `max_delay`: 60 seconds
- Max attempts: 5

### Error Recovery

| Status | Action |
|--------|--------|
| 400 | Fix request parameters |
| 401 | Re-authenticate |
| 403 | Check permissions |
| 404 | Verify resource exists |
| 409 | Resolve the reported conflict or limit; inspect the error code |
| 429 | Wait and retry |
| 500 | Report and retry later |

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

```json
{
  "detail": "Error message describing the issue"
}
```

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
| File size exceeds limit | Over 5 MB |
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
| Certificate is still valid for X days. Renewal only available within 30 days of expiry. | Early renewal |

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
| Certificates not available for this player | No certs generated |
| Invalid or expired registration code | Bad or expired code |
| Post not found | Invalid post ID |
| Playset 'name' not found | Invalid playset |
| No registered players found | No devices |

### 429 Too Many Requests

| Detail | Cause |
|--------|-------|
| Too many credential requests. Please try again later. | Credential rate limit (20/min/IP) |
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

MQTT responses use structured error codes.

### Error Response Format

```json
{
  "status": "error",
  "error_code": "ERROR_CODE",
  "message": "Human-readable description"
}
```

### Error Codes

| Code | Description |
|------|-------------|
| `INVALID_REQUEST` | Malformed request payload |
| `VALIDATION_ERROR` | Invalid field values or criteria |
| `NOT_FOUND` | Requested resource doesn't exist |
| `RATE_LIMITED` | Too many requests |
| `INTERNAL_ERROR` | Server-side failure |

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
| Registration | Varies | Per IP |
| Login | Varies | Per IP |
| Email verification | 20 | 1 hour |
| Password reset | Varies | Per IP |
| Credential fetch | 20 | 1 minute per IP |
| Upload (rep < 100) | 4 | 1 hour |
| Upload (rep 100-499) | 16 | 1 hour |
| Upload (rep 500+) | 64 | 1 hour |
| Player commands | 300 | 1 minute per player |
| User commands | 1000 | 1 minute per user |

## Handling Errors

### Retry Strategy

For 429 errors, implement exponential backoff:

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
| 409 | Use existing resource |
| 429 | Wait and retry |
| 500 | Report and retry later |

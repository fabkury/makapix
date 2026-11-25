# HTTP API Reference

REST API for web clients, mobile apps, and integrations.

## Base URL

| Environment | Base URL |
|-------------|----------|
| Production | `https://makapix.club/api/v1` |
| Development | `https://development.makapix.club/api/v1` |

Paths in the app-facing references are relative to these bases. **Player device and owner-management endpoints remain under `/api`**, not `/api/v1`; see [Player](player.md). The [committed OpenAPI contract](../../api/openapi.json) and [versioning policy](../api-versioning-policy.md) describe the available routes.

## Authentication

User endpoints generally use a JWT bearer token. Player devices use their own opaque device token for [HTTPS RPC](player-rpc.md); it is not a user login token. Start with the [Player Device Guide](../player/README.md) when building a display.

### Obtaining Tokens

1. **Email/Password**: `POST /auth/login`
2. **GitHub OAuth**: `GET /auth/github/login`

### Using Tokens

Include the access token in the `Authorization` header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Token Refresh

Access tokens expire after 60 minutes by default (configurable on the server). Use the refresh endpoint:

```
POST /auth/refresh
```

For the browser login flow, the refresh token is an HttpOnly cookie; cross-origin fetch clients must include credentials. Native apps use `/auth/token` and body-based refresh tokens; see [Authentication](authentication.md).

### Public Endpoints

These endpoints work without authentication:

- `GET /post/recent` - Recent artwork
- `GET /p/{public_sqid}` - Single artwork by sqid
- `GET /user/browse` - Browse users
- `GET /user/u/{public_sqid}` - User profile
Player provisioning and credential retrieval use the separate `/api/player/...` paths. Credential retrieval requires possession of the secret `player_key`.

## Response Format

### Success Response

```json
{
  "id": 12345,
  "title": "My Artwork",
  "created_at": "2024-01-15T09:00:00Z"
}
```

### Error Response

Under `/v1` (the app-facing API), every error uses the envelope:

```json
{
  "error": {
    "code": "post_not_found",
    "message": "Post not found",
    "details": { "...": "..." }
  }
}
```

Unversioned paths (players, `/pmd`, `/admin/user`, the website's legacy root
copies) keep FastAPI's `detail`, with the same stable `code` (and `details`,
when present) beside it:

```json
{
  "detail": "Player not found",
  "code": "player_not_found"
}
```

`code` is a value of `ErrorCode` (`api/app/errors.py`); plain errors carry the
status fallback (`not_found`, `forbidden`, …). Clients should branch on `code`
and treat `message` / `detail` as display text.

### Paginated Response

```json
{
  "items": [...],
  "next_cursor": "eyJpZCI6MTIzfQ"
}
```

## Pagination

List endpoints use cursor-based pagination:

```
GET /post?limit=50&cursor=eyJpZCI6MTIzfQ
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Results per page (1-200) |
| `cursor` | string | null | Cursor from previous response |

The `next_cursor` field in the response provides the cursor for the next page. When `next_cursor` is null, there are no more results.

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| Registration | 30/hour/IP |
| Login | 20/5 min/IP |
| Upload | 4-64/hour/user (by reputation) |
| Password reset | 15/hour/IP |
| Credential requests | 30/min/IP |
| Player commands | 300/min/player |

A rate-limited request returns 429. Honor `Retry-After` when present; otherwise retry with backoff. The API does not consistently return `X-RateLimit-*` headers, so clients must not depend on them.

## Common Headers

### Request

```
Content-Type: application/json
Authorization: Bearer {token}
```

### Response

```
Content-Type: application/json
```

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 204 | No Content (success with no body) |
| 400 | Bad Request (invalid input) |
| 401 | Unauthorized (missing/invalid token) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 409 | Conflict (duplicate resource) |
| 413 | Payload Too Large |
| 429 | Too Many Requests (rate limited) |
| 500 | Server Error |

## API Sections

| Section | Description |
|---------|-------------|
| [Authentication](authentication.md) | Login, registration, OAuth, tokens |
| [Posts](posts.md) | Artwork upload, listing, management |
| [Users](users.md) | Profiles, follows, highlights |
| [Reactions](reactions.md) | Emoji reactions and comments |
| [Playlists](playlists.md) | Curated artwork collections |
| [Notifications](notifications.md) | Social notification inbox and SSE stream |
| [Player](player.md) | Device management and commands |
| [Player RPC](player-rpc.md) | HTTPS query/reaction/view protocol for player devices |
| [Admin](admin.md) | Moderation, bans, trust, audit log |
| [Artist Dashboard](dashboard.md) | Artist analytics and statistics |

## Identifiers

The API uses several identifier types:

| Type | Format | Example |
|------|--------|---------|
| `id` | Integer | `12345` |
| `public_sqid` | Short alphanumeric | `k5fNx` |
| `user_key` | UUID | `550e8400-e29b-41d4-a716-446655440000` |
| `storage_key` | UUID | `abc123-def456-789` |
| `player_key` | UUID | `550e8400-e29b-41d4-a716-446655440000` |

### Sqids

Public-facing URLs use sqids (short IDs) instead of numeric IDs:

- Artwork: `/p/{sqid}` (e.g., `/p/k5fNx`)
- Users: `/u/{sqid}` (e.g., `/u/m8gPq`)

## CORS

The API allows cross-origin requests from:

- `https://makapix.club`
- `https://development.makapix.club`
- `http://localhost:3000` (development)

Preflight requests are handled automatically.

## Versioning

App-facing routes use `/api/v1`. Legacy unversioned aliases remain in the current server for compatibility, but new app integrations should use v1. Player routes have a separate unversioned contract. See the [versioning and deprecation policy](../api-versioning-policy.md).

## Example: Fetch Recent Artwork

```bash
curl -X GET "https://makapix.club/api/v1/post/recent?limit=10" \
  -H "Accept: application/json"
```

Response:

```json
{
  "items": [
    {
      "id": 12345,
      "public_sqid": "k5fNx",
      "title": "Pixel Landscape",
      "art_url": "https://vault.makapix.club/21/32/storage-key.png",
      "width": 64,
      "height": 64,
      "created_at": "2024-01-15T09:00:00Z",
      "owner": {
        "id": 1,
        "handle": "artist",
        "public_sqid": "m8gPq"
      }
    }
  ],
  "next_cursor": "eyJpZCI6MTIzNDR9"
}
```

## Example: Add a Reaction

```bash
curl -X PUT "https://makapix.club/api/v1/post/12345/reactions/%E2%9D%A4%EF%B8%8F" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Returns **204 with no body**. Repeating the request leaves the reaction in place; use `DELETE` on the same URL to remove it. See [Reactions and Comments](reactions.md).

# HTTP API Reference

REST API for web clients, mobile apps, and integrations.

## Base URL

| Environment | Base URL |
|-------------|----------|
| Production | `https://makapix.club/api` |
| Development | `https://development.makapix.club/api` |

## Authentication

Most endpoints require authentication via JWT bearer token.

### Obtaining Tokens

1. **Email/Password**: `POST /auth/login`
2. **GitHub OAuth**: `GET /auth/github/login`

### Using Tokens

Include the access token in the `Authorization` header:

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

### Token Refresh

Access tokens expire after 15 minutes. Use the refresh endpoint:

```
POST /auth/refresh
```

The refresh token is stored in an HttpOnly cookie and automatically included.

### Public Endpoints

These endpoints work without authentication:

- `GET /post/recent` - Recent artwork
- `GET /p/{public_sqid}` - Single artwork by sqid
- `GET /user/browse` - Browse users
- `GET /user/u/{public_sqid}` - User profile
- `POST /player/provision` - Device provisioning
- `GET /player/{player_key}/credentials` - Device credentials

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

```json
{
  "detail": "Error message describing what went wrong"
}
```

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
| Registration | 15/hour/IP |
| Login | 10/5 min/IP |
| Upload | 4-64/hour/user (by reputation) |
| Password reset | 5/hour/IP |
| Credential requests | 20/min/IP |
| Player commands | 300/min/player |

Rate limit headers:

```
X-RateLimit-Limit: 15
X-RateLimit-Remaining: 14
X-RateLimit-Reset: 1705320000
```

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
| [Player](player.md) | Device management and commands |

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

The API is currently unversioned. Breaking changes will be communicated in advance via Discord and documentation updates.

## Example: Fetch Recent Artwork

```bash
curl -X GET "https://makapix.club/api/post/recent?limit=10" \
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
      "art_url": "https://makapix.club/api/vault/a1/b2/c3/storage-key.png",
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

## Example: Authenticated Request

```bash
curl -X POST "https://makapix.club/api/post/12345/reactions" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"emoji": "❤️"}'
```

Response:

```json
{
  "id": "reaction-uuid",
  "post_id": 12345,
  "user_id": 1,
  "emoji": "❤️",
  "created_at": "2024-01-15T10:30:00Z"
}
```

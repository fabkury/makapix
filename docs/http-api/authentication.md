# Authentication

Login, registration, OAuth, and token management.

## Registration

Create a new account with email.

### POST /auth/register

```json
{
  "email": "user@example.com"
}
```

**Response (201):**

```json
{
  "message": "Please check your email to verify your account",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "handle": "makapix-user-42"
}
```

**Notes:**

- Generates a default handle (`makapix-user-X`)
- Generates a random password (sent via email)
- Sends verification email
- Account cannot login until email is verified
- Rate limited: 15 registrations/hour/IP

**Errors:**

| Status | Detail |
|--------|--------|
| 409 | `pending_verification` - Account exists, not verified |
| 409 | `An account with this email already exists` |
| 429 | Rate limited |

## Email Verification

### GET /auth/verify-email

```
GET /auth/verify-email?token={verification_token}
```

**Response (200):**

```json
{
  "message": "Email verified successfully. You can now log in.",
  "verified": true,
  "handle": "makapix-user-42",
  "can_change_password": true,
  "can_change_handle": true,
  "needs_welcome": true,
  "public_sqid": "k5fNx"
}
```

### POST /auth/request-verification

Request verification email (unauthenticated).

```json
{
  "email": "user@example.com"
}
```

**Response (200):**

```json
{
  "message": "If an unverified account exists with this email, a verification link has been sent.",
  "email": "user@example.com"
}
```

Always returns success to prevent email enumeration.

## Login

### POST /auth/login

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response (200):**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": null,
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "user_key": "550e8400-e29b-41d4-a716-446655440000",
  "public_sqid": "k5fNx",
  "user_handle": "artist",
  "expires_at": "2024-01-15T11:00:00Z",
  "needs_welcome": false
}
```

**Notes:**

- Refresh token is set as HttpOnly cookie
- Access token expires in 15 minutes
- Rate limited: 10 attempts/5 min/IP

**Errors:**

| Status | Detail |
|--------|--------|
| 401 | Invalid email or password |
| 403 | Email not verified |
| 429 | Rate limited |

## Token Refresh

### POST /auth/refresh

No request body. Refresh token is read from HttpOnly cookie.

**Response (200):**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": null,
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "user_key": "550e8400-e29b-41d4-a716-446655440000",
  "public_sqid": "k5fNx",
  "user_handle": "artist",
  "expires_at": "2024-01-15T11:15:00Z",
  "needs_welcome": false
}
```

**Notes:**

- Old refresh token remains valid for 60 seconds (grace period)
- New refresh token set in HttpOnly cookie

## Logout

### POST /auth/logout

Requires authentication.

**Response (204):** No content

Revokes refresh token and clears cookie.

## Current User

### GET /auth/me

Requires authentication.

**Response (200):**

```json
{
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "user_key": "550e8400-e29b-41d4-a716-446655440000",
    "public_sqid": "k5fNx",
    "handle": "artist",
    "bio": "Pixel artist",
    "avatar_url": "https://...",
    "email": "user@example.com",
    "email_verified": true,
    "created_at": "2024-01-01T00:00:00Z"
  },
  "roles": ["user"]
}
```

## GitHub OAuth

### GET /auth/github/login

Redirects to GitHub for authentication.

Optional query parameter:

```
GET /auth/github/login?installation_id=12345
```

### GET /auth/github/callback

GitHub redirects here after authentication. Sets tokens and redirects to app.

### POST /auth/github/exchange

Exchange GitHub code for tokens (SPA flow).

```json
{
  "code": "github_auth_code",
  "redirect_uri": "https://makapix.club/auth/callback",
  "installation_id": null,
  "setup_action": null
}
```

**Response (201):**

Same as login response.

## Password Management

### POST /auth/change-password

Requires authentication.

```json
{
  "current_password": "oldpassword",
  "new_password": "newpassword123"
}
```

**Response (200):**

```json
{
  "message": "Password changed successfully"
}
```

**Password Requirements:**

- Minimum 8 characters
- At least one letter
- At least one number

### POST /auth/forgot-password

```json
{
  "email": "user@example.com"
}
```

**Response (200):**

```json
{
  "message": "If an account exists with this email, a password reset link has been sent."
}
```

Always returns success to prevent email enumeration.

### POST /auth/reset-password

```json
{
  "token": "reset_token_from_email",
  "new_password": "newpassword123"
}
```

**Response (200):**

```json
{
  "message": "Password reset successfully. You can now log in with your new password."
}
```

## Handle Management

### POST /auth/change-handle

Requires authentication.

```json
{
  "new_handle": "newhandle"
}
```

**Response (200):**

```json
{
  "message": "Handle changed successfully",
  "handle": "newhandle"
}
```

**Handle Rules:**

- 3-32 characters
- Alphanumeric plus hyphens and underscores
- Cannot start/end with hyphen or underscore
- Case-insensitive uniqueness

### POST /auth/check-handle-availability

```json
{
  "handle": "desired_handle"
}
```

**Response (200):**

```json
{
  "handle": "desired_handle",
  "available": true,
  "message": "This handle is available"
}
```

## Welcome Flow

### POST /auth/complete-welcome

Requires authentication. Marks welcome flow as completed.

**Response (204):** No content

## Auth Providers

### GET /auth/providers

Requires authentication. Lists linked authentication methods.

**Response (200):**

```json
{
  "identities": [
    {
      "id": "identity-uuid",
      "provider": "password",
      "email": "user@example.com",
      "created_at": "2024-01-01T00:00:00Z"
    },
    {
      "id": "identity-uuid-2",
      "provider": "github",
      "email": "user@example.com",
      "provider_metadata": {
        "username": "github_user",
        "avatar_url": "https://..."
      },
      "created_at": "2024-01-02T00:00:00Z"
    }
  ]
}
```

### DELETE /auth/providers/{provider}/{identity_id}

Unlink an authentication provider.

**Response (204):** No content

**Errors:**

| Status | Detail |
|--------|--------|
| 400 | Cannot unlink the last authentication method |
| 404 | Identity not found |

## GitHub App Integration

### GET /auth/github-app/status

Check GitHub App installation status.

**Response (200):**

```json
{
  "installed": true,
  "installation_id": 12345,
  "install_url": "https://github.com/apps/makapix-club/installations/new"
}
```

### GET /auth/github-app/validate

Validate GitHub App installation.

**Response (200):**

```json
{
  "valid": true,
  "installation_id": 12345,
  "target_repo": "user/repo",
  "account_login": "github_user"
}
```

### POST /auth/github-app/clear-installation

Clear invalid installation.

**Response (200):**

```json
{
  "status": "cleared",
  "message": "Installation 12345 has been cleared. You can now reinstall the GitHub App."
}
```

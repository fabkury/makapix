# Production Environment Variables Template

Copy this content to `.env` on your production VPS and fill in your actual values.

```bash
# Makapix Production Environment Configuration

# Database Configuration
POSTGRES_DB=makapix
POSTGRES_USER=makapix_user
POSTGRES_PASSWORD=your_secure_random_password_here

# API Configuration
DATABASE_URL=postgresql://makapix_user:your_secure_random_password_here@db:5432/makapix
API_PORT=8000

# JWT Authentication
JWT_SECRET_KEY=your_secure_random_jwt_secret_here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# GitHub OAuth (create at https://github.com/settings/developers)
GITHUB_OAUTH_CLIENT_ID=your_oauth_client_id_here
GITHUB_OAUTH_CLIENT_SECRET=your_oauth_client_secret_here
GITHUB_REDIRECT_URI=https://makapix.club/auth/github/callback

# GitHub App (create at https://github.com/settings/apps)
GITHUB_APP_ID=your_github_app_id_here
GITHUB_APP_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
your_private_key_content_here_with_newlines
-----END RSA PRIVATE KEY-----"

# Celery Task Queue
CELERY_BROKER_URL=redis://cache:6379/0
CELERY_RESULT_BACKEND=redis://cache:6379/0

# Frontend Configuration
NEXT_PUBLIC_API_BASE_URL=https://makapix.club/api
NEXT_PUBLIC_MQTT_WS_URL=wss://makapix.club:9001

# MQTT Configuration
MQTT_CA_FILE=/certs/ca.crt
```

## Notes

- **Generate secure random values** for `POSTGRES_PASSWORD` and `JWT_SECRET_KEY`
- **Paste your actual GitHub OAuth credentials** from https://github.com/settings/developers
- **Paste your actual GitHub App credentials** from https://github.com/settings/apps
- **Preserve newlines** in the `GITHUB_APP_PRIVATE_KEY` value
- **Set permissions**: `chmod 600 .env` after creating the file
- **Never commit** the `.env` file to git (it's already in `.gitignore`)


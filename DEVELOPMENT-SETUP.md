# Development Environment Setup

This guide helps you set up seamless development environments for both **local** (localhost) and **remote** (dev.makapix.club) development.

## Quick Start

### 1. Initial Setup

Run the setup script:

**Windows (PowerShell):**
```powershell
.\scripts\setup-dev.ps1
```

**Linux/Mac:**
```bash
chmod +x scripts/*.sh
./scripts/setup-dev.sh
```

This creates `.env.local` and `.env.remote` from templates.

### 2. Configure GitHub Apps

You need **two separate GitHub OAuth Apps** and **two GitHub Apps** (one for local, one for remote):

#### Local GitHub OAuth App
- Go to: https://github.com/settings/applications/new
- **Homepage URL:** `http://localhost`
- **Authorization callback URL:** `http://localhost/auth/github/callback`
- Copy Client ID and Secret to `.env.local`

#### Remote GitHub OAuth App
- Go to: https://github.com/settings/applications/new
- **Homepage URL:** `https://dev.makapix.club`
- **Authorization callback URL:** `https://dev.makapix.club/auth/github/callback`
- Copy Client ID and Secret to `.env.remote`

#### GitHub Apps (for publishing features)
Create two GitHub Apps (same URLs as OAuth Apps above but with webhook URL):
- **Webhook URL:** `http://localhost/api/webhooks/github` (local) or `https://dev.makapix.club/api/webhooks/github` (remote)

### 3. Switch Environment

**For local development:**

Windows:
```powershell
.\dev.ps1 local
.\dev.ps1 up
```

Linux/Mac:
```bash
make local
make up
```

**For remote development:**

Windows:
```powershell
.\dev.ps1 remote
.\dev.ps1 up
```

Linux/Mac:
```bash
make remote
make up
```

The environment automatically configures:
- Correct domain (localhost vs dev.makapix.club)
- Correct GitHub OAuth credentials
- Correct SSL/TLS settings (HTTP for local, HTTPS for remote)
- Correct URLs for API and MQTT

### 4. Access Your Site

- **Local:** http://localhost
- **Remote:** https://dev.makapix.club

## Common Commands

```bash
make local          # Switch to local environment
make remote         # Switch to remote environment
make up             # Start services
make down           # Stop services
make restart        # Restart services
make logs           # View all logs
make logs-api       # View API logs
make status         # Check current environment
```

## How It Works

1. **Environment Files**: `.env.local` and `.env.remote` contain environment-specific configurations
2. **Switch Script**: `make local` or `make remote` copies the appropriate `.env` file and docker-compose override
3. **Caddy Config**: Automatically generated with the correct domain
4. **GitHub Integration**: Each environment uses its own GitHub OAuth App and GitHub App

## File Structure

```
.env.local                          # Local environment config (gitignored)
.env.remote                         # Remote environment config (gitignored)
env.local.template                  # Template for local config
env.remote.template                 # Template for remote config
docker-compose.override.local.yml   # Local docker overrides
docker-compose.override.remote.yml  # Remote docker overrides
scripts/switch-env.sh               # Environment switcher (Unix)
scripts/switch-env.ps1              # Environment switcher (Windows)
```

## Remote VPS Setup

On your VPS, clone the repo and:

```bash
# Install Docker if needed
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Setup and start
./scripts/setup-dev.sh
make remote
make up
```

Make sure DNS for `dev.makapix.club` points to your VPS IP. Caddy will automatically get SSL certificates from Let's Encrypt.

## Troubleshooting

**Environment not switching?**
- Check that `.env.local` and `.env.remote` exist
- Run `make status` to see current environment

**GitHub OAuth not working?**
- Verify callback URLs match exactly in GitHub settings
- Check that correct credentials are in the active `.env` file
- Restart services after changing `.env`: `make restart`

**Caddy not getting SSL certificate?**
- Ensure port 80 and 443 are accessible
- Verify DNS points to your server
- Check logs: `make logs-proxy`


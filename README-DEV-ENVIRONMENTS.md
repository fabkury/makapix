# Development Environment Configuration

This project is configured for **seamless development** on both:
- **Local laptop** (localhost)
- **Remote VPS** (dev.makapix.club)

## Overview

The environment system automatically handles:
- ✅ Domain configuration (localhost vs dev.makapix.club)
- ✅ GitHub OAuth Apps (separate credentials for each environment)
- ✅ GitHub Apps (separate apps for each environment)
- ✅ SSL/TLS (HTTP for local, HTTPS for remote)
- ✅ API and MQTT URLs

## Quick Start

### First Time Setup

1. **Initialize environment files:**
   ```powershell
   # Windows
   .\scripts\setup-dev.ps1
   
   # Linux/Mac
   ./scripts/setup-dev.sh
   ```

2. **Create GitHub Apps** (you need 4 total):
   - 2 OAuth Apps (one for local, one for remote)
   - 2 GitHub Apps (one for local, one for remote)
   
   See [GitHub Configuration](#github-configuration) below for details.

3. **Update credentials:**
   - Edit `.env.local` with local GitHub credentials
   - Edit `.env.remote` with remote GitHub credentials

4. **Switch to your environment and start:**
   ```powershell
   # Windows
   .\dev.ps1 local
   .\dev.ps1 up
   
   # Linux/Mac
   make local
   make up
   ```

## Commands

### Windows (PowerShell)
```powershell
.\dev.ps1 help         # Show all commands
.\dev.ps1 local        # Switch to local environment
.\dev.ps1 remote       # Switch to remote environment
.\dev.ps1 up           # Start services
.\dev.ps1 down         # Stop services
.\dev.ps1 status       # Check current environment
.\dev.ps1 logs         # View logs
```

### Linux/Mac (Makefile)
```bash
make help              # Show all commands
make local             # Switch to local environment
make remote            # Switch to remote environment
make up                # Start services
make down              # Stop services
make status            # Check current environment
make logs              # View logs
```

## GitHub Configuration

You need **separate GitHub OAuth Apps and GitHub Apps** for each environment.

### Local Environment (localhost)

**OAuth App:**
- Go to: https://github.com/settings/applications/new
- Application name: `Makapix Local Dev`
- Homepage URL: `http://localhost`
- Authorization callback URL: `http://localhost/auth/github/callback`
- Copy Client ID and Secret to `.env.local`

**GitHub App:**
- Go to: https://github.com/settings/apps/new
- GitHub App name: `Makapix Local Dev`
- Homepage URL: `http://localhost`
- Callback URL: `http://localhost/auth/github/callback`
- Webhook URL: `http://localhost/api/webhooks/github` (or disable webhooks)
- Permissions: Repository: Contents (Read & Write), Pages (Read & Write)
- Copy App ID and Private Key to `.env.local`

### Remote Environment (dev.makapix.club)

**OAuth App:**
- Go to: https://github.com/settings/applications/new
- Application name: `Makapix Remote Dev`
- Homepage URL: `https://dev.makapix.club`
- Authorization callback URL: `https://dev.makapix.club/auth/github/callback`
- Copy Client ID and Secret to `.env.remote`

**GitHub App:**
- Go to: https://github.com/settings/apps/new
- GitHub App name: `Makapix Remote Dev`
- Homepage URL: `https://dev.makapix.club`
- Callback URL: `https://dev.makapix.club/auth/github/callback`
- Webhook URL: `https://dev.makapix.club/api/webhooks/github`
- Permissions: Repository: Contents (Read & Write), Pages (Read & Write)
- Copy App ID and Private Key to `.env.remote`

## File Structure

```
.env                              # Active environment (gitignored)
.env.local                        # Local env config (gitignored)
.env.remote                       # Remote env config (gitignored)
env.local.template                # Template for local config
env.remote.template               # Template for remote config

docker-compose.yml                # Base docker config
docker-compose.override.yml       # Active override (gitignored)
docker-compose.override.local.yml # Local override settings
docker-compose.override.remote.yml# Remote override settings

proxy/Caddyfile                   # Active Caddy config (gitignored)
proxy/Caddyfile.template          # Caddy config template

scripts/
  setup-dev.sh                    # Initial setup (Unix)
  setup-dev.ps1                   # Initial setup (Windows)
  switch-env.sh                   # Environment switcher (Unix)
  switch-env.ps1                  # Environment switcher (Windows)

dev.ps1                           # PowerShell dev helper
Makefile                          # Make-based dev helper
```

## How It Works

When you run `.\dev.ps1 local` or `make local`:

1. Copies `.env.local` → `.env`
2. Copies `docker-compose.override.local.yml` → `docker-compose.override.yml`
3. Generates `proxy/Caddyfile` with `localhost` domain
4. All services automatically use the correct configuration

When you run `.\dev.ps1 remote` or `make remote`:

1. Copies `.env.remote` → `.env`
2. Copies `docker-compose.override.remote.yml` → `docker-compose.override.yml`
3. Generates `proxy/Caddyfile` with `dev.makapix.club` domain
4. All services automatically use the correct configuration

## Accessing Your Site

- **Local:** http://localhost
- **Remote:** https://dev.makapix.club (with automatic SSL via Let's Encrypt)

## VPS Setup

On your remote VPS:

1. **Clone the repository**
2. **Run setup:**
   ```bash
   ./scripts/setup-dev.sh
   ```
3. **Configure `.env.remote`** with your remote GitHub credentials
4. **Switch to remote environment:**
   ```bash
   make remote
   make up
   ```
5. **Ensure DNS is configured:** Point `dev.makapix.club` to your VPS IP
6. **Caddy will automatically obtain SSL certificates** from Let's Encrypt

## ⚠️ Important: Never Manually Edit Generated Files

The following files are **automatically generated** by the switch-env scripts:
- `.env`
- `docker-compose.override.yml`
- `proxy/Caddyfile`

**Never edit these files manually!** Always use:
- `.\dev.ps1 local|remote` (Windows)
- `make local|remote` (Linux/Mac)

If you manually edit these files:
- Your changes will be overwritten on the next switch
- You may get inconsistent behavior across environments
- Git conflicts may occur (though they're gitignored now)

See [WORKFLOW.md](WORKFLOW.md) for the proper workflow.

## Troubleshooting

### Environment not switching?
```bash
# Check current environment
.\dev.ps1 status    # Windows
make status         # Linux/Mac

# Ensure .env.local and .env.remote exist
ls .env.*
```

### GitHub OAuth not working?
- Verify callback URLs match exactly in GitHub settings
- Check correct credentials are in active `.env` file
- Restart services: `.\dev.ps1 restart` or `make restart`

### Caddy not getting SSL certificate?
- Ensure ports 80 and 443 are accessible
- Verify DNS points to your server
- Check logs: `.\dev.ps1 logs-proxy` or `make logs-proxy`

## Documentation

- **⭐ Daily Workflow:** [WORKFLOW.md](WORKFLOW.md) - **Start here for seamless local/remote switching**
- **Quick Start:** [QUICK-START.md](QUICK-START.md)
- **Detailed Setup:** [DEVELOPMENT-SETUP.md](DEVELOPMENT-SETUP.md)

## Security Notes

- `.env.local` and `.env.remote` contain **secrets** and are gitignored
- Never commit these files to version control
- Use different JWT secrets for each environment
- Use strong database passwords in production


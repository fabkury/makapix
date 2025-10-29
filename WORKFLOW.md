# Developer Workflow Guide

This guide ensures seamless switching between local and remote (VPS) development environments.

## Quick Reference

### Local Development
```powershell
# PowerShell (Windows)
.\scripts\switch-env.ps1 local
docker compose down
docker compose up -d
```

### Remote Development (VPS)
```bash
# Bash (Linux)
./scripts/switch-env.sh remote
docker compose down
docker compose up -d
```

## How It Works

### Environment-Specific Files (NOT in Git)

These files are **generated per environment** and **never committed to Git**:

- `.env` - Generated from `.env.local` or `.env.remote`
- `docker-compose.override.yml` - Generated from `docker-compose.override.local.yml` or `docker-compose.override.remote.yml`
- `proxy/Caddyfile` - Generated from `proxy/Caddyfile.template`

✅ These files are in `.gitignore` and will not cause conflicts when pushing/pulling.

### Environment Templates (IN Git)

These files are **committed to Git** and shared across environments:

- `env.local.template` - Template for local `.env`
- `env.remote.template` - Template for remote `.env`
- `.env.local` - Your actual local environment config
- `.env.remote` - Your actual remote environment config
- `docker-compose.override.local.yml` - Local Docker overrides
- `docker-compose.override.remote.yml` - Remote Docker overrides
- `proxy/Caddyfile.template` - Caddy configuration template

## First-Time Setup

### On Your Local Machine

1. **Copy and configure local environment:**
   ```powershell
   cp env.local.template .env.local
   # Edit .env.local with your local settings (GitHub OAuth, etc.)
   ```

2. **Switch to local environment:**
   ```powershell
   .\scripts\switch-env.ps1 local
   ```

3. **Start services:**
   ```powershell
   docker compose up -d
   ```

4. **Access your app:**
   - http://localhost
   - http://localhost/publish
   - http://localhost/api

### On Your VPS

1. **Copy and configure remote environment:**
   ```bash
   cp env.remote.template .env.remote
   # Edit .env.remote with your remote settings
   ```

2. **Switch to remote environment:**
   ```bash
   ./scripts/switch-env.sh remote
   ```

3. **Start services:**
   ```bash
   docker compose up -d
   ```

4. **Access your app:**
   - https://dev.makapix.club
   - https://dev.makapix.club/publish
   - https://dev.makapix.club/api

## Daily Workflow

### Working Locally, Then Pushing to VPS

1. **Make changes on local machine**
   ```powershell
   # Ensure you're in local mode
   .\scripts\switch-env.ps1 local
   docker compose up -d
   
   # Make your code changes...
   # Test at http://localhost
   ```

2. **Commit and push to Git**
   ```powershell
   git add .
   git commit -m "Your changes"
   git push origin main
   ```

3. **Deploy to VPS**
   ```bash
   # SSH into VPS
   cd /path/to/repo
   git pull origin main
   
   # Ensure remote environment is active
   ./scripts/switch-env.sh remote
   
   # Restart services
   docker compose down
   docker compose up -d
   ```

### Pulling Changes from VPS to Local

1. **Pull from VPS**
   ```powershell
   git pull origin main
   ```

2. **Ensure local environment is active**
   ```powershell
   .\scripts\switch-env.ps1 local
   docker compose down
   docker compose up -d
   ```

✅ **No manual Caddyfile editing required!** The switch script handles everything.

## Troubleshooting

### Issue: Getting redirected to HTTPS on localhost

**Cause:** Wrong Caddyfile configuration (using remote domain on local)

**Solution:**
```powershell
.\scripts\switch-env.ps1 local
docker compose down
docker compose up -d
```

### Issue: Caddyfile has wrong domain after git pull

**Cause:** You pulled but forgot to run the switch script

**Solution:**
```powershell
# Always run switch-env after pulling
.\scripts\switch-env.ps1 local  # or remote, depending on where you are
docker compose down
docker compose up -d
```

### Issue: Port conflicts or services not starting

**Solution:**
```powershell
# Full restart
docker compose down
docker compose up -d

# Check logs
docker compose logs -f

# Check specific service
docker compose logs -f api
docker compose logs -f proxy
```

## What Each Environment File Controls

### `.env.local` / `.env.remote`
- Database credentials
- API URLs (localhost vs dev.makapix.club)
- GitHub OAuth credentials (different for local vs remote)
- MQTT settings
- Domain configuration

### `docker-compose.override.local.yml`
- Binds ports directly (80, 443, 3000, 8000)
- No external proxy needed
- HTTP only (no HTTPS on localhost)

### `docker-compose.override.remote.yml`
- Uses caddy-docker-proxy for routing
- HTTPS via Let's Encrypt
- No direct port bindings (goes through proxy)
- Disables standalone proxy service

### `proxy/Caddyfile` (Generated)
- **Local:** `http://localhost` - no HTTPS, direct access
- **Remote:** `http://{$DOMAIN}` - proxied via caddy-docker-proxy with HTTPS

## Pro Tips

1. **Always use the switch-env script** - Never manually edit `.env` or `Caddyfile`
2. **After every git pull** - Run the appropriate switch-env script
3. **Keep credentials separate** - Never commit secrets; use `.env.local` and `.env.remote`
4. **Test before pushing** - Always test locally before deploying to VPS
5. **Use Docker logs** - When debugging, check `docker compose logs -f`

## Environment Comparison

| Feature | Local | Remote (VPS) |
|---------|-------|--------------|
| Domain | localhost | dev.makapix.club |
| Protocol | HTTP | HTTPS |
| Ports | Direct binding | Proxied |
| SSL | None | Let's Encrypt |
| Proxy | Standalone Caddy | caddy-docker-proxy |
| OAuth Callback | http://localhost/api/auth/github/callback | https://dev.makapix.club/api/auth/github/callback |

## Summary

The key to a seamless workflow is:

1. ✅ **Use switch-env scripts** for all environment changes
2. ✅ **Generated files are gitignored** - no conflicts
3. ✅ **Templates are in Git** - shared configuration patterns
4. ✅ **Secrets stay local** - each environment has its own credentials
5. ✅ **No manual Caddyfile editing** - always generated from template

This setup ensures you can work seamlessly across environments without manual configuration changes! 🚀


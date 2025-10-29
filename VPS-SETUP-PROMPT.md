# VPS Setup Prompt

Copy and paste the following prompt to the AI model running on your VPS:

---

## Prompt for VPS AI:

I need you to set up the Makapix development environment on this VPS for the remote environment (dev.makapix.club). Please follow these steps:

### 1. Pull Latest Changes from GitHub

Navigate to the repository directory and pull the latest changes:

```bash
cd /path/to/makapix/repo  # Update this path to your actual repo location
git pull origin main
```

### 2. Run Initial Setup

Run the setup script to create environment files:

```bash
./scripts/setup-dev.sh
```

This will create `.env.local` and `.env.remote` from templates.

### 3. Configure Remote GitHub Credentials

I need to add my GitHub OAuth App and GitHub App credentials for the **remote** environment (dev.makapix.club).

Edit `.env.remote` and update these values:

```bash
nano .env.remote
```

**Required GitHub OAuth App credentials (for dev.makapix.club):**
- `GITHUB_OAUTH_CLIENT_ID` - Your remote OAuth Client ID
- `GITHUB_OAUTH_CLIENT_SECRET` - Your remote OAuth Client Secret

**Required GitHub App credentials (for dev.makapix.club):**
- `GITHUB_APP_ID` - Your remote GitHub App ID
- `GITHUB_APP_PRIVATE_KEY` - Your remote GitHub App Private Key (multiline)

**Also update these if needed:**
- `JWT_SECRET_KEY` - Use a strong random secret for production
- `POSTGRES_PASSWORD` - Use a strong password

After updating the credentials, save and exit.

### 4. Switch to Remote Environment

Run the environment switcher:

```bash
make remote
```

This will:
- Copy `.env.remote` to `.env`
- Copy `docker-compose.override.remote.yml` to `docker-compose.override.yml`
- Generate `proxy/Caddyfile` with `dev.makapix.club` domain

### 5. Stop Existing Containers (if any)

```bash
make down
```

Or:

```bash
docker compose down
```

### 6. Start All Services

```bash
make up
```

Or:

```bash
docker compose up -d
```

This will:
- Build/pull all Docker images
- Start PostgreSQL, Redis, MQTT, API, Web, Worker, and Caddy proxy
- Caddy will automatically obtain SSL certificates from Let's Encrypt for dev.makapix.club

### 7. Verify the Setup

Check that all services are running:

```bash
make status
```

Or:

```bash
docker compose ps
```

All services should show as "healthy" or "Up".

### 8. Test the API

```bash
curl https://dev.makapix.club/api/health
```

Should return: `{"status":"ok","uptime_s":...}`

### 9. Test the Web Interface

Open in browser: https://dev.makapix.club

You should see the Makapix homepage.

### 10. View Logs (if needed)

```bash
make logs          # All services
make logs-api      # API only
make logs-web      # Web only
make logs-proxy    # Caddy proxy only
```

---

## Important Notes for VPS Setup:

1. **DNS Configuration:** Ensure `dev.makapix.club` DNS A record points to this VPS IP address
2. **Firewall:** Ports 80 and 443 must be open for HTTP/HTTPS traffic
3. **SSL Certificates:** Caddy will automatically obtain Let's Encrypt certificates (may take 1-2 minutes on first run)
4. **GitHub Apps:** Make sure you've created separate GitHub OAuth App and GitHub App for dev.makapix.club with correct callback URLs
5. **Security:** Use strong passwords and secrets in production `.env.remote`

---

## Troubleshooting:

If Caddy can't get SSL certificates:
- Check DNS is pointing to this server: `dig dev.makapix.club`
- Check ports are open: `netstat -tuln | grep -E '(:80|:443)'`
- Check Caddy logs: `make logs-proxy`

If services won't start:
- Check for port conflicts: `docker compose ps -a`
- Check logs: `make logs`
- Verify environment: `cat .env | grep ENVIRONMENT` (should show "remote")

---

Please execute these steps and let me know if you encounter any issues or need clarification on any step.


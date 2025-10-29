# Quick Start Guide

## First Time Setup

1. **Run setup:**
   ```bash
   # Windows
   .\scripts\setup-dev.ps1
   
   # Mac/Linux
   ./scripts/setup-dev.sh
   ```

2. **Create GitHub OAuth Apps:**
   - **Local:** https://github.com/settings/applications/new
     - Homepage: `http://localhost`
     - Callback: `http://localhost/auth/github/callback`
   
   - **Remote:** https://github.com/settings/applications/new
     - Homepage: `https://dev.makapix.club`
     - Callback: `https://dev.makapix.club/auth/github/callback`

3. **Update credentials:**
   - Edit `.env.local` with local GitHub OAuth credentials
   - Edit `.env.remote` with remote GitHub OAuth credentials

4. **Start developing:**
   ```bash
   make local    # or: make remote
   make up
   ```

## Daily Workflow

### Local Development (Laptop)

**Windows (PowerShell):**
```powershell
.\dev.ps1 local   # Switch to local environment
.\dev.ps1 up      # Start services
# Develop at http://localhost
.\dev.ps1 down    # Stop when done
```

**Linux/Mac:**
```bash
make local        # Switch to local environment
make up           # Start services
# Develop at http://localhost
make down         # Stop when done
```

### Remote Development (VPS)

**Windows:**
```powershell
.\dev.ps1 remote  # Switch to remote environment
.\dev.ps1 up      # Start services
.\dev.ps1 logs    # View logs
```

**Linux/Mac:**
```bash
make remote       # Switch to remote environment
make up           # Start services
make logs         # View logs
```

## Common Commands

### Windows (PowerShell)
| Command | Description |
|---------|-------------|
| `.\dev.ps1 local` | Switch to local (localhost) |
| `.\dev.ps1 remote` | Switch to remote (dev.makapix.club) |
| `.\dev.ps1 up` | Start all services |
| `.\dev.ps1 down` | Stop all services |
| `.\dev.ps1 restart` | Restart all services |
| `.\dev.ps1 logs` | View all logs |
| `.\dev.ps1 status` | Check current environment |

### Linux/Mac (Makefile)
| Command | Description |
|---------|-------------|
| `make local` | Switch to local (localhost) |
| `make remote` | Switch to remote (dev.makapix.club) |
| `make up` | Start all services |
| `make down` | Stop all services |
| `make restart` | Restart all services |
| `make logs` | View all logs |
| `make status` | Check current environment |

## Switching Environments

The system automatically handles:
- ✅ Domain configuration (localhost vs dev.makapix.club)
- ✅ GitHub OAuth credentials
- ✅ SSL/TLS (HTTP local, HTTPS remote)
- ✅ API and MQTT URLs

Just run `make local` or `make remote` and everything is configured!


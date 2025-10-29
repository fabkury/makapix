# 🚀 Start Here - Development Environment Setup

## What Was Done

Your Makapix project now has **seamless environment management** for both:
- **Local development** on your laptop (localhost)
- **Remote development** on your VPS (dev.makapix.club)

## Quick Start (3 Steps)

### Step 1: Configure GitHub Apps

You need **4 GitHub applications** total. Follow this guide:

📋 **Read:** [.github-apps-needed.md](.github-apps-needed.md)

This takes about 10-15 minutes and only needs to be done once.

### Step 2: Update Environment Files

**On Windows (PowerShell):**
```powershell
notepad .env.local    # Add local GitHub credentials
notepad .env.remote   # Add remote GitHub credentials
```

**On Linux/Mac:**
```bash
nano .env.local       # Add local GitHub credentials
nano .env.remote      # Add remote GitHub credentials
```

### Step 3: Start Developing

**On your laptop (Windows):**
```powershell
.\dev.ps1 local
.\dev.ps1 up
# Visit http://localhost
```

**On your VPS (Linux):**
```bash
make remote
make up
# Visit https://dev.makapix.club
```

## How to Use

### Switch Between Environments

**Windows:**
```powershell
.\dev.ps1 local      # Work on laptop
.\dev.ps1 remote     # Work on VPS
```

**Linux/Mac:**
```bash
make local           # Work on laptop
make remote          # Work on VPS
```

### Common Commands

**Windows:**
```powershell
.\dev.ps1 up         # Start all services
.\dev.ps1 down       # Stop all services
.\dev.ps1 logs       # View logs
.\dev.ps1 status     # Check current environment
.\dev.ps1 help       # Show all commands
```

**Linux/Mac:**
```bash
make up              # Start all services
make down            # Stop all services
make logs            # View logs
make status          # Check current environment
make help            # Show all commands
```

## What Changed

### New Files Created

```
Environment Templates:
├── env.local.template              # Local config template
├── env.remote.template             # Remote config template
├── .env.local                      # Your local config (gitignored)
├── .env.remote                     # Your remote config (gitignored)
└── .env                            # Active config (gitignored)

Docker Overrides:
├── docker-compose.override.local.yml   # Local Docker settings
├── docker-compose.override.remote.yml  # Remote Docker settings
└── docker-compose.override.yml         # Active override (gitignored)

Proxy Configuration:
├── proxy/Caddyfile.template        # Caddy template
└── proxy/Caddyfile                 # Active Caddy config (gitignored)

Scripts:
├── scripts/setup-dev.sh            # Initial setup (Unix)
├── scripts/setup-dev.ps1           # Initial setup (Windows)
├── scripts/switch-env.sh           # Env switcher (Unix)
└── scripts/switch-env.ps1          # Env switcher (Windows)

Dev Helpers:
├── dev.ps1                         # PowerShell dev helper
└── Makefile                        # Make-based dev helper

Documentation:
├── START-HERE.md                   # This file!
├── SETUP-SUMMARY.md                # What was set up
├── README-DEV-ENVIRONMENTS.md      # Complete guide
├── DEVELOPMENT-SETUP.md            # Detailed setup
├── QUICK-START.md                  # Quick reference
└── .github-apps-needed.md          # GitHub apps guide
```

### Modified Files

```
├── .gitignore                      # Updated to ignore secrets
└── Makefile                        # Updated with new commands
```

## Documentation

| File | Purpose |
|------|---------|
| **START-HERE.md** (this file) | First-time setup guide |
| **SETUP-SUMMARY.md** | What was configured |
| **QUICK-START.md** | Command reference |
| **README-DEV-ENVIRONMENTS.md** | Complete environment guide |
| **DEVELOPMENT-SETUP.md** | Detailed setup instructions |
| **.github-apps-needed.md** | GitHub apps configuration |

## Features

✅ **Automatic Environment Switching**
- One command switches everything (domain, GitHub apps, SSL, URLs)

✅ **Separate GitHub Integrations**
- Different OAuth apps and GitHub Apps for each environment

✅ **SSL/TLS Handled Automatically**
- HTTP for local, HTTPS with Let's Encrypt for remote

✅ **Zero Manual Configuration**
- No editing docker-compose.yml or Caddyfile manually

✅ **Git-Safe**
- All secrets are gitignored, only templates are tracked

## Current Status

✅ Environment system is configured  
✅ Currently set to: **LOCAL** (localhost)  
⚠️ GitHub OAuth apps need to be configured  
⚠️ GitHub Apps need to be configured  

## Next Action

👉 **Read and follow:** [.github-apps-needed.md](.github-apps-needed.md)

This will guide you through creating the 4 GitHub applications you need.

## Need Help?

- Run `.\dev.ps1 help` (Windows) or `make help` (Linux/Mac)
- Check `.\dev.ps1 status` or `make status` to see current environment
- Read the documentation files listed above

---

**You're ready to go!** Just configure the GitHub apps and start developing. 🎉


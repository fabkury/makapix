# Monorepo Migration Summary

## What Was Done

### 1. CTA Site Integration
- ✅ Moved `/opt/makapix-cta/` → `apps/cta/` (now in version control)
- ✅ All static files (HTML, CSS, JS, artwork) are now tracked in git

### 2. Stack Orchestration Integration  
- ✅ Moved `/opt/makapix-stack/` → `deploy/stack/` (now in version control)
- ✅ Updated `docker-compose.yml` to use relative paths:
  - CTA volume: `../apps/cta` (relative to `deploy/stack/`)
  - Dev build context: `../..` (repo root)
- ✅ Created `.env.example` template
- ✅ Updated `monitor-cta-stats.sh` to use script-relative paths
- ✅ Updated documentation

### 3. Repository Structure
```
/opt/makapix/                    (monorepo root)
├── apps/
│   └── cta/                     (CTA website - version controlled)
├── deploy/
│   └── stack/                   (VPS deployment - version controlled)
│       ├── docker-compose.yml
│       ├── .env.example
│       ├── README.stack.md
│       ├── MIGRATION.md
│       ├── monitor-cta-stats.sh
│       └── caddy/
│           └── Caddyfile.global
├── web/                         (Next.js app - existing)
├── api/                         (FastAPI backend - existing)
└── ...                          (other existing directories)
```

### 4. Documentation Updates
- ✅ Created main `README.md` explaining monorepo structure
- ✅ Updated `deploy/stack/README.stack.md` with workflow info
- ✅ Created `deploy/stack/MIGRATION.md` migration guide
- ✅ Updated `Makefile` with `stack-*` commands

### 5. Git Configuration
- ✅ Updated `.gitignore` to ignore `cta-stats.csv` but track `.example` files

## Next Steps

1. **Review Changes**: Check `git status` to see all new/modified files
2. **Commit to Repo**: 
   ```bash
   cd /opt/makapix
   git add .
   git commit -m "Migrate CTA site and stack config into monorepo"
   git push origin main
   ```
3. **Migrate Running Services**: Follow `deploy/stack/MIGRATION.md`
4. **Clean Up**: After verifying everything works, remove old directories:
   ```bash
   rm -rf /opt/makapix-stack
   rm -rf /opt/makapix-cta
   ```

## Verification

- ✅ Docker compose config validates
- ✅ All paths are relative (works from any location)
- ✅ CTA site files preserved
- ✅ Stack configuration preserved
- ✅ Documentation complete

## Workflow Going Forward

- **Local Dev**: Use `make up` from repo root (localhost)
- **VPS Stack**: Use `make stack-up` or `cd deploy/stack && docker compose up -d`
- **All Changes**: Commit to monorepo, pull on VPS, restart services
